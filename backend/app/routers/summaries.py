"""DOC_01 - Daily Request For Inspection Summary Sheet (batch of RFIs). SRS 5.2 step 1-2, FR-04..08."""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import RfiSummary, Rfi, User, Project, RfiStatusHistory, ReviewerAssignment
from app.schemas import SummaryCreate, SummarySubmit, ReturnBatch
from app.security import current_user
from app import authz
from app.project_settings import get_settings
from app.services.audit import log
from app.services.notify import notify, notify_project_roles
from app.services.workflow import compute_notice, rfi_dict, inspection_datetime, site_now

router = APIRouter(prefix='/rfi-summaries', tags=['DOC_01 Summaries'])
COLS = RfiSummary.__table__.columns.keys()


def sdict(db, s, extra=None):
    d = {k: getattr(s, k) for k in COLS}
    users = {u.id: u.full_name for u in db.scalars(select(User).where(User.id.in_({s.submitted_by, s.received_by} - {None})))}
    d['submitted_by_name'] = users.get(s.submitted_by); d['received_by_name'] = users.get(s.received_by)
    if extra: d.update(extra)
    return d


def validate_rfi_for_submission(r: Rfi) -> list[str]:
    errs = []
    if not (r.rfi_number or '').strip(): errs.append('RFI No.')
    if not (r.contractor_request or '').strip() and not (r.description or '').strip(): errs.append('Works description')
    if not (r.work_item or '').strip(): errs.append('Work item')
    if not r.inspection_date: errs.append('Inspection date')
    if not r.inspection_time: errs.append('Inspection time')
    if not (r.chainage_from or r.location_text or r.material_source): errs.append('Station / location')
    return errs


@router.get('')
def ls(project_id: int | None = None, workflow_status: str | None = None, db: Session = Depends(get_db), u: User = Depends(current_user)):
    vis = authz.visible_project_ids(db, u)
    q = select(RfiSummary).order_by(RfiSummary.id.desc())
    if project_id is not None:
        authz.require_project(db, u, project_id)
        q = q.where(RfiSummary.project_id == project_id)
    elif vis is not None:
        q = q.where(RfiSummary.project_id.in_(vis or [-1]))
    if workflow_status: q = q.where(RfiSummary.workflow_status == workflow_status)
    out = []
    for s in db.scalars(q.limit(500)):
        role = authz.project_role(db, u, s.project_id)
        st = get_settings(db.get(Project, s.project_id))
        if role in authz.INSPECTORS and not st.get('inspector_register_access'): continue
        if role in authz.CONTRACTOR and st.get('contractor_visibility') == 'OWN' and s.submitted_by != u.id: continue
        counts = dict(db.execute(select(Rfi.workflow_status, func.count()).where(Rfi.summary_id == s.id).group_by(Rfi.workflow_status)).all())
        short = db.scalar(select(func.count()).select_from(Rfi).where(Rfi.summary_id == s.id, Rfi.short_notice == True)) or 0
        out.append(sdict(db, s, {'rfi_count': sum(counts.values()), 'status_counts': counts, 'short_notice_count': short}))
    return out


@router.get('/{sid}')
def one(sid: int, db: Session = Depends(get_db), u: User = Depends(current_user)):
    s, role = authz.load_summary(db, u, sid)
    rows = list(db.scalars(select(Rfi).where(Rfi.summary_id == sid).order_by(Rfi.id)))
    editable = role in authz.CONTRACTOR and s.workflow_status in ('DRAFT', 'RETURNED')
    assigned = any(db.scalar(select(func.count()).select_from(ReviewerAssignment).where(ReviewerAssignment.rfi_id == r.id)) for r in rows)
    p = db.get(Project, s.project_id)
    return {'summary': sdict(db, s), 'rfis': [rfi_dict(r, {'missing': validate_rfi_for_submission(r)}) for r in rows], 'my_role': role,
            'project': {'id': p.id, 'code': p.code, 'name': p.name},
            'notice_policy': get_settings(p)['notice_policy'], 'notice_hours': get_settings(p)['notice_hours'],
            'permissions': {'edit': editable, 'submit': editable and bool(rows),
                            'return': role in authz.MANAGEMENT and s.workflow_status == 'SUBMITTED' and not assigned,
                            'receive': (role in authz.MANAGEMENT or role == 'SECRETARY') and s.workflow_status == 'SUBMITTED' and not s.received_at}}


@router.post('')
def create(d: SummaryCreate, db: Session = Depends(get_db), u: User = Depends(current_user)):
    authz.require_project(db, u, d.project_id, authz.CONTRACTOR, write=True)
    if d.client_request_id:
        prev = db.scalar(select(RfiSummary).where(RfiSummary.client_request_id == d.client_request_id))
        if prev:
            if prev.submitted_by != u.id: raise HTTPException(409, 'Duplicate request id')
            return sdict(db, prev)
    ref = (d.summary_reference or '').strip()
    if not ref: raise HTTPException(400, 'Summary reference is required')
    if db.scalar(select(RfiSummary.id).where(RfiSummary.project_id == d.project_id, RfiSummary.summary_reference == ref)):
        raise HTTPException(409, f'A DOC_01 batch with reference {ref} already exists in this project')
    data = d.model_dump(); data['summary_reference'] = ref
    data['contractor_rep_name'] = (d.contractor_rep_name or '').strip() or u.full_name
    s = RfiSummary(**data, submitted_by=u.id)
    db.add(s); db.flush()
    log(db, u.id, 'RFI_SUMMARY', s.id, 'CREATE', ref, project_id=s.project_id)
    db.commit(); db.refresh(s)
    return sdict(db, s)


@router.post('/{sid}/submit')
def submit(sid: int, body: SummarySubmit | None = None, db: Session = Depends(get_db), u: User = Depends(current_user)):
    s = db.scalar(select(RfiSummary).where(RfiSummary.id == sid).with_for_update())
    if not s: raise HTTPException(404, 'Summary not found')
    authz.require_project(db, u, s.project_id, authz.CONTRACTOR, write=True)
    if s.workflow_status == 'SUBMITTED':
        return sdict(db, s, {'already_submitted': True})  # idempotent retry
    if s.workflow_status not in ('DRAFT', 'RETURNED'): raise HTTPException(409, 'This batch is locked')
    children = list(db.scalars(select(Rfi).where(Rfi.summary_id == sid, Rfi.record_state == 'ACTIVE').with_for_update()))
    if not children: raise HTTPException(400, 'Add at least one individual RFI before submitting')
    problems = {r.rfi_number or f'#{r.id}': m for r in children if (m := validate_rfi_for_submission(r))}
    if problems:
        raise HTTPException(422, 'Complete the mandatory fields before submitting: ' + '; '.join(f'{k}: {", ".join(v)}' for k, v in problems.items()))
    nums = [r.rfi_number.strip().lower() for r in children]
    dups = sorted({n for n in nums if nums.count(n) > 1})
    if dups: raise HTTPException(409, 'Duplicate RFI numbers in this batch: ' + ', '.join(dups))
    p = db.get(Project, s.project_id); st = get_settings(p)
    now_local = site_now()
    for r in children: compute_notice(r, now_local, st['notice_hours'])
    short = [r for r in children if r.short_notice]
    reason = ((body.short_notice_reason if body else None) or '').strip()
    if short and st['notice_policy'] == 'REQUIRE_OVERRIDE' and not reason:
        raise HTTPException(422, f'{len(short)} RFI(s) are proposed less than {st["notice_hours"]} hours before inspection. Give a short-notice reason to submit.')
    for r in children:
        if r.short_notice and reason: r.short_notice_reason = reason
        if not r.requested_date: r.requested_date = now_local.date()
        if not r.requested_time: r.requested_time = now_local.strftime('%H:%M')
        if r.workflow_status == 'DRAFT':
            r.workflow_status = 'SUBMITTED'; r.version += 1
            db.add(RfiStatusHistory(rfi_id=r.id, workflow_status='SUBMITTED', changed_by=u.id, reason=f'Submitted with DOC_01 {s.summary_reference}' + (' (short notice)' if r.short_notice else '')))
    s.workflow_status = 'SUBMITTED'; s.submitted_at = datetime.utcnow(); s.returned_reason = None
    first = min((inspection_datetime(r.inspection_date, r.inspection_time) for r in children if r.inspection_date), default=None)
    msg = (f'DOC_01 {s.summary_reference} from {u.full_name}: {len(children)} RFI(s), first inspection {first:%d/%m/%Y %H:%M}.' if first else f'DOC_01 {s.summary_reference}: {len(children)} RFI(s).')
    if short: msg += f' {len(short)} RFI(s) are SHORT NOTICE (< {st["notice_hours"]} h).'
    notify_project_roles(db, s.project_id, authz.MANAGEMENT, 'New DOC_01 submitted', msg, 'RFI_SUMMARY', s.id)
    log(db, u.id, 'RFI_SUMMARY', s.id, 'SUBMIT', f'{len(children)} RFIs, {len(short)} short notice', project_id=s.project_id)
    db.commit()
    return sdict(db, s, {'short_notice_count': len(short)})


@router.post('/{sid}/receive')
def receive(sid: int, db: Session = Depends(get_db), u: User = Depends(current_user)):
    s = db.scalar(select(RfiSummary).where(RfiSummary.id == sid).with_for_update())
    if not s: raise HTTPException(404, 'Summary not found')
    authz.require_project(db, u, s.project_id, authz.MANAGEMENT | {'SECRETARY'}, write=True)
    if s.workflow_status != 'SUBMITTED': raise HTTPException(409, 'Only a submitted batch can be acknowledged')
    if s.received_at: return sdict(db, s)
    s.received_by = u.id; s.received_at = datetime.utcnow()
    log(db, u.id, 'RFI_SUMMARY', s.id, 'RECEIVE', None, project_id=s.project_id)
    db.commit()
    return sdict(db, s)


@router.post('/{sid}/return')
def ret(sid: int, d: ReturnBatch, db: Session = Depends(get_db), u: User = Depends(current_user)):
    s = db.scalar(select(RfiSummary).where(RfiSummary.id == sid).with_for_update())
    if not s: raise HTTPException(404, 'Summary not found')
    authz.require_project(db, u, s.project_id, authz.MANAGEMENT, write=True)
    if not d.reason.strip(): raise HTTPException(400, 'Return reason required')
    if s.workflow_status != 'SUBMITTED': raise HTTPException(409, 'Only a submitted batch can be returned')
    children = list(db.scalars(select(Rfi).where(Rfi.summary_id == sid, Rfi.record_state == 'ACTIVE')))
    if any(r.workflow_status not in ('DRAFT', 'SUBMITTED') for r in children):
        raise HTTPException(409, 'Cannot return: inspectors have already been assigned to one or more RFIs in this batch')
    for r in children:
        if r.workflow_status == 'SUBMITTED':
            r.workflow_status = 'DRAFT'; r.version += 1
            db.add(RfiStatusHistory(rfi_id=r.id, workflow_status='DRAFT', changed_by=u.id, reason=f'Batch returned: {d.reason}'))
    s.workflow_status = 'RETURNED'; s.returned_reason = d.reason.strip()
    notify(db, s.submitted_by, 'DOC_01 returned', f'DOC_01 {s.summary_reference} was returned for correction: {d.reason}', 'RFI_SUMMARY', s.id, s.project_id)
    log(db, u.id, 'RFI_SUMMARY', s.id, 'RETURN', d.reason, project_id=s.project_id)
    db.commit()
    return sdict(db, s)
