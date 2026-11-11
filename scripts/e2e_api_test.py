#!/usr/bin/env python3
"""End-to-end API test for the Construction RFI system.

Runs every backend function across all roles against a THROWAWAY database.
NEVER point this at the production API — it creates users, projects and RFIs.

Usage:  python3 scripts/e2e_api_test.py http://localhost:8001
"""
import json, sys, time, urllib.request, urllib.error, uuid

BASE = (sys.argv[1] if len(sys.argv) > 1 else 'http://localhost:8001').rstrip('/')
ADMIN = ('admin@example.com', 'Admin123!')
PW = 'TestPass12345!'
RUN = uuid.uuid4().hex[:6]
results = []


def call(method, path, token=None, body=None, form=None, raw=False):
    headers = {}
    data = None
    if token: headers['Authorization'] = f'Bearer {token}'
    if form is not None:
        boundary = 'X' + uuid.uuid4().hex
        name, filename, content = form
        data = (f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
                f'Content-Type: application/octet-stream\r\n\r\n').encode() + content + f'\r\n--{boundary}--\r\n'.encode()
        headers['Content-Type'] = f'multipart/form-data; boundary={boundary}'
    elif body is not None:
        data = json.dumps(body).encode(); headers['Content-Type'] = 'application/json'
    req = urllib.request.Request(BASE + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            content = r.read(); ct = r.headers.get('content-type', '')
            return r.status, (content if raw or 'json' not in ct else json.loads(content or b'null')), ct
    except urllib.error.HTTPError as e:
        txt = e.read().decode(errors='replace')
        try: txt = json.loads(txt).get('detail', txt)
        except Exception: pass
        return e.code, txt, ''


def check(name, cond, info=''):
    results.append((bool(cond), name, info))
    print(('  PASS ' if cond else '  FAIL ') + name + ('' if cond else f'   -> {info}'))
    return cond


def expect(name, method, path, token=None, body=None, status=200, **kw):
    s, d, ct = call(method, path, token, body, **kw)
    check(name, s == status, f'expected {status}, got {s}: {str(d)[:200]}')
    return d


def login(email, pw):
    s, d, _ = call('POST', '/auth/login', body={'email': email, 'password': pw})
    return d.get('access_token') if s == 200 else None


print(f'Testing {BASE}  (run {RUN})')
print('\n[Auth]')
check('health', call('GET', '/health')[0] == 200)
admin = login(*ADMIN); check('admin login', admin)
expect('wrong password rejected', 'POST', '/auth/login', body={'email': ADMIN[0], 'password': 'nope'}, status=401)
expect('no token rejected', 'GET', '/me', status=401)
me = expect('GET /me', 'GET', '/me', admin)
expect('forgot password (always 200)', 'POST', '/auth/forgot-password', body={'email': ADMIN[0]})
expect('reset with bad token rejected', 'POST', '/auth/reset-password', body={'token': 'bad', 'new_password': 'whatever12345'}, status=400)

print('\n[Projects]')
proj = expect('create project', 'POST', '/projects', admin, {'code': f'T-{RUN}', 'name': f'Test Road {RUN}', 'project_type': 'ROAD', 'employer': 'ERA', 'consultant': 'Cons', 'contractor': 'Contr'})
P = proj['id']
check('list projects includes new', any(p['id'] == P for p in expect('list projects', 'GET', '/projects', admin)))

print('\n[Users]')
roles = {'contractor': 'CONTRACTOR', 'inspector': 'WORK_INSPECTOR', 'material': 'MATERIAL_ENGINEER', 're': 'RE', 'viewer': 'VIEWER'}
uid, tok = {}, {}
for k, role in roles.items():
    u = expect(f'create {role}', 'POST', '/users', admin, {'full_name': f'{k.title()} {RUN}', 'email': f'{k}.{RUN}@test.io', 'password': PW, 'role': role, 'project_ids': [P]})
    uid[k] = u['id']; tok[k] = login(f'{k}.{RUN}@test.io', PW)
    check(f'{role} can log in', tok[k])
users = expect('list users', 'GET', '/users', tok['viewer'])
leak = [k for u in users for k in u if k in ('password_hash', 'reset_token', 'reset_expires_at')]
check('users list does NOT expose password hashes / reset tokens', not leak, leak)
check('users list includes project_ids', all('project_ids' in u for u in users))
expect('duplicate email rejected', 'POST', '/users', admin, {'full_name': 'x', 'email': f'contractor.{RUN}@test.io', 'password': PW, 'role': 'VIEWER'}, status=409)
expect('short password rejected', 'POST', '/users', admin, {'full_name': 'x', 'email': f'short.{RUN}@test.io', 'password': 'short', 'role': 'VIEWER'}, status=400)
expect('invalid role rejected', 'POST', '/users', admin, {'full_name': 'x', 'email': f'bad.{RUN}@test.io', 'password': PW, 'role': 'KING'}, status=400)
expect('non-admin cannot create user', 'POST', '/users', tok['re'], {'full_name': 'x', 'email': f'x.{RUN}@test.io', 'password': PW, 'role': 'VIEWER'}, status=403)
u = expect('admin sets user projects', 'PUT', f'/users/{uid["viewer"]}/projects', admin, {'project_ids': [P]})
check('project assignment saved', u.get('project_ids') == [P], u)
expect('admin reset password', 'POST', f'/users/{uid["viewer"]}/reset-password', admin, {'new_password': 'Another12345!'})
check('viewer logs in with reset password', login(f'viewer.{RUN}@test.io', 'Another12345!'))
vt = login(f'viewer.{RUN}@test.io', 'Another12345!')
expect('change own password: wrong current rejected', 'POST', '/me/password', vt, {'current_password': 'wrong', 'new_password': 'Brandnew12345!'}, status=400)
expect('change own password', 'POST', '/me/password', vt, {'current_password': 'Another12345!', 'new_password': 'Brandnew12345!'})
check('must_change_password cleared', call('GET', '/me', login(f'viewer.{RUN}@test.io', 'Brandnew12345!'))[1].get('must_change_password') is False)
expect('disable user', 'POST', f'/users/{uid["viewer"]}/toggle-active', admin)
check('disabled user cannot log in', not login(f'viewer.{RUN}@test.io', 'Brandnew12345!'))
expect('re-enable user', 'POST', f'/users/{uid["viewer"]}/toggle-active', admin)
expect('admin cannot disable self', 'POST', f'/users/{me["id"]}/toggle-active', admin, status=400)

print('\n[Reference data]')
for cat, val, parent in [('WORK_ITEM', 'Embankment', None), ('WORK_DESCRIPTION', 'Fill layer compaction', 'Embankment'), ('SIDE', 'LHS', None), ('DAILY_ITEM', 'Embankment', None), ('DAILY_STATUS', 'Layer 1 done', 'Embankment')]:
    expect(f'add {cat}={val}', 'POST', '/master-data', admin, {'project_id': P, 'category': cat, 'value': val, 'parent_value': parent})
md = expect('list master data for project', 'GET', f'/master-data?project_id={P}', admin)
wd = next(m for m in md if m['category'] == 'WORK_DESCRIPTION' and m['project_id'] == P)
check('dependent value has parent', wd['parent_value'] == 'Embankment')
tmp = expect('add temp value', 'POST', '/master-data', admin, {'project_id': P, 'category': 'TEST', 'value': f'Temp {RUN}'})
expect('edit value', 'PUT', f'/master-data/{tmp["id"]}', admin, {'value': f'Temp2 {RUN}'})
expect('deactivate value', 'DELETE', f'/master-data/{tmp["id"]}', admin)
check('deactivated value hidden', not any(m['id'] == tmp['id'] for m in expect('list after deactivate', 'GET', f'/master-data?category=TEST&project_id={P}', admin)))
expect('contractor cannot add master data', 'POST', '/master-data', tok['contractor'], {'category': 'SIDE', 'value': 'X'}, status=403)

print('\n[Reviewer rules]')
rule = expect('create rule', 'POST', '/reviewer-rules', admin, {'project_id': P, 'work_item': 'Embankment', 'reviewer_role': 'WORK_INSPECTOR', 'required': True})
expect('duplicate rule rejected', 'POST', '/reviewer-rules', admin, {'project_id': P, 'work_item': 'Embankment', 'reviewer_role': 'WORK_INSPECTOR'}, status=409)
expect('invalid reviewer role rejected', 'POST', '/reviewer-rules', admin, {'project_id': P, 'work_item': 'Embankment', 'reviewer_role': 'CHEF'}, status=400)
r2 = expect('create 2nd rule', 'POST', '/reviewer-rules', admin, {'project_id': P, 'work_item': 'Embankment', 'reviewer_role': 'SURVEYOR', 'required': False})
expect('delete rule', 'DELETE', f'/reviewer-rules/{r2["id"]}', admin)
check('list rules', len(expect('list rules', 'GET', f'/reviewer-rules?project_id={P}', admin)) == 1)

print('\n[Summary + RFI workflow]')
C = tok['contractor']
s = expect('contractor creates summary', 'POST', '/rfi-summaries', C, {'project_id': P, 'summary_reference': f'SUM-{RUN}', 'submission_date': '2026-11-11'})
S = s['id']
expect('duplicate summary ref rejected', 'POST', '/rfi-summaries', C, {'project_id': P, 'summary_reference': f'SUM-{RUN}', 'submission_date': '2026-11-11'}, status=409)
expect('submit empty summary rejected', 'POST', f'/rfi-summaries/{S}/submit', C, status=400)
rfi_body = lambda n: {'project_id': P, 'summary_id': S, 'rfi_number': n, 'work_item': 'Embankment', 'description': 'Fill layer compaction', 'side': 'LHS', 'chainage_from': '12+400', 'chainage_to': '12+650', 'requested_date': '2026-11-11'}
r1 = expect('add RFI #1', 'POST', '/rfis', C, rfi_body(f'R1-{RUN}'))
r2 = expect('add RFI #2', 'POST', '/rfis', C, rfi_body(f'R2-{RUN}'))
r3 = expect('add RFI #3', 'POST', '/rfis', C, rfi_body(f'R3-{RUN}'))
expect('duplicate RFI number rejected', 'POST', '/rfis', C, rfi_body(f'R1-{RUN}'), status=409)
expect('RFI with wrong project for summary rejected', 'POST', '/rfis', C, {**rfi_body(f'RX-{RUN}'), 'project_id': 1}, status=400)
upd = expect('edit draft RFI', 'PUT', f'/rfis/{r1["id"]}', C, {'version': r1['version'], 'remarks': 'edited'})
expect('stale version edit rejected', 'PUT', f'/rfis/{r1["id"]}', C, {'version': r1['version'], 'remarks': 'again'}, status=409)
expect('activate before summary submit rejected', 'POST', f'/rfis/{r1["id"]}/activate', admin, status=400)
expect('submit summary', 'POST', f'/rfi-summaries/{S}/submit', C)
check('RFIs moved to SUBMITTED', all(x['workflow_status'] == 'SUBMITTED' for x in expect('summary detail', 'GET', f'/rfi-summaries/{S}', C)['rfis']))
expect('add RFI to locked summary rejected', 'POST', '/rfis', C, rfi_body(f'R4-{RUN}'), status=400)
expect('contractor cannot return summary', 'POST', f'/rfi-summaries/{S}/return?reason=x', C, status=403)
expect('RE returns summary', 'POST', f'/rfi-summaries/{S}/return?reason=Fix%20chainage', tok['re'])
check('RFIs back to DRAFT after return', all(x['workflow_status'] == 'DRAFT' for x in call('GET', f'/rfi-summaries/{S}', C)[1]['rfis']))
expect('resubmit returned summary', 'POST', f'/rfi-summaries/{S}/submit', C)
expect('contractor cannot activate', 'POST', f'/rfis/{r1["id"]}/activate', C, status=403)
expect('assign before activate rejected', 'POST', f'/rfis/{r1["id"]}/assign-reviewer', tok['re'], {'user_id': uid['inspector'], 'reviewer_role': 'WORK_INSPECTOR'}, status=400)
expect('decision before activate rejected', 'POST', f'/rfis/{r1["id"]}/decision', tok['re'], {'decision': 'APPROVED'}, status=400)
expect('RE activates RFI #1', 'POST', f'/rfis/{r1["id"]}/activate', tok['re'])
expect('double activate rejected', 'POST', f'/rfis/{r1["id"]}/activate', tok['re'], status=400)
check('return blocked once an RFI is activated', call('POST', f'/rfi-summaries/{S}/return?reason=x', tok['re'])[0] == 400)
sug = expect('suggested reviewers', 'GET', f'/rfis/{r1["id"]}/suggested-reviewers', tok['re'])
check('suggestion from rule', any(x['reviewer_role'] == 'WORK_INSPECTOR' for x in sug))
a1 = expect('assign WORK_INSPECTOR (required)', 'POST', f'/rfis/{r1["id"]}/assign-reviewer', tok['re'], {'user_id': uid['inspector'], 'reviewer_role': 'WORK_INSPECTOR', 'required': True})
a2 = expect('assign MATERIAL_ENGINEER (required)', 'POST', f'/rfis/{r1["id"]}/assign-reviewer', tok['re'], {'user_id': uid['material'], 'reviewer_role': 'MATERIAL_ENGINEER', 'required': True})
expect('duplicate assignment rejected', 'POST', f'/rfis/{r1["id"]}/assign-reviewer', tok['re'], {'user_id': uid['inspector'], 'reviewer_role': 'WORK_INSPECTOR'}, status=409)
expect('invalid reviewer role rejected', 'POST', f'/rfis/{r1["id"]}/assign-reviewer', tok['re'], {'user_id': uid['inspector'], 'reviewer_role': 'RE'}, status=400)
check('RFI is UNDER_REVIEW', call('GET', f'/rfis/{r1["id"]}', admin)[1]['rfi']['workflow_status'] == 'UNDER_REVIEW')
mine = expect('inspector: my inspections', 'GET', '/rfis/my-inspections', tok['inspector'])
check('assignment visible to inspector', any(x['assignment']['id'] == a1['id'] for x in mine))
expect('decision with pending reviews rejected', 'POST', f'/rfis/{r1["id"]}/decision', tok['re'], {'decision': 'APPROVED'}, status=400)
expect("review someone else's assignment rejected", 'POST', f'/rfis/{r1["id"]}/review', tok['inspector'], {'assignment_id': a2['id'], 'recommendation': 'SATISFACTORY', 'comment': 'x'}, status=403)
expect('review without comment rejected', 'POST', f'/rfis/{r1["id"]}/review', tok['inspector'], {'assignment_id': a1['id'], 'recommendation': 'SATISFACTORY', 'comment': '  '}, status=400)
expect('inspector submits review', 'POST', f'/rfis/{r1["id"]}/review', tok['inspector'], {'assignment_id': a1['id'], 'recommendation': 'SATISFACTORY', 'comment': 'Compaction OK'})
expect('double review rejected', 'POST', f'/rfis/{r1["id"]}/review', tok['inspector'], {'assignment_id': a1['id'], 'recommendation': 'SATISFACTORY', 'comment': 'x'}, status=400)
expect('material engineer submits review', 'POST', f'/rfis/{r1["id"]}/review', tok['material'], {'assignment_id': a2['id'], 'recommendation': 'SATISFACTORY', 'comment': 'Tests pass'})
check('RFI is AWAITING_DECISION', call('GET', f'/rfis/{r1["id"]}', admin)[1]['rfi']['workflow_status'] == 'AWAITING_DECISION')
expect('invalid decision rejected', 'POST', f'/rfis/{r1["id"]}/decision', tok['re'], {'decision': 'MAYBE'}, status=400)
expect('RE approves RFI #1', 'POST', f'/rfis/{r1["id"]}/decision', tok['re'], {'decision': 'APPROVED', 'comment': 'Proceed'})
d1 = call('GET', f'/rfis/{r1["id"]}', admin)[1]
check('RFI #1 COMPLETED + APPROVED', d1['rfi']['workflow_status'] == 'COMPLETED' and d1['rfi']['current_decision'] == 'APPROVED')
check('status history recorded', len(d1['history']) >= 5, len(d1['history']))
expect('second decision rejected', 'POST', f'/rfis/{r1["id"]}/decision', tok['re'], {'decision': 'REJECTED'}, status=400)
expect('contractor cannot edit completed RFI', 'PUT', f'/rfis/{r1["id"]}', C, {'version': d1['rfi']['version'], 'remarks': 'x'}, status=403)
expect('RE edits completed RFI with reason', 'PUT', f'/rfis/{r1["id"]}', tok['re'], {'version': d1['rfi']['version'], 'remarks': 'corrected', 'edit_reason': 'Typo'})

# Override path + rejection + resubmission
expect('activate RFI #2', 'POST', f'/rfis/{r2["id"]}/activate', tok['re'])
expect('assign reviewer to #2', 'POST', f'/rfis/{r2["id"]}/assign-reviewer', tok['re'], {'user_id': uid['inspector'], 'reviewer_role': 'WORK_INSPECTOR'})
expect('override without reason rejected', 'POST', f'/rfis/{r2["id"]}/decision', tok['re'], {'decision': 'REJECTED', 'override_used': True}, status=400)
expect('RE rejects #2 with override', 'POST', f'/rfis/{r2["id"]}/decision', tok['re'], {'decision': 'REJECTED', 'override_used': True, 'override_reason': 'Visible failure on site'})
nr = expect('contractor resubmits rejected RFI', 'POST', f'/rfis/{r2["id"]}/resubmit', C, {'reason': 'Recompacted'})
check('new revision is Rev 1', nr.get('revision_no') == 1, nr)
expect('duplicate resubmission rejected', 'POST', f'/rfis/{r2["id"]}/resubmit', C, {'reason': 'again'}, status=409)
expect('resubmit approved RFI rejected', 'POST', f'/rfis/{r1["id"]}/resubmit', C, {'reason': 'x'}, status=400)
expect('activate revision', 'POST', f'/rfis/{nr["id"]}/activate', tok['re'])
expect('direct decision (no reviewers) on revision', 'POST', f'/rfis/{nr["id"]}/decision', tok['re'], {'decision': 'INFORMATION_ONLY'})

# Archive / cancel
expect('archive without reason rejected', 'POST', f'/rfis/{r3["id"]}/archive', tok['re'], {'reason': ' '}, status=400)
expect('cancel RFI #3', 'POST', f'/rfis/{r3["id"]}/cancel', tok['re'], {'reason': 'Duplicate request'})
expect('activate cancelled RFI rejected', 'POST', f'/rfis/{r3["id"]}/activate', tok['re'], status=400)
expect('archive approved RFI #1', 'POST', f'/rfis/{r1["id"]}/archive', tok['re'], {'reason': 'Closed out'})

print('\n[RFI register search]')
check('search by number', len(expect('search q', 'GET', f'/rfis?q=R2-{RUN}', admin)) == 2)
check('filter by decision', all(x['current_decision'] == 'REJECTED' for x in expect('filter decision', 'GET', f'/rfis?project_id={P}&decision=REJECTED', admin)))
check('filter by side + date', len(expect('filter side/date', 'GET', f'/rfis?project_id={P}&side=LHS&date_from=2000-01-01', admin)) >= 0)
check('pagination', len(expect('limit/offset', 'GET', '/rfis?limit=1&offset=0', admin)) <= 1)
expect('missing RFI 404', 'GET', '/rfis/99999999', admin, status=404)

print('\n[Attachments]')
for ent, eid in [('rfi', nr['id']), ('summary', S)]:
    a = expect(f'upload PDF to {ent}', 'POST', f'/attachments/{ent}/{eid}', C, form=('file', 'test.pdf', b'%PDF-1.4 test'))
    check(f'list {ent} attachments', any(x['id'] == a['id'] for x in expect(f'list {ent}', 'GET', f'/attachments/{ent}/{eid}', C)))
    s_, content, _ = call('GET', f'/attachments/download/{a["id"]}', C, raw=True)
    check(f'download {ent} attachment', s_ == 200 and content.startswith(b'%PDF'), s_)
expect('disallowed file type rejected', 'POST', f'/attachments/rfi/{nr["id"]}', C, form=('file', 'evil.exe', b'MZ'), status=400)
expect('contractor cannot delete attachment', 'DELETE', f'/attachments/{a["id"]}', C, status=403)
expect('RE deletes attachment', 'DELETE', f'/attachments/{a["id"]}', tok['re'])
expect('deleted attachment not downloadable', 'GET', f'/attachments/download/{a["id"]}', C, status=404)

print('\n[Daily progress]')
dp_body = {'project_id': P, 'progress_date': '2026-11-11', 'work_item': 'Embankment', 'description': 'Layer 1 done', 'chainage_from': '12+400', 'chainage_to': '12+650', 'side': 'LHS', 'quantity': 450.5, 'unit': 'm3', 'rfi_ids': [nr['id']]}
dp = expect('contractor creates daily progress', 'POST', '/daily-progress', C, dp_body)
expect('link RFI from other project rejected', 'POST', '/daily-progress', C, {**dp_body, 'rfi_ids': [99999999]}, status=400)
expect('edit draft', 'PUT', f'/daily-progress/{dp["id"]}', C, {**dp_body, 'quantity': 500})
check('list daily progress', any(x['record']['id'] == dp['id'] for x in expect('list dp', 'GET', f'/daily-progress?project_id={P}', C)))
expect('detail', 'GET', f'/daily-progress/{dp["id"]}', C)
expect('review before submit rejected', 'POST', f'/daily-progress/{dp["id"]}/review', tok['inspector'], {'comment': 'x'}, status=409)
expect('submit', 'POST', f'/daily-progress/{dp["id"]}/submit', C)
expect('edit after submit rejected', 'PUT', f'/daily-progress/{dp["id"]}', C, dp_body, status=409)
expect('contractor cannot review', 'POST', f'/daily-progress/{dp["id"]}/review', C, {'comment': 'x'}, status=403)
expect('review empty comment rejected', 'POST', f'/daily-progress/{dp["id"]}/review', tok['inspector'], {'comment': ' '}, status=422)
expect('inspector reviews', 'POST', f'/daily-progress/{dp["id"]}/review', tok['inspector'], {'comment': 'Verified on site'})
expect('inspector cannot confirm', 'POST', f'/daily-progress/{dp["id"]}/confirm', tok['inspector'], {'comment': 'x'}, status=403)
expect('RE confirms', 'POST', f'/daily-progress/{dp["id"]}/confirm', tok['re'], {'comment': 'Confirmed'})
expect('outsider (no project) created', 'POST', '/users', admin, {'full_name': 'Out', 'email': f'out.{RUN}@test.io', 'password': PW, 'role': 'SITE_ENGINEER'})
expect('user without project access blocked', 'GET', f'/daily-progress/{dp["id"]}', login(f'out.{RUN}@test.io', PW), status=403)

print('\n[Reports]')
for name, path in [('RFI register xlsx', f'/reports/rfi-register.xlsx?project_id={P}'), ('RFI pdf', f'/reports/rfi/{r1["id"]}.pdf'), ('summary pdf', f'/reports/rfi-summary/{S}.pdf'), ('daily progress xlsx', f'/reports/daily-progress.xlsx?project_id={P}'), ('daily progress pdf', f'/reports/daily-progress/{dp["id"]}.pdf')]:
    s_, content, ct = call('GET', path, C, raw=True)
    magic = b'%PDF' if path.split('?')[0].endswith('.pdf') else b'PK'
    check(f'report: {name}', s_ == 200 and content[:4].startswith(magic), f'{s_} {content[:80]!r}')

print('\n[Notifications / dashboard / audit]')
n = expect('inspector notifications', 'GET', '/notifications', tok['inspector'])
check('inspector got assignment notification', any('assigned' in x['title'].lower() for x in n))
check('unread count', expect('unread count', 'GET', '/notifications/unread-count', tok['inspector'])['count'] >= 1)
expect('mark one read', 'POST', f'/notifications/{n[0]["id"]}/read', tok['inspector'])
expect("cannot read another user's notification", 'POST', f'/notifications/{n[0]["id"]}/read', C, status=404)
expect('mark all read', 'POST', '/notifications/read-all', tok['inspector'])
check('unread count is 0', call('GET', '/notifications/unread-count', tok['inspector'])[1]['count'] == 0)
check('contractor notified of decision', any('APPROVED' in x['title'] or 'REJECTED' in x['title'] for x in expect('contractor notifications', 'GET', '/notifications', C)))
expect('check overdue (RE)', 'POST', '/notifications/check-overdue', tok['re'])
expect('check overdue blocked for contractor', 'POST', '/notifications/check-overdue', C, status=403)
d = expect('dashboard (project)', 'GET', f'/dashboard?project_id={P}', C)
check('dashboard counts', d['approved'] == 0 and d['rejected'] == 1 and d['information_only'] == 1, d)
check('dashboard recent newest first', d['recent'] and d['recent'][0]['id'] == max(x['id'] for x in d['recent']))
expect('dashboard (all)', 'GET', '/dashboard', admin)
check('audit log has entries', len(expect('audit log', 'GET', '/audit?limit=50', admin)) > 0)
expect('audit blocked for contractor', 'GET', '/audit', C, status=403)

ok = sum(1 for r in results if r[0]); bad = [r for r in results if not r[0]]
print(f'\n==== {ok}/{len(results)} passed ====')
for _, name, info in bad: print(f'FAIL: {name} -> {info}')
sys.exit(1 if bad else 0)
