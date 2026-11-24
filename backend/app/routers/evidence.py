"""Evidence endpoints (UI design s.5-9, s.14): Category 2.1 management remarks, Category 2.2 inspector review evidence,
secure preview/download, removal before submission, and controlled evidence amendments.

Every write re-checks project membership, role, record state and workflow turn on the server.
"""
import json
from datetime import datetime
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import (Attachment, ManagementRemark, REMARK_STAGES, ReviewerAssignment, Review, Rfi, RfiSummary, RfiAmendment, Project, User)
from app.schemas import RemarkCreate, RemarkUpdate, DraftComment, EvidenceAmendmentCreate
from app.security import current_user
from app import authz
from app.services import evidence as ev
from app.services.audit import log
from app.services.notify import notify_project_roles
from app.services.workflow import require_active_record, OPEN_FOR_ASSIGNMENT, STATUS_LABELS

router = APIRouter(prefix='/evidence', tags=['Evidence'])
STAGE_LABELS = {'DOC01_REVIEW': 'DOC_01 review', 'ASSIGNMENT': 'Inspector assignment', 'SEQUENCE_CHANGE': 'Assignment sequence change',
                'REASSIGNMENT_RETURN': 'Controlled reassignment / return', 'FINAL_DISPOSITION': 'Final disposition'}


# ------------------------------------------------------------------------------------------------ helpers
def remark_out(db, rem: ManagementRemark, viewer: User, files=None) -> dict:
    if files is None:
        files = ev.visible(db, viewer, list(db.scalars(select(Attachment).where(Attachment.management_remark_id == rem.id, *ev.live_clause()).order_by(Attachment.id))))
    nm = ev.names_for(db, [rem.author_id] + [f.uploaded_by for f in files])
    return {'id': rem.id, 'project_id': rem.project_id, 'rfi_id': rem.rfi_id, 'summary_id': rem.summary_id, 'stage': rem.stage,
            'stage_label': STAGE_LABELS.get(rem.stage, rem.stage), 'author_id': rem.author_id, 'author_name': rem.author_name_snapshot or nm.get(rem.author_id),
            'author_role': rem.author_role, 'author_role_label': authz.ROLE_LABELS.get(rem.author_role, rem.author_role), 'body': rem.body,
            'status': rem.status, 'decision_id': rem.decision_id, 'created_at': rem.created_at, 'updated_at': rem.updated_at,
            'submitted_at': rem.submitted_at, 'version': rem.version, 'editable': rem.status == 'DRAFT' and rem.author_id == viewer.id,
            'files': [ev.out(f, nm) for f in files]}


def _remark_parent(db, u, rfi_id, summary_id):
    """Resolve and validate the parent; returns (project_id, rfi, summary, role). Only RE/DRE (Category 2.1) may write."""
    rfi = db.get(Rfi, rfi_id) if rfi_id else None
    summary = db.get(RfiSummary, summary_id) if summary_id else None
    if rfi_id and not rfi: raise HTTPException(404, 'RFI not found')
    if summary_id and not summary: raise HTTPException(404, 'DOC_01 batch not found')
    if not rfi and not summary: raise HTTPException(400, 'A management remark belongs to an RFI or a DOC_01 batch')
    if rfi and summary and rfi.summary_id != summary.id: raise HTTPException(400, 'The RFI is not part of this DOC_01 batch')
    pid = rfi.project_id if rfi else summary.project_id
    role = authz.require_project(db, u, pid, authz.MANAGEMENT, write=True)
    if rfi: require_active_record(rfi)
    return pid, rfi, summary, role


def _check_stage(stage, rfi, summary):
    if stage not in REMARK_STAGES: raise HTTPException(400, f'Unknown remark stage {stage}')
    ws = rfi.workflow_status if rfi else None
    if stage == 'FINAL_DISPOSITION':
        if not rfi or ws != 'AWAITING_DECISION':
            raise HTTPException(409, 'Final-disposition remarks can be written only when all inspector reviews are complete')
    elif stage in ('ASSIGNMENT', 'SEQUENCE_CHANGE'):
        if not rfi or ws not in OPEN_FOR_ASSIGNMENT:
            raise HTTPException(409, f'Assignment remarks cannot be written while the RFI is {STATUS_LABELS.get(ws, ws)}')
    elif stage == 'DOC01_REVIEW':
        if rfi and ws not in OPEN_FOR_ASSIGNMENT: raise HTTPException(409, 'DOC_01 review remarks can be written while the RFI awaits management action')
        if summary and not rfi and summary.workflow_status != 'SUBMITTED': raise HTTPException(409, 'DOC_01 review remarks can be written on a submitted batch')
    elif stage == 'REASSIGNMENT_RETURN':
        if summary and not rfi and summary.workflow_status != 'SUBMITTED': raise HTTPException(409, 'Only a submitted DOC_01 batch can be returned')
        if rfi and ws not in OPEN_FOR_ASSIGNMENT: raise HTTPException(409, 'Reassignment remarks require an open RFI')


def own_draft_remark(db, u, rid: int, lock_row=True) -> ManagementRemark:
    q = select(ManagementRemark).where(ManagementRemark.id == rid)
    rem = db.scalar(q.with_for_update() if lock_row else q)
    if not rem: raise HTTPException(404, 'Remark not found')
    authz.require_project(db, u, rem.project_id, authz.MANAGEMENT, write=True)
    if rem.author_id != u.id: raise HTTPException(403, 'Only the author can change this management remark')
    if rem.status != 'DRAFT': raise HTTPException(409, 'This management remark has been submitted and is locked. Use a controlled amendment.')
    return rem


def submit_remark(db, u, rem_id: int | None, *, stage: str, rfi: Rfi | None = None, summary: RfiSummary | None = None, body: str | None = None,
                  decision_id: int | None = None, require_content=False):
    """Lock a draft remark as part of a workflow action (called inside the action's transaction). Returns the remark or None."""
    if not rem_id:
        return None
    rem = own_draft_remark(db, u, rem_id)
    if rfi is not None and rem.rfi_id not in (None, rfi.id): raise HTTPException(400, 'The management remark belongs to a different RFI')
    if rfi is not None and rem.rfi_id is None and rem.summary_id != rfi.summary_id: raise HTTPException(400, 'The management remark belongs to a different DOC_01 batch')
    if summary is not None and rem.summary_id != summary.id: raise HTTPException(400, 'The management remark belongs to a different DOC_01 batch')
    now = datetime.utcnow()
    if body is not None and body.strip(): rem.body = body.strip()
    n = ev.count_live(db, management_remark_id=rem.id)
    if require_content and not (rem.body or '').strip() and not n:
        raise HTTPException(400, 'Write the remark or attach at least one file before submitting')
    if not (rem.body or '').strip() and not n:
        rem.status = 'DISCARDED'  # an empty draft carried along by the screen is not recorded as a remark
        return None
    rem.stage = stage; rem.status = 'SUBMITTED'; rem.submitted_at = now; rem.updated_at = now; rem.version += 1
    if decision_id: rem.decision_id = decision_id
    ev.lock(db, Attachment.management_remark_id == rem.id, *ev.live_clause(), when=now)
    for a in db.scalars(select(Attachment).where(Attachment.management_remark_id == rem.id)): a.workflow_stage = stage
    log(db, u.id, 'MANAGEMENT_REMARK', rem.id, 'SUBMIT_REMARK', f'{stage}; {n} file(s)', project_id=rem.project_id,
        after={'rfi_id': rem.rfi_id, 'summary_id': rem.summary_id, 'body': rem.body, 'files': n})
    return rem


def _new_attachment(db, u, project, stored: dict, *, kind, token, **fields) -> Attachment:
    a = Attachment(original_name=stored['original_name'], stored_name=stored['stored_name'], content_type=stored['content_type'],
                   size_bytes=stored['size_bytes'], sha256=stored['sha256'], scan_status=stored['scan_status'], scanned_at=stored['scanned_at'],
                   uploaded_by=u.id, attachment_kind=kind, project_id=project.id, upload_token=(token or None) and token[:64],
                   upload_status=fields.pop('upload_status', 'COMPLETE'), version_no=fields.pop('version_no', 1), **fields)
    db.add(a)
    try:
        db.flush()
    except IntegrityError:
        # A parallel request with the same upload token won the race: keep its record, drop this copy of the file.
        db.rollback()
        ev.discard_stored(stored['stored_name'])
        prev = ev.existing_by_token(db, u, token)
        if prev is None: raise
        prev._duplicate = True
        return prev
    return a


def _token_replay(db, u, token, **expect):
    """Idempotent retry: the same upload token from the same user returns the stored attachment instead of a duplicate."""
    prev = ev.existing_by_token(db, u, token)
    if prev is None: return None
    for k, v in expect.items():
        if getattr(prev, k) != v: raise HTTPException(409, 'This upload token was already used for a different record')
    return prev


# ------------------------------------------------------------------------------------- management remarks
@router.post('/remarks')
def create_remark(d: RemarkCreate, db: Session = Depends(get_db), u: User = Depends(current_user)):
    """Create (or reuse) the caller's DRAFT remark for a stage of an RFI / DOC_01 batch. Drafts are private to their author."""
    if d.client_request_id:
        prev = db.scalar(select(ManagementRemark).where(ManagementRemark.client_request_id == d.client_request_id))
        if prev:
            if prev.author_id != u.id: raise HTTPException(409, 'Duplicate request id')
            return remark_out(db, prev, u)
    pid, rfi, summary, role = _remark_parent(db, u, d.rfi_id, d.summary_id)
    _check_stage(d.stage, rfi, summary)
    t_rfi = rfi.id if rfi else None
    t_sum = summary.id if summary else (rfi.summary_id if rfi else None)
    eq = lambda col, v: col.is_(None) if v is None else col == v  # noqa: E731
    existing = db.scalar(select(ManagementRemark).where(ManagementRemark.author_id == u.id, ManagementRemark.status == 'DRAFT', ManagementRemark.stage == d.stage,
                                                        eq(ManagementRemark.rfi_id, t_rfi), eq(ManagementRemark.summary_id, t_sum)))
    if existing:  # one open draft per author, stage and record: reopening the screen resumes it
        if d.body is not None and d.body.strip(): existing.body = d.body.strip(); existing.updated_at = datetime.utcnow(); db.commit()
        return remark_out(db, existing, u)
    rem = ManagementRemark(project_id=pid, rfi_id=t_rfi, summary_id=t_sum,
                           stage=d.stage, author_id=u.id, author_role=role, author_name_snapshot=u.full_name, body=(d.body or '').strip() or None,
                           status='DRAFT', client_request_id=d.client_request_id)
    db.add(rem); db.flush()
    log(db, u.id, 'MANAGEMENT_REMARK', rem.id, 'CREATE_REMARK_DRAFT', d.stage, project_id=pid)
    db.commit(); db.refresh(rem)
    return remark_out(db, rem, u)


@router.get('/remarks')
def list_remarks(rfi_id: int | None = None, summary_id: int | None = None, db: Session = Depends(get_db), u: User = Depends(current_user)):
    """Submitted remarks the user may see, plus the user's own drafts."""
    from sqlalchemy import or_
    if rfi_id:
        r, role = authz.load_rfi(db, u, rfi_id)
        parent = or_(ManagementRemark.rfi_id == rfi_id, (ManagementRemark.summary_id == r.summary_id) & ManagementRemark.rfi_id.is_(None)) if r.summary_id else ManagementRemark.rfi_id == rfi_id
    elif summary_id:
        authz.load_summary(db, u, summary_id)
        parent = ManagementRemark.summary_id == summary_id
    else:
        raise HTTPException(400, 'rfi_id or summary_id is required')
    rows = list(db.scalars(select(ManagementRemark).where(parent, or_(ManagementRemark.status == 'SUBMITTED', (ManagementRemark.status == 'DRAFT') & (ManagementRemark.author_id == u.id)))
                           .order_by(ManagementRemark.submitted_at.is_(None), ManagementRemark.submitted_at, ManagementRemark.id)))
    out = []
    for rem in rows:
        files = list(db.scalars(select(Attachment).where(Attachment.management_remark_id == rem.id, *ev.live_clause()).order_by(Attachment.id)))
        try:
            # the remark text is part of the record for everyone who may view the RFI; files follow the evidence rule
            files = ev.visible(db, u, files)
        except HTTPException:
            files = []
        out.append(remark_out(db, rem, u, files))
    return out


@router.put('/remarks/{rid}')
def update_remark(rid: int, d: RemarkUpdate, db: Session = Depends(get_db), u: User = Depends(current_user)):
    rem = own_draft_remark(db, u, rid)
    if d.version is not None and d.version != rem.version: raise HTTPException(409, 'This remark changed in another window. Reload it.')
    rem.body = (d.body or '').strip() or None; rem.updated_at = datetime.utcnow(); rem.version += 1
    db.commit()
    return remark_out(db, rem, u)


@router.post('/remarks/{rid}/submit')
def submit_standalone(rid: int, db: Session = Depends(get_db), u: User = Depends(current_user)):
    """Record a DOC_01 review remark on its own. Other stages are submitted by their workflow action."""
    rem = own_draft_remark(db, u, rid)
    if rem.stage != 'DOC01_REVIEW':
        raise HTTPException(409, f'A {STAGE_LABELS.get(rem.stage, rem.stage).lower()} remark is submitted together with that action')
    rfi = db.get(Rfi, rem.rfi_id) if rem.rfi_id else None
    summary = db.get(RfiSummary, rem.summary_id) if rem.summary_id and not rfi else None
    _check_stage(rem.stage, rfi, summary)
    submit_remark(db, u, rem.id, stage='DOC01_REVIEW', require_content=True)
    db.commit()
    return remark_out(db, rem, u)


@router.delete('/remarks/{rid}')
def discard_remark(rid: int, db: Session = Depends(get_db), u: User = Depends(current_user)):
    rem = own_draft_remark(db, u, rid)
    now = datetime.utcnow()
    rem.status = 'DISCARDED'; rem.updated_at = now
    for a in db.scalars(select(Attachment).where(Attachment.management_remark_id == rem.id, Attachment.removed_at.is_(None))):
        a.removed_at = now; a.removed_by = u.id
    log(db, u.id, 'MANAGEMENT_REMARK', rem.id, 'DISCARD_REMARK_DRAFT', None, project_id=rem.project_id)
    db.commit()
    return {'ok': True}


@router.post('/remarks/{rid}/files')
def upload_remark_file(rid: int, file: UploadFile = File(...), upload_token: str | None = Form(None), description: str | None = Form(None),
                       db: Session = Depends(get_db), u: User = Depends(current_user)):
    prev = _token_replay(db, u, upload_token, management_remark_id=rid)
    if prev: return {**ev.out(prev, ev.names_for(db, [u.id])), 'duplicate': True}
    rem = own_draft_remark(db, u, rid)
    if rem.rfi_id: require_active_record(db.get(Rfi, rem.rfi_id))
    project = db.get(Project, rem.project_id)
    stored = ev.store_upload(file, project, ev.count_live(db, management_remark_id=rem.id))
    a = _new_attachment(db, u, project, stored, kind='MANAGEMENT_REMARK', token=upload_token, rfi_id=rem.rfi_id, summary_id=rem.summary_id,
                        management_remark_id=rem.id, workflow_stage=rem.stage, author_role=rem.author_role, description=(description or '')[:255] or None,
                        entity_type='rfi' if rem.rfi_id else 'summary', entity_id=rem.rfi_id or rem.summary_id)
    rem.updated_at = datetime.utcnow()
    if getattr(a, '_duplicate', False): return {**ev.out(a, ev.names_for(db, [u.id])), 'duplicate': True}
    log(db, u.id, 'MANAGEMENT_REMARK', rem.id, 'UPLOAD_EVIDENCE', f'{a.original_name} ({a.size_bytes} bytes, sha256 {a.sha256[:12]})', project_id=rem.project_id)
    db.commit(); db.refresh(a)
    return ev.out(a, ev.names_for(db, [u.id]))


# ------------------------------------------------------------------------------------ inspector review path
def _assignment(db, aid: int, lock_row=False) -> ReviewerAssignment:
    q = select(ReviewerAssignment).where(ReviewerAssignment.id == aid)
    a = db.scalar(q.with_for_update() if lock_row else q)
    if not a: raise HTTPException(404, 'Assignment not found')
    return a


def active_own_assignment(db, u, aid: int):
    """The inspector's own assignment whose turn is active, on an RFI under review. Anything else is refused."""
    a = _assignment(db, aid, lock_row=True)
    r = db.scalar(select(Rfi).where(Rfi.id == a.rfi_id).with_for_update())
    if a.user_id != u.id: raise HTTPException(403, 'You can only add evidence to your own assigned DOC_03 review')
    if authz.project_role(db, u, r.project_id) not in authz.INSPECTORS: raise HTTPException(403, 'You are no longer an inspector on this project')
    require_active_record(r)
    if a.status == 'COMPLETED': raise HTTPException(409, 'Your review has been submitted and is locked. Use a controlled amendment.')
    if a.status == 'REPLACED': raise HTTPException(403, 'This assignment was replaced; it no longer accepts evidence')
    if a.status != 'ACTIVE' or r.workflow_status != 'UNDER_REVIEW':
        raise HTTPException(409, 'It is not your turn yet. Evidence can be added when the previous inspector has submitted.')
    return a, r


@router.get('/assignments/{aid}')
def review_workspace(aid: int, db: Session = Depends(get_db), u: User = Depends(current_user)):
    a = _assignment(db, aid)
    r, role = authz.load_rfi(db, u, a.rfi_id)
    own = a.user_id == u.id
    if not own and role not in authz.MANAGEMENT | authz.OFFICE | {authz.ADMIN} and role not in authz.INSPECTORS:
        raise HTTPException(403, 'Not permitted')
    files = list(db.scalars(select(Attachment).where(Attachment.assignment_id == a.id, *ev.live_clause()).order_by(Attachment.id)))
    files = ev.visible(db, u, files)
    rv = db.scalar(select(Review).where(Review.assignment_id == a.id))
    nm = ev.names_for(db, [a.user_id] + [f.uploaded_by for f in files])
    can_edit = own and a.status == 'ACTIVE' and r.workflow_status == 'UNDER_REVIEW' and r.record_state == 'ACTIVE' and role in authz.INSPECTORS
    pol = ev.policy_for(db.get(Project, r.project_id))
    return {'assignment': {'id': a.id, 'rfi_id': a.rfi_id, 'sequence_no': a.sequence_no, 'reviewer_role': a.reviewer_role,
                           'reviewer_role_label': authz.ROLE_LABELS.get(a.reviewer_role, a.reviewer_role), 'status': a.status, 'user_id': a.user_id,
                           'user_name': nm.get(a.user_id), 'activated_at': a.activated_at, 'completed_at': a.completed_at},
            'draft_comment': a.draft_comment if own else None, 'draft_saved_at': a.draft_saved_at if own else None,
            'review': {'comment': rv.comment, 'reviewed_at': rv.reviewed_at, 'reviewer_name': rv.reviewer_name_snapshot or nm.get(rv.reviewer_id),
                       'attachment_count': rv.attachment_count} if rv else None,
            'files': [ev.out(f, nm) for f in files], 'can_edit': can_edit,
            'policy': {'allowed_extensions': pol['allowed_extensions'], 'max_file_mb': pol['max_file_mb'], 'max_files_per_record': pol['max_files_per_record']}}


@router.put('/assignments/{aid}/draft')
def save_draft(aid: int, d: DraftComment, db: Session = Depends(get_db), u: User = Depends(current_user)):
    a, r = active_own_assignment(db, u, aid)
    a.draft_comment = (d.comment or '')[:20000] or None; a.draft_saved_at = datetime.utcnow()
    db.commit()
    return {'ok': True, 'draft_saved_at': a.draft_saved_at}


@router.post('/assignments/{aid}/files')
def upload_review_file(aid: int, file: UploadFile = File(...), upload_token: str | None = Form(None), description: str | None = Form(None),
                       db: Session = Depends(get_db), u: User = Depends(current_user)):
    prev = _token_replay(db, u, upload_token, assignment_id=aid)
    if prev: return {**ev.out(prev, ev.names_for(db, [u.id])), 'duplicate': True}
    a, r = active_own_assignment(db, u, aid)
    project = db.get(Project, r.project_id)
    stored = ev.store_upload(file, project, ev.count_live(db, assignment_id=a.id))
    x = _new_attachment(db, u, project, stored, kind='INSPECTOR_REVIEW', token=upload_token, rfi_id=r.id, summary_id=r.summary_id, assignment_id=a.id,
                        workflow_stage=f'INSPECTOR_REVIEW#{a.sequence_no}', author_role=a.reviewer_role, description=(description or '')[:255] or None,
                        entity_type='rfi', entity_id=r.id)
    if getattr(x, '_duplicate', False): return {**ev.out(x, ev.names_for(db, [u.id])), 'duplicate': True}
    log(db, u.id, 'RFI', r.id, 'UPLOAD_EVIDENCE', f'review #{a.sequence_no} {x.original_name} (sha256 {x.sha256[:12]})', project_id=r.project_id)
    db.commit(); db.refresh(x)
    return ev.out(x, ev.names_for(db, [u.id]))


# --------------------------------------------------------------------------------------- files (all paths)
@router.get('/files/{fid}')
def file_meta(fid: int, db: Session = Depends(get_db), u: User = Depends(current_user)):
    a = db.get(Attachment, fid)
    if not a: raise HTTPException(404, 'Attachment not found')
    ev.can_view_attachment(db, u, a)
    return ev.out(a, ev.names_for(db, [a.uploaded_by]))


@router.get('/files/{fid}/download')
def download(fid: int, inline: bool = False, db: Session = Depends(get_db), u: User = Depends(current_user)):
    a = db.get(Attachment, fid)
    if not a: raise HTTPException(404, 'Attachment not found')
    ev.can_view_attachment(db, u, a)
    path = ev.file_path(a)
    pid = a.project_id or None
    if not path.exists():
        raise HTTPException(404, 'File unavailable: the stored file is missing. The administrator has been notified in the audit log.')
    if not ev.verify_integrity(a):
        log(db, u.id, 'ATTACHMENT', a.id, 'INTEGRITY_FAILURE', a.original_name, project_id=pid, commit=True)
        raise HTTPException(409, 'This file failed its integrity check (checksum mismatch) and was not served')
    log(db, u.id, 'ATTACHMENT', a.id, 'PREVIEW_ATTACHMENT' if inline else 'DOWNLOAD_ATTACHMENT', a.original_name, project_id=pid, commit=True)
    from pathlib import Path as P
    ext = P(a.original_name or '').suffix.lower()
    show_inline = inline and ext in ev.INLINE
    headers = {'Content-Security-Policy': "sandbox; default-src 'none'; img-src 'self'; style-src 'unsafe-inline'", 'X-Content-Type-Options': 'nosniff'}
    return FileResponse(path, filename=a.original_name, media_type=ev.media_type(ext) if a.attachment_kind else (a.content_type or 'application/octet-stream'),
                        content_disposition_type='inline' if show_inline else 'attachment', headers=headers)


@router.delete('/files/{fid}')
def remove_file(fid: int, db: Session = Depends(get_db), u: User = Depends(current_user)):
    """Remove a file before submission. Only its uploader may do this, and never after it is locked."""
    a = db.scalar(select(Attachment).where(Attachment.id == fid).with_for_update())
    if not a or not a.is_active or a.removed_at: raise HTTPException(404, 'Attachment not found')
    ev.can_view_attachment(db, u, a)
    if a.uploaded_by != u.id: raise HTTPException(403, 'Only the person who added a file can remove it before submission')
    if a.locked_at: raise HTTPException(409, 'This file was submitted and is locked. Corrections go through a controlled amendment.')
    if a.attachment_kind == 'INSPECTOR_REVIEW': active_own_assignment(db, u, a.assignment_id)
    if a.attachment_kind == 'MANAGEMENT_REMARK': own_draft_remark(db, u, a.management_remark_id)
    if a.amendment_id:
        am = db.get(RfiAmendment, a.amendment_id)
        if not am or am.status != 'DRAFT': raise HTTPException(409, 'This amendment has been sent and its files are locked')
    a.removed_at = datetime.utcnow(); a.removed_by = u.id
    log(db, u.id, 'ATTACHMENT', a.id, 'REMOVE_BEFORE_SUBMIT', a.original_name, project_id=a.project_id)
    db.commit()
    return {'ok': True}


@router.get('/rfis/{rid}')
def rfi_index(rid: int, db: Session = Depends(get_db), u: User = Depends(current_user)):
    """Attachment index of an RFI: every file the user may see, with author, stage, time and checksum."""
    r, role = authz.load_rfi(db, u, rid)
    rows = ev.rfi_evidence(db, u, rid)
    nm = ev.names_for(db, [a.uploaded_by for a in rows])
    return {'rfi_id': rid, 'files': [ev.out(a, nm) for a in rows], 'legacy_document': legacy_document(r)}


@router.get('/mine')
def my_files(project_id: int | None = None, db: Session = Depends(get_db), u: User = Depends(current_user)):
    """Evidence the signed-in user added (inspector 'Attachments' menu)."""
    q = select(Attachment).where(Attachment.uploaded_by == u.id, Attachment.is_active == True, Attachment.removed_at.is_(None))
    if project_id: authz.require_project(db, u, project_id); q = q.where(Attachment.project_id == project_id)
    rows = ev.visible(db, u, list(db.scalars(q.order_by(Attachment.id.desc()).limit(500))))
    nums = {r.id: r.rfi_number for r in db.scalars(select(Rfi).where(Rfi.id.in_({a.rfi_id for a in rows if a.rfi_id} or {-1})))}
    return [ev.out(a, {u.id: u.full_name}, {'rfi_number': nums.get(a.rfi_id)}) for a in rows]


def legacy_document(r: Rfi) -> dict | None:
    """Historical File_Path / IPC helper values are network-drive pointers the system cannot reach. They are never returned as paths."""
    if r.provenance != 'LEGACY_IMPORT' and not (r.legacy_file_path or r.legacy_ipc_file_path):
        return None
    return {'available': False, 'label': 'File unavailable — migration required', 'has_reference': bool(r.legacy_file_path),
            'ipc_included': r.legacy_ipc_included, 'has_ipc_reference': bool(r.legacy_ipc_file_path),
            'note': 'The historical register pointed to a document on the former shared drive. It has not been migrated into the system.'}


# ------------------------------------------------------------------------------------ evidence amendments
def _amendment_target(db, u, kind: str, tid: int):
    if kind == 'REVIEW':
        a = _assignment(db, tid)
        r = db.scalar(select(Rfi).where(Rfi.id == a.rfi_id).with_for_update())
        role = authz.require_project(db, u, r.project_id, write=True)
        if a.status != 'COMPLETED': raise HTTPException(409, 'Only a submitted review can be amended; edit the draft instead')
        if not (a.user_id == u.id and role in authz.INSPECTORS) and role not in authz.MANAGEMENT:
            raise HTTPException(403, 'Only the inspector who submitted the review, or the RE/DRE, can request its correction')
        rv = db.scalar(select(Review).where(Review.assignment_id == a.id))
        return r, a, None, rv.comment if rv else None
    if kind == 'REMARK':
        rem = db.get(ManagementRemark, tid)
        if not rem: raise HTTPException(404, 'Remark not found')
        if not rem.rfi_id: raise HTTPException(409, 'A DOC_01 batch remark cannot be amended; record a new DOC_01 review remark')
        r = db.scalar(select(Rfi).where(Rfi.id == rem.rfi_id).with_for_update())
        role = authz.require_project(db, u, r.project_id, authz.MANAGEMENT, write=True)
        if rem.status != 'SUBMITTED': raise HTTPException(409, 'Only a submitted remark can be amended; edit the draft instead')
        return r, None, rem, rem.body
    raise HTTPException(400, 'target_kind must be REVIEW or REMARK')


@router.post('/amendments')
def create_evidence_amendment(d: EvidenceAmendmentCreate, db: Session = Depends(get_db), u: User = Depends(current_user)):
    r, a, rem, current = _amendment_target(db, u, d.target_kind, d.target_id)
    require_active_record(r)
    if r.workflow_status in ('COMPLETED', 'CANCELLED'):
        raise HTTPException(409, 'The DOC_03 has been issued; issued records are not amended. Corrections need a new revision of the RFI.')
    if not d.reason.strip(): raise HTTPException(400, 'A reason is required')
    changes = {}
    if d.new_comment is not None and d.new_comment.strip() and d.new_comment.strip() != (current or ''):
        changes['comment'] = {'old': current, 'new': d.new_comment.strip()}
    am = RfiAmendment(rfi_id=r.id, project_id=r.project_id, changes_json=json.dumps(changes), reason=d.reason.strip(), status='DRAFT',
                      requested_by=u.id, amendment_type=d.target_kind, target_assignment_id=a.id if a else None, target_remark_id=rem.id if rem else None)
    db.add(am); db.flush()
    log(db, u.id, 'RFI', r.id, 'DRAFT_EVIDENCE_AMENDMENT', d.reason.strip(), project_id=r.project_id, after={'target': d.target_kind, 'id': d.target_id, **changes})
    db.commit()
    return amendment_out(db, am, u)


def amendment_out(db, am: RfiAmendment, u: User) -> dict:
    files = list(db.scalars(select(Attachment).where(Attachment.amendment_id == am.id, Attachment.removed_at.is_(None)).order_by(Attachment.id)))
    nm = ev.names_for(db, [am.requested_by, am.resolved_by] + [f.uploaded_by for f in files])
    return {'id': am.id, 'rfi_id': am.rfi_id, 'amendment_type': am.amendment_type, 'status': am.status, 'reason': am.reason,
            'changes': json.loads(am.changes_json or '{}'), 'target_assignment_id': am.target_assignment_id, 'target_remark_id': am.target_remark_id,
            'requested_by': am.requested_by, 'requested_by_name': nm.get(am.requested_by), 'requested_at': am.requested_at,
            'resolved_by_name': nm.get(am.resolved_by), 'resolved_at': am.resolved_at, 'resolution_comment': am.resolution_comment,
            'files': [ev.out(f, nm) for f in files]}


def _own_draft_amendment(db, u, aid):
    am = db.scalar(select(RfiAmendment).where(RfiAmendment.id == aid).with_for_update())
    if not am or am.amendment_type not in ('REVIEW', 'REMARK'): raise HTTPException(404, 'Evidence amendment not found')
    authz.require_project(db, u, am.project_id, write=True)
    if am.requested_by != u.id: raise HTTPException(403, 'Only the requester can change this amendment')
    if am.status != 'DRAFT': raise HTTPException(409, 'This amendment has been sent for approval and is locked')
    return am


@router.post('/amendments/{aid}/files')
def upload_amendment_file(aid: int, file: UploadFile = File(...), upload_token: str | None = Form(None), supersedes_id: int | None = Form(None),
                          db: Session = Depends(get_db), u: User = Depends(current_user)):
    prev = _token_replay(db, u, upload_token, amendment_id=aid)
    if prev: return {**ev.out(prev, ev.names_for(db, [u.id])), 'duplicate': True}
    am = _own_draft_amendment(db, u, aid)
    r = db.get(Rfi, am.rfi_id); project = db.get(Project, am.project_id)
    target = dict(assignment_id=am.target_assignment_id) if am.amendment_type == 'REVIEW' else dict(management_remark_id=am.target_remark_id)
    version = 1
    if supersedes_id:
        old = db.get(Attachment, supersedes_id)
        if not old or not ev.is_live(old) or any(getattr(old, k) != v for k, v in target.items()):
            raise HTTPException(400, 'The file to replace must be a current file of the amended review / remark')
        version = (old.version_no or 1) + 1
    stored = ev.store_upload(file, project, ev.count_live(db, **target))
    kind = 'INSPECTOR_REVIEW' if am.amendment_type == 'REVIEW' else 'MANAGEMENT_REMARK'
    stage = None
    if am.amendment_type == 'REVIEW':
        asg = db.get(ReviewerAssignment, am.target_assignment_id); stage = f'INSPECTOR_REVIEW#{asg.sequence_no}'; role = asg.reviewer_role
    else:
        rem = db.get(ManagementRemark, am.target_remark_id); stage = rem.stage; role = rem.author_role
    x = _new_attachment(db, u, project, stored, kind=kind, token=upload_token, rfi_id=r.id, summary_id=r.summary_id, workflow_stage=stage, author_role=role,
                        amendment_id=am.id, supersedes_id=supersedes_id, version_no=version, upload_status='PENDING_APPROVAL', entity_type='rfi', entity_id=r.id, **target)
    if getattr(x, '_duplicate', False): return {**ev.out(x, ev.names_for(db, [u.id])), 'duplicate': True}
    log(db, u.id, 'RFI', r.id, 'UPLOAD_AMENDMENT_EVIDENCE', f'amendment {am.id}: {x.original_name}', project_id=r.project_id)
    db.commit(); db.refresh(x)
    return ev.out(x, ev.names_for(db, [u.id]))


@router.post('/amendments/{aid}/send')
def send_amendment(aid: int, db: Session = Depends(get_db), u: User = Depends(current_user)):
    am = _own_draft_amendment(db, u, aid)
    changes = json.loads(am.changes_json or '{}')
    nfiles = db.scalar(select(func.count()).select_from(Attachment).where(Attachment.amendment_id == am.id, Attachment.removed_at.is_(None))) or 0
    if not changes and not nfiles: raise HTTPException(400, 'The amendment has no corrected text and no files')
    am.status = 'PENDING'; am.requested_at = datetime.utcnow()
    ev.lock(db, Attachment.amendment_id == am.id, Attachment.removed_at.is_(None))
    r = db.get(Rfi, am.rfi_id)
    notify_project_roles(db, am.project_id, authz.MANAGEMENT, 'Evidence correction requested',
                         f'A correction to a {"inspector review" if am.amendment_type == "REVIEW" else "management remark"} on RFI {r.rfi_number} awaits approval: {am.reason}', 'RFI', r.id, exclude={u.id})
    log(db, u.id, 'RFI', r.id, 'REQUEST_EVIDENCE_AMENDMENT', am.reason, project_id=r.project_id, after={**changes, 'files': nfiles})
    db.commit()
    return amendment_out(db, am, u)


@router.delete('/amendments/{aid}')
def withdraw_amendment(aid: int, db: Session = Depends(get_db), u: User = Depends(current_user)):
    am = _own_draft_amendment(db, u, aid)
    now = datetime.utcnow()
    am.status = 'WITHDRAWN'; am.resolved_at = now; am.resolved_by = u.id
    for a in db.scalars(select(Attachment).where(Attachment.amendment_id == am.id, Attachment.removed_at.is_(None))):
        a.removed_at = now; a.removed_by = u.id
    db.commit()
    return {'ok': True}


@router.get('/amendments')
def list_amendments(rfi_id: int, db: Session = Depends(get_db), u: User = Depends(current_user)):
    r, role = authz.load_rfi(db, u, rfi_id)
    rows = list(db.scalars(select(RfiAmendment).where(RfiAmendment.rfi_id == rfi_id, RfiAmendment.amendment_type.in_(['REVIEW', 'REMARK'])).order_by(RfiAmendment.id.desc())))
    return [amendment_out(db, a, u) for a in rows if a.status != 'DRAFT' or a.requested_by == u.id]


def apply_evidence_amendment(db, am: RfiAmendment, approve: bool, u: User):
    """Called by the RE/DRE approve/reject endpoint for REVIEW / REMARK amendments. Original text and files are kept."""
    now = datetime.utcnow()
    changes = json.loads(am.changes_json or '{}')
    files = list(db.scalars(select(Attachment).where(Attachment.amendment_id == am.id, Attachment.removed_at.is_(None))))
    if not approve:
        for f in files: f.upload_status = 'REJECTED'
        return
    if 'comment' in changes:
        if am.amendment_type == 'REVIEW':
            rv = db.scalar(select(Review).where(Review.assignment_id == am.target_assignment_id).with_for_update())
            if (rv.comment or '') != (changes['comment']['old'] or ''): raise HTTPException(409, 'The review changed since the correction was requested')
            rv.comment = changes['comment']['new']
        else:
            rem = db.scalar(select(ManagementRemark).where(ManagementRemark.id == am.target_remark_id).with_for_update())
            if (rem.body or '') != (changes['comment']['old'] or ''): raise HTTPException(409, 'The remark changed since the correction was requested')
            rem.body = changes['comment']['new']; rem.version += 1; rem.updated_at = now
    for f in files:
        f.upload_status = 'COMPLETE'; f.locked_at = f.locked_at or now
        if f.supersedes_id:
            old = db.get(Attachment, f.supersedes_id)
            if old and old.superseded_at is None: old.superseded_at = now
    if am.amendment_type == 'REVIEW':
        rv = db.scalar(select(Review).where(Review.assignment_id == am.target_assignment_id))
        if rv: rv.attachment_count = ev.count_live(db, assignment_id=am.target_assignment_id)
