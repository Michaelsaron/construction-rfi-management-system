"""Projects, project settings and project memberships (FR-01/02/03, SRS 3.1, 7)."""
import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Project, User, ProjectUser
from app.schemas import ProjectCreate, ProjectUpdate
from app.security import current_user, require_roles
from app import authz
from app.project_settings import get_settings, validate_settings, DOC03_WORK_CATEGORIES
from app.services.audit import log

router = APIRouter(prefix='/projects', tags=['Projects'])
PCOLS = [c for c in Project.__table__.columns.keys() if c != 'settings_json']


class MemberIn(BaseModel):
    user_id: int
    role: str


def pdict(db, u, p):
    d = {k: getattr(p, k) for k in PCOLS}
    d['status'] = 'ARCHIVED' if p.archived_at else ('ACTIVE' if p.is_active else 'INACTIVE')
    d['my_role'] = authz.project_role(db, u, p.id)
    d['my_category'] = authz.category(d['my_role'])
    s = get_settings(p)
    d['deputy_label'] = s['deputy_label']
    return d


@router.get('')
def ls(include_archived: bool = False, db: Session = Depends(get_db), u: User = Depends(current_user)):
    q = select(Project).order_by(Project.name)
    vis = authz.visible_project_ids(db, u)
    if vis is not None: q = q.where(Project.id.in_(vis or [-1]))
    if not include_archived: q = q.where(Project.archived_at.is_(None))
    return [pdict(db, u, p) for p in db.scalars(q)]


@router.get('/meta/work-categories')
def work_categories(_: User = Depends(current_user)):
    return [{'group': g, 'label': lbl, 'items': [{'code': c, 'label': l} for c, l in items]} for g, lbl, items in DOC03_WORK_CATEGORIES]


@router.get('/meta/roles')
def roles(_: User = Depends(current_user)):
    groups = [('2.1', 'Consultant - Management', authz.MANAGEMENT), ('2.2', 'Consultant - Inspectors', authz.INSPECTORS),
              ('2.3', 'Consultant - Office', authz.OFFICE), ('3', 'Contractor', authz.CONTRACTOR)]
    return [{'category': c, 'label': l, 'roles': [{'code': r, 'label': authz.ROLE_LABELS[r]} for r in sorted(rs)]} for c, l, rs in groups]


@router.post('')
def create(d: ProjectCreate, db: Session = Depends(get_db), u: User = Depends(require_roles('ADMIN'))):
    if not d.code.strip() or not d.name.strip(): raise HTTPException(400, 'Code and name are required')
    if db.scalar(select(Project.id).where(Project.code == d.code.strip())): raise HTTPException(409, 'Project code already exists')
    p = Project(**{**d.model_dump(), 'code': d.code.strip(), 'name': d.name.strip()})
    db.add(p); db.flush()
    log(db, u.id, 'PROJECT', p.id, 'CREATE', p.code, project_id=p.id, after=d.model_dump())
    db.commit(); db.refresh(p)
    return pdict(db, u, p)


@router.get('/{pid}')
def one(pid: int, db: Session = Depends(get_db), u: User = Depends(current_user)):
    authz.require_project(db, u, pid)
    return pdict(db, u, authz.get_project(db, pid))


@router.put('/{pid}')
def update(pid: int, d: ProjectUpdate, db: Session = Depends(get_db), u: User = Depends(require_roles('ADMIN'))):
    p = authz.get_project(db, pid)
    data = d.model_dump(exclude_unset=True)
    before = {k: getattr(p, k) for k in data}
    for k, v in data.items(): setattr(p, k, v)
    log(db, u.id, 'PROJECT', pid, 'EDIT', None, project_id=pid, before=before, after=data)
    db.commit()
    return pdict(db, u, p)


@router.post('/{pid}/archive')
def archive(pid: int, db: Session = Depends(get_db), u: User = Depends(require_roles('ADMIN'))):
    p = authz.get_project(db, pid)
    p.archived_at = p.archived_at or datetime.utcnow(); p.is_active = False
    log(db, u.id, 'PROJECT', pid, 'ARCHIVE', None, project_id=pid); db.commit()
    return pdict(db, u, p)


@router.post('/{pid}/activate')
def activate(pid: int, db: Session = Depends(get_db), u: User = Depends(require_roles('ADMIN'))):
    p = authz.get_project(db, pid)
    p.archived_at = None; p.is_active = True
    log(db, u.id, 'PROJECT', pid, 'ACTIVATE', None, project_id=pid); db.commit()
    return pdict(db, u, p)


@router.get('/{pid}/settings')
def get_project_settings(pid: int, db: Session = Depends(get_db), u: User = Depends(current_user)):
    authz.require_project(db, u, pid)
    return get_settings(authz.get_project(db, pid))


@router.put('/{pid}/settings')
def put_settings(pid: int, d: dict, db: Session = Depends(get_db), u: User = Depends(require_roles('ADMIN'))):
    p = authz.get_project(db, pid)
    try: data = validate_settings(d)
    except ValueError as e: raise HTTPException(400, str(e))
    before = get_settings(p)
    stored = json.loads(p.settings_json) if p.settings_json else {}
    stored.update(data)
    p.settings_json = json.dumps(stored)
    log(db, u.id, 'PROJECT', pid, 'SETTINGS', ','.join(sorted(data)), project_id=pid, before={k: before.get(k) for k in data}, after=data)
    db.commit()
    return get_settings(p)


@router.get('/{pid}/members')
def members(pid: int, include_revoked: bool = False, db: Session = Depends(get_db), u: User = Depends(current_user)):
    """Members of one project. Non-admin members see names and project roles only (no e-mail, no other projects)."""
    authz.require_project(db, u, pid)
    q = select(ProjectUser, User).join(User, User.id == ProjectUser.user_id).where(ProjectUser.project_id == pid)
    if not (include_revoked and authz.is_admin(u)): q = q.where(ProjectUser.status == 'ACTIVE')
    out = []
    for m, usr in db.execute(q.order_by(User.full_name)).all():
        role = authz.effective_role(m, usr)
        row = {'membership_id': m.id, 'user_id': usr.id, 'full_name': usr.full_name, 'role': role, 'role_label': authz.ROLE_LABELS.get(role, role),
               'category': authz.category(role), 'is_active': usr.is_active, 'legacy_role': m.role is None}
        if authz.is_admin(u): row.update(email=usr.email, status=m.status, revoked_at=m.revoked_at)
        out.append(row)
    return out


@router.post('/{pid}/members')
def add_member(pid: int, d: MemberIn, db: Session = Depends(get_db), u: User = Depends(require_roles('ADMIN'))):
    authz.get_project(db, pid)
    target = db.get(User, d.user_id)
    if not target: raise HTTPException(404, 'User not found')
    if d.role not in authz.PROJECT_ROLES: raise HTTPException(400, 'Invalid project role')
    if target.role == 'ADMIN': raise HTTPException(400, 'Administrators have system-wide access and do not need a project role')
    m = db.scalar(select(ProjectUser).where(ProjectUser.project_id == pid, ProjectUser.user_id == d.user_id))
    before = {'role': m.role, 'status': m.status} if m else None
    if m:
        m.role = d.role; m.status = 'ACTIVE'; m.revoked_at = None
    else:
        m = ProjectUser(project_id=pid, user_id=d.user_id, role=d.role, status='ACTIVE'); db.add(m)
    db.flush()
    log(db, u.id, 'MEMBERSHIP', m.id, 'SET_ROLE', f'user {d.user_id} -> {d.role}', project_id=pid, before=before, after={'role': d.role, 'status': 'ACTIVE'})
    db.commit()
    return {'ok': True, 'membership_id': m.id}


@router.delete('/{pid}/members/{user_id}')
def revoke_member(pid: int, user_id: int, db: Session = Depends(get_db), u: User = Depends(require_roles('ADMIN'))):
    """Revoke project access. Historical actions (reviews, decisions, audit) are kept (SRS 13.1)."""
    m = db.scalar(select(ProjectUser).where(ProjectUser.project_id == pid, ProjectUser.user_id == user_id, ProjectUser.status == 'ACTIVE'))
    if not m: raise HTTPException(404, 'Active membership not found')
    m.status = 'REVOKED'; m.revoked_at = datetime.utcnow()
    log(db, u.id, 'MEMBERSHIP', m.id, 'REVOKE', f'user {user_id}', project_id=pid, before={'status': 'ACTIVE', 'role': m.role}, after={'status': 'REVOKED'})
    db.commit()
    return {'ok': True}
