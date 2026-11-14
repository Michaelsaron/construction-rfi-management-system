from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, Rfi, ReviewerRule, Notification, Project, ProjectUser, RfiSummary, ReviewerAssignment, AuditLog, RfiAmendment
from app.schemas import ReviewerRuleCreate, ChangePasswordIn
from app.security import current_user, verify_password, hash_password
from app import authz
from app.project_settings import get_settings
from app.services.audit import log
from app.services.notify import create_overdue_notifications
from app.services.workflow import rfi_dict

router = APIRouter(tags=['System'])


@router.get('/me')
def me(db: Session = Depends(get_db), u: User = Depends(current_user)):
    rows = db.execute(select(ProjectUser, Project).join(Project, Project.id == ProjectUser.project_id)
                      .where(ProjectUser.user_id == u.id, ProjectUser.status == 'ACTIVE', Project.archived_at.is_(None))).all()
    ms = []
    for m, p in rows:
        role = m.role or (u.role if u.role in authz.PROJECT_ROLES else None)
        if role: ms.append({'project_id': p.id, 'code': p.code, 'name': p.name, 'role': role, 'role_label': authz.ROLE_LABELS.get(role, role),
                            'category': authz.category(role), 'deputy_label': get_settings(p)['deputy_label']})
    return {'id': u.id, 'name': u.full_name, 'email': u.email, 'role': u.role, 'is_admin': u.role == 'ADMIN',
            'must_change_password': u.must_change_password, 'memberships': ms}


@router.post('/me/password')
def change_password(d: ChangePasswordIn, db: Session = Depends(get_db), u: User = Depends(current_user)):
    if not verify_password(d.current_password, u.password_hash): raise HTTPException(400, 'Current password is incorrect')
    if len(d.new_password) < 10: raise HTTPException(400, 'Password must be at least 10 characters')
    if d.new_password == d.current_password: raise HTTPException(400, 'New password must be different from the current password')
    u.password_hash = hash_password(d.new_password); u.must_change_password = False
    log(db, u.id, 'USER', u.id, 'CHANGE_PASSWORD'); db.commit()
    return {'ok': True}


def brief(rows):
    return [{'id': r.id, 'rfi_number': r.rfi_number, 'revision_no': r.revision_no, 'work_item': r.work_item, 'contractor_request': r.contractor_request,
             'inspection_date': r.inspection_date, 'inspection_time': r.inspection_time, 'workflow_status': r.workflow_status, 'current_decision': r.current_decision,
             'current_disposition': r.current_disposition, 'short_notice': r.short_notice, 'chainage_from': r.chainage_from, 'chainage_to': r.chainage_to, 'side': r.side} for r in rows]


@router.get('/dashboard')
def dashboard(project_id: int, db: Session = Depends(get_db), u: User = Depends(current_user)):
    """Role-specific dashboard for one project (SRS 12 Usability, brief section 8)."""
    role = authz.require_project(db, u, project_id)
    p = db.get(Project, project_id); st = get_settings(p)
    base = [Rfi.project_id == project_id, Rfi.record_state == 'ACTIVE']
    by_wf = dict(db.execute(select(Rfi.workflow_status, func.count()).where(*base).group_by(Rfi.workflow_status)).all())
    by_dec = dict(db.execute(select(Rfi.current_decision, func.count()).where(*base).group_by(Rfi.current_decision)).all())
    out = {'role': role, 'category': authz.category(role), 'project': {'id': p.id, 'code': p.code, 'name': p.name},
           'counts': {'total': sum(by_wf.values()), 'by_workflow': by_wf, 'by_decision': {k or 'NONE': v for k, v in by_dec.items()}}}
    cutoff = datetime.utcnow() - timedelta(hours=st['overdue_hours'])
    if role in authz.MANAGEMENT or role == authz.ADMIN:
        out['new_batches'] = [{'id': s.id, 'summary_reference': s.summary_reference, 'submitted_at': s.submitted_at, 'received_at': s.received_at,
                               'rfi_count': db.scalar(select(func.count()).select_from(Rfi).where(Rfi.summary_id == s.id)),
                               'short_notice': db.scalar(select(func.count()).select_from(Rfi).where(Rfi.summary_id == s.id, Rfi.short_notice == True))}
                              for s in db.scalars(select(RfiSummary).where(RfiSummary.project_id == project_id, RfiSummary.workflow_status == 'SUBMITTED').order_by(RfiSummary.submitted_at.desc()).limit(20))]
        out['awaiting_assignment'] = brief(db.scalars(select(Rfi).where(*base, Rfi.workflow_status.in_(['SUBMITTED', 'ACTIVATED'])).order_by(Rfi.inspection_date, Rfi.id).limit(50)))
        out['under_review'] = brief(db.scalars(select(Rfi).where(*base, Rfi.workflow_status == 'UNDER_REVIEW').order_by(Rfi.inspection_date).limit(50)))
        out['awaiting_decision'] = brief(db.scalars(select(Rfi).where(*base, Rfi.workflow_status == 'AWAITING_DECISION').order_by(Rfi.updated_at).limit(50)))
        out['overdue_reviews'] = brief(db.scalars(select(Rfi).join(ReviewerAssignment, ReviewerAssignment.rfi_id == Rfi.id).where(*base, ReviewerAssignment.status == 'ACTIVE', ReviewerAssignment.activated_at < cutoff).limit(50)))
        out['recent_decisions'] = brief(db.scalars(select(Rfi).where(*base, Rfi.workflow_status == 'COMPLETED', Rfi.provenance == 'PORTAL').order_by(Rfi.updated_at.desc()).limit(10)))
        out['pending_amendments'] = db.scalar(select(func.count()).select_from(RfiAmendment).where(RfiAmendment.project_id == project_id, RfiAmendment.status == 'PENDING')) or 0
    if role in authz.INSPECTORS:
        rows = db.execute(select(ReviewerAssignment, Rfi).join(Rfi, Rfi.id == ReviewerAssignment.rfi_id)
                          .where(Rfi.project_id == project_id, ReviewerAssignment.user_id == u.id, ReviewerAssignment.status != 'REPLACED')).all()
        def pick(st_): return [{**brief([r])[0], 'sequence_no': a.sequence_no, 'activated_at': a.activated_at, 'overdue': bool(a.activated_at and a.activated_at < cutoff)} for a, r in rows if a.status == st_]
        out['my_active'] = pick('ACTIVE'); out['my_upcoming'] = pick('PENDING'); out['my_completed'] = pick('COMPLETED')[:20]
    if role in authz.CONTRACTOR:
        own = [RfiSummary.project_id == project_id]
        if st['contractor_visibility'] == 'OWN': own.append(RfiSummary.submitted_by == u.id)
        out['drafts'] = [{'id': s.id, 'summary_reference': s.summary_reference, 'workflow_status': s.workflow_status, 'returned_reason': s.returned_reason}
                         for s in db.scalars(select(RfiSummary).where(*own, RfiSummary.workflow_status.in_(['DRAFT', 'RETURNED'])).order_by(RfiSummary.id.desc()))]
        out['submitted_batches'] = [{'id': s.id, 'summary_reference': s.summary_reference, 'submitted_at': s.submitted_at}
                                    for s in db.scalars(select(RfiSummary).where(*own, RfiSummary.workflow_status == 'SUBMITTED').order_by(RfiSummary.id.desc()).limit(10))]
        out['recent_decisions'] = brief(db.scalars(select(Rfi).where(*base, Rfi.workflow_status == 'COMPLETED', Rfi.provenance == 'PORTAL').order_by(Rfi.updated_at.desc()).limit(15)))
        out['action_required'] = brief(db.scalars(select(Rfi).where(*base, Rfi.provenance == 'PORTAL', Rfi.current_decision.in_(['REJECTED', 'PARTIALLY_APPROVED'])).order_by(Rfi.updated_at.desc()).limit(20)))
    if role in authz.OFFICE:
        out['recent_decisions'] = brief(db.scalars(select(Rfi).where(*base, Rfi.workflow_status == 'COMPLETED', Rfi.provenance == 'PORTAL').order_by(Rfi.updated_at.desc()).limit(20)))
    if role == authz.ADMIN:
        out['admin'] = {'projects': db.scalar(select(func.count()).select_from(Project)), 'users': db.scalar(select(func.count()).select_from(User)),
                        'memberships': db.scalar(select(func.count()).select_from(ProjectUser).where(ProjectUser.project_id == project_id, ProjectUser.status == 'ACTIVE')),
                        'recent_audit': [{'action': a.action, 'entity_type': a.entity_type, 'entity_id': a.entity_id, 'created_at': a.created_at}
                                         for a in db.scalars(select(AuditLog).where(AuditLog.project_id == project_id).order_by(AuditLog.id.desc()).limit(10))]}
    return out


@router.get('/reviewer-rules')
def rules(project_id: int, db: Session = Depends(get_db), u: User = Depends(current_user)):
    authz.require_project(db, u, project_id)
    return list(db.scalars(select(ReviewerRule).where(ReviewerRule.project_id == project_id).order_by(ReviewerRule.work_item)))


@router.post('/reviewer-rules')
def add_rule(d: ReviewerRuleCreate, db: Session = Depends(get_db), u: User = Depends(current_user)):
    authz.require_project(db, u, d.project_id, authz.MANAGEMENT | {authz.ADMIN}, write=True)
    if d.reviewer_role not in authz.INSPECTORS: raise HTTPException(400, 'Invalid reviewer role')
    if not d.work_item.strip(): raise HTTPException(400, 'Work item is required')
    if db.scalar(select(ReviewerRule).where(ReviewerRule.project_id == d.project_id, ReviewerRule.work_item == d.work_item, ReviewerRule.reviewer_role == d.reviewer_role)):
        raise HTTPException(409, 'This rule already exists')
    r = ReviewerRule(**d.model_dump()); db.add(r); db.flush()
    log(db, u.id, 'REVIEWER_RULE', r.id, 'CREATE', project_id=d.project_id); db.commit(); db.refresh(r)
    return r


@router.delete('/reviewer-rules/{rid}')
def delete_rule(rid: int, db: Session = Depends(get_db), u: User = Depends(current_user)):
    r = db.get(ReviewerRule, rid)
    if not r: raise HTTPException(404, 'Rule not found')
    authz.require_project(db, u, r.project_id, authz.MANAGEMENT | {authz.ADMIN}, write=True)
    pid = r.project_id; db.delete(r)
    log(db, u.id, 'REVIEWER_RULE', rid, 'DELETE', project_id=pid); db.commit()
    return {'ok': True}


def my_notifications(db, u):
    """A user's notifications, hiding those of projects they no longer belong to."""
    q = select(Notification).where(Notification.user_id == u.id)
    vis = authz.visible_project_ids(db, u)
    if vis is not None: q = q.where((Notification.project_id.is_(None)) | (Notification.project_id.in_(vis or [-1])))
    return q


@router.post('/notifications/read-all')
def read_all(db: Session = Depends(get_db), u: User = Depends(current_user)):
    for n in db.scalars(select(Notification).where(Notification.user_id == u.id, Notification.is_read == False)): n.is_read = True
    db.commit(); return {'ok': True}


@router.get('/notifications/unread-count')
def unread_count(db: Session = Depends(get_db), u: User = Depends(current_user)):
    q = my_notifications(db, u).where(Notification.is_read == False)
    return {'count': db.scalar(select(func.count()).select_from(q.subquery())) or 0}


@router.get('/notifications')
def notifications(db: Session = Depends(get_db), u: User = Depends(current_user)):
    return list(db.scalars(my_notifications(db, u).order_by(Notification.id.desc()).limit(200)))


@router.post('/notifications/{nid}/read')
def read_notification(nid: int, db: Session = Depends(get_db), u: User = Depends(current_user)):
    n = db.get(Notification, nid)
    if not n or n.user_id != u.id: raise HTTPException(404, 'Not found')
    n.is_read = True; db.commit(); return {'ok': True}


@router.post('/notifications/check-overdue')
def overdue(db: Session = Depends(get_db), u: User = Depends(current_user)):
    if not authz.is_admin(u) and not any(authz.project_role(db, u, pid) in authz.MANAGEMENT for pid in (authz.visible_project_ids(db, u) or [])):
        raise HTTPException(403, 'Insufficient permission')
    return {'created': create_overdue_notifications(db)}
