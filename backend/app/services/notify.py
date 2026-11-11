from datetime import datetime, timedelta
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models import Notification, User, Rfi, ReviewerAssignment
from app.config import settings
from app.services.emailer import send_email


def notify(db:Session,user_id:int,title:str,message:str,entity_type:str|None=None,entity_id:int|None=None,email:bool=True):
    n=Notification(user_id=user_id,title=title,message=message,entity_type=entity_type,entity_id=entity_id)
    db.add(n); db.flush()
    if email:
        u=db.get(User,user_id)
        if u and u.email:
            try: send_email(u.email,title,message)
            except Exception as e: print('[EMAIL-WARN]',e)
    return n


def notify_roles(db:Session,roles:set[str],title:str,message:str,entity_type:str|None=None,entity_id:int|None=None):
    users=list(db.scalars(select(User).where(User.is_active==True,User.role.in_(list(roles)))))
    for u in users: notify(db,u.id,title,message,entity_type,entity_id)
    return users


def create_overdue_notifications(db:Session):
    cutoff=datetime.utcnow()-timedelta(hours=settings.overdue_hours)
    assignments=list(db.scalars(select(ReviewerAssignment).where(ReviewerAssignment.status!='COMPLETED',ReviewerAssignment.assigned_at<=cutoff)))
    made=0
    for a in assignments:
        r=db.get(Rfi,a.rfi_id)
        if not r or r.workflow_status=='COMPLETED': continue
        marker=f'OVERDUE:{a.id}'
        exists=db.scalar(select(Notification).where(Notification.user_id==a.user_id,Notification.message.like(f'%{marker}%')))
        if exists: continue
        notify(db,a.user_id,'Overdue RFI inspection',f'RFI {r.rfi_number} has been waiting more than {settings.overdue_hours} hours. {marker}','RFI',r.id)
        made+=1
    db.commit(); return made
