from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import MasterData, User
from app.schemas import MasterCreate, MasterUpdate
from app.security import current_user
from app import authz
from app.services.audit import log

router = APIRouter(prefix='/master-data', tags=['Master Data'])
EDITORS = authz.MANAGEMENT | {authz.ADMIN}


def can_edit(db, u, project_id):
    if project_id is None:
        if not authz.is_admin(u): raise HTTPException(403, 'Only Admin can edit global reference data')
    else:
        authz.require_project(db, u, project_id, EDITORS, write=True)


@router.get('')
def ls(category: str | None = None, project_id: int | None = None, db: Session = Depends(get_db), u: User = Depends(current_user)):
    q = select(MasterData).where(MasterData.is_active == True)
    if category: q = q.where(MasterData.category == category)
    if project_id:
        authz.require_project(db, u, project_id)
        q = q.where((MasterData.project_id == project_id) | (MasterData.project_id.is_(None)))
    else:
        vis = authz.visible_project_ids(db, u)
        if vis is not None: q = q.where((MasterData.project_id.is_(None)) | (MasterData.project_id.in_(vis or [-1])))
    return list(db.scalars(q.order_by(MasterData.category, MasterData.value)))


@router.post('')
def create(d: MasterCreate, db: Session = Depends(get_db), u: User = Depends(current_user)):
    can_edit(db, u, d.project_id)
    if not d.value.strip(): raise HTTPException(400, 'Value is required')
    if db.scalar(select(MasterData.id).where(MasterData.project_id == d.project_id, MasterData.category == d.category, MasterData.value == d.value.strip(), MasterData.parent_value == d.parent_value, MasterData.is_active == True)):
        raise HTTPException(409, 'Duplicate reference value')
    m = MasterData(**{**d.model_dump(), 'value': d.value.strip()}); db.add(m); db.flush()
    log(db, u.id, 'MASTER_DATA', m.id, 'CREATE', f'{d.category}={m.value}', project_id=d.project_id); db.commit(); db.refresh(m)
    return m


@router.put('/{mid}')
def update(mid: int, d: MasterUpdate, db: Session = Depends(get_db), u: User = Depends(current_user)):
    m = db.get(MasterData, mid)
    if not m: raise HTTPException(404, 'Reference value not found')
    can_edit(db, u, m.project_id)
    before = {'value': m.value, 'parent_value': m.parent_value, 'code': m.code}
    m.value = d.value; m.parent_value = d.parent_value; m.code = d.code
    log(db, u.id, 'MASTER_DATA', m.id, 'EDIT', project_id=m.project_id, before=before, after=d.model_dump()); db.commit()
    return m


@router.delete('/{mid}')
def deactivate(mid: int, db: Session = Depends(get_db), u: User = Depends(current_user)):
    m = db.get(MasterData, mid)
    if not m: raise HTTPException(404, 'Reference value not found')
    can_edit(db, u, m.project_id)
    m.is_active = False
    log(db, u.id, 'MASTER_DATA', m.id, 'DEACTIVATE', project_id=m.project_id); db.commit()
    return {'ok': True}
