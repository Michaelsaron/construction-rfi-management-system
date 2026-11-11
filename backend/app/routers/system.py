from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import select,func
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User,Rfi,ReviewerRule,Notification,Project,ProjectUser
from app.schemas import ReviewerRuleCreate,ChangePasswordIn
from app.security import current_user,require_roles,verify_password,hash_password
from app.services.audit import log
from app.services.notify import create_overdue_notifications
router=APIRouter(tags=['System'])

@router.get('/me')
def me(u:User=Depends(current_user)):
    return {'id':u.id,'name':u.full_name,'email':u.email,'role':u.role,'must_change_password':u.must_change_password}

@router.post('/me/password')
def change_password(d:ChangePasswordIn,db:Session=Depends(get_db),u:User=Depends(current_user)):
    if not verify_password(d.current_password,u.password_hash): raise HTTPException(400,'Current password is incorrect')
    if len(d.new_password)<10: raise HTTPException(400,'Password must be at least 10 characters')
    if d.new_password==d.current_password: raise HTTPException(400,'New password must be different from the current password')
    u.password_hash=hash_password(d.new_password);u.must_change_password=False;db.commit();log(db,u.id,'USER',u.id,'CHANGE_PASSWORD');return {'ok':True}

@router.get('/dashboard')
def dashboard(project_id:int|None=None,db:Session=Depends(get_db),u:User=Depends(current_user)):
    base=[Rfi.record_state=='ACTIVE']
    if project_id:base.append(Rfi.project_id==project_id)
    by_dec=dict(db.execute(select(Rfi.current_decision,func.count()).where(*base).group_by(Rfi.current_decision)).all())
    by_wf=dict(db.execute(select(Rfi.workflow_status,func.count()).where(*base).group_by(Rfi.workflow_status)).all())
    recent=list(db.scalars(select(Rfi).where(*base).order_by(Rfi.id.desc()).limit(8)))
    return {'total':sum(by_wf.values()),'approved':by_dec.get('APPROVED',0),'rejected':by_dec.get('REJECTED',0),'on_progress':by_dec.get('ON_PROGRESS',0),'information_only':by_dec.get('INFORMATION_ONLY',0),'under_review':by_wf.get('UNDER_REVIEW',0),'awaiting_decision':by_wf.get('AWAITING_DECISION',0),'activated':by_wf.get('ACTIVATED',0),'submitted':by_wf.get('SUBMITTED',0),'recent':[{'id':r.id,'rfi_number':r.rfi_number,'revision_no':r.revision_no,'work_item':r.work_item,'workflow_status':r.workflow_status,'decision':r.current_decision} for r in recent]}

@router.get('/reviewer-rules')
def rules(project_id:int|None=None,db:Session=Depends(get_db),u:User=Depends(current_user)):
    s=select(ReviewerRule)
    if project_id:s=s.where(ReviewerRule.project_id==project_id)
    return list(db.scalars(s.order_by(ReviewerRule.work_item)))

@router.post('/reviewer-rules')
def add_rule(d:ReviewerRuleCreate,db:Session=Depends(get_db),u:User=Depends(require_roles('ADMIN','RE','ARE','RE_ARE'))):
    from app.routers.rfis import REVIEW_ROLES
    if not db.get(Project,d.project_id): raise HTTPException(400,'Project not found')
    if d.reviewer_role not in REVIEW_ROLES: raise HTTPException(400,'Invalid reviewer role')
    if not d.work_item.strip(): raise HTTPException(400,'Work item is required')
    if db.scalar(select(ReviewerRule).where(ReviewerRule.project_id==d.project_id,ReviewerRule.work_item==d.work_item,ReviewerRule.reviewer_role==d.reviewer_role)): raise HTTPException(409,'This rule already exists')
    r=ReviewerRule(**d.model_dump());db.add(r);db.commit();db.refresh(r);log(db,u.id,'REVIEWER_RULE',r.id,'CREATE');return r

@router.delete('/reviewer-rules/{rid}')
def delete_rule(rid:int,db:Session=Depends(get_db),u:User=Depends(require_roles('ADMIN','RE','ARE','RE_ARE'))):
    r=db.get(ReviewerRule,rid)
    if not r: raise HTTPException(404,'Rule not found')
    db.delete(r);db.commit();log(db,u.id,'REVIEWER_RULE',rid,'DELETE');return {'ok':True}

@router.post('/notifications/read-all')
def read_all(db:Session=Depends(get_db),u:User=Depends(current_user)):
    for n in db.scalars(select(Notification).where(Notification.user_id==u.id,Notification.is_read==False)): n.is_read=True
    db.commit();return {'ok':True}

@router.get('/notifications/unread-count')
def unread_count(db:Session=Depends(get_db),u:User=Depends(current_user)):
    return {'count':db.scalar(select(func.count()).select_from(Notification).where(Notification.user_id==u.id,Notification.is_read==False)) or 0}

@router.get('/notifications')
def notifications(db:Session=Depends(get_db),u:User=Depends(current_user)):
    return list(db.scalars(select(Notification).where(Notification.user_id==u.id).order_by(Notification.id.desc()).limit(100)))

@router.post('/notifications/{nid}/read')
def read_notification(nid:int,db:Session=Depends(get_db),u:User=Depends(current_user)):
    n=db.get(Notification,nid)
    if not n or n.user_id!=u.id: raise HTTPException(404,'Not found')
    n.is_read=True;db.commit();return {'ok':True}

@router.post('/notifications/check-overdue')
def overdue(db:Session=Depends(get_db),u:User=Depends(require_roles('ADMIN','RE','ARE','RE_ARE'))):
    return {'created':create_overdue_notifications(db)}
