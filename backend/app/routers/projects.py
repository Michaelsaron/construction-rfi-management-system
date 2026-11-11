from fastapi import APIRouter,Depends
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Project,User
from app.schemas import ProjectCreate
from app.security import current_user,require_roles
from app.services.audit import log
router=APIRouter(prefix='/projects',tags=['Projects'])
@router.get('')
def ls(db:Session=Depends(get_db),_=Depends(current_user)): return list(db.scalars(select(Project).where(Project.is_active==True).order_by(Project.name)))
@router.post('')
def create(d:ProjectCreate,db:Session=Depends(get_db),u:User=Depends(require_roles('ADMIN'))):
    p=Project(**d.model_dump()); db.add(p); db.commit(); db.refresh(p); log(db,u.id,'PROJECT',p.id,'CREATE'); return p
