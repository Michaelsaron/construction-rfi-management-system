from datetime import datetime
from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import RfiSummary,Rfi,User,Project,RfiStatusHistory
from app.schemas import SummaryCreate
from app.security import current_user,require_roles
from app.services.audit import log
from app.services.notify import notify,notify_roles
router=APIRouter(prefix='/rfi-summaries',tags=['RFI Summaries'])
DECISION_ROLES={'ADMIN','RE','ARE','RE_ARE'}

@router.get('')
def ls(db:Session=Depends(get_db),_=Depends(current_user)): return list(db.scalars(select(RfiSummary).order_by(RfiSummary.id.desc())))
@router.get('/{sid}')
def one(sid:int,db:Session=Depends(get_db),_=Depends(current_user)):
    s=db.get(RfiSummary,sid)
    if not s: raise HTTPException(404,'Summary not found')
    return {'summary':s,'rfis':list(db.scalars(select(Rfi).where(Rfi.summary_id==sid).order_by(Rfi.id)))}
@router.post('')
def create(d:SummaryCreate,db:Session=Depends(get_db),u:User=Depends(current_user)):
    if not db.get(Project,d.project_id):raise HTTPException(400,'Project not found')
    if not d.summary_reference.strip():raise HTTPException(400,'Summary reference is required')
    s=RfiSummary(**d.model_dump(),submitted_by=u.id);db.add(s)
    try:db.commit()
    except Exception:db.rollback();raise HTTPException(409,'Summary reference already exists')
    db.refresh(s);log(db,u.id,'RFI_SUMMARY',s.id,'CREATE');return s
@router.post('/{sid}/submit')
def submit(sid:int,db:Session=Depends(get_db),u:User=Depends(current_user)):
    s=db.get(RfiSummary,sid)
    if not s:raise HTTPException(404,'Summary not found')
    if s.workflow_status not in ('DRAFT','RETURNED'):raise HTTPException(400,'Summary locked')
    children=list(db.scalars(select(Rfi).where(Rfi.summary_id==sid,Rfi.record_state=='ACTIVE')));count=len(children)
    if count==0: raise HTTPException(400,'Add at least one individual RFI before submitting')
    for r in children:
        if r.workflow_status=='DRAFT':
            r.workflow_status='SUBMITTED';r.version+=1;db.add(RfiStatusHistory(rfi_id=r.id,workflow_status='SUBMITTED',decision=r.current_decision,changed_by=u.id,reason=f'Submitted with summary {s.summary_reference}'))
    s.workflow_status='SUBMITTED';s.submitted_at=datetime.utcnow();s.returned_reason=None
    notify_roles(db,DECISION_ROLES,'RFI Summary submitted',f'Summary {s.summary_reference} containing {count} RFI(s) is ready for review.','RFI_SUMMARY',s.id)
    db.commit();log(db,u.id,'RFI_SUMMARY',s.id,'SUBMIT');return s
@router.post('/{sid}/return')
def ret(sid:int,reason:str,db:Session=Depends(get_db),u:User=Depends(require_roles('ADMIN','RE','ARE','RE_ARE'))):
    s=db.get(RfiSummary,sid)
    if not s:raise HTTPException(404,'Summary not found')
    if not reason.strip():raise HTTPException(400,'Return reason required')
    if s.workflow_status!='SUBMITTED':raise HTTPException(400,'Only a submitted summary can be returned')
    children=list(db.scalars(select(Rfi).where(Rfi.summary_id==sid,Rfi.record_state=='ACTIVE')))
    if any(r.workflow_status not in ('DRAFT','SUBMITTED') for r in children):raise HTTPException(400,'Cannot return: one or more RFIs in this summary have already been activated')
    for r in children:
        if r.workflow_status=='SUBMITTED':
            r.workflow_status='DRAFT';r.version+=1;db.add(RfiStatusHistory(rfi_id=r.id,workflow_status='DRAFT',decision=r.current_decision,changed_by=u.id,reason=f'Summary returned: {reason}'))
    s.workflow_status='RETURNED';s.returned_reason=reason;notify(db,s.submitted_by,'RFI Summary returned',f'Summary {s.summary_reference} was returned: {reason}','RFI_SUMMARY',s.id);db.commit();log(db,u.id,'RFI_SUMMARY',s.id,'RETURN',reason);return s
