from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import DailyProgress, DailyProgressRfi, User, Rfi, Project, ProjectUser
from app.schemas import DailyProgressCreate, DailyProgressComment
from app.security import current_user, require_roles
from app.services.audit import log
from app.services.notify import notify, notify_roles

router = APIRouter(prefix='/daily-progress', tags=['Daily Progress'])
REVIEW_ROLES = {'ADMIN','WORK_INSPECTOR','STRUCTURE_INSPECTOR','SURVEYOR','SENIOR_SURVEYOR','MATERIAL_INSPECTOR','LAB_TECHNICIAN','MATERIAL_ENGINEER','RE','ARE','RE_ARE'}
DECISION_ROLES = {'ADMIN','RE','ARE','RE_ARE'}
CREATE_ROLES = {'ADMIN','CONTRACTOR','SITE_ENGINEER','RE','ARE','RE_ARE'}

def check_project(db, user, project_id):
    if not db.get(Project,project_id): raise HTTPException(404,'Project not found')
    if user.role != 'ADMIN' and not db.scalar(select(ProjectUser.id).where(ProjectUser.project_id==project_id, ProjectUser.user_id==user.id)):
        raise HTTPException(403,'You are not assigned to this project')

def get_record(db, user, pid):
    p=db.get(DailyProgress,pid)
    if not p: raise HTTPException(404,'Daily Progress not found')
    check_project(db,user,p.project_id)
    return p

def check_links(db,project_id,rfi_ids):
    for rid in set(rfi_ids):
        r=db.get(Rfi,rid)
        if not r or r.project_id != project_id:
            raise HTTPException(400,f'RFI {rid} does not belong to the selected project')

@router.get('')
def ls(project_id:int|None=None,limit:int=100,offset:int=0,db:Session=Depends(get_db),u:User=Depends(current_user)):
    limit=max(1,min(limit,500));offset=max(0,offset)
    q=select(DailyProgress).order_by(DailyProgress.progress_date.desc(),DailyProgress.id.desc())
    if project_id is not None:
        check_project(db,u,project_id)
        q=q.where(DailyProgress.project_id==project_id)
    elif u.role!='ADMIN':
        q=q.where(DailyProgress.project_id.in_(select(ProjectUser.project_id).where(ProjectUser.user_id==u.id)))
    rows=list(db.scalars(q.offset(offset).limit(limit)))
    ids=[p.id for p in rows]
    links=list(db.scalars(select(DailyProgressRfi).where(DailyProgressRfi.daily_progress_id.in_(ids)))) if ids else []
    linked={pid:[] for pid in ids}
    for x in links:linked[x.daily_progress_id].append(x.rfi_id)
    return [{'record':p,'rfi_ids':linked[p.id]} for p in rows]

@router.get('/{pid}')
def detail(pid:int,db:Session=Depends(get_db),u:User=Depends(current_user)):
    p=get_record(db,u,pid)
    return {'record':p,'rfi_ids':list(db.scalars(select(DailyProgressRfi.rfi_id).where(DailyProgressRfi.daily_progress_id==pid)))}

@router.post('')
def create(d:DailyProgressCreate,db:Session=Depends(get_db),u:User=Depends(require_roles(*CREATE_ROLES))):
    check_project(db,u,d.project_id);check_links(db,d.project_id,d.rfi_ids)
    p=DailyProgress(**d.model_dump(exclude={'rfi_ids'}),created_by=u.id)
    db.add(p);db.flush()
    for rid in set(d.rfi_ids):db.add(DailyProgressRfi(daily_progress_id=p.id,rfi_id=rid))
    db.commit();db.refresh(p);log(db,u.id,'DAILY_PROGRESS',p.id,'CREATE');return p

@router.put('/{pid}')
def update(pid:int,d:DailyProgressCreate,db:Session=Depends(get_db),u:User=Depends(current_user)):
    p=get_record(db,u,pid)
    if p.status!='DRAFT':raise HTTPException(409,'Only draft records can be edited')
    if u.role!='ADMIN' and p.created_by!=u.id:raise HTTPException(403,'Only the creator or Admin can edit this draft')
    check_project(db,u,d.project_id);check_links(db,d.project_id,d.rfi_ids)
    for k,v in d.model_dump(exclude={'rfi_ids'}).items():setattr(p,k,v)
    for old in db.scalars(select(DailyProgressRfi).where(DailyProgressRfi.daily_progress_id==pid)):db.delete(old)
    db.flush()
    for rid in set(d.rfi_ids):db.add(DailyProgressRfi(daily_progress_id=pid,rfi_id=rid))
    db.commit();db.refresh(p);log(db,u.id,'DAILY_PROGRESS',pid,'UPDATE');return p

@router.post('/{pid}/submit')
def submit(pid:int,db:Session=Depends(get_db),u:User=Depends(current_user)):
    p=get_record(db,u,pid)
    if u.role!='ADMIN' and p.created_by!=u.id:raise HTTPException(403,'Only the creator or Admin can submit')
    if p.status!='DRAFT':raise HTTPException(409,'Only draft records can be submitted')
    p.status='SUBMITTED'
    notify_roles(db,REVIEW_ROLES,'Daily Progress submitted',f'Daily Progress #{p.id} for {p.progress_date} is ready for inspection.','DAILY_PROGRESS',p.id)
    db.commit();log(db,u.id,'DAILY_PROGRESS',p.id,'SUBMIT');return p

@router.post('/{pid}/review')
def review(pid:int,body:DailyProgressComment,db:Session=Depends(get_db),u:User=Depends(require_roles(*REVIEW_ROLES))):
    p=get_record(db,u,pid)
    if p.status!='SUBMITTED':raise HTTPException(409,'Daily Progress must be submitted first')
    if not body.comment.strip():raise HTTPException(422,'Inspector review comment is required')
    p.status='REVIEWED';p.review_comment=body.comment.strip();p.reviewed_by=u.id;p.reviewed_at=datetime.utcnow()
    notify_roles(db,DECISION_ROLES,'Daily Progress awaiting confirmation',f'Daily Progress #{p.id} is ready for RE/ARE confirmation.','DAILY_PROGRESS',p.id)
    db.commit();log(db,u.id,'DAILY_PROGRESS',p.id,'REVIEW');return p

@router.post('/{pid}/confirm')
def confirm(pid:int,body:DailyProgressComment,db:Session=Depends(get_db),u:User=Depends(require_roles(*DECISION_ROLES))):
    p=get_record(db,u,pid)
    if p.status!='REVIEWED':raise HTTPException(409,'Daily Progress must be reviewed first')
    if not body.comment.strip():raise HTTPException(422,'RE/ARE confirmation comment is required')
    p.status='CONFIRMED';p.confirmation_comment=body.comment.strip();p.confirmed_by=u.id;p.confirmed_at=datetime.utcnow()
    notify(db,p.created_by,'Daily Progress confirmed',f'Daily Progress #{p.id} was confirmed by RE/ARE.','DAILY_PROGRESS',p.id)
    db.commit();log(db,u.id,'DAILY_PROGRESS',p.id,'CONFIRM');return p
