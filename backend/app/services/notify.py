"""In-app notifications (SRS 11). Recipients are always resolved inside one project, so a
notification can never reveal a record to a user who is not a member of that project."""
from datetime import datetime, timedelta
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models import Notification, User, Rfi, ReviewerAssignment, ProjectUser, Project
from app.services.emailer import send_email
from app.authz import normalize_role


def notify(db: Session, user_id: int, title: str, message: str, entity_type: str | None = None, entity_id: int | None = None,
           project_id: int | None = None, email: bool = True):
    n = Notification(user_id=user_id, title=title, message=message, entity_type=entity_type, entity_id=entity_id, project_id=project_id)
    db.add(n); db.flush()
    if email:
        u = db.get(User, user_id)
        if u and u.email and u.is_active:
            try: send_email(u.email, title, message)
            except Exception as e: print('[EMAIL-WARN]', e)
    return n


def project_members(db: Session, project_id: int, roles: set[str]):
    """Active users holding one of `roles` in this project (legacy memberships fall back to users.role)."""
    rows = db.execute(select(User, ProjectUser).join(ProjectUser, ProjectUser.user_id == User.id)
                      .where(ProjectUser.project_id == project_id, ProjectUser.status == 'ACTIVE', User.is_active == True)).all()
    return [u for u, m in rows if normalize_role(m.role or u.role) in roles]


def notify_project_roles(db: Session, project_id: int, roles: set[str], title: str, message: str, entity_type=None, entity_id=None, exclude: set[int] | None = None):
    users = [u for u in project_members(db, project_id, roles) if not exclude or u.id not in exclude]
    for u in users:
        notify(db, u.id, title, message, entity_type, entity_id, project_id)
    return users


def create_overdue_notifications(db: Session):
    """Remind the inspector whose turn has been active longer than the project's overdue_hours."""
    from app.project_settings import get_settings
    made = 0
    active = list(db.scalars(select(ReviewerAssignment).where(ReviewerAssignment.status == 'ACTIVE')))
    for a in active:
        r = db.get(Rfi, a.rfi_id)
        if not r or r.workflow_status != 'UNDER_REVIEW':
            continue
        hours = get_settings(db.get(Project, r.project_id)).get('overdue_hours', 24)
        started = a.activated_at or a.assigned_at
        if started > datetime.utcnow() - timedelta(hours=hours):
            continue
        marker = f'OVERDUE:{a.id}'
        if db.scalar(select(Notification.id).where(Notification.user_id == a.user_id, Notification.message.like(f'%{marker}%'))):
            continue
        notify(db, a.user_id, 'Overdue RFI inspection', f'RFI {r.rfi_number} has been waiting for your review for more than {hours} hours. {marker}', 'RFI', r.id, r.project_id)
        made += 1
    db.commit()
    return made
