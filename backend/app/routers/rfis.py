from datetime import datetime,date
from fastapi import APIRouter,Depends,HTTPException,Query
from sqlalchemy import select,or_
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Rfi,RfiSummary,ReviewerAssignment,Review,Decision,User,ReviewerRule,RfiStatusHistory,Project
from app.schemas import RfiCreate,AssignmentCreate,ReviewCreate,DecisionCreate,RevisionCreate,RfiUpdate,StateChange
from app.security import current_user,require_roles
from app.services.audit import log
from app.services.notify import notify,notify_roles
router=APIRouter(prefix='/rfis',tags=['RFIs'])

REVIEW_ROLES={'WORK_INSPECTOR','STRUCTURE_INSPECTOR','SURVEYOR','SENIOR_SURVEYOR','MATERIAL_INSPECTOR','LAB_TECHNICIAN','MATERIAL_ENGINEER'}
DECISION_ROLES={'ADMIN','RE','ARE','RE_ARE'}

def hist(db,r,u,reason=None):
    db.add(RfiStatusHistory(rfi_id=r.id,workflow_status=r.workflow_status,decision=r.current_decision,changed_by=u.id,reason=reason))

def can_edit_completed(u): return u.role in DECISION_ROLES
REVIEWABLE={'ACTIVATED','UNDER_REVIEW','AWAITING_DECISION'}

def get_active(db,rid):
    r=db.get(Rfi,rid)
    if not r:raise HTTPException(404,'RFI not found')
    if r.record_state!='ACTIVE':raise HTTPException(400,f'RFI is {r.record_state.lower()} and cannot be changed')
    return r

@router.get('')
def ls(project_id:int|None=None,workflow_status:str|None=None,decision:str|None=None,q:str|None=None,work_item:str|None=None,side:str|None=None,date_from:date|None=None,date_to:date|None=None,limit:int=Query(200,ge=1,le=1000),offset:int=Query(0,ge=0),db:Session=Depends(get_db),_=Depends(current_user)):
    s=select(Rfi).where(Rfi.record_state=='ACTIVE').order_by(Rfi.id.desc())
    if project_id:s=s.where(Rfi.project_id==project_id)
    if workflow_status:s=s.where(Rfi.workflow_status==workflow_status)
    if decision:s=s.where(Rfi.current_decision==decision)
    if work_item:s=s.where(Rfi.work_item==work_item)
    if side:s=s.where(Rfi.side==side)
    if date_from:s=s.where(Rfi.inspection_date>=date_from)
    if date_to:s=s.where(Rfi.inspection_date<=date_to)
    if q:
        like=f'%{q}%';s=s.where(or_(Rfi.rfi_number.like(like),Rfi.description.like(like),Rfi.work_item.like(like),Rfi.chainage_from.like(like),Rfi.chainage_to.like(like)))
    return list(db.scalars(s.offset(offset).limit(limit)))

@router.get('/my-inspections')
def mine(db:Session=Depends(get_db),u:User=Depends(current_user)):
    rows=db.execute(select(ReviewerAssignment,Rfi).join(Rfi,Rfi.id==ReviewerAssignment.rfi_id).where(ReviewerAssignment.user_id==u.id).order_by(ReviewerAssignment.id.desc())).all()
    return [{'assignment':a,'rfi':r} for a,r in rows]

@router.get('/{rid}/suggested-reviewers')
def suggested(rid:int,db:Session=Depends(get_db),_=Depends(current_user)):
    r=db.get(Rfi,rid)
    if not r:raise HTTPException(404,'RFI not found')
    return list(db.scalars(select(ReviewerRule).where(ReviewerRule.project_id==r.project_id,ReviewerRule.work_item==r.work_item)))

@router.get('/{rid}')
def one(rid:int,db:Session=Depends(get_db),_=Depends(current_user)):
    r=db.get(Rfi,rid)
    if not r:raise HTTPException(404,'RFI not found')
    return {'rfi':r,'assignments':list(db.scalars(select(ReviewerAssignment).where(ReviewerAssignment.rfi_id==rid))),'reviews':list(db.scalars(select(Review).where(Review.rfi_id==rid))),'decisions':list(db.scalars(select(Decision).where(Decision.rfi_id==rid).order_by(Decision.id.desc()))),'history':list(db.scalars(select(RfiStatusHistory).where(RfiStatusHistory.rfi_id==rid).order_by(RfiStatusHistory.id.desc())))}

@router.post('')
def create(d:RfiCreate,db:Session=Depends(get_db),u:User=Depends(current_user)):
    if not db.get(Project,d.project_id):raise HTTPException(400,'Project not found')
    if not d.rfi_number.strip() or not d.work_item.strip() or not d.description.strip():raise HTTPException(400,'RFI number, work item and description are required')
    if d.summary_id:
        s=db.get(RfiSummary,d.summary_id)
        if not s:raise HTTPException(404,'Summary not found')
        if s.project_id!=d.project_id:raise HTTPException(400,'RFI project must match the summary project')
        if s.workflow_status not in ('DRAFT','RETURNED'):raise HTTPException(400,'Summary is locked after submission')
    r=Rfi(**d.model_dump(),created_by=u.id,workflow_status='DRAFT' if d.summary_id else 'SUBMITTED');db.add(r)
    try:db.flush();hist(db,r,u,'Created');db.commit()
    except Exception:db.rollback();raise HTTPException(409,'Duplicate RFI/revision in project')
    db.refresh(r);log(db,u.id,'RFI',r.id,'CREATE');return r

@router.put('/{rid}')
def update(rid:int,d:RfiUpdate,db:Session=Depends(get_db),u:User=Depends(current_user)):
    r=db.get(Rfi,rid)
    if not r:raise HTTPException(404,'RFI not found')
    if r.record_state!='ACTIVE':raise HTTPException(400,'Archived/cancelled RFI cannot be edited')
    if d.version!=r.version:raise HTTPException(409,'This RFI was modified by another user. Refresh before saving.')
    if r.workflow_status=='COMPLETED' and not can_edit_completed(u):raise HTTPException(403,'Completed RFI is locked')
    if r.workflow_status=='COMPLETED' and not d.edit_reason:raise HTTPException(400,'Edit reason required for completed RFI')
    fields=d.model_dump(exclude={'version','edit_reason'},exclude_none=True)
    for k,v in fields.items():setattr(r,k,v)
    r.version+=1;db.commit();log(db,u.id,'RFI',r.id,'EDIT',d.edit_reason);return r

@router.post('/{rid}/activate')
def activate(rid:int,db:Session=Depends(get_db),u:User=Depends(require_roles('ADMIN','RE','ARE','RE_ARE'))):
    r=get_active(db,rid)
    if r.workflow_status not in ('DRAFT','SUBMITTED'):raise HTTPException(400,f'RFI is already {r.workflow_status.replace("_"," ").lower()}')
    if r.summary_id:
        s=db.get(RfiSummary,r.summary_id)
        if not s or s.workflow_status!='SUBMITTED':raise HTTPException(400,'Summary must be submitted')
    r.workflow_status='ACTIVATED';r.activated_by=u.id;r.activated_at=datetime.utcnow();r.version+=1;hist(db,r,u,'Accepted/activated by RE/ARE');db.commit();log(db,u.id,'RFI',r.id,'ACTIVATE');return r

@router.post('/{rid}/assign-reviewer')
def assign(rid:int,d:AssignmentCreate,db:Session=Depends(get_db),u:User=Depends(require_roles('ADMIN','RE','ARE','RE_ARE'))):
    r=get_active(db,rid)
    if r.workflow_status not in REVIEWABLE:raise HTTPException(400,'Activate the RFI before assigning reviewers')
    target=db.get(User,d.user_id)
    if not target or not target.is_active:raise HTTPException(400,'Reviewer user is inactive/missing')
    if d.reviewer_role not in REVIEW_ROLES:raise HTTPException(400,'Invalid reviewer role')
    if db.scalar(select(ReviewerAssignment).where(ReviewerAssignment.rfi_id==rid,ReviewerAssignment.user_id==d.user_id,ReviewerAssignment.reviewer_role==d.reviewer_role,ReviewerAssignment.status!='COMPLETED')):raise HTTPException(409,'This reviewer is already assigned with that role')
    a=ReviewerAssignment(rfi_id=rid,user_id=d.user_id,reviewer_role=d.reviewer_role,required=d.required,assigned_by=u.id);db.add(a);db.flush();r.workflow_status='UNDER_REVIEW' if d.required or r.workflow_status=='ACTIVATED' else r.workflow_status;r.version+=1;hist(db,r,u,f'Assigned {d.reviewer_role}');notify(db,d.user_id,'New RFI inspection assigned',f'You were assigned to RFI {r.rfi_number} Rev {r.revision_no}.','RFI',rid);db.commit();db.refresh(a);log(db,u.id,'RFI',rid,'ASSIGN_REVIEWER',d.reviewer_role);return a

@router.post('/{rid}/review')
def review(rid:int,d:ReviewCreate,db:Session=Depends(get_db),u:User=Depends(current_user)):
    a=db.get(ReviewerAssignment,d.assignment_id)
    if not a or a.rfi_id!=rid:raise HTTPException(404,'Assignment not found')
    if a.status=='COMPLETED':raise HTTPException(400,'Assignment already completed')
    if a.user_id!=u.id and u.role!='ADMIN':raise HTTPException(403,'Not your assignment')
    r=get_active(db,rid)
    if r.workflow_status not in REVIEWABLE:raise HTTPException(400,'RFI is not open for review')
    if not d.comment.strip():raise HTTPException(400,'Review comment is required')
    rv=Review(assignment_id=a.id,rfi_id=rid,reviewer_id=u.id,recommendation=d.recommendation,comment=d.comment);db.add(rv);a.status='COMPLETED';a.completed_at=datetime.utcnow();db.flush()
    pending=list(db.scalars(select(ReviewerAssignment).where(ReviewerAssignment.rfi_id==rid,ReviewerAssignment.required==True,ReviewerAssignment.status!='COMPLETED')))
    if not pending and r.workflow_status!='AWAITING_DECISION':
        r.workflow_status='AWAITING_DECISION';r.version+=1;hist(db,r,u,'Required reviews completed');notify_roles(db,DECISION_ROLES,'RFI awaiting decision',f'RFI {r.rfi_number} is ready for RE/ARE decision.','RFI',r.id)
    db.commit();log(db,u.id,'RFI',rid,'REVIEW',d.recommendation);return rv

@router.post('/{rid}/decision')
def decide(rid:int,d:DecisionCreate,db:Session=Depends(get_db),u:User=Depends(require_roles('ADMIN','RE','ARE','RE_ARE'))):
    r=get_active(db,rid)
    if r.workflow_status not in REVIEWABLE:raise HTTPException(400,'RFI must be activated before a final decision' if r.workflow_status in ('DRAFT','SUBMITTED') else 'A final decision has already been recorded')
    if d.decision not in ('APPROVED','REJECTED','ON_PROGRESS','INFORMATION_ONLY'):raise HTTPException(400,'Invalid final decision')
    pending=list(db.scalars(select(ReviewerAssignment).where(ReviewerAssignment.rfi_id==rid,ReviewerAssignment.required==True,ReviewerAssignment.status!='COMPLETED')))
    if pending and not d.override_used:raise HTTPException(400,'Required reviews pending')
    if d.override_used and not (d.override_reason or '').strip():raise HTTPException(400,'Override reason required')
    x=Decision(rfi_id=rid,revision_no=r.revision_no,decision=d.decision,comment=d.comment,override_used=d.override_used,override_reason=d.override_reason,decided_by=u.id);db.add(x);r.current_decision=d.decision;r.workflow_status='COMPLETED';r.version+=1;hist(db,r,u,d.comment or d.override_reason);notify(db,r.created_by,f'RFI {d.decision.replace("_"," ")}',f'RFI {r.rfi_number} Rev {r.revision_no} final decision: {d.decision}.','RFI',r.id);db.commit();log(db,u.id,'RFI',rid,'DECISION',d.decision);return x

@router.post('/{rid}/resubmit')
def resubmit(rid:int,d:RevisionCreate,db:Session=Depends(get_db),u:User=Depends(current_user)):
    o=db.get(Rfi,rid)
    if not o or o.current_decision!='REJECTED':raise HTTPException(400,'Only rejected RFI may be resubmitted')
    if not d.reason.strip():raise HTTPException(400,'Resubmission reason is required')
    if db.scalar(select(Rfi).where(Rfi.project_id==o.project_id,Rfi.rfi_number==o.rfi_number,Rfi.revision_no==o.revision_no+1)):raise HTTPException(409,f'Revision {o.revision_no+1} of this RFI already exists')
    n=Rfi(project_id=o.project_id,summary_id=o.summary_id,rfi_number=o.rfi_number,revision_no=o.revision_no+1,parent_rfi_id=o.id,contractor_request=o.contractor_request,work_item=o.work_item,description=o.description,structure_type=o.structure_type,test_name=o.test_name,boq_item=o.boq_item,road_type=o.road_type,direction=o.direction,side=o.side,fill_layer=o.fill_layer,chainage_from=o.chainage_from,chainage_to=o.chainage_to,location_text=o.location_text,material_source_type=o.material_source_type,material_source=o.material_source,requested_date=o.requested_date,workflow_status='SUBMITTED',remarks=d.reason,created_by=u.id);db.add(n);db.flush();hist(db,n,u,f'Resubmitted from RFI record {o.id}: {d.reason}');db.commit();db.refresh(n);log(db,u.id,'RFI',n.id,'RESUBMIT',f'from {o.id}');return n

@router.post('/{rid}/archive')
def archive(rid:int,d:StateChange,db:Session=Depends(get_db),u:User=Depends(require_roles('ADMIN','RE','ARE','RE_ARE'))):
    r=get_active(db,rid)
    if not d.reason.strip():raise HTTPException(400,'Reason is required')
    r.record_state='ARCHIVED';r.version+=1;hist(db,r,u,'Archived: '+d.reason);db.commit();log(db,u.id,'RFI',rid,'ARCHIVE',d.reason);return r

@router.post('/{rid}/cancel')
def cancel(rid:int,d:StateChange,db:Session=Depends(get_db),u:User=Depends(require_roles('ADMIN','RE','ARE','RE_ARE'))):
    r=get_active(db,rid)
    if not d.reason.strip():raise HTTPException(400,'Reason is required')
    r.record_state='CANCELLED';r.workflow_status='CANCELLED';r.version+=1;hist(db,r,u,'Cancelled: '+d.reason);db.commit();log(db,u.id,'RFI',rid,'CANCEL',d.reason);return r
