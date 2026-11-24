"""DOC_02 register query (SRS 10, FR-20/21). The screen, Excel export and PDF export all call
`register_query`, so an export can never contain rows the user could not see on screen."""
from dataclasses import dataclass, fields
from datetime import date
from fastapi import HTTPException
from sqlalchemy import select, or_, and_, func
from app.models import Rfi, Project, ReviewerAssignment, RfiSummary
from app import authz
from app.project_settings import get_settings

SORTABLE = {
    'id': Rfi.id, 'rfi_number': Rfi.rfi_number, 'inspection_date': Rfi.inspection_date, 'requested_date': Rfi.requested_date,
    'work_item': Rfi.work_item, 'workflow_status': Rfi.workflow_status, 'current_decision': Rfi.current_decision,
    'chainage_from': Rfi.chainage_from, 'side': Rfi.side, 'road_type': Rfi.road_type, 'updated_at': Rfi.updated_at,
}


@dataclass
class RegisterFilter:
    project_id: int | None = None
    q: str | None = None
    rfi_number: str | None = None
    workflow_status: str | None = None
    decision: str | None = None
    disposition: str | None = None
    legacy_status: str | None = None
    work_item: str | None = None
    side: str | None = None
    road_type: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    inspector_id: int | None = None
    submitted_by: int | None = None
    summary_id: int | None = None
    provenance: str | None = None
    short_notice: bool | None = None
    latest_only: bool = False
    include_inactive: bool = False
    sort: str = 'id'
    dir: str = 'desc'

    def active(self) -> dict:
        skip = {'sort', 'dir'}
        return {f.name: getattr(self, f.name) for f in fields(self) if f.name not in skip and getattr(self, f.name) not in (None, '', False)}


HIDDEN_FIELDS = ('fill_layer', 'material_source_type', 'material_source_cut_section', 'material_source_designation', 'material_destination_designation', 'work_status')


def hidden_policy(db, user):
    """Returns a function rfi -> bool: may this user see the workbook's hidden columns I:M and S for that RFI's project? (UD-06)"""
    cache = {}
    def allowed(r) -> bool:
        if r.project_id not in cache:
            role = authz.project_role(db, user, r.project_id)
            cats = get_settings(db.get(Project, r.project_id)).get('hidden_field_categories') or []
            cache[r.project_id] = bool(role) and authz.category(role) in cats
        return cache[r.project_id]
    return allowed


def register_query(db, user, f: RegisterFilter, for_export: bool = False):
    """Return a SELECT over Rfi restricted to what `user` may see, with filters applied."""
    if f.project_id is not None:
        project_ids = [f.project_id]
    else:
        vis = authz.visible_project_ids(db, user)
        project_ids = list(db.scalars(select(Project.id))) if vis is None else vis
    clauses = []
    allowed = []
    for pid in project_ids:
        project = db.get(Project, pid)
        if not project:
            if f.project_id is not None: raise HTTPException(404, 'Project not found')
            continue
        role = authz.project_role(db, user, pid)
        settings = get_settings(project)
        if role is None:
            if f.project_id is not None: raise HTTPException(403, 'You are not a member of this project')
            continue
        if for_export and not authz.can_export(role, settings):
            if f.project_id is not None: raise HTTPException(403, 'Your project role does not permit exporting the register')
            continue
        extra = authz.rfi_visibility_clause(db, user, pid, role, settings)
        if extra is None and role in authz.INSPECTORS and not settings.get('inspector_register_access'):
            continue
        allowed.append(pid)
        clauses.append(and_(Rfi.project_id == pid, extra) if extra is not None else Rfi.project_id == pid)
    s = select(Rfi)
    s = s.where(or_(*clauses)) if clauses else s.where(Rfi.id == -1)
    if not f.include_inactive:
        s = s.where(Rfi.record_state == 'ACTIVE')
    if f.workflow_status: s = s.where(Rfi.workflow_status == f.workflow_status)
    if f.decision: s = s.where(Rfi.current_decision == f.decision)
    if f.disposition: s = s.where(Rfi.current_disposition == f.disposition)
    if f.legacy_status: s = s.where(Rfi.legacy_rfi_status == f.legacy_status)
    if f.work_item: s = s.where(Rfi.work_item == f.work_item)
    if f.side: s = s.where(Rfi.side == f.side)
    if f.road_type: s = s.where(Rfi.road_type == f.road_type)
    if f.date_from: s = s.where(Rfi.inspection_date >= f.date_from)
    if f.date_to: s = s.where(Rfi.inspection_date <= f.date_to)
    if f.summary_id: s = s.where(Rfi.summary_id == f.summary_id)
    if f.provenance: s = s.where(Rfi.provenance == f.provenance)
    if f.short_notice is not None: s = s.where(Rfi.short_notice == f.short_notice)
    if f.rfi_number: s = s.where(Rfi.rfi_number == f.rfi_number.strip())
    if f.inspector_id:
        s = s.where(Rfi.id.in_(select(ReviewerAssignment.rfi_id).where(ReviewerAssignment.user_id == f.inspector_id, ReviewerAssignment.status != 'REPLACED')))
    if f.submitted_by:
        s = s.where(or_(and_(Rfi.created_by == f.submitted_by, or_(Rfi.provenance.is_(None), Rfi.provenance != 'LEGACY_IMPORT')), Rfi.summary_id.in_(select(RfiSummary.id).where(RfiSummary.submitted_by == f.submitted_by))))
    if f.latest_only:
        r2 = Rfi.__table__.alias('r2')
        s = s.where(~select(r2.c.id).where(r2.c.project_id == Rfi.project_id, r2.c.rfi_number == Rfi.rfi_number, r2.c.revision_no > Rfi.revision_no).exists())
    if f.q:
        like = f'%{f.q.strip()}%'
        s = s.where(or_(Rfi.rfi_number.like(like), Rfi.description.like(like), Rfi.contractor_request.like(like), Rfi.work_item.like(like),
                        Rfi.chainage_from.like(like), Rfi.chainage_to.like(like), Rfi.remarks.like(like), Rfi.road_type.like(like)))
    col = SORTABLE.get(f.sort, Rfi.id)
    s = s.order_by(col.asc() if f.dir == 'asc' else col.desc(), Rfi.id.desc())
    return s, allowed
