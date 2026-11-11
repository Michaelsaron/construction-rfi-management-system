from fastapi import APIRouter,Depends
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import AuditLog
from app.security import require_roles
router=APIRouter(prefix='/audit',tags=['Audit'])
@router.get('')
def ls(limit:int=500,db:Session=Depends(get_db),_=Depends(require_roles('ADMIN','RE','ARE','RE_ARE'))):return list(db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(min(limit,2000))))
