"""Daily Progress (complementary module, preserved). Project-scoped like the RFI core."""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import DailyProgress, DailyProgressRfi, User, Rfi
from app.schemas import DailyProgressCreate, DailyProgressComment
from app.security import current_user
from app import authz
from app.services.audit import log
from app.services.notify import notify, notify_project_roles

router = APIRouter(prefix='/daily-progress', tags=['Daily Progress'])
CREATE_ROLES = authz.CONTRACTOR | authz.MANAGEMENT
REVIEW_ROLES = authz.INSPECTORS | authz.MANAGEMENT
DECISION_ROLES = authz.MANAGEMENT


def get_record(db, user, pid):
    p = db.get(DailyProgress, pid)
    if not p: raise HTTPException(404, 'Daily Progress not found')
    role = authz.require_project(db, user, p.project_id)
    return p, role


def check_links(db, project_id, rfi_ids):
    for rid in set(rfi_ids):
        r = db.get(Rfi, rid)
        if not r or r.project_id != project_id:
            raise HTTPException(400, f'RFI {rid} does not belong to the selected project')


@router.get('')
def ls(project_id: int | None = None, limit: int = 100, offset: int = 0, db: Session = Depends(get_db), u: User = Depends(current_user)):
    limit = max(1, min(limit, 500)); offset = max(0, offset)
    q = select(DailyProgress).order_by(DailyProgress.progress_date.desc(), DailyProgress.id.desc())
    if project_id is not None:
        authz.require_project(db, u, project_id); q = q.where(DailyProgress.project_id == project_id)
    else:
        vis = authz.visible_project_ids(db, u)
        if vis is not None: q = q.where(DailyProgress.project_id.in_(vis or [-1]))
    rows = list(db.scalars(q.offset(offset).limit(limit)))
    ids = [p.id for p in rows]
    links = list(db.scalars(select(DailyProgressRfi).where(DailyProgressRfi.daily_progress_id.in_(ids)))) if ids else []
    linked = {pid: [] for pid in ids}
    for x in links: linked[x.daily_progress_id].append(x.rfi_id)
    return [{'record': p, 'rfi_ids': linked[p.id]} for p in rows]


@router.get('/{pid}')
def detail(pid: int, db: Session = Depends(get_db), u: User = Depends(current_user)):
    p, _ = get_record(db, u, pid)
    return {'record': p, 'rfi_ids': list(db.scalars(select(DailyProgressRfi.rfi_id).where(DailyProgressRfi.daily_progress_id == pid)))}


@router.post('')
def create(d: DailyProgressCreate, db: Session = Depends(get_db), u: User = Depends(current_user)):
    authz.require_project(db, u, d.project_id, CREATE_ROLES, write=True); check_links(db, d.project_id, d.rfi_ids)
    p = DailyProgress(**d.model_dump(exclude={'rfi_ids'}), created_by=u.id)
    db.add(p); db.flush()
    for rid in set(d.rfi_ids): db.add(DailyProgressRfi(daily_progress_id=p.id, rfi_id=rid))
    log(db, u.id, 'DAILY_PROGRESS', p.id, 'CREATE', project_id=p.project_id); db.commit(); db.refresh(p)
    return p


@router.put('/{pid}')
def update(pid: int, d: DailyProgressCreate, db: Session = Depends(get_db), u: User = Depends(current_user)):
    p, _ = get_record(db, u, pid)
    if p.status != 'DRAFT': raise HTTPException(409, 'Only draft records can be edited')
    if p.created_by != u.id: raise HTTPException(403, 'Only the creator can edit this draft')
    if d.project_id != p.project_id: raise HTTPException(400, 'The project of a record cannot be changed')
    authz.require_project(db, u, p.project_id, CREATE_ROLES, write=True); check_links(db, p.project_id, d.rfi_ids)
    for k, v in d.model_dump(exclude={'rfi_ids'}).items(): setattr(p, k, v)
    for old in db.scalars(select(DailyProgressRfi).where(DailyProgressRfi.daily_progress_id == pid)): db.delete(old)
    db.flush()
    for rid in set(d.rfi_ids): db.add(DailyProgressRfi(daily_progress_id=pid, rfi_id=rid))
    log(db, u.id, 'DAILY_PROGRESS', pid, 'UPDATE', project_id=p.project_id); db.commit(); db.refresh(p)
    return p


@router.post('/{pid}/submit')
def submit(pid: int, db: Session = Depends(get_db), u: User = Depends(current_user)):
    p, _ = get_record(db, u, pid)
    if p.created_by != u.id: raise HTTPException(403, 'Only the creator can submit')
    if p.status != 'DRAFT': raise HTTPException(409, 'Only draft records can be submitted')
    p.status = 'SUBMITTED'
    notify_project_roles(db, p.project_id, authz.INSPECTORS, 'Daily Progress submitted', f'Daily Progress #{p.id} for {p.progress_date} is ready for inspection.', 'DAILY_PROGRESS', p.id)
    log(db, u.id, 'DAILY_PROGRESS', p.id, 'SUBMIT', project_id=p.project_id); db.commit()
    return p


@router.post('/{pid}/review')
def review(pid: int, body: DailyProgressComment, db: Session = Depends(get_db), u: User = Depends(current_user)):
    p, _ = get_record(db, u, pid)
    authz.require_project(db, u, p.project_id, REVIEW_ROLES, write=True)
    if p.status != 'SUBMITTED': raise HTTPException(409, 'Daily Progress must be submitted first')
    if not body.comment.strip(): raise HTTPException(422, 'Inspector review comment is required')
    p.status = 'REVIEWED'; p.review_comment = body.comment.strip(); p.reviewed_by = u.id; p.reviewed_at = datetime.utcnow()
    notify_project_roles(db, p.project_id, DECISION_ROLES, 'Daily Progress awaiting confirmation', f'Daily Progress #{p.id} is ready for RE/DRE confirmation.', 'DAILY_PROGRESS', p.id)
    log(db, u.id, 'DAILY_PROGRESS', p.id, 'REVIEW', project_id=p.project_id); db.commit()
    return p


@router.post('/{pid}/confirm')
def confirm(pid: int, body: DailyProgressComment, db: Session = Depends(get_db), u: User = Depends(current_user)):
    p, _ = get_record(db, u, pid)
    authz.require_project(db, u, p.project_id, DECISION_ROLES, write=True)
    if p.status != 'REVIEWED': raise HTTPException(409, 'Daily Progress must be reviewed first')
    if not body.comment.strip(): raise HTTPException(422, 'RE/DRE confirmation comment is required')
    p.status = 'CONFIRMED'; p.confirmation_comment = body.comment.strip(); p.confirmed_by = u.id; p.confirmed_at = datetime.utcnow()
    notify(db, p.created_by, 'Daily Progress confirmed', f'Daily Progress #{p.id} was confirmed by RE/DRE.', 'DAILY_PROGRESS', p.id, p.project_id)
    log(db, u.id, 'DAILY_PROGRESS', p.id, 'CONFIRM', project_id=p.project_id); db.commit()
    return p
