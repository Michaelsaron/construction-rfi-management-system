from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User,ProjectUser,Project
from app.schemas import UserCreate,AdminResetPasswordIn,UserProjectsIn
from app.security import current_user,require_roles,hash_password
from app.services.audit import log
router=APIRouter(prefix='/users',tags=['Users'])

ROLES={'ADMIN','RE','ARE','RE_ARE','CONTRACTOR','SITE_ENGINEER','WORK_INSPECTOR','STRUCTURE_INSPECTOR','SURVEYOR','SENIOR_SURVEYOR','MATERIAL_INSPECTOR','LAB_TECHNICIAN','MATERIAL_ENGINEER','PROJECT_MANAGER','VIEWER'}
MIN_PASSWORD=10

def check_password(p:str):
    if len(p or '')<MIN_PASSWORD: raise HTTPException(400,f'Password must be at least {MIN_PASSWORD} characters')

def project_ids(db,uid):
    return list(db.scalars(select(ProjectUser.project_id).where(ProjectUser.user_id==uid)))

def public(db,u:User):
    """Never expose password hashes or reset tokens."""
    return {'id':u.id,'full_name':u.full_name,'email':u.email,'role':u.role,'is_active':u.is_active,'must_change_password':u.must_change_password,'created_at':u.created_at,'last_login_at':u.last_login_at,'project_ids':project_ids(db,u.id)}

def set_projects(db,uid,ids):
    ids=list(dict.fromkeys(ids))
    for pid in ids:
        if not db.get(Project,pid): raise HTTPException(400,f'Project {pid} does not exist')
    for old in db.scalars(select(ProjectUser).where(ProjectUser.user_id==uid)): db.delete(old)
    db.flush()
    for pid in ids: db.add(ProjectUser(project_id=pid,user_id=uid))

@router.get('')
def ls(db:Session=Depends(get_db),_=Depends(current_user)):
    return [public(db,u) for u in db.scalars(select(User).order_by(User.full_name))]

@router.post('')
def create(d:UserCreate,db:Session=Depends(get_db),admin:User=Depends(require_roles('ADMIN'))):
    email=d.email.lower()
    if d.role not in ROLES: raise HTTPException(400,'Invalid role')
    if not d.full_name.strip(): raise HTTPException(400,'Full name is required')
    check_password(d.password)
    if db.scalar(select(User).where(User.email==email)): raise HTTPException(409,'A user with this email already exists')
    u=User(full_name=d.full_name.strip(),email=email,password_hash=hash_password(d.password),role=d.role,must_change_password=True);db.add(u);db.flush()
    set_projects(db,u.id,d.project_ids)
    db.commit();db.refresh(u);log(db,admin.id,'USER',u.id,'CREATE',d.role);return public(db,u)

@router.put('/{uid}/projects')
def update_projects(uid:int,d:UserProjectsIn,db:Session=Depends(get_db),admin:User=Depends(require_roles('ADMIN'))):
    u=db.get(User,uid)
    if not u: raise HTTPException(404,'User not found')
    set_projects(db,uid,d.project_ids);db.commit();log(db,admin.id,'USER',uid,'SET_PROJECTS',','.join(map(str,d.project_ids)));return public(db,u)

@router.post('/{uid}/reset-password')
def reset_password(uid:int,d:AdminResetPasswordIn,db:Session=Depends(get_db),admin:User=Depends(require_roles('ADMIN'))):
    u=db.get(User,uid)
    if not u: raise HTTPException(404,'User not found')
    check_password(d.new_password)
    u.password_hash=hash_password(d.new_password);u.must_change_password=True;u.reset_token=None;u.reset_expires_at=None;db.commit();log(db,admin.id,'USER',u.id,'RESET_PASSWORD');return {'ok':True}

@router.post('/{uid}/toggle-active')
def toggle(uid:int,db:Session=Depends(get_db),admin:User=Depends(require_roles('ADMIN'))):
    u=db.get(User,uid)
    if not u: raise HTTPException(404,'User not found')
    if u.id==admin.id and u.is_active: raise HTTPException(400,'You cannot disable your own account')
    u.is_active=not u.is_active;db.commit();log(db,admin.id,'USER',u.id,'ENABLE' if u.is_active else 'DISABLE');return public(db,u)
