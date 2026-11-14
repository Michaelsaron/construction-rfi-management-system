"""Historical (LEGACY_IMPORT) rows: misleading labels are corrected in presentation only; stored values stay unchanged."""
from datetime import date
from io import BytesIO
import uuid
from openpyxl import load_workbook
from app.database import SessionLocal
from app import models
from conftest import legacy_rfi


def _importer_style_legacy(project_id):
    """Mimic the original importer: requested_date copied from the inspection date, created_by = admin."""
    rid = legacy_rfi(project_id, f'LEG-D-{uuid.uuid4().hex[:6]}')
    with SessionLocal() as db:
        r = db.get(models.Rfi, rid); r.requested_date = r.inspection_date; db.commit()
    return rid


def test_legacy_detail_does_not_show_importer_as_submitter_or_copied_request_date(world):
    rid = _importer_style_legacy(world.B)
    d = world.re_b.get(f'/rfis/{rid}').json()
    r = d['rfi']
    assert r['is_legacy'] and r['origin_label'] == 'Imported from the historical DOC_02 register'
    assert r['requested_date_display'] is None and r['requested_date_note'] == 'Not recorded in the historical register'
    # the stored value is unchanged and still available to the API
    assert r['requested_date'] == r['inspection_date'] == '2024-07-15'
    with SessionLocal() as db:
        assert db.get(models.Rfi, rid).requested_date == date(2024, 7, 15)


def test_portal_rfi_keeps_real_request_date_and_submitter(world):
    from conftest import submitted_batch
    _, (rid,) = submitted_batch(world.encoder, world.A)
    r = world.re.get(f'/rfis/{rid}').json()['rfi']
    assert r['origin_label'] is None and r['requested_date_note'] is None
    assert r['requested_date_display'] == r['requested_date']


def test_register_export_blanks_copied_request_date_and_filter_ignores_import_account(world, admin):
    rid = _importer_style_legacy(world.B)
    with SessionLocal() as db:
        number = db.get(models.Rfi, rid).rfi_number
        admin_id = db.query(models.User).filter_by(email='admin@example.com').one().id
    resp = world.re_b.get(f'/reports/register.xlsx?project_id={world.B}')
    assert resp.status_code == 200
    ws = load_workbook(BytesIO(resp.content)).active
    header = [c.value for c in ws[4]]
    row = next(r for r in ws.iter_rows(min_row=5, values_only=True) if r[header.index('RFI_No.')] == number)
    assert row[header.index('Requested Date')] in (None, '')
    assert row[header.index('Inspection_Date')] is not None
    # "submitted by <import account>" must not return historical rows
    items = admin.get(f'/rfis?project_id={world.B}&submitted_by={admin_id}').json()['items']
    assert all(not i['is_legacy'] for i in items)
