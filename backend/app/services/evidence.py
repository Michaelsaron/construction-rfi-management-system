"""Evidence (attachment) service - UI design s.14, docs/ui-upgrade/ATTACHMENT_ARCHITECTURE.md.

Two separate permission paths own new evidence:
  * MANAGEMENT_REMARK - Category 2.1 (RE/DRE) files attached to their own management remark;
  * INSPECTOR_REVIEW  - Category 2.2 files attached by the active assigned inspector to their own DOC_03 review.
RECORD covers contractor enclosures, DOC_01 batch files, Daily Progress files and every file stored before this release.

Files are streamed to a private folder under UPLOAD_DIR with a random name. The storage name never leaves the server:
API responses carry an attachment id, and downloads go through `/evidence/files/{id}/download`, which re-checks access.
"""
import hashlib
import os
import socket
import struct
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from fastapi import HTTPException, UploadFile
from sqlalchemy import select, func
from app.config import settings as app_settings
from app.models import Attachment, ManagementRemark, ReviewerAssignment, Rfi, RfiSummary, User, Project
from app.project_settings import get_settings
from app import authz

CHUNK = 1024 * 1024
MEDIA = {'.pdf': 'application/pdf', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png', '.webp': 'image/webp', '.heic': 'image/heic',
         '.xls': 'application/vnd.ms-excel', '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
         '.doc': 'application/msword', '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
         '.dwg': 'application/acad', '.dxf': 'application/dxf', '.dgn': 'application/octet-stream', '.csv': 'text/csv', '.txt': 'text/plain'}
# Types a browser may display inline. Everything else is always downloaded.
INLINE = {'.pdf', '.jpg', '.jpeg', '.png', '.webp'}
OLE = b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'
SIGNATURES = {
    '.pdf': [b'%PDF-'], '.png': [b'\x89PNG\r\n\x1a\n'], '.jpg': [b'\xff\xd8\xff'], '.jpeg': [b'\xff\xd8\xff'], '.webp': [b'RIFF'],
    '.xlsx': [b'PK\x03\x04'], '.docx': [b'PK\x03\x04'], '.xls': [OLE], '.doc': [OLE], '.dwg': [b'AC10', b'AC1.', b'AC2.'],
}
HUMAN_KIND = {'MANAGEMENT_REMARK': 'Management remark', 'INSPECTOR_REVIEW': 'Inspector review', 'RECORD': 'Record attachment'}


def policy_for(project) -> dict:
    p = dict(get_settings(project)['attachment_policy'])
    p['max_file_mb'] = min(int(p.get('max_file_mb') or app_settings.max_upload_mb), app_settings.max_upload_mb)
    return p


def media_type(ext: str) -> str:
    return MEDIA.get(ext.lower(), 'application/octet-stream')


def _sniff_ok(ext: str, head: bytes) -> bool:
    sigs = SIGNATURES.get(ext)
    if not sigs:
        return True  # DGN / DXF / text have no reliable signature; extension and size rules still apply
    if ext == '.dwg':
        return any(head.startswith(s[:3]) for s in sigs)
    return any(head.startswith(s) for s in sigs)


def _clamd_scan(path: Path) -> str:
    """Return CLEAN / INFECTED / ERROR using clamd INSTREAM (CLAMD_HOST, CLAMD_PORT). ERROR when no scanner is reachable."""
    host = os.environ.get('CLAMD_HOST')
    if not host:
        return 'ERROR'
    try:
        with socket.create_connection((host, int(os.environ.get('CLAMD_PORT', '3310'))), timeout=30) as s, open(path, 'rb') as f:
            s.sendall(b'zINSTREAM\0')
            while chunk := f.read(CHUNK):
                s.sendall(struct.pack('!L', len(chunk)) + chunk)
            s.sendall(struct.pack('!L', 0))
            reply = s.recv(4096).decode(errors='replace')
        return 'CLEAN' if reply.strip('\0').endswith('OK') else ('INFECTED' if 'FOUND' in reply else 'ERROR')
    except OSError:
        return 'ERROR'


def store_upload(file: UploadFile, project, existing_count: int = 0) -> dict:
    """Validate and store one uploaded file. Raises 400/413/422 with a readable reason; never leaves a partial file."""
    pol = policy_for(project)
    name = (file.filename or '').strip()
    ext = Path(name).suffix.lower()
    if not name or not ext:
        raise HTTPException(400, 'The file has no name or extension')
    if ext not in pol['allowed_extensions']:
        raise HTTPException(400, f'File type {ext} is not allowed for this project. Allowed: {", ".join(pol["allowed_extensions"])}')
    if existing_count >= pol['max_files_per_record']:
        raise HTTPException(400, f'This record already has the maximum of {pol["max_files_per_record"]} files')
    limit = pol['max_file_mb'] * 1024 * 1024
    base = Path(app_settings.upload_dir).resolve()
    folder = base / 'evidence' / f'p{project.id}'
    folder.mkdir(parents=True, exist_ok=True)
    stored = f'evidence/p{project.id}/{uuid4().hex}{ext}'
    tmp = base / (stored + '.part')
    h = hashlib.sha256(); size = 0; head = b''
    try:
        with open(tmp, 'wb') as out:
            while chunk := file.file.read(CHUNK):
                if not head: head = chunk[:16]
                size += len(chunk)
                if size > limit:
                    raise HTTPException(413, f'File is larger than the {pol["max_file_mb"]} MB limit')
                h.update(chunk); out.write(chunk)
        if size == 0:
            raise HTTPException(400, 'The file is empty')
        if not _sniff_ok(ext, head):
            raise HTTPException(422, f'The file content does not match its {ext} extension')
        scan = 'NOT_SCANNED'
        if pol['scanning'] != 'DISABLED':
            scan = _clamd_scan(tmp)
            if scan == 'INFECTED':
                raise HTTPException(422, 'The file was rejected by the malware scanner')
            if scan == 'ERROR' and pol['scanning'] == 'REQUIRED':
                raise HTTPException(503, 'The malware scanner is not available; the file was not stored. Try again later.')
        os.replace(tmp, base / stored)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    return {'stored_name': stored, 'size_bytes': size, 'sha256': h.hexdigest(), 'scan_status': scan, 'content_type': media_type(ext),
            'original_name': name[:255], 'scanned_at': datetime.utcnow() if scan != 'NOT_SCANNED' else None}


def discard_stored(stored_name: str):
    base = Path(app_settings.upload_dir).resolve()
    path = (base / stored_name).resolve()
    if base in path.parents: path.unlink(missing_ok=True)


def existing_by_token(db, user: User, token: str | None):
    if not token:
        return None
    return db.scalar(select(Attachment).where(Attachment.uploaded_by == user.id, Attachment.upload_token == token[:64]))


def file_path(a) -> Path:
    base = Path(app_settings.upload_dir).resolve()
    path = (base / a.stored_name).resolve()
    if base not in path.parents:
        raise HTTPException(404, 'Stored file missing')
    return path


def verify_integrity(a) -> bool:
    """True when the stored bytes still match the recorded SHA-256 (pre-v1 files without a hash are reported as unknown)."""
    path = file_path(a)
    if not path.exists():
        return False
    if not a.sha256:
        return True
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while chunk := f.read(CHUNK): h.update(chunk)
    return h.hexdigest() == a.sha256


def is_live(a: Attachment) -> bool:
    return a.is_active and a.removed_at is None and (a.upload_status or 'COMPLETE') == 'COMPLETE' and a.superseded_at is None


def live_clause():
    return [Attachment.is_active == True, Attachment.removed_at.is_(None), func.coalesce(Attachment.upload_status, 'COMPLETE') == 'COMPLETE',
            Attachment.superseded_at.is_(None)]


def count_live(db, **where) -> int:
    q = select(func.count()).select_from(Attachment).where(*live_clause())
    for k, v in where.items(): q = q.where(getattr(Attachment, k) == v)
    return db.scalar(q) or 0


def out(a: Attachment, names: dict | None = None, extra: dict | None = None) -> dict:
    """Public representation. Never includes the storage name or a filesystem path."""
    names = names or {}
    d = {'id': a.id, 'original_name': a.original_name, 'content_type': a.content_type, 'size_bytes': a.size_bytes, 'description': a.description,
         'uploaded_by': a.uploaded_by, 'uploaded_by_name': names.get(a.uploaded_by), 'uploaded_at': a.uploaded_at,
         'attachment_kind': a.attachment_kind or 'RECORD', 'kind_label': HUMAN_KIND.get(a.attachment_kind or 'RECORD'),
         'entity_type': a.entity_type, 'entity_id': a.entity_id, 'project_id': a.project_id, 'rfi_id': a.rfi_id, 'summary_id': a.summary_id,
         'management_remark_id': a.management_remark_id, 'assignment_id': a.assignment_id, 'review_id': a.review_id, 'amendment_id': a.amendment_id,
         'workflow_stage': a.workflow_stage, 'author_role': a.author_role, 'author_role_label': authz.ROLE_LABELS.get(a.author_role or '', a.author_role),
         'sha256': a.sha256, 'upload_status': a.upload_status or 'COMPLETE', 'scan_status': a.scan_status or 'NOT_SCANNED',
         'version_no': a.version_no or 1, 'supersedes_id': a.supersedes_id, 'superseded_at': a.superseded_at, 'locked': a.locked_at is not None,
         'locked_at': a.locked_at, 'removed': a.removed_at is not None or not a.is_active, 'previewable': Path(a.original_name or '').suffix.lower() in INLINE}
    if extra: d.update(extra)
    return d


def names_for(db, ids) -> dict:
    ids = {i for i in ids if i}
    return {u.id: u.full_name for u in db.scalars(select(User).where(User.id.in_(ids)))} if ids else {}


def lock(db, *where, when=None):
    when = when or datetime.utcnow()
    for a in db.scalars(select(Attachment).where(*where, Attachment.locked_at.is_(None))):
        a.locked_at = when


# ----------------------------------------------------------------------------------------------- visibility
def can_view_attachment(db, u: User, a: Attachment) -> str:
    """Return the viewer's project role or raise 403/404. One rule set for listing, preview, download and bundles."""
    if not a.is_active:
        raise HTTPException(404, 'Attachment not found')
    kind = a.attachment_kind or 'RECORD'
    if kind == 'RECORD':
        return _record_parent_role(db, u, a)
    rfi = db.get(Rfi, a.rfi_id) if a.rfi_id else None
    if kind == 'INSPECTOR_REVIEW':
        r, role = authz.load_rfi(db, u, rfi.id)
        asg = db.get(ReviewerAssignment, a.assignment_id)
        own = asg is not None and asg.user_id == u.id
        if a.locked_at is None and not own:
            raise HTTPException(403, 'This evidence belongs to a review that has not been submitted')
        return _evidence_role_ok(db, u, r.project_id, role, own, rfi_ids=[r.id])
    if kind == 'MANAGEMENT_REMARK':
        rem = db.get(ManagementRemark, a.management_remark_id)
        if rem is None: raise HTTPException(404, 'Attachment not found')
        if rem.rfi_id:
            _, role = authz.load_rfi(db, u, rem.rfi_id)
        else:
            _, role = authz.load_summary(db, u, rem.summary_id)
        own = rem.author_id == u.id
        if rem.status != 'SUBMITTED' and not own:
            raise HTTPException(403, 'This evidence belongs to a remark that has not been submitted')
        ids = [rem.rfi_id] if rem.rfi_id else list(db.scalars(select(Rfi.id).where(Rfi.summary_id == rem.summary_id)))
        return _evidence_role_ok(db, u, rem.project_id, role, own, rfi_ids=ids)
    raise HTTPException(404, 'Attachment not found')


def _evidence_role_ok(db, u, project_id, role, own, rfi_ids=()) -> str:
    if own or role == authz.ADMIN or role in authz.MANAGEMENT or role in authz.OFFICE:
        return role
    if role in authz.INSPECTORS:
        # Conservative (UD-05): register read access does not extend to evidence. An inspector sees the submitted evidence
        # of RFIs on which they hold (or held) a turn; an inspector who was replaced is locked out.
        if rfi_ids and db.scalar(select(func.count()).select_from(ReviewerAssignment).where(
                ReviewerAssignment.rfi_id.in_(list(rfi_ids)), ReviewerAssignment.user_id == u.id, ReviewerAssignment.status != 'REPLACED')):
            return role
        raise HTTPException(403, 'Inspection evidence is visible to the inspectors assigned to this RFI')
    if role in authz.CONTRACTOR and get_settings(db.get(Project, project_id)).get('contractor_evidence_access'):
        return role
    raise HTTPException(403, 'Your project role does not give access to inspection evidence (pending client decision UD-04)')


def _record_parent_role(db, u, a) -> str:
    t = (a.entity_type or '').lower()
    if t == 'rfi':
        return authz.load_rfi(db, u, a.entity_id)[1]
    if t == 'summary':
        return authz.load_summary(db, u, a.entity_id)[1]
    if t == 'daily_progress':
        from app.models import DailyProgress
        p = db.get(DailyProgress, a.entity_id)
        if not p: raise HTTPException(404, 'Attachment not found')
        return authz.require_project(db, u, p.project_id)
    raise HTTPException(404, 'Attachment not found')


def visible(db, u: User, rows) -> list:
    keep = []
    for a in rows:
        try:
            can_view_attachment(db, u, a); keep.append(a)
        except HTTPException:
            pass
    return keep


def rfi_evidence(db, u: User, rfi_id: int, include_history: bool = False) -> list:
    """All evidence of an RFI the user may see (management remarks of the RFI and of its DOC_01 batch, inspector reviews, records)."""
    r = db.get(Rfi, rfi_id)
    q = select(Attachment).where(Attachment.is_active == True, Attachment.removed_at.is_(None))
    from sqlalchemy import or_, and_
    parents = [Attachment.rfi_id == rfi_id, and_(Attachment.entity_type == 'rfi', Attachment.entity_id == rfi_id)]
    if r and r.summary_id:
        parents.append(and_(Attachment.attachment_kind == 'MANAGEMENT_REMARK', Attachment.summary_id == r.summary_id, Attachment.rfi_id.is_(None)))
    q = q.where(or_(*parents))
    if not include_history:
        q = q.where(func.coalesce(Attachment.upload_status, 'COMPLETE') == 'COMPLETE', Attachment.superseded_at.is_(None))
    return visible(db, u, list(db.scalars(q.order_by(Attachment.uploaded_at, Attachment.id))))
