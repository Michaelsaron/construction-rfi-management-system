"""User accounts - administration only (FR-02/03). Ordinary users cannot list other users (SRS 7.1)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, ProjectUser, Project
from app.schemas import UserCreate, AdminResetPasswordIn, UserProjectsIn
from app.security import require_roles, hash_password
from app import authz
from app.services.audit import log

router = APIRouter(prefix='/users', tags=['Users'])
MIN_PASSWORD = 10


def check_password(p: str):
    if len(p or '') < MIN_PASSWORD: raise HTTPException(400, f'Password must be at least {MIN_PASSWORD} characters')


def memberships(db, uid):
    rows = db.execute(select(ProjectUser, Project).join(Project, Project.id == ProjectUser.project_id).where(ProjectUser.user_id == uid)).all()
    u = db.get(User, uid)
    return [{'project_id': p.id, 'project_code': p.code, 'role': authz.normalize_role(m.role or u.role), 'legacy_role': m.role is None, 'status': m.status} for m, p in rows]


def public(db, u: User):
    ms = memberships(db, u.id)
    return {'id': u.id, 'full_name': u.full_name, 'email': u.email, 'role': authz.normalize_role(u.role), 'role_label': authz.ROLE_LABELS.get(authz.normalize_role(u.role), u.role), 'is_active': u.is_active,
            'must_change_password': u.must_change_password, 'created_at': u.created_at, 'last_login_at': u.last_login_at,
            'memberships': ms, 'project_ids': [m['project_id'] for m in ms if m['status'] == 'ACTIVE']}


def upsert_membership(db, uid, pid, role):
    if not db.get(Project, pid): raise HTTPException(400, f'Project {pid} does not exist')
    if role not in authz.PROJECT_ROLES: raise HTTPException(400, f'Invalid project role {role}')
    m = db.scalar(select(ProjectUser).where(ProjectUser.project_id == pid, ProjectUser.user_id == uid))
    if m: m.role = role; m.status = 'ACTIVE'; m.revoked_at = None
    else: db.add(ProjectUser(project_id=pid, user_id=uid, role=role, status='ACTIVE'))


@router.get('')
def ls(db: Session = Depends(get_db), _=Depends(require_roles('ADMIN'))):
    return [public(db, u) for u in db.scalars(select(User).order_by(User.full_name))]


@router.post('')
def create(d: UserCreate, db: Session = Depends(get_db), admin: User = Depends(require_roles('ADMIN'))):
    email = d.email.lower()
    if d.role not in authz.GLOBAL_ROLES: raise HTTPException(400, 'Invalid role')
    if not d.full_name.strip(): raise HTTPException(400, 'Full name is required')
    check_password(d.password)
    if db.scalar(select(User).where(User.email == email)): raise HTTPException(409, 'A user with this email already exists')
    u = User(full_name=d.full_name.strip(), email=email, password_hash=hash_password(d.password), role=d.role, must_change_password=True)
    db.add(u); db.flush()
    if d.role != 'ADMIN':
        for pid in dict.fromkeys(d.project_ids): upsert_membership(db, u.id, pid, d.role)
        for m in d.memberships: upsert_membership(db, u.id, m.project_id, m.role)
    log(db, admin.id, 'USER', u.id, 'CREATE', d.role, after={'email': email, 'role': d.role, 'memberships': [m.model_dump() for m in d.memberships], 'project_ids': d.project_ids})
    db.commit(); db.refresh(u)
    return public(db, u)


@router.put('/{uid}/projects')
def update_projects(uid: int, d: UserProjectsIn, db: Session = Depends(get_db), admin: User = Depends(require_roles('ADMIN'))):
    """Legacy endpoint: grant membership (role = the user's global role) to the listed projects; revoke others."""
    from datetime import datetime
    u = db.get(User, uid)
    if not u: raise HTTPException(404, 'User not found')
    if authz.normalize_role(u.role) not in authz.PROJECT_ROLES: raise HTTPException(400, 'Use project memberships with an explicit role for this user')
    want = set(d.project_ids)
    for m in db.scalars(select(ProjectUser).where(ProjectUser.user_id == uid)):
        if m.project_id not in want and m.status == 'ACTIVE': m.status = 'REVOKED'; m.revoked_at = datetime.utcnow()
    for pid in want:
        m = db.scalar(select(ProjectUser).where(ProjectUser.user_id == uid, ProjectUser.project_id == pid))
        if not m or m.status != 'ACTIVE': upsert_membership(db, uid, pid, authz.normalize_role(m.role if m and m.role else u.role))
    log(db, admin.id, 'USER', uid, 'SET_PROJECTS', ','.join(map(str, sorted(want))))
    db.commit()
    return public(db, u)


@router.post('/{uid}/reset-password')
def reset_password(uid: int, d: AdminResetPasswordIn, db: Session = Depends(get_db), admin: User = Depends(require_roles('ADMIN'))):
    u = db.get(User, uid)
    if not u: raise HTTPException(404, 'User not found')
    check_password(d.new_password)
    u.password_hash = hash_password(d.new_password); u.must_change_password = True; u.reset_token = None; u.reset_expires_at = None
    log(db, admin.id, 'USER', u.id, 'RESET_PASSWORD'); db.commit()
    return {'ok': True}


@router.post('/{uid}/toggle-active')
def toggle(uid: int, db: Session = Depends(get_db), admin: User = Depends(require_roles('ADMIN'))):
    u = db.get(User, uid)
    if not u: raise HTTPException(404, 'User not found')
    if u.id == admin.id and u.is_active: raise HTTPException(400, 'You cannot disable your own account')
    u.is_active = not u.is_active
    log(db, admin.id, 'USER', u.id, 'ENABLE' if u.is_active else 'DISABLE'); db.commit()
    return public(db, u)
