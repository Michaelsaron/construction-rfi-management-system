"""RFI workflow engine (SRS 5). All status changes go through `transition`, which validates the
move against the state table, writes status history and is committed by the caller in the same
transaction as the business change and its audit record."""
import json
from datetime import datetime, date, time, timedelta
from fastapi import HTTPException
from sqlalchemy import select
from zoneinfo import ZoneInfo
from app.config import settings
from app.models import Rfi, RfiStatusHistory, ReviewerAssignment, User

# Legacy imported rows use COMPLETED (with a decision) or ARCHIVED (no decision recorded); both are read-only.
TRANSITIONS = {
    'DRAFT': {'SUBMITTED'},
    'SUBMITTED': {'DRAFT', 'UNDER_REVIEW', 'CANCELLED'},
    'ACTIVATED': {'UNDER_REVIEW', 'CANCELLED'},          # pre-v1.0 "accepted" state
    'UNDER_REVIEW': {'UNDER_REVIEW', 'AWAITING_DECISION', 'CANCELLED'},
    'AWAITING_DECISION': {'COMPLETED', 'UNDER_REVIEW', 'CANCELLED'},
    'COMPLETED': set(),
    'CANCELLED': set(),
    'ARCHIVED': set(),
}
STATUS_LABELS = {
    'DRAFT': 'Draft', 'SUBMITTED': 'Submitted', 'ACTIVATED': 'Received', 'UNDER_REVIEW': 'Under Inspector Review',
    'AWAITING_DECISION': 'Awaiting Final Decision', 'COMPLETED': 'Completed', 'CANCELLED': 'Cancelled', 'ARCHIVED': 'Legacy - no decision recorded',
}
OPEN_FOR_ASSIGNMENT = {'SUBMITTED', 'ACTIVATED', 'UNDER_REVIEW', 'AWAITING_DECISION'}


def lock_rfi(db, rid: int) -> Rfi:
    """SELECT ... FOR UPDATE so concurrent reviews/decisions on one RFI are serialised."""
    r = db.scalar(select(Rfi).where(Rfi.id == rid).with_for_update())
    if not r:
        raise HTTPException(404, 'RFI not found')
    return r


def transition(db, r: Rfi, to: str, user: User, reason: str | None = None):
    frm = r.workflow_status
    if to not in TRANSITIONS.get(frm, set()):
        raise HTTPException(409, f'RFI {r.rfi_number} cannot move from {STATUS_LABELS.get(frm, frm)} to {STATUS_LABELS.get(to, to)}')
    r.workflow_status = to
    r.version = (r.version or 0) + 1
    db.add(RfiStatusHistory(rfi_id=r.id, workflow_status=to, decision=r.current_decision, changed_by=user.id, reason=reason))


def require_active_record(r: Rfi):
    if r.record_state != 'ACTIVE':
        raise HTTPException(409, f'RFI is {r.record_state.lower()} and cannot be changed')
    if r.provenance == 'LEGACY_IMPORT' or (r.summary_id is None and r.workflow_status in ('COMPLETED', 'ARCHIVED')):
        raise HTTPException(409, 'Historical (legacy imported) RFIs are read-only')


def site_now() -> datetime:
    """Current wall-clock time at the site (naive), so it compares with inspection times as entered.
    Containers run in UTC; Ethiopian sites are UTC+3 (SITE_TIMEZONE, default Africa/Addis_Ababa)."""
    return datetime.now(ZoneInfo(settings.site_timezone)).replace(tzinfo=None)


def inspection_datetime(d: date | None, t: str | None):
    if not d:
        return None
    if t:
        hh, mm = t.split(':')
        return datetime.combine(d, time(int(hh), int(mm)))
    return datetime.combine(d, time(0, 0))


def compute_notice(r: Rfi, submitted_at: datetime, notice_hours: float):
    """BR-09. Hours between submission and proposed inspection (local site time as entered)."""
    when = inspection_datetime(r.inspection_date, r.inspection_time)
    if not when:
        r.notice_hours = None; r.short_notice = None
        return
    hours = round((when - submitted_at).total_seconds() / 3600, 1)
    r.notice_hours = hours
    r.short_notice = hours < notice_hours


def active_assignments(db, rid: int):
    return list(db.scalars(select(ReviewerAssignment).where(ReviewerAssignment.rfi_id == rid, ReviewerAssignment.status != 'REPLACED')
                           .order_by(ReviewerAssignment.sequence_no, ReviewerAssignment.id)))


def parse_categories(v):
    if not v:
        return []
    try:
        x = json.loads(v)
        return x if isinstance(x, list) else []
    except ValueError:
        return []


RFI_FIELDS = [c for c in Rfi.__table__.columns.keys()]


LEGACY_REQUESTED_NOTE = 'Not recorded in the historical register'
LEGACY_ORIGIN_LABEL = 'Imported from the historical DOC_02 register'


def requested_date_is_import_copy(r: Rfi) -> bool:
    """The historical workbook has no request date. The original importer copied Inspection_Date into
    requested_date, so for imported rows that value is not a real request date. The stored value is kept
    unchanged; only its presentation changes."""
    return r.provenance == 'LEGACY_IMPORT' and (r.requested_date is None or r.requested_date == r.inspection_date)


def display_requested_date(r: Rfi):
    return None if requested_date_is_import_copy(r) else r.requested_date


def rfi_dict(r: Rfi, extra: dict | None = None) -> dict:
    d = {k: getattr(r, k) for k in RFI_FIELDS}
    d['work_categories'] = parse_categories(r.work_categories)
    d['status_label'] = STATUS_LABELS.get(r.workflow_status, r.workflow_status)
    d['is_legacy'] = r.provenance == 'LEGACY_IMPORT' or (r.summary_id is None and r.workflow_status in ('COMPLETED', 'ARCHIVED'))
    d['rfi_status'] = r.legacy_rfi_status if d['is_legacy'] and r.legacy_rfi_status else None
    # Presentation of historical rows (stored values are untouched; see requested_date_is_import_copy).
    copy = requested_date_is_import_copy(r)
    d['requested_date_display'] = None if copy else r.requested_date
    d['requested_date_note'] = LEGACY_REQUESTED_NOTE if copy else None
    d['origin_label'] = LEGACY_ORIGIN_LABEL if r.provenance == 'LEGACY_IMPORT' else None
    if extra:
        d.update(extra)
    return d
