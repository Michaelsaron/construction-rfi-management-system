"""Individual RFI (DOC_02 row / DOC_03 sheet) endpoints - SRS sections 5, 6, 7."""
import json
from datetime import datetime, date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import (Rfi, RfiSummary, ReviewerAssignment, Review, Decision, User, ReviewerRule, RfiStatusHistory, Project,
                        RfiAmendment, IssuedDocument, ProjectUser, Attachment, ManagementRemark)
from app.schemas import RfiCreate, RfiUpdate, AssignmentPlan, ReviewCreate, DecisionCreate, RevisionCreate, StateChange, AmendmentCreate, AmendmentResolve, RfiFields
from app.security import current_user
from app import authz
from app.project_settings import get_settings, disposition, WORK_CATEGORY_CODES
from app.services.audit import log
from app.services.notify import notify, notify_project_roles
from app.services.workflow import (lock_rfi, transition, require_active_record, active_assignments, rfi_dict, compute_notice,
                                   OPEN_FOR_ASSIGNMENT, STATUS_LABELS, site_now)
from app.services.register import RegisterFilter, register_query, hidden_policy, HIDDEN_FIELDS
from app.services import evidence as ev

router = APIRouter(prefix='/rfis', tags=['RFIs'])

AMENDABLE = {'contractor_request', 'work_item', 'description', 'structure_type', 'test_name', 'boq_item', 'road_type', 'direction', 'side', 'fill_layer',
             'chainage_from', 'chainage_to', 'location_text', 'material_source_type', 'material_source', 'material_source_offset',
             'material_source_cut_section', 'material_source_designation', 'material_destination_designation', 'requested_date', 'requested_time',
             'inspection_date', 'inspection_time', 'inspection_order', 'enclosure_sheets', 'work_categories', 'remarks'}
NOT_NULL_TEXT = {'work_item', 'description'}


def names(db, ids):
    ids = {i for i in ids if i}
    if not ids: return {}
    return {u.id: u.full_name for u in db.scalars(select(User).where(User.id.in_(ids)))}


def clean_fields(data: dict) -> dict:
    out = {}
    for k, v in data.items():
        if isinstance(v, str):
            v = v.strip()
            if v == '' and k not in NOT_NULL_TEXT: v = None
        if k == 'work_categories':
            v = v or []
            bad = [c for c in v if c not in WORK_CATEGORY_CODES]
            if bad: raise HTTPException(400, f'Unknown DOC_03 work category: {", ".join(bad)}')
            v = json.dumps(sorted(set(v)))
        if k in NOT_NULL_TEXT and v is None: v = ''
        out[k] = v
    return out


def duplicate_check(db, project_id, number, exclude_id=None, revision_no=0):
    q = select(Rfi).where(Rfi.project_id == project_id, func.lower(func.trim(Rfi.rfi_number)) == number.strip().lower(), Rfi.revision_no == revision_no)
    if exclude_id: q = q.where(Rfi.id != exclude_id)
    ex = db.scalar(q)
    if ex:
        raise HTTPException(409, f'RFI No. {number.strip()} already exists in this project (record #{ex.id}, {STATUS_LABELS.get(ex.workflow_status, ex.workflow_status)}). Duplicate RFI numbers are not allowed.')


def editable_draft(db, u, r: Rfi):
    require_active_record(r)
    authz.require_project(db, u, r.project_id, authz.CONTRACTOR, write=True)
    s = db.get(RfiSummary, r.summary_id) if r.summary_id else None
    if r.workflow_status != 'DRAFT' or not s or s.workflow_status not in ('DRAFT', 'RETURNED'):
        raise HTTPException(409, 'This RFI has been submitted and is locked. Request a controlled amendment instead.')
    return s


def filter_params(project_id: int | None = None, q: str | None = None, rfi_number: str | None = None, workflow_status: str | None = None,
                  decision: str | None = None, disposition: str | None = None, legacy_status: str | None = None, work_item: str | None = None,
                  side: str | None = None, road_type: str | None = None, date_from: date | None = None, date_to: date | None = None,
                  inspector_id: int | None = None, submitted_by: int | None = None, summary_id: int | None = None, provenance: str | None = None,
                  short_notice: bool | None = None, latest_only: bool = False, include_inactive: bool = False, sort: str = 'id', dir: str = 'desc',
                  rfi_no: str | None = None) -> RegisterFilter:
    return RegisterFilter(project_id, q, rfi_number, workflow_status, decision, disposition, legacy_status, work_item, side, road_type, date_from,
                          date_to, inspector_id, submitted_by, summary_id, provenance, short_notice, latest_only, include_inactive, sort, dir, rfi_no)


def inspectors_by_rfi(db, ids):
    if not ids: return {}
    rows = list(db.scalars(select(ReviewerAssignment).where(ReviewerAssignment.rfi_id.in_(ids), ReviewerAssignment.status != 'REPLACED')
                           .order_by(ReviewerAssignment.rfi_id, ReviewerAssignment.sequence_no, ReviewerAssignment.id)))
    nm = names(db, [a.user_id for a in rows])
    out = {}
    for a in rows:
        out.setdefault(a.rfi_id, []).append({'sequence_no': a.sequence_no, 'name': nm.get(a.user_id), 'role': a.reviewer_role, 'status': a.status})
    return out


@router.get('')
def ls(f: RegisterFilter = Depends(filter_params), limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0),
       db: Session = Depends(get_db), u: User = Depends(current_user)):
    s, _ = register_query(db, u, f)
    total = db.scalar(select(func.count()).select_from(s.order_by(None).subquery()))
    rows = list(db.scalars(s.offset(offset).limit(limit)))
    insp = inspectors_by_rfi(db, [r.id for r in rows])
    refs = {x.id: x.summary_reference for x in db.scalars(select(RfiSummary).where(RfiSummary.id.in_({r.summary_id for r in rows if r.summary_id})))} if rows else {}
    allowed = hidden_policy(db, u)
    items = []
    for r in rows:
        d = rfi_dict(r, {'inspectors': insp.get(r.id, []), 'summary_reference': refs.get(r.summary_id)})
        if not allowed(r):
            for k in HIDDEN_FIELDS: d[k] = None
            d['hidden_fields_restricted'] = True
        items.append(d)
    hidden_ok = None
    if f.project_id:
        role = authz.project_role(db, u, f.project_id)
        hidden_ok = bool(role) and authz.category(role) in (get_settings(db.get(Project, f.project_id)).get('hidden_field_categories') or [])
    return {'total': total, 'limit': limit, 'offset': offset, 'filters': f.active(), 'hidden_fields_allowed': hidden_ok, 'items': items}


@router.get('/my-inspections')
def mine(db: Session = Depends(get_db), u: User = Depends(current_user)):
    rows = db.execute(select(ReviewerAssignment, Rfi).join(Rfi, Rfi.id == ReviewerAssignment.rfi_id)
                      .where(ReviewerAssignment.user_id == u.id, ReviewerAssignment.status != 'REPLACED').order_by(ReviewerAssignment.id.desc())).all()
    out = []
    for a, r in rows:
        if authz.project_role(db, u, r.project_id) not in authz.INSPECTORS:
            continue  # membership revoked: history kept, no access
        ahead = None
        if a.status == 'PENDING':
            cur = db.scalar(select(ReviewerAssignment).where(ReviewerAssignment.rfi_id == r.id, ReviewerAssignment.status == 'ACTIVE'))
            if cur: ahead = {'sequence_no': cur.sequence_no, 'role': cur.reviewer_role, 'name': names(db, [cur.user_id]).get(cur.user_id)}
        out.append({'assignment': {k: getattr(a, k) for k in ReviewerAssignment.__table__.columns.keys()}, 'rfi': rfi_dict(r), 'waiting_for': ahead})
    return out


@router.get('/{rid}/suggested-reviewers')
def suggested(rid: int, db: Session = Depends(get_db), u: User = Depends(current_user)):
    r, role = authz.load_rfi(db, u, rid)
    if role not in authz.MANAGEMENT and role != authz.ADMIN: raise HTTPException(403, 'Not permitted')
    return list(db.scalars(select(ReviewerRule).where(ReviewerRule.project_id == r.project_id, ReviewerRule.work_item == r.work_item)))


@router.get('/{rid}')
def one(rid: int, db: Session = Depends(get_db), u: User = Depends(current_user)):
    r, role = authz.load_rfi(db, u, rid)
    project = db.get(Project, r.project_id); settings = get_settings(project)
    assigns = list(db.scalars(select(ReviewerAssignment).where(ReviewerAssignment.rfi_id == rid).order_by(ReviewerAssignment.sequence_no, ReviewerAssignment.id)))
    reviews = list(db.scalars(select(Review).where(Review.rfi_id == rid)))
    decs = list(db.scalars(select(Decision).where(Decision.rfi_id == rid).order_by(Decision.id.desc())))
    hist = list(db.scalars(select(RfiStatusHistory).where(RfiStatusHistory.rfi_id == rid).order_by(RfiStatusHistory.id.desc())))
    amends = [a for a in db.scalars(select(RfiAmendment).where(RfiAmendment.rfi_id == rid).order_by(RfiAmendment.id.desc()))
              if a.status not in ('DRAFT', 'WITHDRAWN') or a.requested_by == u.id]
    ev_counts = dict(db.execute(select(Attachment.assignment_id, func.count()).where(Attachment.rfi_id == rid, Attachment.assignment_id.is_not(None), *ev.live_clause())
                                .group_by(Attachment.assignment_id)).all())
    issued = list(db.scalars(select(IssuedDocument).where(IssuedDocument.rfi_id == rid).order_by(IssuedDocument.id.desc())))
    revisions = list(db.scalars(select(Rfi).where(Rfi.project_id == r.project_id, Rfi.rfi_number == r.rfi_number).order_by(Rfi.revision_no)))
    summary = db.get(RfiSummary, r.summary_id) if r.summary_id else None
    nm = names(db, [a.user_id for a in assigns] + [x.reviewer_id for x in reviews] + [d.decided_by for d in decs] + [h.changed_by for h in hist]
               + [a.requested_by for a in amends] + [a.resolved_by for a in amends] + [r.created_by, r.received_by, summary.submitted_by if summary else None])
    rv = {x.assignment_id: x for x in reviews}
    mgmt = role in authz.MANAGEMENT
    is_legacy = rfi_dict(r)['is_legacy']
    open_ = r.record_state == 'ACTIVE' and not is_legacy
    my_active = next((a.id for a in assigns if a.user_id == u.id and a.status == 'ACTIVE' and role in authz.INSPECTORS), None)
    latest = revisions[-1].id == r.id if revisions else True
    disp = disposition(settings, r.current_disposition) if r.current_disposition else None
    can_resub = open_ and role in authz.CONTRACTOR and latest and r.workflow_status == 'COMPLETED' and (bool(disp and disp.get('allows_resubmit')) or (not disp and r.current_decision == 'REJECTED'))
    def a_out(a):
        x = {k: getattr(a, k) for k in ReviewerAssignment.__table__.columns.keys()}
        x['user_name'] = nm.get(a.user_id)
        rr = rv.get(a.id)
        x['review'] = {'comment': rr.comment, 'recommendation': rr.recommendation, 'reviewed_at': rr.reviewed_at, 'reviewer_name': rr.reviewer_name_snapshot or nm.get(rr.reviewer_id),
                       'attachment_count': rr.attachment_count} if rr else None
        x['evidence_count'] = ev_counts.get(a.id, 0) if (rr or a.user_id == u.id or mgmt) else None
        x['reviewer_role_label'] = authz.ROLE_LABELS.get(a.reviewer_role, a.reviewer_role)
        x.pop('draft_comment', None)  # the inspector's unsent draft is private (GET /evidence/assignments/{id})
        # Later inspectors see that an earlier review exists, not necessarily its content? SRS: read-only view is permitted.
        return x
    return {
        'rfi': rfi_dict(r), 'project': {'id': project.id, 'code': project.code, 'name': project.name, 'deputy_label': settings['deputy_label']},
        'summary': {'id': summary.id, 'summary_reference': summary.summary_reference, 'workflow_status': summary.workflow_status,
                    'submitted_at': summary.submitted_at, 'submitted_by_name': nm.get(summary.submitted_by)} if summary else None,
        'my_role': role, 'my_category': authz.category(role), 'my_name': u.full_name, 'assignments': [a_out(a) for a in assigns],
        'project_detail': {'contract_number': project.contract_number, 'employer': project.employer, 'consultant': project.consultant, 'contractor': project.contractor},
        'decisions': [{**{k: getattr(d, k) for k in Decision.__table__.columns.keys()}, 'decided_by_name': d.decided_by_name_snapshot or nm.get(d.decided_by),
                       'disposition_label': (disposition(settings, d.disposition_code) or {}).get('label') if d.disposition_code else None} for d in decs],
        'history': [{**{k: getattr(h, k) for k in RfiStatusHistory.__table__.columns.keys()}, 'changed_by_name': nm.get(h.changed_by)} for h in hist],
        'amendments': [{**{k: getattr(a, k) for k in RfiAmendment.__table__.columns.keys()}, 'changes': json.loads(a.changes_json or '{}'),
                        'requested_by_name': nm.get(a.requested_by), 'resolved_by_name': nm.get(a.resolved_by)} for a in amends],
        'issued_documents': [{'id': i.id, 'doc_type': i.doc_type, 'revision_no': i.revision_no, 'issued_at': i.issued_at, 'sha256': i.sha256} for i in issued],
        'revisions': [{'id': x.id, 'revision_no': x.revision_no, 'workflow_status': x.workflow_status, 'current_decision': x.current_decision} for x in revisions],
        'created_by_name': nm.get(r.created_by), 'received_by_name': nm.get(r.received_by),
        'dispositions': settings['dispositions'] if mgmt else [{'code': d['code'], 'label': d['label']} for d in settings['dispositions']],
        'permissions': {
            'edit_draft': open_ and role in authz.CONTRACTOR and r.workflow_status == 'DRAFT',
            'assign': open_ and mgmt and r.workflow_status in OPEN_FOR_ASSIGNMENT,
            'review_assignment_id': my_active if open_ and r.workflow_status == 'UNDER_REVIEW' else None,
            'decide': open_ and mgmt and r.workflow_status == 'AWAITING_DECISION',
            'request_amendment': open_ and (role in authz.CONTRACTOR or mgmt) and r.workflow_status not in ('DRAFT', 'CANCELLED'),
            'resolve_amendment': open_ and mgmt,
            'resubmit': can_resub,
            'cancel': open_ and mgmt and r.workflow_status not in ('COMPLETED', 'CANCELLED'),
            # UI design v1
            'management_remark': open_ and mgmt and r.workflow_status in OPEN_FOR_ASSIGNMENT,
            'amend_review_assignment_ids': [a.id for a in assigns if a.status == 'COMPLETED' and open_ and r.workflow_status not in ('COMPLETED', 'CANCELLED')
                                            and ((a.user_id == u.id and role in authz.INSPECTORS) or mgmt)],
        },
        # read capability (not a write permission)
        'can_download_bundle': r.workflow_status == 'COMPLETED' and role in (authz.MANAGEMENT | authz.OFFICE | {authz.ADMIN}),
    }


@router.post('')
def create(d: RfiCreate, db: Session = Depends(get_db), u: User = Depends(current_user)):
    s = db.get(RfiSummary, d.summary_id)
    if not s: raise HTTPException(404, 'DOC_01 batch not found')
    if s.project_id != d.project_id: raise HTTPException(400, 'RFI project must match the batch project')
    authz.require_project(db, u, d.project_id, authz.CONTRACTOR, write=True)
    if s.workflow_status not in ('DRAFT', 'RETURNED'): raise HTTPException(409, 'This DOC_01 batch has been submitted and is locked')
    if not d.rfi_number.strip(): raise HTTPException(400, 'RFI No. is required')
    if d.client_request_id:
        prev = db.scalar(select(Rfi).where(Rfi.summary_id == s.id, Rfi.rfi_number == d.rfi_number.strip(), Rfi.created_by == u.id))
        if prev: return rfi_dict(prev)  # idempotent retry of the same offline request
    duplicate_check(db, d.project_id, d.rfi_number)
    data = clean_fields(d.model_dump(exclude={'project_id', 'summary_id', 'rfi_number', 'client_request_id'}))
    r = Rfi(project_id=d.project_id, summary_id=s.id, rfi_number=d.rfi_number.strip(), revision_no=0, created_by=u.id,
            workflow_status='DRAFT', provenance='PORTAL', **data)
    db.add(r); db.flush()
    db.add(RfiStatusHistory(rfi_id=r.id, workflow_status='DRAFT', changed_by=u.id, reason='Created in DOC_01 batch ' + s.summary_reference))
    log(db, u.id, 'RFI', r.id, 'CREATE', r.rfi_number, project_id=r.project_id, after=data)
    db.commit(); db.refresh(r)
    return rfi_dict(r)


@router.put('/{rid}')
def update(rid: int, d: RfiUpdate, db: Session = Depends(get_db), u: User = Depends(current_user)):
    r = lock_rfi(db, rid)
    editable_draft(db, u, r)
    if d.version != r.version: raise HTTPException(409, 'This RFI was modified by another user. Refresh before saving.')
    data = d.model_dump(exclude={'version'}, exclude_unset=True)
    if 'rfi_number' in data:
        if not (data['rfi_number'] or '').strip(): raise HTTPException(400, 'RFI No. is required')
        duplicate_check(db, r.project_id, data['rfi_number'], exclude_id=r.id)
        data['rfi_number'] = data['rfi_number'].strip()
    data = clean_fields(data)
    before = {k: getattr(r, k) for k in data}
    for k, v in data.items(): setattr(r, k, v)
    r.version += 1
    log(db, u.id, 'RFI', r.id, 'EDIT_DRAFT', None, project_id=r.project_id, before=before, after=data)
    db.commit(); db.refresh(r)
    return rfi_dict(r)


@router.delete('/{rid}')
def delete_draft(rid: int, db: Session = Depends(get_db), u: User = Depends(current_user)):
    """Remove an RFI line from a DOC_01 batch that has never been submitted."""
    r = lock_rfi(db, rid)
    editable_draft(db, u, r)
    if db.scalar(select(func.count()).select_from(RfiStatusHistory).where(RfiStatusHistory.rfi_id == rid, RfiStatusHistory.workflow_status != 'DRAFT')):
        raise HTTPException(409, 'This RFI has been submitted before and cannot be removed')
    snapshot = rfi_dict(r)
    for h in db.scalars(select(RfiStatusHistory).where(RfiStatusHistory.rfi_id == rid)): db.delete(h)
    db.flush()
    db.delete(r)
    log(db, u.id, 'RFI', rid, 'DELETE_DRAFT_LINE', snapshot['rfi_number'], project_id=snapshot['project_id'], before=snapshot)
    db.commit()
    return {'ok': True}


@router.post('/{rid}/assignments')
def plan_assignments(rid: int, d: AssignmentPlan, db: Session = Depends(get_db), u: User = Depends(current_user)):
    """RE/DRE sets the ordered list of inspectors still to review (FR-09, FR-10, SRS 5.4)."""
    r = lock_rfi(db, rid)
    require_active_record(r)
    authz.require_project(db, u, r.project_id, authz.MANAGEMENT, write=True)
    if r.workflow_status not in OPEN_FOR_ASSIGNMENT:
        raise HTTPException(409, f'Inspectors cannot be assigned while the RFI is {STATUS_LABELS.get(r.workflow_status, r.workflow_status)}')
    if not d.assignments: raise HTTPException(400, 'Assign at least one inspector')
    existing = active_assignments(db, rid)
    completed = [a for a in existing if a.status == 'COMPLETED']
    pending = [a for a in existing if a.status in ('PENDING', 'ACTIVE')]
    started = bool(completed)
    reason = (d.reason or '').strip()
    if started and not reason:
        raise HTTPException(400, 'Inspection has already started: a reason is required to change the assignment or sequence')
    plan = []
    seen = set()
    for item in d.assignments:
        target = db.get(User, item.user_id)
        if not target or not target.is_active: raise HTTPException(400, f'User {item.user_id} is inactive or does not exist')
        mrole = authz.project_role(db, target, r.project_id)
        if mrole not in authz.INSPECTORS:
            raise HTTPException(400, f'{target.full_name} is not an inspector (Category 2.2) on this project')
        role = item.reviewer_role or mrole
        if role != mrole:
            raise HTTPException(400, f'{target.full_name} holds the {authz.ROLE_LABELS.get(mrole, mrole)} role on this project and can only review in that DOC_03 field')
        if (target.id, role) in seen: raise HTTPException(400, f'{target.full_name} appears twice in the sequence')
        seen.add((target.id, role)); plan.append((target, role))
    before = [{'seq': a.sequence_no, 'user_id': a.user_id, 'role': a.reviewer_role, 'status': a.status} for a in existing]
    if [(a.user_id, a.reviewer_role) for a in pending] == [(t.id, ro) for t, ro in plan]:
        return {'ok': True, 'changed': False}
    from app.routers.evidence import submit_remark
    remark = submit_remark(db, u, d.management_remark_id, stage='SEQUENCE_CHANGE' if (started or pending) else 'ASSIGNMENT', rfi=r,
                           body=(d.remark or '').strip() or reason or None)
    now = datetime.utcnow()
    for a in pending:
        a.status = 'REPLACED'; a.change_reason = reason or 'Re-planned before inspection started'
    start = max([a.sequence_no or 0 for a in completed], default=0)
    created = []
    for i, (t, role) in enumerate(plan, start=1):
        a = ReviewerAssignment(rfi_id=rid, user_id=t.id, reviewer_role=role, required=True, assigned_by=u.id, sequence_no=start + i,
                               status='ACTIVE' if i == 1 else 'PENDING', activated_at=now if i == 1 else None, change_reason=reason or None)
        db.add(a); created.append(a)
    db.flush()
    if not r.received_at:
        r.received_by = u.id; r.received_at = now
    transition(db, r, 'UNDER_REVIEW', u, ('Assignment changed: ' + reason) if (started or pending) and reason else
               'Inspectors assigned: ' + ' → '.join(authz.ROLE_LABELS.get(ro, ro) for _, ro in plan))
    for a in created:
        if a.status == 'ACTIVE':
            notify(db, a.user_id, 'RFI ready for your inspection', f'RFI {r.rfi_number} Rev {r.revision_no}: it is your turn to inspect (sequence {a.sequence_no}). Inspection date {r.inspection_date or "-"} {r.inspection_time or ""}.', 'RFI', rid, r.project_id)
        else:
            notify(db, a.user_id, 'RFI inspection assigned', f'RFI {r.rfi_number} Rev {r.revision_no}: you are number {a.sequence_no} in the inspection sequence. You will be notified when it is your turn.', 'RFI', rid, r.project_id)
    after = [{'seq': a.sequence_no, 'user_id': a.user_id, 'role': a.reviewer_role, 'status': a.status} for a in created]
    log(db, u.id, 'RFI', rid, 'ASSIGN_SEQUENCE' if not started else 'CHANGE_SEQUENCE', reason or None, project_id=r.project_id, before=before, after=after)
    db.commit()
    return {'ok': True, 'changed': True, 'assignments': after, 'management_remark_id': remark.id if remark else None}


@router.post('/{rid}/review')
def review(rid: int, d: ReviewCreate, db: Session = Depends(get_db), u: User = Depends(current_user)):
    """Strictly sequential inspector review (FR-12/13/14, BR-05/06)."""
    r = lock_rfi(db, rid)
    a = db.scalar(select(ReviewerAssignment).where(ReviewerAssignment.id == d.assignment_id).with_for_update())
    if not a or a.rfi_id != rid or a.status == 'REPLACED': raise HTTPException(404, 'Assignment not found')
    if a.user_id != u.id: raise HTTPException(403, 'Only the assigned inspector may enter comments in this DOC_03 field')
    role = authz.project_role(db, u, r.project_id)
    if role not in authz.INSPECTORS: raise HTTPException(403, 'You are no longer an inspector on this project')
    require_active_record(r)
    if a.status == 'COMPLETED': raise HTTPException(409, 'Your review for this RFI has already been submitted and is locked')
    if a.status != 'ACTIVE' or r.workflow_status != 'UNDER_REVIEW':
        cur = db.scalar(select(ReviewerAssignment).where(ReviewerAssignment.rfi_id == rid, ReviewerAssignment.status == 'ACTIVE'))
        who = f' Waiting for inspector #{cur.sequence_no} ({authz.ROLE_LABELS.get(cur.reviewer_role, cur.reviewer_role)}).' if cur else ''
        raise HTTPException(409, 'It is not your turn to review this RFI yet.' + who)
    if not (d.comment or '').strip(): raise HTTPException(400, 'Inspection comment is required')
    n_files = ev.count_live(db, assignment_id=a.id)
    if d.attachment_count is not None and d.attachment_count != n_files:
        raise HTTPException(409, f'Your review has {n_files} evidence file(s) on the server, not {d.attachment_count}. An upload may still be running or has failed. Check the evidence list and submit again.')
    now = datetime.utcnow()
    rv = Review(assignment_id=a.id, rfi_id=rid, reviewer_id=u.id, recommendation=(d.recommendation or 'NOT_STATED')[:50], comment=d.comment.strip(), reviewed_at=now,
                reviewer_name_snapshot=u.full_name, reviewer_role_snapshot=a.reviewer_role, attachment_count=n_files)
    db.add(rv)
    a.status = 'COMPLETED'; a.completed_at = now; a.draft_comment = None
    db.flush()
    # The review and its evidence are locked together (version preservation).
    ev.lock(db, Attachment.assignment_id == a.id, *ev.live_clause(), when=now)
    for f in db.scalars(select(Attachment).where(Attachment.assignment_id == a.id, Attachment.review_id.is_(None))): f.review_id = rv.id
    nxt = db.scalar(select(ReviewerAssignment).where(ReviewerAssignment.rfi_id == rid, ReviewerAssignment.status == 'PENDING').order_by(ReviewerAssignment.sequence_no))
    if nxt:
        nxt.status = 'ACTIVE'; nxt.activated_at = now
        r.version += 1
        db.add(RfiStatusHistory(rfi_id=r.id, workflow_status=r.workflow_status, decision=r.current_decision, changed_by=u.id,
                                reason=f'Review {a.sequence_no} submitted ({authz.ROLE_LABELS.get(a.reviewer_role, a.reviewer_role)}); inspector #{nxt.sequence_no} now active'))
        notify(db, nxt.user_id, 'RFI ready for your inspection', f'The previous inspector has submitted. RFI {r.rfi_number} Rev {r.revision_no} is now ready for your review.', 'RFI', rid, r.project_id)
    else:
        transition(db, r, 'AWAITING_DECISION', u, 'All assigned inspector reviews completed')
        notify_project_roles(db, r.project_id, authz.MANAGEMENT, 'RFI awaiting final decision', f'All inspector reviews for RFI {r.rfi_number} Rev {r.revision_no} are complete. It awaits the RE/DRE final decision.', 'RFI', rid)
    log(db, u.id, 'RFI', rid, 'REVIEW', f'sequence {a.sequence_no} {a.reviewer_role}; {n_files} evidence file(s)', project_id=r.project_id, after={'comment': rv.comment, 'recommendation': rv.recommendation, 'attachments': n_files})
    db.commit()
    return {'ok': True, 'review_id': rv.id, 'next_sequence': nxt.sequence_no if nxt else None, 'workflow_status': r.workflow_status, 'attachment_count': n_files, 'reviewed_at': now}


@router.post('/{rid}/decision')
def decide(rid: int, d: DecisionCreate, db: Session = Depends(get_db), u: User = Depends(current_user)):
    """Final RE/DRE disposition (FR-16/17/18, BR-07). Admin has no decision authority (DR-01)."""
    r = lock_rfi(db, rid)
    require_active_record(r)
    authz.require_project(db, u, r.project_id, authz.MANAGEMENT, write=True)
    if r.workflow_status != 'AWAITING_DECISION':
        raise HTTPException(409, 'A final decision can only be recorded after all assigned inspector reviews are complete' if r.workflow_status != 'COMPLETED' else 'A final decision has already been recorded for this revision')
    if db.scalar(select(func.count()).select_from(ReviewerAssignment).where(ReviewerAssignment.rfi_id == rid, ReviewerAssignment.status.in_(['PENDING', 'ACTIVE']))):
        raise HTTPException(409, 'Inspector reviews are still pending')
    settings = get_settings(db.get(Project, r.project_id))
    disp = disposition(settings, d.disposition_code)
    if not disp: raise HTTPException(400, 'Select one of the configured DOC_03 disposition options')
    af, at = (d.approved_from or '').strip() or None, (d.approved_to or '').strip() or None
    if disp.get('requires_section') and not (af and at):
        raise HTTPException(400, 'This disposition requires the approved (executed) section: Approved From and Approved To')
    if disp['decision'] == 'APPROVED' and not af and not at:
        af, at = r.chainage_from, r.chainage_to
    before = {'current_decision': r.current_decision, 'current_disposition': r.current_disposition, 'approved_from': r.approved_from, 'approved_to': r.approved_to, 'work_status': r.work_status}
    role = authz.project_role(db, u, r.project_id)
    x = Decision(rfi_id=rid, revision_no=r.revision_no, decision=disp['decision'], disposition_code=disp['code'], comment=(d.comment or '').strip() or None,
                 conditions=(d.conditions or '').strip() or None, approved_from=af, approved_to=at, decided_by=u.id, override_used=False,
                 decided_by_name_snapshot=u.full_name, designation_snapshot=authz.ROLE_LABELS.get(role, role))
    db.add(x); db.flush()
    from app.routers.evidence import submit_remark
    remark = submit_remark(db, u, d.management_remark_id, stage='FINAL_DISPOSITION', rfi=r, body=x.comment, decision_id=x.id)
    if d.evidence_count is not None:
        n_mgmt = ev.count_live(db, management_remark_id=remark.id) if remark else 0
        if n_mgmt != d.evidence_count:
            raise HTTPException(409, f'The final remark has {n_mgmt} file(s) on the server, not {d.evidence_count}. An upload may still be running. Check and record again.')
    r.current_decision = disp['decision']; r.current_disposition = disp['code']
    r.approved_from = af; r.approved_to = at
    if d.work_status: r.work_status = d.work_status
    transition(db, r, 'COMPLETED', u, f"{disp['label']}" + (f' - {x.comment}' if x.comment else ''))
    db.flush()
    after = {'current_decision': r.current_decision, 'current_disposition': r.current_disposition, 'approved_from': af, 'approved_to': at, 'work_status': r.work_status}
    log(db, u.id, 'RFI', rid, 'FINAL_DECISION', disp['code'], project_id=r.project_id, before=before, after=after)
    # Issued DOC_03 snapshot (SRS 11.2) - the PDF exactly as issued is stored with a SHA-256 hash.
    try:
        from app.services.documents import issue_doc03
        issue_doc03(db, r, u)
    except Exception as e:  # never lose the decision because of a rendering problem; record it instead
        log(db, u.id, 'RFI', rid, 'ISSUE_SNAPSHOT_FAILED', str(e)[:500], project_id=r.project_id)
    recipients = {r.created_by}
    s = db.get(RfiSummary, r.summary_id) if r.summary_id else None
    if s: recipients.add(s.submitted_by)
    for uid in recipients:
        if authz.project_role(db, db.get(User, uid), r.project_id):
            notify(db, uid, f"RFI {r.rfi_number}: {disp['label']}", f"Final decision for RFI {r.rfi_number} Rev {r.revision_no}: {disp['label']}. The completed DOC_03 is available.", 'RFI', rid, r.project_id)
    notify_project_roles(db, r.project_id, authz.MANAGEMENT | authz.OFFICE, f"RFI {r.rfi_number} decided", f"RFI {r.rfi_number} Rev {r.revision_no}: {disp['label']}.", 'RFI', rid, exclude={u.id} | recipients)
    db.commit()
    return {'ok': True, 'decision_id': x.id, 'decision': x.decision, 'disposition_code': x.disposition_code}


@router.post('/{rid}/resubmit')
def resubmit(rid: int, d: RevisionCreate, db: Session = Depends(get_db), u: User = Depends(current_user)):
    o = lock_rfi(db, rid)
    require_active_record(o)
    authz.require_project(db, u, o.project_id, authz.CONTRACTOR, write=True)
    settings = get_settings(db.get(Project, o.project_id))
    disp = disposition(settings, o.current_disposition) if o.current_disposition else None
    if o.workflow_status != 'COMPLETED' or not ((disp and disp.get('allows_resubmit')) or (not disp and o.current_decision == 'REJECTED')):
        raise HTTPException(409, 'Only an RFI decided as "Not Approved" or "Approved for the executed section, resubmit remaining" can be resubmitted')
    if db.scalar(select(Rfi.id).where(Rfi.project_id == o.project_id, Rfi.rfi_number == o.rfi_number, Rfi.revision_no > o.revision_no)):
        raise HTTPException(409, 'A newer revision of this RFI already exists')
    if not d.reason.strip(): raise HTTPException(400, 'Resubmission reason is required')
    if not d.inspection_date or not d.inspection_time: raise HTTPException(400, 'Proposed inspection date and time are required for the resubmission')
    copy = {k: getattr(o, k) for k in AMENDABLE}
    now_site = site_now()
    copy.update(inspection_date=d.inspection_date, inspection_time=d.inspection_time, requested_date=now_site.date(), requested_time=now_site.strftime('%H:%M'))
    if d.chainage_from: copy['chainage_from'] = d.chainage_from.strip()
    if d.chainage_to: copy['chainage_to'] = d.chainage_to.strip()
    n = Rfi(project_id=o.project_id, summary_id=o.summary_id, rfi_number=o.rfi_number, revision_no=o.revision_no + 1, parent_rfi_id=o.id,
            workflow_status='SUBMITTED', provenance='PORTAL', created_by=u.id, **copy)
    n.remarks = d.reason.strip()
    compute_notice(n, now_site, settings['notice_hours'])
    db.add(n); db.flush()
    db.add(RfiStatusHistory(rfi_id=n.id, workflow_status='SUBMITTED', changed_by=u.id, reason=f'Resubmitted as Rev {n.revision_no} from record {o.id}: {d.reason.strip()}'))
    notify_project_roles(db, n.project_id, authz.MANAGEMENT, 'RFI resubmitted', f'RFI {n.rfi_number} Rev {n.revision_no} was resubmitted and awaits assignment.' + (' SHORT NOTICE.' if n.short_notice else ''), 'RFI', n.id)
    log(db, u.id, 'RFI', n.id, 'RESUBMIT', f'from record {o.id}', project_id=n.project_id)
    db.commit(); db.refresh(n)
    return rfi_dict(n)


@router.post('/{rid}/amendments')
def request_amendment(rid: int, d: AmendmentCreate, db: Session = Depends(get_db), u: User = Depends(current_user)):
    r = lock_rfi(db, rid)
    require_active_record(r)
    role = authz.require_project(db, u, r.project_id, authz.CONTRACTOR | authz.MANAGEMENT, write=True)
    if r.workflow_status in ('DRAFT', 'CANCELLED'): raise HTTPException(409, 'Draft RFIs are edited directly; cancelled RFIs cannot be amended')
    if not d.reason.strip(): raise HTTPException(400, 'A reason is required')
    bad = set(d.changes) - AMENDABLE
    if bad: raise HTTPException(400, f'These fields cannot be amended: {", ".join(sorted(bad))}')
    if not d.changes: raise HTTPException(400, 'No changes given')
    validated = RfiFields(**d.changes).model_dump(include=set(d.changes))
    new = clean_fields(validated)
    changes = {}
    for k, v in new.items():
        old = getattr(r, k)
        if (str(old) if old is not None else None) != (str(v) if v is not None else None):
            changes[k] = {'old': old.isoformat() if hasattr(old, 'isoformat') else old, 'new': v.isoformat() if hasattr(v, 'isoformat') else v}
    if not changes: raise HTTPException(400, 'The requested values are identical to the current record')
    a = RfiAmendment(rfi_id=rid, project_id=r.project_id, changes_json=json.dumps(changes), reason=d.reason.strip(), requested_by=u.id)
    db.add(a); db.flush()
    log(db, u.id, 'RFI', rid, 'REQUEST_AMENDMENT', d.reason.strip(), project_id=r.project_id, after=changes)
    notify_project_roles(db, r.project_id, authz.MANAGEMENT, 'Amendment requested', f'An amendment to RFI {r.rfi_number} was requested: {d.reason.strip()}', 'RFI', rid, exclude={u.id})
    db.commit()
    return {'ok': True, 'amendment_id': a.id, 'changes': changes}


def _resolve(aid, approve, d, db, u):
    a = db.scalar(select(RfiAmendment).where(RfiAmendment.id == aid).with_for_update())
    if not a: raise HTTPException(404, 'Amendment not found')
    r = lock_rfi(db, a.rfi_id)
    authz.require_project(db, u, a.project_id, authz.MANAGEMENT, write=True)
    if a.status != 'PENDING': raise HTTPException(409, 'This amendment has already been resolved')
    changes = json.loads(a.changes_json)
    if a.amendment_type in ('REVIEW', 'REMARK'):
        require_active_record(r)
        if approve and r.workflow_status in ('COMPLETED', 'CANCELLED'):
            raise HTTPException(409, 'The DOC_03 has been issued since this correction was requested; it can only be rejected')
        from app.routers.evidence import apply_evidence_amendment
        apply_evidence_amendment(db, a, approve, u)
        a.status = 'APPROVED' if approve else 'REJECTED'; a.resolved_by = u.id; a.resolved_at = datetime.utcnow(); a.resolution_comment = (d.comment or '').strip() or None
        db.add(RfiStatusHistory(rfi_id=r.id, workflow_status=r.workflow_status, decision=r.current_decision, changed_by=u.id,
                                reason=f'Evidence correction {"approved" if approve else "rejected"} ({a.amendment_type.lower()}): {a.reason}'))
        log(db, u.id, 'RFI', r.id, 'APPROVE_EVIDENCE_AMENDMENT' if approve else 'REJECT_EVIDENCE_AMENDMENT', a.resolution_comment, project_id=r.project_id, after=changes)
        if a.requested_by != u.id:
            notify(db, a.requested_by, f'Evidence correction {"approved" if approve else "rejected"}', f'Your correction on RFI {r.rfi_number} was {"approved" if approve else "rejected"}.', 'RFI', r.id, r.project_id)
        db.commit()
        return {'ok': True, 'status': a.status}
    if approve:
        require_active_record(r)
        for k, ch in changes.items():
            cur = getattr(r, k)
            cur_s = cur.isoformat() if hasattr(cur, 'isoformat') else cur
            if (str(cur_s) if cur_s is not None else None) != (str(ch['old']) if ch['old'] is not None else None):
                raise HTTPException(409, f'Field {k} changed since the amendment was requested; ask for a new amendment')
        typed = clean_fields(RfiFields(**{k: (json.loads(ch['new']) if k == 'work_categories' and isinstance(ch['new'], str) else ch['new']) for k, ch in changes.items()}).model_dump(include=set(changes)))
        for k, v in typed.items(): setattr(r, k, v)
        r.version += 1
        db.add(RfiStatusHistory(rfi_id=r.id, workflow_status=r.workflow_status, decision=r.current_decision, changed_by=u.id, reason='Amendment approved: ' + a.reason))
    a.status = 'APPROVED' if approve else 'REJECTED'; a.resolved_by = u.id; a.resolved_at = datetime.utcnow(); a.resolution_comment = (d.comment or '').strip() or None
    log(db, u.id, 'RFI', r.id, 'APPROVE_AMENDMENT' if approve else 'REJECT_AMENDMENT', a.resolution_comment, project_id=r.project_id,
        before={k: ch['old'] for k, ch in changes.items()}, after={k: ch['new'] for k, ch in changes.items()} if approve else None)
    if a.requested_by != u.id:
        notify(db, a.requested_by, f'Amendment {"approved" if approve else "rejected"}', f'Your amendment to RFI {r.rfi_number} was {"approved" if approve else "rejected"}.', 'RFI', r.id, r.project_id)
    db.commit()
    return {'ok': True, 'status': a.status}


@router.post('/amendments/{aid}/approve')
def approve_amendment(aid: int, d: AmendmentResolve, db: Session = Depends(get_db), u: User = Depends(current_user)):
    return _resolve(aid, True, d, db, u)


@router.post('/amendments/{aid}/reject')
def reject_amendment(aid: int, d: AmendmentResolve, db: Session = Depends(get_db), u: User = Depends(current_user)):
    return _resolve(aid, False, d, db, u)


@router.post('/{rid}/cancel')
def cancel(rid: int, d: StateChange, db: Session = Depends(get_db), u: User = Depends(current_user)):
    r = lock_rfi(db, rid)
    require_active_record(r)
    authz.require_project(db, u, r.project_id, authz.MANAGEMENT, write=True)
    if not d.reason.strip(): raise HTTPException(400, 'Reason is required')
    for a in db.scalars(select(ReviewerAssignment).where(ReviewerAssignment.rfi_id == rid, ReviewerAssignment.status.in_(['PENDING', 'ACTIVE']))):
        a.status = 'REPLACED'; a.change_reason = 'RFI cancelled: ' + d.reason
    transition(db, r, 'CANCELLED', u, 'Cancelled: ' + d.reason)
    r.record_state = 'CANCELLED'
    log(db, u.id, 'RFI', rid, 'CANCEL', d.reason, project_id=r.project_id)
    db.commit()
    return rfi_dict(r)
