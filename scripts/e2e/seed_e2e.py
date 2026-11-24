"""Seed an ISOLATED test backend with synthetic data for browser testing (UI design v1).

Never point this at a real database: it refuses unless the API reports ENVIRONMENT test/development data and the
database name (checked by the operator) is a throwaway one. All names, numbers and dates are synthetic.

    python scripts/e2e/seed_e2e.py http://localhost:8001 admin@example.com 'E2eAdmin!2026x' > seed.json
"""
import json
import sys
import uuid
from datetime import date, datetime, timedelta
import httpx

BASE, ADMIN, ADMIN_PW = sys.argv[1], sys.argv[2], sys.argv[3]
PW = 'E2eUser!2026pass'
PDF = b'%PDF-1.4\n% synthetic test evidence\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n'
JPG = b'\xff\xd8\xff\xe0' + b'\x00' * 2048
c = httpx.Client(base_url=BASE, timeout=60)


def login(email, pw):
    r = c.post('/auth/login', json={'email': email, 'password': pw}, headers={'X-Auth-Mode': 'bearer'})
    r.raise_for_status()
    return {'Authorization': f'Bearer {r.json()["access_token"]}'}


def call(h, method, path, ok=(200,), **kw):
    r = c.request(method, path, headers=h, **kw)
    if r.status_code not in ok: raise SystemExit(f'{method} {path} -> {r.status_code} {r.text[:300]}')
    return r.json() if 'json' in r.headers.get('content-type', '') else r


def first_login(email, temp, final):
    h = login(email, temp)
    call(h, 'POST', '/me/password', json={'current_password': temp, 'new_password': final})
    return login(email, final)


run = uuid.uuid4().hex[:4].upper()
admin = first_login(ADMIN, ADMIN_PW, ADMIN_PW + 'x')
p = call(admin, 'POST', '/projects', json={'code': f'GBS-{run}', 'name': 'Sample Road Upgrading Project', 'contract_number': 'Contract II',
                                           'employer': 'Sample Roads Authority', 'consultant': 'Sample Consulting Engineers', 'contractor': 'Sample Contractor Ltd'})
pid = p['id']
users = {}
for key, name, role in [('re', 'R. Engineer', 'RE'), ('dre', 'D. Engineer', 'DRE'), ('wi', 'A. Inspector', 'WORK_INSPECTOR'), ('mi', 'B. Inspector', 'MATERIAL_INSPECTOR'),
                        ('me', 'C. Engineer', 'MATERIAL_ENGINEER'), ('qs', 'E. Surveyor', 'QUANTITY_SURVEYOR'), ('sec', 'F. Secretary', 'SECRETARY'),
                        ('enc', 'G. Encoder', 'DATA_ENCODER'), ('oe', 'H. Office Engineer', 'OFFICE_ENGINEER')]:
    email = f'{key}.{run.lower()}@example.com'
    u = call(admin, 'POST', '/users', json={'full_name': name, 'email': email, 'password': PW + 'tmp', 'role': 'VIEWER', 'memberships': [{'project_id': pid, 'role': role}]})
    users[key] = {'id': u['id'], 'email': email, 'name': name, 'h': first_login(email, PW + 'tmp', PW)}
# one deactivated account to show on the admin dashboard
x = call(admin, 'POST', '/users', json={'full_name': 'Z. Former', 'email': f'former.{run.lower()}@example.com', 'password': PW + 'tmp', 'role': 'VIEWER', 'memberships': [{'project_id': pid, 'role': 'SURVEYOR'}]})
call(admin, 'POST', f'/users/{x["id"]}/toggle-active')
H = {k: v['h'] for k, v in users.items()}


def batch(ref, rows, hours=48, submit=True):
    s = call(H['enc'], 'POST', '/rfi-summaries', json={'project_id': pid, 'summary_reference': ref, 'submission_date': date.today().isoformat(), 'contractor_rep_name': 'G. Encoder'})
    t = datetime.now() + timedelta(hours=hours)
    ids = []
    for i, (num, desc, frm, to, side, mat, item) in enumerate(rows):
        r = call(H['enc'], 'POST', '/rfis', json={'project_id': pid, 'summary_id': s['id'], 'rfi_number': num, 'work_item': item, 'contractor_request': desc,
                                                  'chainage_from': frm, 'chainage_to': to, 'side': side, 'material_source': mat, 'material_source_offset': '20 m',
                                                  'inspection_date': t.date().isoformat(), 'inspection_time': f'{8 + i:02d}:00', 'boq_item': '64.02(a)', 'inspection_order': 1,
                                                  'road_type': 'AC', 'fill_layer': 'Layer 2', 'material_source_type': 'Plant', 'work_categories': ['PV_WEARING']})
        ids.append(r['id'])
    if submit: call(H['enc'], 'POST', f'/rfi-summaries/{s["id"]}/submit', json={})
    return s['id'], ids


def assign(rid, keys):
    call(H['re'], 'POST', f'/rfis/{rid}/assignments', json={'assignments': [{'user_id': users[k]['id']} for k in keys]})


def active(h, rid):
    return call(h, 'GET', f'/rfis/{rid}')['permissions']['review_assignment_id']


def review(key, rid, comment, files=()):
    aid = active(H[key], rid)
    for name, data in files:
        call(H[key], 'POST', f'/evidence/assignments/{aid}/files', files={'file': (name, data)}, data={'upload_token': uuid.uuid4().hex})
    call(H[key], 'POST', f'/rfis/{rid}/review', json={'assignment_id': aid, 'comment': comment})


Y = date.today().year
# 1) completed with evidence and a final-disposition remark
_, (r1,) = batch(f'DOC01-{run}-024', [(f'AS-014/{Y}', 'Inspection for 50 mm asphalt surfacing', '187+325', '187+405', 'LHS', 'Plant A', 'Asphalt')])
assign(r1, ['wi', 'mi', 'me'])
review('wi', r1, 'Surface preparation inspected. Limits and levels checked at the requested chainage.', [('IMG_0910.jpg', JPG), ('Prior_Layer_FDT.pdf', PDF)])
review('mi', r1, 'Material source and test records checked.', [('mix_test.pdf', PDF)])
review('me', r1, 'Material compliance reviewed.', [('compliance.pdf', PDF)])
rem = call(H['re'], 'POST', '/evidence/remarks', json={'project_id': pid, 'rfi_id': r1, 'stage': 'FINAL_DISPOSITION'})
call(H['re'], 'POST', f'/evidence/remarks/{rem["id"]}/files', files={'file': ('site_note.pdf', PDF)}, data={'upload_token': uuid.uuid4().hex})
call(H['re'], 'POST', f'/rfis/{r1}/decision', json={'disposition_code': 'APPROVED_FURTHER_WORKS', 'comment': 'Proceed subject to recorded comments and conditions.', 'management_remark_id': rem['id']})
# 2) under review: work inspector active (for the inspector screens)
_, (r2, r3) = batch(f'DOC01-{run}-025', [(f'EW-021/{Y}', 'Subgrade preparation inspection', '190+020', '190+080', 'RHS', 'Borrow Pit 03', 'Subgrade'),
                                         (f'ST-006/{Y}', 'Reinforcement inspection', '156+300', '156+310', 'LHS', '—', 'Reinforcement')])
assign(r2, ['wi', 'mi', 'me'])
# 3) awaiting decision
assign(r3, ['mi'])
review('mi', r3, 'Reinforcement spacing and cover checked.', [('rebar.jpg', JPG)])
# 4) submitted batch with short notice, awaiting assignment
batch(f'DOC01-{run}-026', [(f'AS-015/{Y}', 'Inspection for tack coat', '188+000', '188+200', 'BHS', 'Plant A', 'Asphalt'),
                           (f'EW-022/{Y}', 'Embankment 3rd layer FDT', '191+100', '191+300', 'RHS', 'Borrow Pit 04', 'Embankment')], hours=10)
# 5) a draft batch for the contractor screens
d_sid, _ = batch(f'DOC01-{run}-027', [(f'CC-513/{Y}', 'Culvert concreting', '160+450', '160+460', 'Centre', 'Batch plant', 'Concrete')], submit=False)

out = {'project_id': pid, 'project_code': p['code'], 'password': PW, 'admin': {'email': ADMIN, 'password': ADMIN_PW + 'x'},
       'users': {k: {kk: vv for kk, vv in v.items() if kk != 'h'} for k, v in users.items()},
       'rfis': {'completed': r1, 'under_review': r2, 'awaiting_decision': r3}, 'draft_summary': d_sid}
print(json.dumps(out, indent=2))
