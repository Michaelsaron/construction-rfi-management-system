"""Record attachments (FR-28): contractor DOC_01 enclosures, batch files and Daily Progress files.

Inspection evidence does NOT use this path any more (UI design s.14): RE/DRE attach files to their own management remark
and inspectors to their own active DOC_03 review, through /evidence. Files stored here before release 6 remain readable
as legacy record evidence; their authorship is never re-attributed.
"""
from datetime import datetime
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Attachment, User, Project, DailyProgress
from app.security import current_user
from app import authz
from app.services import evidence as ev
from app.services.audit import log

router = APIRouter(prefix='/attachments', tags=['Attachments'])


def parent_access(db, u, entity_type: str, entity_id: int, write=False):
    """Returns (type, project_id, role, rfi_id, summary_id, lock_now)."""
    t = entity_type.lower()
    if t == 'rfi':
        r, role = authz.load_rfi(db, u, entity_id)
        if write:
            if r.record_state != 'ACTIVE' or r.provenance == 'LEGACY_IMPORT': raise HTTPException(409, 'This RFI is read-only')
            if role in authz.MANAGEMENT:
                raise HTTPException(403, 'RE/DRE evidence is attached to a management remark (DOC_01 review, assignment or final disposition)')
            if role in authz.INSPECTORS:
                raise HTTPException(403, 'Inspectors attach evidence to their own active DOC_03 review')
            if not (role in authz.CONTRACTOR and r.workflow_status in ('DRAFT', 'SUBMITTED')):
                raise HTTPException(403, 'You cannot add attachments to this RFI at its current stage')
        # Enclosures added after submission are appended and locked at once (version preservation).
        return t, r.project_id, role, r.id, r.summary_id, r.workflow_status != 'DRAFT'
    if t == 'summary':
        s, role = authz.load_summary(db, u, entity_id)
        if write and not (role in authz.CONTRACTOR and s.workflow_status in ('DRAFT', 'RETURNED')):
            raise HTTPException(403, 'Batch files are added by the contractor while the DOC_01 is a draft. RE/DRE use a DOC_01 review remark.')
        return t, s.project_id, role, None, s.id, False
    if t == 'daily_progress':
        p = db.get(DailyProgress, entity_id)
        if not p: raise HTTPException(404, 'Parent record not found')
        role = authz.require_project(db, u, p.project_id, write=write)
        return t, p.project_id, role, None, None, False
    raise HTTPException(400, 'Unsupported attachment entity')


@router.get('/download/{aid}')
def download(aid: int, db: Session = Depends(get_db), u: User = Depends(current_user)):
    """Kept for older clients: same checks as /evidence/files/{id}/download."""
    from app.routers.evidence import download as dl
    return dl(aid, False, db, u)


@router.get('/{entity_type}/{entity_id}')
def ls(entity_type: str, entity_id: int, db: Session = Depends(get_db), u: User = Depends(current_user)):
    t = parent_access(db, u, entity_type, entity_id)[0]
    rows = list(db.scalars(select(Attachment).where(Attachment.entity_type == t, Attachment.entity_id == entity_id,
                                                    (Attachment.attachment_kind == 'RECORD') | Attachment.attachment_kind.is_(None), *ev.live_clause())
                           .order_by(Attachment.id.desc())))
    rows = ev.visible(db, u, rows)
    nm = ev.names_for(db, [a.uploaded_by for a in rows])
    return [ev.out(a, nm) for a in rows]


@router.post('/{entity_type}/{entity_id}')
def upload(entity_type: str, entity_id: int, file: UploadFile = File(...), description: str | None = Form(None), upload_token: str | None = Form(None),
           db: Session = Depends(get_db), u: User = Depends(current_user)):
    t, pid, role, rfi_id, summary_id, lock_now = parent_access(db, u, entity_type, entity_id, write=True)
    prev = ev.existing_by_token(db, u, upload_token)
    if prev:
        if prev.entity_type != t or prev.entity_id != entity_id: raise HTTPException(409, 'This upload token was already used for a different record')
        return {**ev.out(prev, {u.id: u.full_name}), 'duplicate': True}
    project = db.get(Project, pid)
    stored = ev.store_upload(file, project, ev.count_live(db, entity_type=t, entity_id=entity_id))
    now = datetime.utcnow()
    a = Attachment(entity_type=t, entity_id=entity_id, original_name=stored['original_name'], stored_name=stored['stored_name'], content_type=stored['content_type'],
                   size_bytes=stored['size_bytes'], description=(description or '')[:255] or None, uploaded_by=u.id, attachment_kind='RECORD', project_id=pid,
                   rfi_id=rfi_id, summary_id=summary_id, sha256=stored['sha256'], scan_status=stored['scan_status'], scanned_at=stored['scanned_at'],
                   author_role=role, upload_token=(upload_token or None) and upload_token[:64], upload_status='COMPLETE', version_no=1,
                   workflow_stage='DOC01_ENCLOSURE' if t in ('rfi', 'summary') else 'DAILY_PROGRESS', locked_at=now if lock_now else None)
    db.add(a)
    try:
        db.flush()
    except IntegrityError:
        db.rollback(); ev.discard_stored(stored['stored_name'])
        prev = ev.existing_by_token(db, u, upload_token)
        if prev is None: raise
        return {**ev.out(prev, {u.id: u.full_name}), 'duplicate': True}
    log(db, u.id, t.upper(), entity_id, 'UPLOAD', f'{a.original_name} (sha256 {a.sha256[:12]})', project_id=pid)
    db.commit(); db.refresh(a)
    return ev.out(a, {u.id: u.full_name})


@router.delete('/{aid}')
def remove(aid: int, db: Session = Depends(get_db), u: User = Depends(current_user)):
    """Kept for older clients: removal before submission by the uploader only (see /evidence/files/{id})."""
    from app.routers.evidence import remove_file
    return remove_file(aid, db, u)
