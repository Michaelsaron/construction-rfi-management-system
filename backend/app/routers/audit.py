from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import AuditLog, User
from app.security import current_user
from app import authz

router = APIRouter(prefix='/audit', tags=['Audit'])


@router.get('')
def ls(project_id: int | None = None, entity_type: str | None = None, entity_id: int | None = None, limit: int = 500,
       db: Session = Depends(get_db), u: User = Depends(current_user)):
    """Read-only audit trail. Admin: all. RE/DRE: their projects only. No update/delete endpoints exist."""
    q = select(AuditLog)
    if authz.is_admin(u):
        if project_id: q = q.where(AuditLog.project_id == project_id)
    else:
        mgmt = [pid for pid in (authz.visible_project_ids(db, u) or []) if authz.project_role(db, u, pid) in authz.MANAGEMENT]
        if project_id:
            if project_id not in mgmt: raise HTTPException(403, 'Insufficient permission')
            mgmt = [project_id]
        if not mgmt: raise HTTPException(403, 'Insufficient permission')
        q = q.where(AuditLog.project_id.in_(mgmt))
    if entity_type: q = q.where(AuditLog.entity_type == entity_type)
    if entity_id: q = q.where(AuditLog.entity_id == entity_id)
    rows = list(db.scalars(q.order_by(AuditLog.id.desc()).limit(min(limit, 2000))))
    nm = {x.id: x.full_name for x in db.scalars(select(User).where(User.id.in_({r.user_id for r in rows} or {-1})))}
    return [{**{k: getattr(r, k) for k in AuditLog.__table__.columns.keys()}, 'user_name': nm.get(r.user_id)} for r in rows]
