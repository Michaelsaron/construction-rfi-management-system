"""SRS v1.0 acceptance tests UAT-01 ... UAT-12 (section 15) plus the related business rules."""
import hashlib
import io
from pathlib import Path
from openpyxl import load_workbook
from pypdf import PdfReader
from app.config import settings
from app.database import SessionLocal
from app import models
from conftest import make_batch, submitted_batch, assign, review, active_assignment, future, legacy_rfi, login, PW


def pdf_text(content: bytes) -> str:
    return '\n'.join(p.extract_text() or '' for p in PdfReader(io.BytesIO(content)).pages)


# ---------------------------------------------------------------- UAT-01
def test_uat01_admin_creates_project_and_assigns_project_roles(admin, world, client):
    me = world.re.get('/me').json()
    assert [(m['project_id'], m['role'], m['category']) for m in me['memberships']] == [(world.A, 'RE', '2.1')]
    assert world.encoder.get('/me').json()['memberships'][0]['category'] == '3'
    assert world.qs.get('/me').json()['memberships'][0]['category'] == '2.3'
    # only admin creates projects / users / memberships (FR-03)
    assert world.re.post('/projects', {'code': 'X', 'name': 'X'}).status_code == 403
    assert world.re.post('/users', {'full_name': 'x', 'email': 'x@x.io', 'password': PW}).status_code == 403
    assert world.re.post(f'/projects/{world.A}/members', {'user_id': world.outsider.id, 'role': 'RE'}).status_code == 403
    # edit / archive / activate (FR-01)
    assert admin.put(f'/projects/{world.B}', {'contract_number': 'C-II'}).json()['contract_number'] == 'C-II'
    assert admin.post(f'/projects/{world.B}/archive').json()['status'] == 'ARCHIVED'
    r = world.encoder_b.post('/rfi-summaries', {'project_id': world.B, 'summary_reference': 'arch', 'submission_date': '2026-11-14'})
    assert r.status_code == 409  # archived project is read-only
    assert admin.post(f'/projects/{world.B}/activate').json()['status'] == 'ACTIVE'
    # a user only sees projects they belong to
    assert [p['id'] for p in world.re.get('/projects').json()] == [world.A]
    assert world.outsider.get('/projects').json() == []


def test_role_must_be_valid_and_admin_has_no_project_role(admin, world):
    assert admin.post(f'/projects/{world.A}/members', {'user_id': world.outsider.id, 'role': 'KING'}).status_code == 400
    admin_id = admin.get('/me').json()['id']
    assert admin.post(f'/projects/{world.A}/members', {'user_id': admin_id, 'role': 'RE'}).status_code == 400


# ---------------------------------------------------------------- UAT-02
def test_uat02_contractor_submits_doc01_with_multiple_rfis(world):
    sid, ids = make_batch(world.encoder, world.A, n=3)
    det = world.encoder.get(f'/rfi-summaries/{sid}').json()
    assert len(det['rfis']) == 3 and det['permissions']['submit']
    r = world.encoder.post(f'/rfi-summaries/{sid}/submit', {})
    assert r.status_code == 200, r.text
    s = r.json()
    assert s['workflow_status'] == 'SUBMITTED' and s['submitted_by'] == world.encoder.id and s['submitted_at']
    rows = world.re.get(f'/rfis?project_id={world.A}&summary_id={sid}').json()
    assert rows['total'] == 3  # one DOC_02 row per RFI (FR-07)
    for r in rows['items']:
        assert r['workflow_status'] == 'SUBMITTED' and r['short_notice'] is False and r['notice_hours'] > 24
        assert r['inspection_time'] and r['material_source_offset'] == '50m & 300' and r['requested_date']
    # idempotent retry of submit does not duplicate anything
    assert world.encoder.post(f'/rfi-summaries/{sid}/submit', {}).json().get('already_submitted') is True


def test_doc01_validation_and_duplicates(world):
    sid, ids = make_batch(world.encoder, world.A, n=1, extra={'inspection_time': None})
    r = world.encoder.post(f'/rfi-summaries/{sid}/submit', {})
    assert r.status_code == 422 and 'Inspection time' in r.json()['detail']
    # duplicate RFI No. in the project is blocked with a clear message (FR-05)
    num = world.encoder.get(f'/rfis/{ids[0]}').json()['rfi']['rfi_number']
    r = world.encoder.post('/rfis', {'project_id': world.A, 'summary_id': sid, 'rfi_number': num.upper() + ' '})
    assert r.status_code == 409 and 'already exists' in r.json()['detail']
    # but the same number is allowed in another project (uniqueness scope = project, OD-01)
    sidb, _ = make_batch(world.encoder_b, world.B, n=0)
    assert world.encoder_b.post('/rfis', {'project_id': world.B, 'summary_id': sidb, 'rfi_number': num}).status_code == 200
    # invalid time format rejected
    assert world.encoder.post('/rfis', {'project_id': world.A, 'summary_id': sid, 'rfi_number': 'Z-1', 'inspection_time': '9.00am'}).status_code == 422


def test_short_notice_flag_and_override_policy(world, admin):
    sid, ids = submitted_batch(world.encoder, world.A, n=1, hours=5)
    r = world.re.get(f'/rfis/{ids[0]}').json()['rfi']
    assert r['short_notice'] is True and r['notice_hours'] < 24  # flagged, not blocked (BR-09)
    n = [x for x in world.re.get('/notifications').json() if x['entity_id'] == sid]
    assert n and 'SHORT NOTICE' in n[0]['message']
    admin.put(f'/projects/{world.A}/settings', {'notice_policy': 'REQUIRE_OVERRIDE'})
    sid2, _ = make_batch(world.encoder, world.A, n=1, hours=3)
    assert world.encoder.post(f'/rfi-summaries/{sid2}/submit', {}).status_code == 422
    assert world.encoder.post(f'/rfi-summaries/{sid2}/submit', {'short_notice_reason': 'Concrete pour window'}).status_code == 200
    admin.put(f'/projects/{world.A}/settings', {'notice_policy': 'FLAG'})


def test_only_contractor_members_create_doc01(world, admin):
    body = {'project_id': world.A, 'summary_reference': 'x-' + world.run, 'submission_date': '2026-11-14'}
    for api in (world.re, world.surveyor, world.qs, world.encoder_b, world.outsider, admin):
        assert api.post('/rfi-summaries', body).status_code == 403


# ---------------------------------------------------------------- UAT-03
def test_uat03_management_receives_submission_project_scoped(world):
    sid, _ = submitted_batch(world.encoder, world.A, n=2)
    for m in (world.re, world.are, world.dre):
        assert any(n['entity_type'] == 'RFI_SUMMARY' and n['entity_id'] == sid for n in m.get('/notifications').json())
    # RE of another project and other roles are NOT notified (no cross-project leakage)
    for other in (world.re_b, world.surveyor, world.qs):
        assert not any(n['entity_type'] == 'RFI_SUMMARY' and n['entity_id'] == sid for n in other.get('/notifications').json())
    dash = world.re.get(f'/dashboard?project_id={world.A}').json()
    assert any(b['id'] == sid and b['rfi_count'] == 2 for b in dash['new_batches'])
    assert world.secretary.post(f'/rfi-summaries/{sid}/receive').json()['received_by'] == world.secretary.id


# ---------------------------------------------------------------- UAT-04 .. UAT-07
def test_uat04_to_07_sequential_review(world, admin):
    _, (rid,) = submitted_batch(world.encoder, world.A)
    seq = [world.surveyor, world.wi, world.me_eng]
    # nobody but RE/DRE may assign
    for api in (world.encoder, world.surveyor, world.qs, admin, world.re_b):
        assert assign(api, rid, seq).status_code == 403
    r = assign(world.re, rid, seq)
    assert r.status_code == 200, r.text
    d = world.re.get(f'/rfis/{rid}').json()
    assert [(a['sequence_no'], a['user_id'], a['status']) for a in d['assignments']] == [(1, world.surveyor.id, 'ACTIVE'), (2, world.wi.id, 'PENDING'), (3, world.me_eng.id, 'PENDING')]
    assert d['rfi']['workflow_status'] == 'UNDER_REVIEW' and d['rfi']['received_by'] == world.re.id
    assert any(n['entity_id'] == rid and 'your turn' in n['message'] for n in world.surveyor.get('/notifications').json())
    assert any(n['entity_id'] == rid and 'number 2' in n['message'] for n in world.wi.get('/notifications').json())
    # UAT-06: 2nd and 3rd inspectors blocked before their turn (backend enforced)
    for early in (world.wi, world.me_eng):
        r = review(early, rid)
        assert r.status_code == 409 and 'not your turn' in r.json()['detail'].lower()
    # nobody may write in another inspector's field, Admin included (FR-12, DR-01)
    first_aid = active_assignment(world.surveyor, rid)
    assert world.wi.post(f'/rfis/{rid}/review', {'assignment_id': first_aid, 'comment': 'x'}).status_code == 403
    assert admin.post(f'/rfis/{rid}/review', {'assignment_id': first_aid, 'comment': 'x'}).status_code == 403
    # UAT-05: first inspector submits; entry locked and time-stamped
    assert review(world.surveyor, rid, 'Levels checked: within tolerance').status_code == 200
    again = world.surveyor.post(f'/rfis/{rid}/review', {'assignment_id': first_aid, 'comment': 'changed my mind'})
    assert again.status_code == 409
    a1 = world.re.get(f'/rfis/{rid}').json()['assignments'][0]
    assert a1['status'] == 'COMPLETED' and a1['review']['comment'] == 'Levels checked: within tolerance' and a1['review']['reviewed_at']
    assert any(n['entity_id'] == rid and 'previous inspector' in n['message'] for n in world.wi.get('/notifications').json())
    assert review(world.me_eng, rid).status_code == 409   # still not #3's turn
    assert review(world.wi, rid).status_code == 200
    # decision impossible before all reviews (FR-15)
    assert world.re.post(f'/rfis/{rid}/decision', {'disposition_code': 'APPROVED_FURTHER_WORKS'}).status_code == 409
    assert review(world.me_eng, rid).status_code == 200
    # UAT-07: routed to RE/DRE
    d = world.re.get(f'/rfis/{rid}').json()
    assert d['rfi']['workflow_status'] == 'AWAITING_DECISION' and d['permissions']['decide']
    assert any(n['entity_id'] == rid and 'awaits the RE/DRE final decision' in n['message'] for n in world.dre.get('/notifications').json())


def test_assignment_validation_and_change_control(world):
    _, (rid,) = submitted_batch(world.encoder, world.A)
    assert assign(world.re, rid, [world.surveyor_b]).status_code == 400          # not a member of this project
    assert assign(world.re, rid, [world.qs]).status_code == 400                  # not an inspector
    r = world.re.post(f'/rfis/{rid}/assignments', {'assignments': [{'user_id': world.surveyor.id, 'reviewer_role': 'MATERIAL_ENGINEER'}]})
    assert r.status_code == 400                                                  # cannot write in another role's DOC_03 field
    assert assign(world.re, rid, [world.surveyor, world.surveyor]).status_code == 400
    assert assign(world.re, rid, [world.surveyor, world.wi]).status_code == 200
    # before review starts: re-plan freely
    assert assign(world.re, rid, [world.wi, world.surveyor]).status_code == 200
    assert review(world.wi, rid).status_code == 200
    # after review started: reason required, audited, completed review kept
    assert assign(world.re, rid, [world.me_eng]).status_code == 400
    r = assign(world.re, rid, [world.me_eng], reason='Surveyor on leave')
    assert r.status_code == 200
    d = world.re.get(f'/rfis/{rid}').json()
    states = [(a['user_id'], a['status'], a['sequence_no']) for a in d['assignments']]
    assert (world.wi.id, 'COMPLETED', 1) in states and (world.surveyor.id, 'REPLACED', 2) in states and (world.me_eng.id, 'ACTIVE', 2) in states
    audit = world.re.get(f'/audit?project_id={world.A}&entity_type=RFI&entity_id={rid}').json()
    assert any(a['action'] == 'CHANGE_SEQUENCE' and a['details'] == 'Surveyor on leave' and a['before_json'] for a in audit)
    # the replaced inspector can no longer submit
    assert review(world.surveyor, rid).status_code in (404, 409)


def test_concurrent_double_submission_is_serialised(world, client):
    import threading
    _, (rid,) = submitted_batch(world.encoder, world.A)
    assign(world.re, rid, [world.surveyor, world.wi])
    aid = active_assignment(world.surveyor, rid)
    codes = []
    def go():
        codes.append(world.surveyor.post(f'/rfis/{rid}/review', {'assignment_id': aid, 'comment': 'parallel'}).status_code)
    ts = [threading.Thread(target=go) for _ in range(4)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert sorted(codes).count(200) == 1, codes
    db = SessionLocal()
    try:
        assert db.query(models.Review).filter_by(rfi_id=rid).count() == 1
    finally:
        db.close()


def fully_reviewed(world, n=1):
    _, ids = submitted_batch(world.encoder, world.A, n=n)
    for rid in ids:
        assert assign(world.re, rid, [world.surveyor, world.wi]).status_code == 200
        assert review(world.surveyor, rid).status_code == 200
        assert review(world.wi, rid).status_code == 200
    return ids


# ---------------------------------------------------------------- UAT-08 / UAT-09
def test_uat08_09_decisions_update_register_without_duplicates(world, admin):
    a, b = fully_reviewed(world, n=2)
    before_total = world.re.get(f'/rfis?project_id={world.A}').json()['total']
    # only RE/DRE (BR-07); Admin explicitly excluded (DR-01)
    for api in (admin, world.surveyor, world.encoder, world.qs, world.re_b):
        assert api.post(f'/rfis/{a}/decision', {'disposition_code': 'APPROVED_FURTHER_WORKS'}).status_code == 403
    assert world.re.post(f'/rfis/{a}/decision', {'disposition_code': 'BOGUS'}).status_code == 400
    r = world.re.post(f'/rfis/{a}/decision', {'disposition_code': 'APPROVED_FURTHER_WORKS', 'comment': 'Proceed to next layer'})
    assert r.status_code == 200 and r.json()['decision'] == 'APPROVED'
    r = world.dre.post(f'/rfis/{b}/decision', {'disposition_code': 'NOT_APPROVED_RESUBMIT', 'comment': 'Density below spec'})
    assert r.status_code == 200 and r.json()['decision'] == 'REJECTED'
    assert world.re.post(f'/rfis/{a}/decision', {'disposition_code': 'NOT_APPROVED_RESUBMIT'}).status_code == 409  # no silent overwrite
    da = world.re.get(f'/rfis/{a}').json()
    dec = da['decisions'][0]
    assert dec['decided_by'] == world.re.id and dec['decided_at'] and dec['comment'] == 'Proceed to next layer' and dec['disposition_code'] == 'APPROVED_FURTHER_WORKS'
    assert da['rfi']['workflow_status'] == 'COMPLETED' and da['rfi']['approved_from'] == '188+650' and da['rfi']['approved_to'] == '188+870'
    db_ = world.re.get(f'/rfis/{b}').json()
    assert db_['rfi']['current_decision'] == 'REJECTED' and db_['decisions'][0]['decided_by'] == world.dre.id
    # UAT-09: same rows updated, no duplicates
    after = world.re.get(f'/rfis?project_id={world.A}').json()
    assert after['total'] == before_total
    num = da['rfi']['rfi_number']
    assert world.re.get(f'/rfis?project_id={world.A}&rfi_number={num}').json()['total'] == 1
    # contractor is notified with the disposition label
    assert any(n['entity_id'] == b and 'Not Approved' in n['title'] for n in world.encoder.get('/notifications').json())
    # rejected RFI resubmitted as a new revision; original and its decision preserved (BR-08, OD-07)
    d, t = future(30)
    assert world.re.post(f'/rfis/{b}/resubmit', {'reason': 'x', 'inspection_date': d, 'inspection_time': t}).status_code == 403
    r = world.encoder.post(f'/rfis/{b}/resubmit', {'reason': 'Recompacted', 'inspection_date': d, 'inspection_time': t})
    assert r.status_code == 200 and r.json()['revision_no'] == 1 and r.json()['parent_rfi_id'] == b
    assert world.encoder.post(f'/rfis/{b}/resubmit', {'reason': 'again', 'inspection_date': d, 'inspection_time': t}).status_code == 409
    assert world.re.get(f'/rfis/{b}').json()['rfi']['current_decision'] == 'REJECTED'
    assert world.encoder.post(f'/rfis/{a}/resubmit', {'reason': 'x', 'inspection_date': d, 'inspection_time': t}).status_code == 409


def test_partial_approval_requires_section_and_configurable_dispositions(world, admin):
    (rid,) = fully_reviewed(world)
    assert world.re.post(f'/rfis/{rid}/decision', {'disposition_code': 'APPROVED_PARTIAL_RESUBMIT'}).status_code == 400
    r = world.re.post(f'/rfis/{rid}/decision', {'disposition_code': 'APPROVED_PARTIAL_RESUBMIT', 'approved_from': '188+650', 'approved_to': '188+700'})
    assert r.json()['decision'] == 'PARTIALLY_APPROVED'
    rec = world.re.get(f'/rfis/{rid}').json()['rfi']
    assert (rec['approved_from'], rec['approved_to'], rec['current_disposition']) == ('188+650', '188+700', 'APPROVED_PARTIAL_RESUBMIT')
    # dispositions are configuration (OD-06 pending client approval)
    st = admin.get(f'/projects/{world.B}/settings').json()
    custom = st['dispositions'] + [{'code': 'ACCEPTED_AS_NOTED', 'label': 'Accepted as Noted', 'decision': 'APPROVED'}]
    assert admin.put(f'/projects/{world.B}/settings', {'dispositions': custom}).status_code == 200
    assert admin.put(f'/projects/{world.B}/settings', {'dispositions': [{'code': 'X', 'label': 'x', 'decision': 'MAYBE'}]}).status_code == 400
    assert world.re.put(f'/projects/{world.A}/settings', {'deputy_label': 'DRE'}).status_code == 403


# ---------------------------------------------------------------- UAT-10
def test_uat10_office_exports_filtered_register(world):
    ids = fully_reviewed(world, n=2)
    world.re.post(f'/rfis/{ids[0]}/decision', {'disposition_code': 'APPROVED_COMPLY_COMMENTS'})
    legacy_rfi(world.B, 'LEG-B-1')
    q = f'project_id={world.A}&disposition=APPROVED_COMPLY_COMMENTS'
    screen = world.qs.get(f'/rfis?{q}').json()
    x = world.qs.get(f'/reports/register.xlsx?{q}')
    assert x.status_code == 200
    ws = load_workbook(io.BytesIO(x.content)).active
    header = [c.value for c in ws[4]]
    assert header[:3] == ['Contractor_Request', 'Item', 'Structure_Type/Building Block'] and 'RFI_No.' in header and 'Assigned Inspectors (sequence)' in header
    assert ws.freeze_panes == 'A5' and ws.auto_filter.ref.startswith('A4')
    nums = [ws.cell(r, header.index('RFI_No.') + 1).value for r in range(5, ws.max_row + 1)]
    assert sorted(nums) == sorted(i['rfi_number'] for i in screen['items']) and len(nums) == screen['total'] >= 1
    assert 'LEG-B-1' not in nums and 'disposition=APPROVED_COMPLY_COMMENTS' in ws.cell(3, 1).value
    p = world.qs.get(f'/reports/register.pdf?{q}')
    assert p.status_code == 200 and p.content[:4] == b'%PDF'
    text = pdf_text(p.content)
    assert 'DOC_02' in text and 'Page 1 of' in text and nums[0] in ''.join(text.split())
    # another project's register cannot be exported; unauthorised export denied
    assert world.qs.get(f'/reports/register.xlsx?project_id={world.B}').status_code == 403
    assert world.outsider.get('/reports/register.xlsx').status_code == 403
    assert world.surveyor.get(f'/reports/register.xlsx?project_id={world.A}').status_code == 403  # inspectors read-only, no export (OD-04 default)
    # all-projects export for a single-project user only contains their project
    allx = load_workbook(io.BytesIO(world.qs.get('/reports/register.xlsx').content)).active
    assert 'LEG-B-1' not in [allx.cell(r, header.index('RFI_No.') + 1).value for r in range(5, allx.max_row + 1)]


# ---------------------------------------------------------------- UAT-11
def test_uat11_completed_doc03_pdf_matches_issued_record(world):
    (rid,) = fully_reviewed(world)
    world.re.post(f'/rfis/{rid}/decision', {'disposition_code': 'APPROVED_COMPLY_COMMENTS', 'comment': 'Fix edge compaction'})
    d = world.encoder.get(f'/rfis/{rid}').json()
    assert d['issued_documents'] and d['issued_documents'][0]['doc_type'] == 'DOC03'
    r = world.encoder.get(f'/reports/doc03/{rid}.pdf')
    assert r.status_code == 200
    assert hashlib.sha256(r.content).hexdigest() == d['issued_documents'][0]['sha256']   # served exactly as issued
    text = pdf_text(r.content)
    for expected in ['Request For Work Inspection/Approval', d['rfi']['rfi_number'], 'Works Inspector (WI)', 'Soil Lab Technician (SLT)', 'Material Engineer (ME)',
                     'Approved: Compliance to Comments required', 'Fix edge compaction', 'Checked on site - satisfactory', '64.02(a)', 'Electronically recorded',
                     'Order of Inspection', 'Not Approved: RFI to be resubmitted', 'Distribution']:
        assert expected in text, expected
    # later changes do not alter the issued file
    assert world.qs.get(f'/reports/doc03/{rid}.pdf').content == r.content
    # DOC_01 PDF reproduces the summary sheet
    sid = d['summary']['id']
    t1 = pdf_text(world.encoder.get(f'/reports/doc01/{sid}.pdf').content)
    assert 'Daily Request For Inspection Summary Sheet' in t1 and d['rfi']['rfi_number'] in t1 and 'Contractor Representative' in t1 and '50m & 300' in t1


# ---------------------------------------------------------------- UAT-12
def test_uat12_unauthorised_project_and_field_access_denied(world, admin, client):
    sid, (rid,) = submitted_batch(world.encoder, world.A)
    up = world.encoder.post(f'/attachments/rfi/{rid}', files={'file': ('test.pdf', b'%PDF-1.4 test', 'application/pdf')})
    assert up.status_code == 200, up.text
    att = up.json()['id']
    for api in (world.encoder_b, world.re_b, world.outsider):
        for path in (f'/rfis/{rid}', f'/rfi-summaries/{sid}', f'/reports/doc03/{rid}.pdf', f'/reports/doc01/{sid}.pdf', f'/attachments/download/{att}',
                     f'/attachments/rfi/{rid}', f'/projects/{world.A}/members', f'/dashboard?project_id={world.A}', f'/rfis?project_id={world.A}'):
            assert api.get(path).status_code == 403, (path, api.get(path).status_code)
        assert world.A not in [i['project_id'] for i in api.get('/rfis').json()['items']]
        assert api.post(f'/rfis/{rid}/assignments', {'assignments': [{'user_id': world.surveyor.id}]}).status_code == 403
    # user directory is admin-only (S-7); members list hides e-mail for non-admins
    assert world.re.get('/users').status_code == 403 and admin.get('/users').status_code == 200
    assert 'email' not in world.re.get(f'/projects/{world.A}/members').json()[0]
    # submitted RFI cannot be edited directly (S-3) ...
    v = world.encoder.get(f'/rfis/{rid}').json()['rfi']['version']
    assert world.encoder.put(f'/rfis/{rid}', {'version': v, 'remarks': 'sneaky'}).status_code == 409
    assert world.re.put(f'/rfis/{rid}', {'version': v, 'remarks': 'sneaky'}).status_code in (403, 409)
    # ... only via a controlled amendment that keeps the original value
    r = world.encoder.post(f'/rfis/{rid}/amendments', {'changes': {'chainage_to': '188+900'}, 'reason': 'Typo in station'})
    assert r.status_code == 200 and r.json()['changes']['chainage_to'] == {'old': '188+870', 'new': '188+900'}
    aid = r.json()['amendment_id']
    assert world.encoder.post(f'/rfis/amendments/{aid}/approve', {}).status_code == 403
    assert world.re.post(f'/rfis/amendments/{aid}/approve', {'comment': 'ok'}).status_code == 200
    d = world.re.get(f'/rfis/{rid}').json()
    assert d['rfi']['chainage_to'] == '188+900' and d['amendments'][0]['changes']['chainage_to']['old'] == '188+870'
    # revoked member loses access but their history remains
    admin.delete(f'/projects/{world.A}/members/{world.office_eng.id}')
    assert world.office_eng.get(f'/rfis/{rid}').status_code == 403
    assert admin.get(f'/projects/{world.A}/members?include_revoked=true').status_code == 200


def test_legacy_records_are_read_only_and_keep_not_ready(world, admin):
    lid = legacy_rfi(world.A, f'LEG-{world.run}', 'Not Ready')
    d = world.re.get(f'/rfis/{lid}').json()
    assert d['rfi']['is_legacy'] and d['rfi']['rfi_status'] == 'Not Ready' and not any(d['permissions'].values())
    assert world.re.post(f'/rfis/{lid}/amendments', {'changes': {'remarks': 'x'}, 'reason': 'x'}).status_code == 409
    assert world.re.post(f'/rfis/{lid}/cancel', {'reason': 'x'}).status_code == 409
    assert world.re.post(f'/rfis/{lid}/assignments', {'assignments': [{'user_id': world.surveyor.id}]}).status_code == 409
    assert world.encoder.post(f'/rfis/{lid}/resubmit', {'reason': 'x', 'inspection_date': '2027-01-01', 'inspection_time': '09:00'}).status_code == 409
    rows = world.re.get(f'/rfis?project_id={world.A}&legacy_status=Not%20Ready').json()['items']
    assert any(r['id'] == lid for r in rows)
    ws = load_workbook(io.BytesIO(world.re.get(f'/reports/register.xlsx?project_id={world.A}&legacy_status=Not%20Ready').content)).active
    hdr = [c.value for c in ws[4]]
    assert ws.cell(5, hdr.index('RFI_Status') + 1).value == 'Not Ready' and ws.cell(5, hdr.index('Provenance') + 1).value == 'LEGACY_IMPORT'


def test_draft_editing_and_audit_is_transactional(world):
    sid, (rid,) = make_batch(world.encoder, world.A)
    v = world.encoder.get(f'/rfis/{rid}').json()['rfi']['version']
    assert world.office_eng.put(f'/rfis/{rid}', {'version': v, 'remarks': 'team edit'}).status_code in (200, 403)
    v = world.encoder.get(f'/rfis/{rid}').json()['rfi']['version']
    assert world.encoder.put(f'/rfis/{rid}', {'version': v - 1, 'remarks': 'stale'}).status_code == 409   # optimistic lock
    assert world.encoder.put(f'/rfis/{rid}', {'version': v, 'remarks': 'ok'}).status_code == 200
    db = SessionLocal()
    try:
        acts = [a.action for a in db.query(models.AuditLog).filter_by(entity_type='RFI', entity_id=rid)]
        assert 'CREATE' in acts and 'EDIT_DRAFT' in acts
        assert all(a.project_id == world.A for a in db.query(models.AuditLog).filter_by(entity_type='RFI', entity_id=rid))
    finally:
        db.close()
    assert world.encoder.delete(f'/rfis/{rid}').status_code == 200   # never-submitted draft line may be removed


def test_returned_batch_and_overdue(world):
    sid, (rid,) = submitted_batch(world.encoder, world.A)
    assert world.encoder.post(f'/rfi-summaries/{sid}/return', {'reason': 'x'}).status_code == 403
    assert world.re.post(f'/rfi-summaries/{sid}/return', {'reason': 'Missing material source'}).status_code == 200
    assert world.encoder.get(f'/rfis/{rid}').json()['rfi']['workflow_status'] == 'DRAFT'
    assert world.encoder.post(f'/rfi-summaries/{sid}/submit', {}).status_code == 200
    assign(world.re, rid, [world.surveyor])
    assert world.re.post(f'/rfi-summaries/{sid}/return', {'reason': 'too late'}).status_code == 409


def test_role_dashboards(world):
    assert 'my_active' in world.surveyor.get(f'/dashboard?project_id={world.A}').json()
    c = world.encoder.get(f'/dashboard?project_id={world.A}').json()
    assert 'drafts' in c and 'action_required' in c
    assert 'recent_decisions' in world.qs.get(f'/dashboard?project_id={world.A}').json()
    assert world.outsider.get(f'/dashboard?project_id={world.A}').status_code == 403


def test_daily_progress_and_reference_data_scoped(world):
    body = {'project_id': world.A, 'progress_date': '2026-11-14', 'work_item': 'Embankment', 'description': 'Layer 2'}
    assert world.encoder_b.post('/daily-progress', body).status_code == 403
    r = world.encoder.post('/daily-progress', body); assert r.status_code == 200
    assert world.re_b.get(f'/daily-progress/{r.json()["id"]}').status_code == 403
    assert world.encoder.post('/master-data', {'project_id': world.A, 'category': 'SIDE', 'value': 'X'}).status_code == 403
    assert world.re.post('/master-data', {'project_id': world.A, 'category': 'SIDE', 'value': f'X-{world.run}'}).status_code == 200
    assert world.re.post('/master-data', {'project_id': world.B, 'category': 'SIDE', 'value': 'X'}).status_code == 403


def test_audit_access(world, admin):
    assert world.encoder.get('/audit').status_code == 403
    assert world.re.get(f'/audit?project_id={world.B}').status_code == 403
    assert world.re.get(f'/audit?project_id={world.A}').status_code == 200
    assert admin.get('/audit').status_code == 200
