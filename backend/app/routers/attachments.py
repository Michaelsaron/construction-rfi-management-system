"""Attachments (FR-28). Access is resolved through the parent record's project and visibility rules."""
from pathlib import Path
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.config import settings
from app.database import get_db
from app.models import Attachment, User, Rfi, RfiSummary, DailyProgress, ReviewerAssignment
from app.security import current_user
from app import authz
from app.services.files import save_upload
from app.services.audit import log

router = APIRouter(prefix='/attachments', tags=['Attachments'])


def parent_access(db, u, entity_type: str, entity_id: int, write=False):
    t = entity_type.lower()
    if t == 'rfi':
        r, role = authz.load_rfi(db, u, entity_id)
        if write:
            if r.record_state != 'ACTIVE' or r.provenance == 'LEGACY_IMPORT': raise HTTPException(409, 'This RFI is read-only')
            mine = db.scalar(select(ReviewerAssignment.id).where(ReviewerAssignment.rfi_id == r.id, ReviewerAssignment.user_id == u.id, ReviewerAssignment.status.in_(['ACTIVE', 'COMPLETED'])))
            ok = role in authz.MANAGEMENT or (role in authz.CONTRACTOR and r.workflow_status in ('DRAFT', 'SUBMITTED')) or (role in authz.INSPECTORS and mine)
            if not ok: raise HTTPException(403, 'You cannot add attachments to this RFI at its current stage')
        return t, r.project_id, role
    if t == 'summary':
        s, role = authz.load_summary(db, u, entity_id)
        if write and not ((role in authz.CONTRACTOR and s.workflow_status in ('DRAFT', 'RETURNED')) or role in authz.MANAGEMENT):
            raise HTTPException(403, 'You cannot add attachments to this batch')
        return t, s.project_id, role
    if t == 'daily_progress':
        p = db.get(DailyProgress, entity_id)
        if not p: raise HTTPException(404, 'Parent record not found')
        role = authz.require_project(db, u, p.project_id, write=write)
        return t, p.project_id, role
    raise HTTPException(400, 'Unsupported attachment entity')


@router.get('/download/{aid}')
def download(aid: int, db: Session = Depends(get_db), u: User = Depends(current_user)):
    a = db.get(Attachment, aid)
    if not a or not a.is_active: raise HTTPException(404, 'Attachment not found')
    _, pid, _ = parent_access(db, u, a.entity_type, a.entity_id)
    base = Path(settings.upload_dir).resolve()
    path = (base / a.stored_name).resolve()
    if base not in path.parents or not path.exists(): raise HTTPException(404, 'Stored file missing')
    log(db, u.id, a.entity_type.upper(), a.entity_id, 'DOWNLOAD_ATTACHMENT', a.original_name, project_id=pid, commit=True)
    return FileResponse(path, filename=a.original_name, media_type=a.content_type or 'application/octet-stream')


@router.get('/{entity_type}/{entity_id}')
def ls(entity_type: str, entity_id: int, db: Session = Depends(get_db), u: User = Depends(current_user)):
    t, _, _ = parent_access(db, u, entity_type, entity_id)
    return list(db.scalars(select(Attachment).where(Attachment.entity_type == t, Attachment.entity_id == entity_id, Attachment.is_active == True).order_by(Attachment.id.desc())))


@router.post('/{entity_type}/{entity_id}')
def upload(entity_type: str, entity_id: int, file: UploadFile = File(...), description: str | None = Form(None), db: Session = Depends(get_db), u: User = Depends(current_user)):
    t, pid, _ = parent_access(db, u, entity_type, entity_id, write=True)
    stored, size = save_upload(file)
    a = Attachment(entity_type=t, entity_id=entity_id, original_name=(file.filename or stored)[:255], stored_name=stored, content_type=file.content_type,
                   size_bytes=size, description=description, uploaded_by=u.id)
    db.add(a); db.flush()
    log(db, u.id, t.upper(), entity_id, 'UPLOAD', a.original_name, project_id=pid)
    db.commit(); db.refresh(a)
    return a


@router.delete('/{aid}')
def remove(aid: int, db: Session = Depends(get_db), u: User = Depends(current_user)):
    a = db.get(Attachment, aid)
    if not a or not a.is_active: raise HTTPException(404, 'Attachment not found')
    _, pid, role = parent_access(db, u, a.entity_type, a.entity_id)
    if role not in authz.MANAGEMENT and role != authz.ADMIN: raise HTTPException(403, 'Only RE/DRE or Admin can remove attachments')
    a.is_active = False
    log(db, u.id, a.entity_type.upper(), a.entity_id, 'REMOVE_ATTACHMENT', a.original_name, project_id=pid)
    db.commit()
    return {'ok': True}
