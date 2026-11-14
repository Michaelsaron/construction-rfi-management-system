"""Central, server-side authorization (SRS section 7).

Every router resolves access through these helpers: authenticated + active user (security.current_user),
active project membership, the project-specific role, and record visibility.
ADMIN is a global administrator flag: full read/oversight and administration, but NO official
inspector review or final decision authority (decision register DR-01, conservative default).
"""
from fastapi import HTTPException
from sqlalchemy import select, or_
from app.models import ProjectUser, Project, Rfi, RfiSummary, ReviewerAssignment, User
from app.project_settings import get_settings

ADMIN = 'ADMIN'
# Category 2.1. ARE (client form) and RE_ARE (legacy combined code) are kept unchanged; DRE is the SRS term.
MANAGEMENT = {'RE', 'DRE', 'ARE', 'RE_ARE'}
INSPECTORS = {'WORK_INSPECTOR', 'STRUCTURE_INSPECTOR', 'SURVEYOR', 'SENIOR_SURVEYOR', 'MATERIAL_INSPECTOR', 'LAB_TECHNICIAN', 'MATERIAL_ENGINEER'}
OFFICE = {'QUANTITY_SURVEYOR', 'DRAFTSPERSON', 'SECRETARY', 'PROJECT_MANAGER', 'VIEWER'}
CONTRACTOR = {'DATA_ENCODER', 'OFFICE_ENGINEER', 'CONTRACTOR', 'SITE_ENGINEER'}
PROJECT_ROLES = MANAGEMENT | INSPECTORS | OFFICE | CONTRACTOR
GLOBAL_ROLES = PROJECT_ROLES | {ADMIN}

ROLE_LABELS = {
    'ADMIN': 'System Administrator', 'RE': 'Resident Engineer', 'DRE': 'Deputy Resident Engineer', 'ARE': 'Assistant Resident Engineer',
    'RE_ARE': 'RE / ARE (legacy)', 'WORK_INSPECTOR': 'Works Inspector', 'STRUCTURE_INSPECTOR': 'Structure Inspector', 'SURVEYOR': 'Surveyor',
    'SENIOR_SURVEYOR': 'Senior Surveyor', 'MATERIAL_INSPECTOR': 'Material Inspector', 'LAB_TECHNICIAN': 'Soil Lab Technician',
    'MATERIAL_ENGINEER': 'Material Engineer', 'QUANTITY_SURVEYOR': 'Quantity Surveyor', 'DRAFTSPERSON': 'Draftsperson', 'SECRETARY': 'Secretary',
    'PROJECT_MANAGER': 'Project Manager (read-only)', 'VIEWER': 'Viewer (read-only)', 'DATA_ENCODER': 'Data Encoder', 'OFFICE_ENGINEER': 'Office Engineer',
    'CONTRACTOR': 'Contractor (legacy)', 'SITE_ENGINEER': 'Site Engineer (legacy)',
}


def category(role: str | None) -> str | None:
    if role == ADMIN: return '1'
    if role in MANAGEMENT: return '2.1'
    if role in INSPECTORS: return '2.2'
    if role in OFFICE: return '2.3'
    if role in CONTRACTOR: return '3'
    return None


def is_admin(user: User) -> bool:
    return user.role == ADMIN


def membership(db, user: User, project_id: int):
    return db.scalar(select(ProjectUser).where(ProjectUser.project_id == project_id, ProjectUser.user_id == user.id, ProjectUser.status == 'ACTIVE'))


def project_role(db, user: User, project_id: int) -> str | None:
    """The user's role in this project, or None. Legacy memberships without a role fall back to users.role."""
    if is_admin(user):
        return ADMIN
    m = membership(db, user, project_id)
    if not m:
        return None
    return m.role or (user.role if user.role in PROJECT_ROLES else None)


def get_project(db, project_id: int) -> Project:
    p = db.get(Project, project_id)
    if not p:
        raise HTTPException(404, 'Project not found')
    return p


def require_project(db, user: User, project_id: int, roles: set | None = None, write: bool = False) -> str:
    """Return the project role, or raise. `roles` restricts to those project roles (ADMIN excluded unless listed)."""
    p = get_project(db, project_id)
    role = project_role(db, user, project_id)
    if role is None:
        raise HTTPException(403, 'You are not a member of this project')
    if roles is not None and role not in roles:
        raise HTTPException(403, 'Your project role does not permit this action')
    if write and p.archived_at is not None:
        raise HTTPException(409, 'This project is archived and read-only')
    return role


def visible_project_ids(db, user: User):
    """None means all projects (admin)."""
    if is_admin(user):
        return None
    return list(db.scalars(select(ProjectUser.project_id).where(ProjectUser.user_id == user.id, ProjectUser.status == 'ACTIVE')))


def can_view_register(role: str | None, settings: dict) -> bool:
    if role is None: return False
    if role in INSPECTORS: return bool(settings.get('inspector_register_access'))
    return True


def can_export(role: str | None, settings: dict) -> bool:
    if role is None: return False
    if role in INSPECTORS: return bool(settings.get('inspector_register_access')) and bool(settings.get('inspector_export'))
    return True


def rfi_visibility_clause(db, user: User, project_id: int, role: str, settings: dict):
    """Extra WHERE clause (or None) restricting which RFIs of an accessible project the user may see."""
    if role in CONTRACTOR and settings.get('contractor_visibility') == 'OWN':
        own_batches = select(RfiSummary.id).where(RfiSummary.project_id == project_id, RfiSummary.submitted_by == user.id)
        return or_(Rfi.created_by == user.id, Rfi.summary_id.in_(own_batches))
    if role in INSPECTORS and not settings.get('inspector_register_access'):
        return Rfi.id.in_(select(ReviewerAssignment.rfi_id).where(ReviewerAssignment.user_id == user.id))
    return None


def can_view_rfi(db, user: User, rfi: Rfi) -> str:
    """Return the project role if the user may view this RFI, else raise 403/404."""
    project = get_project(db, rfi.project_id)
    role = project_role(db, user, rfi.project_id)
    if role is None:
        raise HTTPException(403, 'You are not a member of this project')
    s = get_settings(project)
    if role in INSPECTORS:
        assigned = db.scalar(select(ReviewerAssignment.id).where(ReviewerAssignment.rfi_id == rfi.id, ReviewerAssignment.user_id == user.id))
        if assigned or s.get('inspector_register_access'):
            return role
        raise HTTPException(403, 'This RFI is not assigned to you')
    if role in CONTRACTOR and s.get('contractor_visibility') == 'OWN':
        batch = db.get(RfiSummary, rfi.summary_id) if rfi.summary_id else None
        if rfi.created_by != user.id and not (batch and batch.submitted_by == user.id):
            raise HTTPException(403, 'You can only view your own submissions in this project')
    return role


def load_rfi(db, user: User, rid: int):
    r = db.get(Rfi, rid)
    if not r:
        raise HTTPException(404, 'RFI not found')
    return r, can_view_rfi(db, user, r)


def load_summary(db, user: User, sid: int):
    s = db.get(RfiSummary, sid)
    if not s:
        raise HTTPException(404, 'Summary not found')
    role = require_project(db, user, s.project_id)
    settings = get_settings(db.get(Project, s.project_id))
    if role in INSPECTORS and not settings.get('inspector_register_access'):
        raise HTTPException(403, 'Not permitted')
    if role in CONTRACTOR and settings.get('contractor_visibility') == 'OWN' and s.submitted_by != user.id:
        raise HTTPException(403, 'You can only view your own submissions in this project')
    return s, role
