"""Category 1 System Admin: overview KPIs, project memberships, role catalogue and access-matrix export (UI design s.2)."""
import csv
import io
import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, Project, ProjectUser, RegisterView
from app.schemas import RegisterViewIn
from app.security import current_user, require_roles
from app import authz
from app.project_settings import get_settings
from app.services.audit import log

router = APIRouter(tags=['Administration'])

CATEGORY_LABELS = {'1': 'System Admin', '2.1': 'RE / DRE', '2.2': 'Inspectors', '2.3': 'Office', '3': 'Contractor'}
# Capability columns of the access matrix. Each is derived from the same rules the API enforces (app/authz.py, routers).
CAPABILITIES = [
    ('Create / submit DOC_01', lambda role, s: role in authz.CONTRACTOR),
    ('Request amendments', lambda role, s: role in authz.CONTRACTOR | authz.MANAGEMENT),
    ('Assign and sequence inspectors', lambda role, s: role in authz.MANAGEMENT),
    ('Management remarks + evidence (Cat. 2.1)', lambda role, s: role in authz.MANAGEMENT),
    ('Inspector review + evidence (Cat. 2.2)', lambda role, s: role in authz.INSPECTORS),
    ('Final disposition', lambda role, s: role in authz.MANAGEMENT),
    ('View DOC_02 register', lambda role, s: authz.can_view_register(role, s)),
    ('Export DOC_02', lambda role, s: authz.can_export(role, s)),
    ('See hidden fields I:M, S', lambda role, s: authz.category(role) in (s.get('hidden_field_categories') or [])),
    ('Open inspection evidence', lambda role, s: role in authz.MANAGEMENT | authz.OFFICE | authz.INSPECTORS or (role in authz.CONTRACTOR and bool(s.get('contractor_evidence_access')))),
    ('Acknowledge DOC_01 receipt', lambda role, s: role in authz.MANAGEMENT or role == 'SECRETARY'),
]
CAPABILITY_NOTES = {'Open inspection evidence': 'Inspectors: only RFIs on which they hold or held a turn.',
                    'View DOC_02 register': 'Inspectors: per project setting inspector_register_access.'}


@router.get('/admin/overview')
def overview(db: Session = Depends(get_db), _: User = Depends(require_roles('ADMIN'))):
    active_projects = db.scalar(select(func.count()).select_from(Project).where(Project.archived_at.is_(None), Project.is_active == True)) or 0
    archived = db.scalar(select(func.count()).select_from(Project).where(Project.archived_at.is_not(None))) or 0
    active_users = db.scalar(select(func.count()).select_from(User).where(User.is_active == True)) or 0
    inactive_users = db.scalar(select(func.count()).select_from(User).where(User.is_active == False)) or 0
    no_access = db.scalar(select(func.count()).select_from(User).where(User.role != 'ADMIN', User.is_active == True,
                                                                         ~User.id.in_(select(ProjectUser.user_id).where(ProjectUser.status == 'ACTIVE')))) or 0
    temp_pw = db.scalar(select(func.count()).select_from(User).where(User.is_active == True, User.must_change_password == True)) or 0
    memberships = db.scalar(select(func.count()).select_from(ProjectUser).where(ProjectUser.status == 'ACTIVE')) or 0
    return {'active_projects': active_projects, 'archived_projects': archived, 'active_accounts': active_users, 'inactive_accounts': inactive_users,
            'accounts_without_project': no_access, 'accounts_with_temporary_password': temp_pw, 'active_memberships': memberships,
            # No invitation workflow exists (decision UD-12). The count is not shown rather than invented.
            'invitations': {'implemented': False, 'pending': None, 'note': 'Invitation workflow pending client decision UD-12; accounts are created by the administrator.'}}


def _membership_rows(db, include_revoked=True):
    q = (select(ProjectUser, User, Project).join(User, User.id == ProjectUser.user_id).join(Project, Project.id == ProjectUser.project_id)
         .order_by(Project.code, User.full_name))
    if not include_revoked: q = q.where(ProjectUser.status == 'ACTIVE')
    out = []
    for m, u, p in db.execute(q).all():
        role = authz.effective_role(m, u)
        out.append({'membership_id': m.id, 'user_id': u.id, 'full_name': u.full_name, 'email': u.email, 'project_id': p.id, 'project_code': p.code,
                    'project_name': p.name, 'project_archived': p.archived_at is not None, 'role': role, 'role_label': authz.ROLE_LABELS.get(role, role or '—'),
                    'category': authz.category(role), 'category_label': CATEGORY_LABELS.get(authz.category(role) or '', '—'),
                    'membership_status': m.status, 'account_active': u.is_active, 'must_change_password': u.must_change_password,
                    'last_login_at': u.last_login_at, 'revoked_at': m.revoked_at, 'legacy_role': m.role is None})
    return out


@router.get('/admin/memberships')
def memberships(include_revoked: bool = True, db: Session = Depends(get_db), _: User = Depends(require_roles('ADMIN'))):
    return _membership_rows(db, include_revoked)


@router.get('/admin/roles')
def roles(_: User = Depends(current_user)):
    groups = [('2.1', authz.MANAGEMENT), ('2.2', authz.INSPECTORS), ('2.3', authz.OFFICE), ('3', authz.CONTRACTOR)]
    defaults = get_settings(None)
    out = [{'category': '1', 'label': CATEGORY_LABELS['1'], 'roles': [{'code': 'ADMIN', 'label': authz.ROLE_LABELS['ADMIN'], 'assignable': True,
            'capabilities': ['Projects, users, memberships, configuration, audit oversight', 'No inspector review or final-decision authority (DR-01)']}]}]
    for cat, codes in groups:
        out.append({'category': cat, 'label': CATEGORY_LABELS[cat], 'roles': [
            {'code': c, 'label': authz.ROLE_LABELS.get(c, c), 'assignable': c not in ('CONTRACTOR', 'SITE_ENGINEER'),
             'capabilities': [name for name, fn in CAPABILITIES if fn(c, defaults)]} for c in sorted(codes)]})
    return {'categories': out, 'capability_notes': CAPABILITY_NOTES, 'note': 'Capabilities shown with the default project settings. Project settings can change register, export, hidden-field and evidence access.'}


def _matrix(db):
    rows = []
    cache = {}
    for m in _membership_rows(db, include_revoked=False):
        if m['project_id'] not in cache: cache[m['project_id']] = get_settings(db.get(Project, m['project_id']))
        s = cache[m['project_id']]
        role = m['role']
        caps = [('Yes' if (role and fn(role, s) and m['account_active'] and not m['project_archived']) else 'No') for _, fn in CAPABILITIES]
        rows.append([m['project_code'], m['full_name'], m['email'], m['category'] or '', m['category_label'], m['role_label'],
                     'Active' if m['account_active'] else 'Deactivated', 'Archived (read-only)' if m['project_archived'] else 'Active', *caps])
    header = ['Project', 'User', 'E-mail', 'Category', 'Category name', 'Role', 'Account', 'Project status', *[c for c, _ in CAPABILITIES]]
    return header, rows


@router.get('/admin/access-matrix.xlsx')
def access_matrix_xlsx(db: Session = Depends(get_db), admin: User = Depends(require_roles('ADMIN'))):
    header, rows = _matrix(db)
    wb = Workbook(); ws = wb.active; ws.title = 'Access matrix'
    ws.append([f'RFIMS access matrix - generated {datetime.utcnow():%d/%m/%Y %H:%M} UTC by {admin.full_name}. Derived from project roles and project settings.'])
    ws.append(header)
    for c in ws[2]: c.font = Font(bold=True); c.fill = PatternFill('solid', fgColor='DDE6EF')
    for r in rows: ws.append(r)
    ws.freeze_panes = 'A3'; ws.auto_filter.ref = f'A2:{ws.cell(2, len(header)).column_letter}{len(rows) + 2}'
    for i, h in enumerate(header, 1): ws.column_dimensions[ws.cell(2, i).column_letter].width = max(12, min(34, len(h) + 2))
    ws2 = wb.create_sheet('Notes')
    for k, v in CAPABILITY_NOTES.items(): ws2.append([k, v])
    out = io.BytesIO(); wb.save(out)
    log(db, admin.id, 'SYSTEM', 0, 'EXPORT_ACCESS_MATRIX', f'{len(rows)} memberships', commit=True)
    return Response(out.getvalue(), media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    headers={'Content-Disposition': f'attachment; filename="access_matrix_{datetime.utcnow():%Y%m%d}.xlsx"'})


@router.get('/admin/access-matrix.csv')
def access_matrix_csv(db: Session = Depends(get_db), admin: User = Depends(require_roles('ADMIN'))):
    header, rows = _matrix(db)
    buf = io.StringIO(); w = csv.writer(buf); w.writerow(header); w.writerows(rows)
    log(db, admin.id, 'SYSTEM', 0, 'EXPORT_ACCESS_MATRIX', f'{len(rows)} memberships (csv)', commit=True)
    return Response(buf.getvalue(), media_type='text/csv', headers={'Content-Disposition': f'attachment; filename="access_matrix_{datetime.utcnow():%Y%m%d}.csv"'})


# ------------------------------------------------------------------------------- saved DOC_02 register views
def _view_out(v: RegisterView):
    return {'id': v.id, 'name': v.name, 'project_id': v.project_id, 'config': json.loads(v.config_json or '{}'), 'updated_at': v.updated_at}


ALLOWED_VIEW_KEYS = {'filters', 'sort', 'dir', 'columns', 'advanced', 'page_size'}


def _clean_config(cfg: dict) -> str:
    bad = set(cfg) - ALLOWED_VIEW_KEYS
    if bad: raise HTTPException(400, f'Unknown view settings: {", ".join(sorted(bad))}')
    txt = json.dumps(cfg)
    if len(txt) > 8000: raise HTTPException(400, 'View definition is too large')
    return txt


@router.get('/register-views')
def list_views(project_id: int | None = None, db: Session = Depends(get_db), u: User = Depends(current_user)):
    q = select(RegisterView).where(RegisterView.user_id == u.id)
    if project_id is not None: q = q.where((RegisterView.project_id == project_id) | RegisterView.project_id.is_(None))
    return [_view_out(v) for v in db.scalars(q.order_by(RegisterView.name))]


@router.post('/register-views')
def save_view(d: RegisterViewIn, db: Session = Depends(get_db), u: User = Depends(current_user)):
    name = d.name.strip()[:80]
    if not name: raise HTTPException(400, 'Name the view')
    if d.project_id is not None: authz.require_project(db, u, d.project_id)
    v = db.scalar(select(RegisterView).where(RegisterView.user_id == u.id, RegisterView.name == name,
                                             RegisterView.project_id == d.project_id if d.project_id is not None else RegisterView.project_id.is_(None)))
    if v is None:
        v = RegisterView(user_id=u.id, project_id=d.project_id, name=name, config_json='{}'); db.add(v)
    v.config_json = _clean_config(d.config); v.updated_at = datetime.utcnow()
    db.commit(); db.refresh(v)
    return _view_out(v)


@router.delete('/register-views/{vid}')
def delete_view(vid: int, db: Session = Depends(get_db), u: User = Depends(current_user)):
    v = db.get(RegisterView, vid)
    if not v or v.user_id != u.id: raise HTTPException(404, 'View not found')
    db.delete(v); db.commit()
    return {'ok': True}
