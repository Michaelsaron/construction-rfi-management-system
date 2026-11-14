"""Test harness. Runs ONLY against a throwaway database whose name ends in `_test`.

    TEST_DATABASE_URL=mysql+pymysql://root:<pw>@127.0.0.1:3307/rfi_test .venv/bin/pytest -q
"""
import os
import tempfile
import uuid
from datetime import date, datetime, timedelta
import pytest

URL = os.environ.get('TEST_DATABASE_URL', '')
if not URL or not URL.rsplit('/', 1)[-1].split('?')[0].endswith('_test'):
    raise SystemExit('Refusing to run: TEST_DATABASE_URL must point to a database whose name ends in "_test".')
os.environ.update(DATABASE_URL=URL, JWT_SECRET='test-secret-' + uuid.uuid4().hex, ENVIRONMENT='test', ADMIN_EMAIL='admin@example.com',
                  ADMIN_PASSWORD='Admin123!Test', UPLOAD_DIR=tempfile.mkdtemp(prefix='rfi_test_uploads_'), SMTP_HOST='')

from fastapi.testclient import TestClient  # noqa: E402
from app.database import Base, engine, SessionLocal  # noqa: E402
from app import models  # noqa: E402,F401
from app.security import hash_password  # noqa: E402

Base.metadata.drop_all(bind=engine)   # throwaway test database only (guarded above)
Base.metadata.create_all(bind=engine)

from app.main import app  # noqa: E402

PW = 'TestPass12345!'


@pytest.fixture(scope='session')
def client():
    with TestClient(app) as c:
        yield c


class Api:
    def __init__(self, client, token=None):
        self.c = client; self.token = token

    def h(self):
        return {'Authorization': f'Bearer {self.token}'} if self.token else {}

    def get(self, path, **kw): return self.c.get(path, headers=self.h(), **kw)
    def post(self, path, json=None, **kw): return self.c.post(path, json=json, headers=self.h(), **kw)
    def put(self, path, json=None, **kw): return self.c.put(path, json=json, headers=self.h(), **kw)
    def delete(self, path, **kw): return self.c.delete(path, headers=self.h(), **kw)


def login(client, email, pw=PW):
    r = client.post('/auth/login', json={'email': email, 'password': pw})
    assert r.status_code == 200, r.text
    return Api(client, r.json()['access_token'])


@pytest.fixture(scope='session')
def admin(client):
    return login(client, 'admin@example.com', 'Admin123!Test')


class World:
    """Two projects with a full cast of users on project A and a few on project B."""


@pytest.fixture(scope='session')
def world(client, admin):
    w = World()
    run = uuid.uuid4().hex[:6]
    def project(code):
        r = admin.post('/projects', {'code': f'{code}-{run}', 'name': f'{code} Road Project', 'employer': 'Employer X', 'consultant': 'Consultant Y', 'contractor': 'Contractor Z'})
        assert r.status_code == 200, r.text
        return r.json()['id']
    w.A = project('PA'); w.B = project('PB')
    def user(key, memberships):
        email = f'{key}.{run}@test.io'
        r = admin.post('/users', {'full_name': key.replace('_', ' ').title(), 'email': email, 'password': PW, 'role': 'VIEWER',
                                  'memberships': [{'project_id': p, 'role': ro} for p, ro in memberships]})
        assert r.status_code == 200, r.text
        api = login(client, email); api.id = r.json()['id']
        setattr(w, key, api)
        return api
    user('re', [(w.A, 'RE')]); user('are', [(w.A, 'DRE')]); user('dre', [(w.A, 'DRE')])
    # 'are' mirrors the live client account: role code ARE stored before the DRE rename (DR-02).
    # ARE can no longer be assigned through the API, so the legacy code is written directly.
    from sqlalchemy import update
    from app.database import SessionLocal
    from app.models import User, ProjectUser
    with SessionLocal() as db:
        db.execute(update(User).where(User.id == w.are.id).values(role='ARE'))
        db.execute(update(ProjectUser).where(ProjectUser.user_id == w.are.id).values(role='ARE'))
        db.commit()
    user('surveyor', [(w.A, 'SURVEYOR')]); user('wi', [(w.A, 'WORK_INSPECTOR')]); user('me_eng', [(w.A, 'MATERIAL_ENGINEER')])
    user('si', [(w.A, 'STRUCTURE_INSPECTOR')])
    user('qs', [(w.A, 'QUANTITY_SURVEYOR')]); user('secretary', [(w.A, 'SECRETARY')])
    user('encoder', [(w.A, 'DATA_ENCODER')]); user('office_eng', [(w.A, 'OFFICE_ENGINEER')])
    user('re_b', [(w.B, 'RE')]); user('encoder_b', [(w.B, 'DATA_ENCODER')]); user('surveyor_b', [(w.B, 'SURVEYOR')])
    user('outsider', [])
    w.run = run
    return w


def future(hours=48):
    from app.services.workflow import site_now
    t = site_now() + timedelta(hours=hours)
    return t.date().isoformat(), t.strftime('%H:%M')


def make_batch(api, project_id, n=1, prefix='T', hours=48, extra=None):
    ref = f'DRS-{uuid.uuid4().hex[:8]}'
    s = api.post('/rfi-summaries', {'project_id': project_id, 'summary_reference': ref, 'submission_date': date.today().isoformat()})
    assert s.status_code == 200, s.text
    sid = s.json()['id']
    d, t = future(hours)
    ids = []
    for i in range(n):
        body = {'project_id': project_id, 'summary_id': sid, 'rfi_number': f'{prefix}-{uuid.uuid4().hex[:6]}/2026', 'work_item': 'Embankment',
                'contractor_request': f'Inspection and FDT for embankment layer {i + 1}', 'chainage_from': '188+650', 'chainage_to': '188+870', 'side': 'FW',
                'material_source': '186+380&186+160 RHS', 'material_source_offset': '50m & 300', 'inspection_date': d, 'inspection_time': t,
                'boq_item': '64.02(a)', 'inspection_order': 1, 'work_categories': ['EW_EARTHWORKS', 'GPS_LEVEL_ROADBED'], 'enclosure_sheets': 2}
        if extra: body.update(extra)
        r = api.post('/rfis', body)
        assert r.status_code == 200, r.text
        ids.append(r.json()['id'])
    return sid, ids


def submitted_batch(api, project_id, n=1, **kw):
    sid, ids = make_batch(api, project_id, n, **kw)
    r = api.post(f'/rfi-summaries/{sid}/submit', {})
    assert r.status_code == 200, r.text
    return sid, ids


def assign(re, rid, inspectors, reason=None):
    return re.post(f'/rfis/{rid}/assignments', {'assignments': [{'user_id': i.id} for i in inspectors], 'reason': reason})


def active_assignment(api, rid):
    d = api.get(f'/rfis/{rid}').json()
    return d['permissions']['review_assignment_id']


def review(api, rid, comment='Checked on site - satisfactory'):
    aid = active_assignment(api, rid)
    if aid is None:
        mine = [a for a in api.get(f'/rfis/{rid}').json()['assignments'] if a['user_id'] == api.id and a['status'] != 'REPLACED']
        aid = mine[0]['id'] if mine else 0
    return api.post(f'/rfis/{rid}/review', {'assignment_id': aid, 'comment': comment})


def legacy_rfi(project_id, number, legacy_status='Not Ready', decision='ON_PROGRESS'):
    db = SessionLocal()
    try:
        admin_id = db.query(models.User).filter_by(email='admin@example.com').one().id
        r = models.Rfi(project_id=project_id, rfi_number=number, revision_no=0, work_item='Embankment', description='Legacy imported record',
                       contractor_request='historical', workflow_status='COMPLETED', current_decision=decision, record_state='ACTIVE',
                       remarks=f'| Legacy status: {legacy_status}', legacy_rfi_status=legacy_status, provenance='LEGACY_IMPORT', created_by=admin_id,
                       inspection_date=date(2024, 7, 15), inspection_time_text='8.00am')
        db.add(r); db.commit(); return r.id
    finally:
        db.close()
