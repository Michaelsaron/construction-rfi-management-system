"""UI design v1 - evidence architecture, workflow monitoring, Completed DOC_03, admin and register (Phase 12)."""
import hashlib
import io
import json
import threading
import uuid
import zipfile
from pathlib import Path
import pytest
from fastapi import HTTPException
from openpyxl import load_workbook
from pypdf import PdfReader
from app.config import settings
from app.database import SessionLocal
from app import models
from conftest import submitted_batch, assign, review, active_assignment, legacy_rfi

PDF = b'%PDF-1.4\n% test evidence\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n'
JPG = b'\xff\xd8\xff\xe0' + b'\x00' * 200
PNG = b'\x89PNG\r\n\x1a\n' + b'\x00' * 64


def up(api, path, name='photo.jpg', data=JPG, token=None, **form):
    data_form = {k: str(v) for k, v in form.items()}
    if token: data_form['upload_token'] = token
    return api.post(path, files={'file': (name, data, 'application/octet-stream')}, data=data_form)


def tok():
    return uuid.uuid4().hex


def under_review(world, inspectors=None):
    _, (rid,) = submitted_batch(world.encoder, world.A)
    r = assign(world.re, rid, inspectors or [world.surveyor, world.wi])
    assert r.status_code == 200, r.text
    return rid


def awaiting_decision(world):
    rid = under_review(world)
    assert review(world.surveyor, rid).status_code == 200
    assert review(world.wi, rid).status_code == 200
    return rid


def draft_remark(api, rid, stage, **kw):
    r = api.post('/evidence/remarks', {'project_id': kw.pop('project_id', None) or api_project(api, rid), 'rfi_id': rid, 'stage': stage, **kw})
    assert r.status_code == 200, r.text
    return r.json()


def api_project(api, rid):
    return api.get(f'/rfis/{rid}').json()['rfi']['project_id']


def set_settings(admin, pid, **kw):
    r = admin.put(f'/projects/{pid}/settings', kw)
    assert r.status_code == 200, r.text


# ------------------------------------------------------------------------------------ inspector path (2.2)
def test_only_active_inspector_uploads_to_own_review(world):
    rid = under_review(world)
    d = world.surveyor.get(f'/rfis/{rid}').json()
    first = next(a for a in d['assignments'] if a['sequence_no'] == 1)
    second = next(a for a in d['assignments'] if a['sequence_no'] == 2)
    # pending inspector (second in sequence) cannot upload or submit early
    r = up(world.wi, f'/evidence/assignments/{second["id"]}/files')
    assert r.status_code == 409 and 'not your turn' in r.json()['detail'].lower()
    assert world.wi.post(f'/rfis/{rid}/review', {'assignment_id': second['id'], 'comment': 'early'}).status_code == 409
    # another inspector cannot upload to the active inspector's review; nor can RE/DRE, contractor or other project
    for api in (world.wi, world.re, world.encoder, world.surveyor_b, world.outsider):
        assert up(api, f'/evidence/assignments/{first["id"]}/files').status_code in (403, 404), api
    # generic RFI-level upload path is closed to inspectors and management
    assert up(world.surveyor, f'/attachments/rfi/{rid}').status_code == 403
    assert up(world.re, f'/attachments/rfi/{rid}').status_code == 403
    # the active inspector can upload
    r = up(world.surveyor, f'/evidence/assignments/{first["id"]}/files', 'IMG_0910.jpg', token=tok())
    assert r.status_code == 200, r.text
    a = r.json()
    assert a['attachment_kind'] == 'INSPECTOR_REVIEW' and a['assignment_id'] == first['id'] and a['rfi_id'] == rid and a['project_id'] == world.A
    assert a['sha256'] == hashlib.sha256(JPG).hexdigest() and a['upload_status'] == 'COMPLETE' and not a['locked']
    assert 'stored_name' not in a and 'path' not in json.dumps(a).lower().replace('previewable', '')
    # draft evidence is private to its author until the review is submitted
    assert world.re.get(f'/evidence/files/{a["id"]}').status_code == 403
    assert world.wi.get(f'/evidence/files/{a["id"]}/download').status_code == 403
    # draft comment is preserved and private
    assert world.surveyor.put(f'/evidence/assignments/{first["id"]}/draft', {'comment': 'Levels checked'}).status_code == 200
    assert world.surveyor.get(f'/evidence/assignments/{first["id"]}').json()['draft_comment'] == 'Levels checked'
    assert world.re.get(f'/evidence/assignments/{first["id"]}').json()['draft_comment'] is None
    assert 'draft_comment' not in json.dumps(world.re.get(f'/rfis/{rid}').json()['assignments'])


def test_submission_locks_review_and_evidence(world):
    rid = under_review(world)
    aid = active_assignment(world.surveyor, rid)
    f1 = up(world.surveyor, f'/evidence/assignments/{aid}/files', 'a.jpg', token=tok()).json()
    f2 = up(world.surveyor, f'/evidence/assignments/{aid}/files', 'b.pdf', PDF, token=tok()).json()
    # remove before submission: only the uploader
    assert world.wi.delete(f'/evidence/files/{f2["id"]}').status_code == 403
    assert world.surveyor.delete(f'/evidence/files/{f2["id"]}').status_code == 200
    # the confirmed attachment count must match the server
    r = world.surveyor.post(f'/rfis/{rid}/review', {'assignment_id': aid, 'comment': 'Surface checked', 'attachment_count': 2})
    assert r.status_code == 409 and '1 evidence file' in r.json()['detail']
    r = world.surveyor.post(f'/rfis/{rid}/review', {'assignment_id': aid, 'comment': 'Surface checked', 'attachment_count': 1})
    assert r.status_code == 200 and r.json()['attachment_count'] == 1
    meta = world.surveyor.get(f'/evidence/files/{f1["id"]}').json()
    assert meta['locked'] and meta['review_id']
    # locked: no more uploads, no removal
    assert up(world.surveyor, f'/evidence/assignments/{aid}/files', token=tok()).status_code == 409
    assert world.surveyor.delete(f'/evidence/files/{f1["id"]}').status_code == 409
    # once submitted, management, office and the next inspector can open it; other projects and contractors cannot
    for api in (world.re, world.qs, world.wi):
        assert api.get(f'/evidence/files/{f1["id"]}/download').status_code == 200, api
    for api in (world.re_b, world.outsider, world.encoder_b):
        assert api.get(f'/evidence/files/{f1["id"]}/download').status_code == 403
    assert world.encoder.get(f'/evidence/files/{f1["id"]}/download').status_code == 403  # UD-04 conservative default
    # the review snapshot records identity and server time
    with SessionLocal() as db:
        rv = db.query(models.Review).filter_by(assignment_id=aid).one()
        assert rv.reviewer_name_snapshot == 'Surveyor' and rv.reviewer_role_snapshot == 'SURVEYOR' and rv.attachment_count == 1


def test_duplicate_upload_token_creates_one_record(world):
    rid = under_review(world)
    aid = active_assignment(world.surveyor, rid)
    t = tok()
    a = up(world.surveyor, f'/evidence/assignments/{aid}/files', token=t)
    b = up(world.surveyor, f'/evidence/assignments/{aid}/files', token=t)
    assert a.status_code == b.status_code == 200 and a.json()['id'] == b.json()['id'] and b.json().get('duplicate')
    with SessionLocal() as db:
        assert db.query(models.Attachment).filter_by(assignment_id=aid).count() == 1
    # the same token cannot be replayed against a different record
    rid2 = under_review(world)
    aid2 = active_assignment(world.surveyor, rid2)
    assert up(world.surveyor, f'/evidence/assignments/{aid2}/files', token=t).status_code == 409


def test_invalid_oversized_mismatched_and_empty_files_are_rejected(world, admin):
    rid = under_review(world)
    aid = active_assignment(world.surveyor, rid)
    base = f'/evidence/assignments/{aid}/files'
    assert up(world.surveyor, base, 'virus.exe', b'MZ' + b'\0' * 50).status_code == 400
    assert up(world.surveyor, base, 'fake.pdf', b'<html>not a pdf</html>').status_code == 422
    assert up(world.surveyor, base, 'empty.jpg', b'').status_code == 400
    assert up(world.surveyor, base, 'noext', PDF).status_code == 400
    set_settings(admin, world.A, attachment_policy={'max_file_mb': 1, 'max_files_per_record': 2})
    try:
        big = b'\xff\xd8\xff' + b'\0' * (1024 * 1024 + 10)
        r = up(world.surveyor, base, 'big.jpg', big)
        assert r.status_code == 413 and '1 MB' in r.json()['detail']
        assert up(world.surveyor, base, 'a.jpg').status_code == 200 and up(world.surveyor, base, 'b.jpg').status_code == 200
        assert 'maximum of 2' in up(world.surveyor, base, 'c.jpg').json()['detail']
    finally:
        set_settings(admin, world.A, attachment_policy={'max_file_mb': 50, 'max_files_per_record': 20})
    # nothing partial is left on disk
    assert not list(Path(settings.upload_dir).rglob('*.part'))


def test_interrupted_upload_leaves_nothing_and_retry_is_clean(world):
    from app.services.evidence import store_upload

    class Broken:
        def __init__(self): self.n = 0
        def read(self, size=-1):
            self.n += 1
            if self.n > 1: raise ConnectionError('client went away')
            return JPG

    class FakeUpload:
        filename = 'IMG.jpg'
        file = Broken()

    with SessionLocal() as db:
        project = db.get(models.Project, world.A)
        before = set(Path(settings.upload_dir).rglob('*'))
        with pytest.raises(ConnectionError):
            store_upload(FakeUpload(), project)
        assert set(Path(settings.upload_dir).rglob('*')) - before <= {p for p in Path(settings.upload_dir).rglob('*') if p.is_dir()}
    rid = under_review(world)
    aid = active_assignment(world.surveyor, rid)
    t = tok()
    assert up(world.surveyor, f'/evidence/assignments/{aid}/files', token=t).status_code == 200
    assert up(world.surveyor, f'/evidence/assignments/{aid}/files', token=t).json()['duplicate']


def test_concurrent_uploads_with_same_token_store_one(world):
    rid = under_review(world)
    aid = active_assignment(world.surveyor, rid)
    t = tok(); codes = []
    def go(): codes.append(up(world.surveyor, f'/evidence/assignments/{aid}/files', token=t).status_code)
    ts = [threading.Thread(target=go) for _ in range(4)]
    [x.start() for x in ts]; [x.join() for x in ts]
    with SessionLocal() as db:
        assert db.query(models.Attachment).filter_by(assignment_id=aid, upload_token=t).count() == 1
    assert codes == [200] * 4, codes


# --------------------------------------------------------------------------------- management path (2.1)
def test_management_remark_ownership_and_final_disposition(world):
    rid = awaiting_decision(world)
    rem = draft_remark(world.re, rid, 'FINAL_DISPOSITION', body='Proceed subject to conditions')
    assert rem['status'] == 'DRAFT' and rem['editable']
    f = up(world.re, f'/evidence/remarks/{rem["id"]}/files', 'prior_layer_FDT.pdf', PDF, token=tok())
    assert f.status_code == 200 and f.json()['attachment_kind'] == 'MANAGEMENT_REMARK' and f.json()['workflow_stage'] == 'FINAL_DISPOSITION'
    fid = f.json()['id']
    # only the author can change the draft or add files; the DRE cannot use the RE's remark; inspectors/contractors cannot create remarks
    assert world.dre.put(f'/evidence/remarks/{rem["id"]}', {'body': 'x'}).status_code == 403
    assert up(world.dre, f'/evidence/remarks/{rem["id"]}/files', token=tok()).status_code == 403
    for api in (world.surveyor, world.encoder, world.qs):
        assert api.post('/evidence/remarks', {'project_id': world.A, 'rfi_id': rid, 'stage': 'FINAL_DISPOSITION'}).status_code == 403
    assert world.re_b.post('/evidence/remarks', {'project_id': world.A, 'rfi_id': rid, 'stage': 'FINAL_DISPOSITION'}).status_code == 403
    # drafts are private
    assert all(x['id'] != rem['id'] for x in world.dre.get(f'/evidence/remarks?rfi_id={rid}').json())
    assert world.dre.get(f'/evidence/files/{fid}').status_code == 403
    # wrong stage for the record state: no final-disposition remark while reviews are still open
    other = under_review(world)
    assert world.re.post('/evidence/remarks', {'project_id': world.A, 'rfi_id': other, 'stage': 'FINAL_DISPOSITION'}).status_code == 409
    assert world.re.post('/evidence/remarks', {'project_id': world.A, 'rfi_id': other, 'stage': 'NONSENSE'}).status_code == 400
    # the DRE cannot attach the RE's draft to their own decision
    r = world.dre.post(f'/rfis/{rid}/decision', {'disposition_code': 'APPROVED_FURTHER_WORKS', 'comment': 'ok', 'management_remark_id': rem['id']})
    assert r.status_code == 403
    # evidence count confirmed by the RE must match
    r = world.re.post(f'/rfis/{rid}/decision', {'disposition_code': 'APPROVED_FURTHER_WORKS', 'comment': 'Proceed subject to recorded comments', 'management_remark_id': rem['id'], 'evidence_count': 3})
    assert r.status_code == 409
    r = world.re.post(f'/rfis/{rid}/decision', {'disposition_code': 'APPROVED_FURTHER_WORKS', 'comment': 'Proceed subject to recorded comments', 'management_remark_id': rem['id'], 'evidence_count': 1})
    assert r.status_code == 200, r.text
    rems = world.qs.get(f'/evidence/remarks?rfi_id={rid}').json()
    final = next(x for x in rems if x['id'] == rem['id'])
    assert final['status'] == 'SUBMITTED' and final['body'] == 'Proceed subject to recorded comments' and final['decision_id'] and final['files'][0]['locked']
    assert world.re.put(f'/evidence/remarks/{rem["id"]}', {'body': 'change'}).status_code == 409
    assert world.re.delete(f'/evidence/files/{fid}').status_code == 409
    with SessionLocal() as db:
        d = db.query(models.Decision).filter_by(rfi_id=rid).one()
        assert d.decided_by_name_snapshot == 'Re' and d.designation_snapshot == 'Resident Engineer'
        assert db.query(models.Attachment).get(fid).uploaded_by == world.re.id  # never attributed to an inspector


def test_doc01_review_assignment_and_return_remarks(world):
    sid, (rid,) = submitted_batch(world.encoder, world.A)
    # DOC_01 review remark on the batch, recorded on its own
    rem = world.re.post('/evidence/remarks', {'project_id': world.A, 'summary_id': sid, 'stage': 'DOC01_REVIEW', 'body': 'Reviewed submitted list'}).json()
    assert up(world.re, f'/evidence/remarks/{rem["id"]}/files', 'note.png', PNG, token=tok()).status_code == 200
    r = world.re.post(f'/evidence/remarks/{rem["id"]}/submit')
    assert r.status_code == 200 and r.json()['status'] == 'SUBMITTED'
    # an empty DOC_01 remark cannot be recorded on its own
    empty = world.dre.post('/evidence/remarks', {'project_id': world.A, 'summary_id': sid, 'stage': 'DOC01_REVIEW'}).json()
    assert world.dre.post(f'/evidence/remarks/{empty["id"]}/submit').status_code == 400
    assert world.dre.delete(f'/evidence/remarks/{empty["id"]}').status_code == 200
    # assignment remark is locked by the assignment action
    arem = draft_remark(world.re, rid, 'ASSIGNMENT', body='Ensure prior layer test results accompany the inspection')
    assert up(world.re, f'/evidence/remarks/{arem["id"]}/files', 'ref.pdf', PDF, token=tok()).status_code == 200
    r = world.re.post(f'/rfis/{rid}/assignments', {'assignments': [{'user_id': world.surveyor.id}, {'user_id': world.wi.id}], 'management_remark_id': arem['id']})
    assert r.status_code == 200 and r.json()['management_remark_id'] == arem['id']
    # sequence change after review started requires a reason; its remark is recorded as SEQUENCE_CHANGE
    assert review(world.surveyor, rid).status_code == 200
    srem = draft_remark(world.re, rid, 'SEQUENCE_CHANGE', body='Works inspector on leave')
    r = world.re.post(f'/rfis/{rid}/assignments', {'assignments': [{'user_id': world.si.id}], 'reason': 'Works inspector on leave', 'management_remark_id': srem['id']})
    assert r.status_code == 200, r.text
    stages = {x['id']: x['stage'] for x in world.re.get(f'/evidence/remarks?rfi_id={rid}').json()}
    assert stages[arem['id']] == 'ASSIGNMENT' and stages[srem['id']] == 'SEQUENCE_CHANGE' and stages[rem['id']] == 'DOC01_REVIEW'
    # return of a batch with its remark
    sid2, _ = submitted_batch(world.encoder, world.A)
    ret = world.re.post('/evidence/remarks', {'project_id': world.A, 'summary_id': sid2, 'stage': 'REASSIGNMENT_RETURN'}).json()
    assert up(world.re, f'/evidence/remarks/{ret["id"]}/files', 'marked_up.pdf', PDF, token=tok()).status_code == 200
    r = world.re.post(f'/rfi-summaries/{sid2}/return', {'reason': 'Station range missing', 'management_remark_id': ret['id']})
    assert r.status_code == 200
    got = next(x for x in world.re.get(f'/evidence/remarks?summary_id={sid2}').json() if x['id'] == ret['id'])
    assert got['status'] == 'SUBMITTED' and got['body'] == 'Station range missing' and got['files'][0]['locked']
    # management can no longer use the generic batch upload path
    assert up(world.re, f'/attachments/summary/{sid2}').status_code == 403


# ---------------------------------------------------------------------------------- controlled amendment
def test_evidence_amendment_supersedes_without_deleting(world):
    rid = under_review(world)
    aid = active_assignment(world.surveyor, rid)
    old = up(world.surveyor, f'/evidence/assignments/{aid}/files', 'wrong.jpg', token=tok()).json()
    assert world.surveyor.post(f'/rfis/{rid}/review', {'assignment_id': aid, 'comment': 'Levels OK'}).status_code == 200
    # another inspector cannot request a correction of this review
    assert world.wi.post('/evidence/amendments', {'target_kind': 'REVIEW', 'target_id': aid, 'reason': 'x'}).status_code == 403
    am = world.surveyor.post('/evidence/amendments', {'target_kind': 'REVIEW', 'target_id': aid, 'reason': 'Wrong photo attached', 'new_comment': 'Levels OK at 188+700'})
    assert am.status_code == 200, am.text
    am = am.json()
    r = up(world.surveyor, f'/evidence/amendments/{am["id"]}/files', 'right.jpg', token=tok(), supersedes_id=old['id'])
    assert r.status_code == 200 and r.json()['upload_status'] == 'PENDING_APPROVAL' and r.json()['version_no'] == 2
    new_id = r.json()['id']
    # draft amendments are invisible to others and do not change the record
    assert world.re.get(f'/evidence/files/{new_id}').status_code in (200, 403)
    assert world.surveyor.post(f'/evidence/amendments/{am["id"]}/send').status_code == 200
    assert up(world.surveyor, f'/evidence/amendments/{am["id"]}/files', token=tok()).status_code == 409
    assert world.re.post(f'/rfis/amendments/{am["id"]}/approve', {'comment': 'ok'}).status_code == 200
    with SessionLocal() as db:
        o = db.get(models.Attachment, old['id']); n = db.get(models.Attachment, new_id)
        assert o.superseded_at is not None and o.is_active and n.upload_status == 'COMPLETE' and n.locked_at is not None and n.supersedes_id == o.id
        assert db.query(models.Review).filter_by(assignment_id=aid).one().comment == 'Levels OK at 188+700'
    ws = world.re.get(f'/evidence/assignments/{aid}').json()
    assert [f['id'] for f in ws['files']] == [new_id]
    # history keeps the original (superseded) file and the audit trail
    idx = world.re.get(f'/evidence/rfis/{rid}').json()['files']
    assert new_id in [f['id'] for f in idx] and old['id'] not in [f['id'] for f in idx]
    assert world.re.get(f'/evidence/files/{old["id"]}/download').status_code == 200


def test_completed_record_issued_snapshot_and_bundle(world):
    rid = under_review(world)
    aid = active_assignment(world.surveyor, rid)
    fa = up(world.surveyor, f'/evidence/assignments/{aid}/files', 'IMG_20261116_0910.jpg', token=tok()).json()
    assert world.surveyor.post(f'/rfis/{rid}/review', {'assignment_id': aid, 'comment': 'Surface preparation inspected', 'attachment_count': 1}).status_code == 200
    assert review(world.wi, rid).status_code == 200
    rem = draft_remark(world.re, rid, 'FINAL_DISPOSITION')
    fm = up(world.re, f'/evidence/remarks/{rem["id"]}/files', 'Prior_Layer_FDT.pdf', PDF, token=tok()).json()
    assert world.re.post(f'/rfis/{rid}/decision', {'disposition_code': 'APPROVED_FURTHER_WORKS', 'comment': 'Proceed', 'management_remark_id': rem['id']}).status_code == 200
    # amendments are refused once the DOC_03 is issued
    assert world.surveyor.post('/evidence/amendments', {'target_kind': 'REVIEW', 'target_id': aid, 'reason': 'late'}).status_code == 409
    rec = world.qs.get(f'/rfis/{rid}/completed-record')
    assert rec.status_code == 200, rec.text
    rec = rec.json()
    assert rec['read_only'] and rec['disposition']['code'] == 'APPROVED_FURTHER_WORKS' and rec['issued_document']['sha256']
    assert {fa['id'], fm['id']} <= {f['id'] for f in rec['attachment_index']}
    assert any(s['key'] == 'DISPOSITION' and s['files'] for s in rec['sections'])
    # the issued PDF is served unchanged and contains the attachment index
    pdf = world.qs.get(f'/reports/doc03/{rid}.pdf').content
    assert hashlib.sha256(pdf).hexdigest() == rec['issued_document']['sha256']
    text = ''.join(p.extract_text() or '' for p in PdfReader(io.BytesIO(pdf)).pages)
    assert 'Attachment index' in text and 'IMG_20261116_0910.jpg' in text and 'Prior_Layer_FDT.pdf' in text
    # bundle: issued PDF + originals + manifest with author, stage, time, checksum
    b = world.qs.get(f'/rfis/{rid}/evidence-bundle.zip')
    assert b.status_code == 200 and b.headers['content-type'] == 'application/zip'
    z = zipfile.ZipFile(io.BytesIO(b.content))
    man = json.loads(z.read('manifest.json'))
    assert hashlib.sha256(z.read(man['issued_doc03']['file'])).hexdigest() == rec['issued_document']['sha256']
    names = {e['original_name']: e for e in man['files']}
    assert names['IMG_20261116_0910.jpg']['sha256'] == hashlib.sha256(JPG).hexdigest() and names['IMG_20261116_0910.jpg']['author'] == 'Surveyor'
    assert names['Prior_Layer_FDT.pdf']['stage'] == 'Final disposition' and 'manifest.csv' in z.namelist()
    for e in man['files']:
        assert hashlib.sha256(z.read(e['file'])).hexdigest() == e['sha256']
    # bundle permissions
    assert world.encoder.get(f'/rfis/{rid}/evidence-bundle.zip').status_code == 403
    for api in (world.re_b, world.outsider):
        assert api.get(f'/rfis/{rid}/evidence-bundle.zip').status_code == 403
    # a tampered stored file is excluded from the bundle and refused on download
    with SessionLocal() as db:
        a = db.get(models.Attachment, fa['id'])
        p = Path(settings.upload_dir) / a.stored_name
        original = p.read_bytes()
    p.write_bytes(original + b'tampered')
    try:
        assert world.re.get(f'/evidence/files/{fa["id"]}/download').status_code == 409
        man2 = json.loads(zipfile.ZipFile(io.BytesIO(world.re.get(f'/rfis/{rid}/evidence-bundle.zip').content)).read('manifest.json'))
        assert any(e['attachment_id'] == fa['id'] for e in man2['excluded'])
    finally:
        p.write_bytes(original)
    # not completed -> no completed record
    other = under_review(world)
    assert world.qs.get(f'/rfis/{other}/completed-record').status_code == 409


def test_contractor_evidence_access_setting(world, admin):
    rid = under_review(world)
    aid = active_assignment(world.surveyor, rid)
    f = up(world.surveyor, f'/evidence/assignments/{aid}/files', token=tok()).json()
    assert world.surveyor.post(f'/rfis/{rid}/review', {'assignment_id': aid, 'comment': 'ok'}).status_code == 200
    assert world.encoder.get(f'/evidence/files/{f["id"]}/download').status_code == 403
    set_settings(admin, world.A, contractor_evidence_access=True)
    try:
        assert world.encoder.get(f'/evidence/files/{f["id"]}/download').status_code == 200
    finally:
        set_settings(admin, world.A, contractor_evidence_access=False)


# ------------------------------------------------------------------------------------------------ timeline
def test_timeline_shows_sequence_and_locks_decision(world):
    rid = under_review(world)
    t = world.re.get(f'/rfis/{rid}/timeline').json()
    keys = [s['key'] for s in t['stages']]
    assert keys[:3] == ['DOC01_RECEIVED', 'MANAGEMENT_REVIEW', 'ASSIGNMENT'] and keys[-1] == 'FINAL_DECISION'
    insp = [s for s in t['stages'] if s['key'].startswith('INSPECTOR_')]
    assert [s['status'] for s in insp] == ['active', 'pending'] and insp[0]['actor'] == 'Surveyor' and insp[0]['due_at']
    assert t['decision_locked'] and t['stages'][-1]['status'] == 'locked'
    assert review(world.surveyor, rid).status_code == 200 and review(world.wi, rid).status_code == 200
    t = world.re.get(f'/rfis/{rid}/timeline').json()
    assert [s['status'] for s in t['stages'] if s['key'].startswith('INSPECTOR_')] == ['done', 'done']
    assert not t['decision_locked'] and t['can_decide'] and t['stages'][-1]['status'] == 'active'
    assert world.outsider.get(f'/rfis/{rid}/timeline').status_code == 403


# ---------------------------------------------------------------------------------- register / historical
def test_hidden_fields_and_legacy_paths(world, admin):
    _, (rid,) = submitted_batch(world.encoder, world.A, extra={'fill_layer': 'Layer 3', 'material_source_type': 'Borrow pit'})
    legacy = legacy_rfi(world.A, f'LEG-{uuid.uuid4().hex[:5]}')
    with SessionLocal() as db:
        r = db.get(models.Rfi, legacy); r.legacy_file_path = r'i:\RFI\2024\0001.pdf'; r.legacy_ipc_file_path = r'i:\IPC\24'; db.commit()
    def row(api, num_id):
        items = api.get(f'/rfis?project_id={world.A}&limit=500').json()['items']
        return next(x for x in items if x['id'] == num_id)
    qs_row = row(world.qs, rid)
    assert qs_row['fill_layer'] == 'Layer 3' and qs_row['material_source_type'] == 'Borrow pit' and not qs_row.get('hidden_fields_restricted')
    sv_row = row(world.surveyor, rid)
    assert sv_row['fill_layer'] is None and sv_row['material_source_type'] is None and sv_row['hidden_fields_restricted']
    assert world.surveyor.get(f'/rfis?project_id={world.A}&limit=1').json()['hidden_fields_allowed'] is False
    # legacy drive paths are never returned; a status label is shown instead
    for api in (world.qs, world.re, world.encoder):
        d = api.get(f'/rfis/{legacy}').json()
        blob = json.dumps(d)
        assert 'i:\\\\RFI' not in blob and 'legacy_file_path' not in d['rfi'] and d['rfi']['legacy_document']['label'] == 'File unavailable — migration required'
    assert world.qs.get(f'/evidence/rfis/{legacy}').json()['legacy_document']['available'] is False
    # Excel export: values present for office, hidden-column flag set; RFI_No. present; no raw path
    wb = load_workbook(io.BytesIO(world.qs.get(f'/reports/register.xlsx?project_id={world.A}').content))
    ws = wb.active
    hdr = [c.value for c in ws[4]]
    fl = hdr.index('Fill Layer/CheckDam/Pww') + 1
    assert ws.column_dimensions[ws.cell(4, fl).column_letter].hidden
    flat = json.dumps([[c.value for c in r] for r in ws.iter_rows(min_row=5)], default=str)
    assert 'Layer 3' in flat and 'i:\\\\RFI' not in flat and 'File unavailable' in flat
    # the hidden-field policy is a project setting
    set_settings(admin, world.A, hidden_field_categories=['1', '2.1'])
    try:
        assert row(world.qs, rid)['fill_layer'] is None
    finally:
        set_settings(admin, world.A, hidden_field_categories=['1', '2.1', '2.3'])
    # historical records accept no new evidence
    assert world.re.post('/evidence/remarks', {'project_id': world.A, 'rfi_id': legacy, 'stage': 'DOC01_REVIEW'}).status_code == 409


def test_register_pdf_columns_and_saved_views(world):
    r = world.qs.get(f'/reports/register.pdf?project_id={world.A}&columns=rfi_number,work_status,inspection_date&limit=5')
    assert r.status_code == 200
    text = ''.join(p.extract_text() or '' for p in PdfReader(io.BytesIO(r.content)).pages)
    assert 'Work_Status' in text
    r = world.surveyor.get(f'/reports/register.pdf?project_id={world.A}&columns=rfi_number,work_status')
    assert r.status_code in (200, 403)  # inspectors may not export by default; if allowed, restricted columns are dropped
    v = world.qs.post('/register-views', {'name': 'Asphalt', 'project_id': world.A, 'config': {'filters': {'q': 'asphalt'}, 'columns': ['rfi_number'], 'advanced': True}})
    assert v.status_code == 200
    assert [x['name'] for x in world.qs.get(f'/register-views?project_id={world.A}').json()] == ['Asphalt']
    assert world.re.get(f'/register-views?project_id={world.A}').json() == []
    assert world.re.delete(f'/register-views/{v.json()["id"]}').status_code == 404
    assert world.qs.post('/register-views', {'name': 'x', 'config': {'evil': 1}}).status_code == 400
    assert world.qs.delete(f'/register-views/{v.json()["id"]}').status_code == 200


# ----------------------------------------------------------------------------------------------- admin
def test_admin_overview_memberships_and_access_matrix(world, admin):
    o = admin.get('/admin/overview').json()
    assert o['active_projects'] >= 2 and o['active_accounts'] > 0 and o['invitations']['implemented'] is False and o['invitations']['pending'] is None
    ms = admin.get('/admin/memberships').json()
    me = next(m for m in ms if m['user_id'] == world.surveyor.id)
    assert me['category'] == '2.2' and me['role'] == 'SURVEYOR' and me['account_active']
    x = admin.get('/admin/access-matrix.xlsx')
    assert x.status_code == 200
    ws = load_workbook(io.BytesIO(x.content)).active
    hdr = [c.value for c in ws[2]]
    rows = [[c.value for c in r] for r in ws.iter_rows(min_row=3)]
    re_row = next(r for r in rows if r[1] == 'Re' and r[0].startswith('PA-'))
    assert re_row[hdr.index('Final disposition')] == 'Yes' and re_row[hdr.index('Inspector review + evidence (Cat. 2.2)')] == 'No'
    for api in (world.re, world.qs, world.encoder):
        assert api.get('/admin/overview').status_code == 403 and api.get('/admin/access-matrix.xlsx').status_code == 403
    assert admin.get('/admin/access-matrix.csv').status_code == 200
    assert world.re.get('/admin/roles').status_code == 200


def test_record_attachments_lock_on_submission(world):
    from conftest import make_batch
    sid, (rid,) = make_batch(world.encoder, world.A)
    a = up(world.encoder, f'/attachments/rfi/{rid}', 'enclosure.pdf', PDF, token=tok()).json()
    assert not a['locked']
    assert world.encoder.post(f'/rfi-summaries/{sid}/submit', {}).status_code == 200
    assert world.encoder.get(f'/evidence/files/{a["id"]}').json()['locked']
    assert world.encoder.delete(f'/attachments/{a["id"]}').status_code == 409
    # an enclosure added after submission is locked at once
    b = up(world.encoder, f'/attachments/rfi/{rid}', 'late.pdf', PDF, token=tok()).json()
    assert b['locked']
    lst = world.encoder.get(f'/attachments/rfi/{rid}').json()
    assert {x['id'] for x in lst} == {a['id'], b['id']} and all('stored_name' not in x for x in lst)


def test_database_constraints_reject_invalid_evidence_relationships(world):
    """Defence in depth: even a direct insert cannot attach evidence to the wrong review / remark / RFI."""
    from sqlalchemy.exc import IntegrityError, OperationalError
    rid = under_review(world)
    other = under_review(world)
    aid = active_assignment(world.surveyor, rid)
    base = dict(entity_type='rfi', original_name='x.jpg', stored_name='evidence/none.jpg', size_bytes=1, uploaded_by=world.surveyor.id, project_id=world.A)
    bad = [
        dict(attachment_kind='INSPECTOR_REVIEW', assignment_id=aid, rfi_id=other, entity_id=other),          # review of another RFI
        dict(attachment_kind='MANAGEMENT_REMARK', rfi_id=rid, entity_id=rid),                                # remark evidence without a remark
        dict(attachment_kind='RECORD', assignment_id=aid, rfi_id=rid, entity_id=rid),                        # record carrying a review link
        dict(attachment_kind='INSPECTOR_REVIEW', assignment_id=999999, rfi_id=rid, entity_id=rid),          # unknown review
    ]
    for row in bad:
        with SessionLocal() as db:
            db.add(models.Attachment(**base, **row))
            with pytest.raises((IntegrityError, OperationalError)):
                db.commit()
