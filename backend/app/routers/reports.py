"""Reports and exports (SRS 10, FR-21/22/24). Every export resolves access exactly like the screens."""
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse, Response
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from openpyxl import Workbook
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.units import mm
from app.config import settings as app_settings
from app.database import get_db
from app.models import Rfi, Project, RfiSummary, DailyProgress, DailyProgressRfi, User, IssuedDocument, ReviewerAssignment
from app.security import current_user
from app import authz
from app.project_settings import get_settings
from app.services.audit import log
from app.services.register import RegisterFilter, register_query, hidden_policy
from app.services import documents
from app.routers.rfis import filter_params

router = APIRouter(prefix='/reports', tags=['Reports'])
XLSX = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'


def safe_name(s):
    return ''.join(c if c.isalnum() or c in '-_.' else '_' for c in str(s))[:80]


def file_response(data: bytes, media: str, name: str):
    return Response(content=data, media_type=media, headers={'Content-Disposition': f'attachment; filename="{safe_name(name)}"'})


def project_label(db, f: RegisterFilter):
    if f.project_id:
        p = db.get(Project, f.project_id)
        return f'{p.code} - {p.name}' if p else ''
    return 'All authorised projects'


def export_rows(db, u, f):
    s, allowed = register_query(db, u, f, for_export=True)
    if not allowed:
        raise HTTPException(403, 'You are not permitted to export the register for any project')
    return list(db.scalars(s.limit(50000)))


@router.get('/register.xlsx')
@router.get('/rfi-register.xlsx')
def register_xlsx(f: RegisterFilter = Depends(filter_params), show_hidden: bool = False, db: Session = Depends(get_db), u: User = Depends(current_user)):
    rows = export_rows(db, u, f)
    data = documents.register_xlsx(db, rows, project_label(db, f), f.active(), u, hidden_allowed=hidden_policy(db, u), show_hidden=show_hidden)
    log(db, u.id, 'REPORT', f.project_id or 0, 'EXPORT_REGISTER_XLSX', f'{len(rows)} rows; filters={f.active()}', project_id=f.project_id, commit=True)
    return file_response(data, XLSX, f'DOC02_register_{datetime.utcnow():%Y%m%d_%H%M}.xlsx')


@router.get('/register.pdf')
def register_pdf(f: RegisterFilter = Depends(filter_params), columns: str | None = None, db: Session = Depends(get_db), u: User = Depends(current_user)):
    rows = export_rows(db, u, f)
    if len(rows) > 5000:
        raise HTTPException(413, f'{len(rows)} records match. Narrow the filters to 5,000 or fewer for a PDF, or use the Excel export.')
    cols = [c.strip() for c in columns.split(',')] if columns else None
    data = documents.register_pdf(db, rows, project_label(db, f), f.active(), u, columns=cols, hidden_allowed=hidden_policy(db, u))
    log(db, u.id, 'REPORT', f.project_id or 0, 'EXPORT_REGISTER_PDF', f'{len(rows)} rows; filters={f.active()}', project_id=f.project_id, commit=True)
    return file_response(data, 'application/pdf', f'DOC02_register_{datetime.utcnow():%Y%m%d_%H%M}.pdf')


@router.get('/doc03/{rid}.pdf')
@router.get('/rfi/{rid}.pdf')
def doc03(rid: int, db: Session = Depends(get_db), u: User = Depends(current_user)):
    r, role = authz.load_rfi(db, u, rid)
    issued = db.scalar(select(IssuedDocument).where(IssuedDocument.rfi_id == rid, IssuedDocument.revision_no == r.revision_no, IssuedDocument.doc_type == 'DOC03').order_by(IssuedDocument.id.desc()))
    data = None
    if issued and r.workflow_status == 'COMPLETED':
        path = Path(app_settings.upload_dir) / issued.stored_name
        if path.exists():
            data = path.read_bytes()
    source = 'ISSUED_SNAPSHOT' if data else 'GENERATED'
    if data is None:
        data = documents.build_doc03_pdf(db, r)
    log(db, u.id, 'RFI', rid, 'EXPORT_DOC03_PDF', source, project_id=r.project_id, commit=True)
    return file_response(data, 'application/pdf', f'DOC03_{r.rfi_number}_rev{r.revision_no}.pdf')


@router.get('/doc01/{sid}.pdf')
@router.get('/rfi-summary/{sid}.pdf')
def doc01(sid: int, db: Session = Depends(get_db), u: User = Depends(current_user)):
    s, role = authz.load_summary(db, u, sid)
    rows = list(db.scalars(select(Rfi).where(Rfi.summary_id == sid, Rfi.revision_no == 0).order_by(Rfi.id)))
    data = documents.build_doc01_pdf(db, s, rows)
    log(db, u.id, 'RFI_SUMMARY', sid, 'EXPORT_DOC01_PDF', None, project_id=s.project_id, commit=True)
    return file_response(data, 'application/pdf', f'DOC01_{s.summary_reference}.pdf')


@router.get('/summary')
def status_summary(project_id: int, db: Session = Depends(get_db), u: User = Depends(current_user)):
    """RFI status / pending / overdue / decision report for one project (JSON; the register exports give the row detail)."""
    role = authz.require_project(db, u, project_id)
    st = get_settings(db.get(Project, project_id))
    if not authz.can_view_register(role, st): raise HTTPException(403, 'Not permitted')
    base = [Rfi.project_id == project_id, Rfi.record_state == 'ACTIVE']
    by_wf = dict(db.execute(select(Rfi.workflow_status, func.count()).where(*base).group_by(Rfi.workflow_status)).all())
    by_dec = dict(db.execute(select(Rfi.current_decision, func.count()).where(*base).group_by(Rfi.current_decision)).all())
    by_disp = dict(db.execute(select(Rfi.current_disposition, func.count()).where(*base, Rfi.current_disposition.is_not(None)).group_by(Rfi.current_disposition)).all())
    by_legacy = dict(db.execute(select(Rfi.legacy_rfi_status, func.count()).where(*base, Rfi.provenance == 'LEGACY_IMPORT').group_by(Rfi.legacy_rfi_status)).all())
    cutoff = datetime.utcnow() - timedelta(hours=st['overdue_hours'])
    overdue = db.execute(select(Rfi.id, Rfi.rfi_number, ReviewerAssignment.sequence_no, ReviewerAssignment.reviewer_role, ReviewerAssignment.activated_at)
                         .join(ReviewerAssignment, ReviewerAssignment.rfi_id == Rfi.id)
                         .where(*base, ReviewerAssignment.status == 'ACTIVE', ReviewerAssignment.activated_at < cutoff)).all()
    return {'by_workflow': by_wf, 'by_decision': {k or 'NONE': v for k, v in by_dec.items()}, 'by_disposition': by_disp,
            'legacy_status': {k or '(blank)': v for k, v in by_legacy.items()},
            'short_notice': db.scalar(select(func.count()).select_from(Rfi).where(*base, Rfi.short_notice == True)) or 0,
            'overdue_reviews': [{'rfi_id': a, 'rfi_number': b, 'sequence_no': c, 'role': d, 'active_since': e} for a, b, c, d, e in overdue]}


# ---------------------------------------------------------------- Daily Progress (complementary module)
def dp_projects(db, u, project_id):
    if project_id:
        authz.require_project(db, u, project_id)
        return [project_id]
    vis = authz.visible_project_ids(db, u)
    return vis


@router.get('/daily-progress.xlsx')
def daily_excel(project_id: int | None = None, db: Session = Depends(get_db), u: User = Depends(current_user)):
    pids = dp_projects(db, u, project_id)
    q = select(DailyProgress).order_by(DailyProgress.progress_date, DailyProgress.id)
    if pids is not None: q = q.where(DailyProgress.project_id.in_(pids or [-1]))
    rows = list(db.scalars(q))
    wb = Workbook(); ws = wb.active; ws.title = 'Daily Progress'
    ws.append(['Date', 'Work Item', 'Description', 'From', 'To', 'Side', 'Quantity', 'Unit', 'Status', 'Remarks'])
    for p in rows: ws.append([p.progress_date, p.work_item, p.description, p.chainage_from, p.chainage_to, p.side, p.quantity, p.unit, p.status, p.remarks])
    ws.freeze_panes = 'A2'; ws.auto_filter.ref = ws.dimensions
    out = BytesIO(); wb.save(out)
    log(db, u.id, 'REPORT', project_id or 0, 'EXPORT_EXCEL', 'Daily Progress', project_id=project_id, commit=True)
    return file_response(out.getvalue(), XLSX, 'daily_progress.xlsx')


@router.get('/daily-progress/{pid}.pdf')
def daily_progress_pdf(pid: int, db: Session = Depends(get_db), u: User = Depends(current_user)):
    r = db.get(DailyProgress, pid)
    if not r: raise HTTPException(404, 'Daily Progress not found')
    authz.require_project(db, u, r.project_id)
    project = db.get(Project, r.project_id)
    def safe(v): return escape(str(v if v is not None else ''))
    linked = list(db.scalars(select(Rfi.rfi_number).join(DailyProgressRfi, DailyProgressRfi.rfi_id == Rfi.id).where(DailyProgressRfi.daily_progress_id == pid)))
    nm = {x.id: x.full_name for x in db.scalars(select(User).where(User.id.in_({r.created_by, r.reviewed_by, r.confirmed_by} - {None})))}
    rows = [('Project', project.name if project else ''), ('Report #', r.id), ('Progress Date', r.progress_date), ('Work Item', r.work_item), ('Description / Stage', r.description),
            ('Chainage', f'{r.chainage_from or ""} - {r.chainage_to or ""}'), ('Side', r.side), ('Quantity / Unit', f'{r.quantity if r.quantity is not None else ""} {r.unit or ""}'),
            ('Status', r.status), ('Linked RFI numbers', ', '.join(linked) or '-'), ('Remarks', r.remarks), ('Created by', nm.get(r.created_by)),
            ('Inspector', nm.get(r.reviewed_by, '-')), ('Inspector comment', r.review_comment), ('Reviewed at', r.reviewed_at), ('RE/DRE', nm.get(r.confirmed_by, '-')),
            ('Confirmation comment', r.confirmation_comment), ('Confirmed at', r.confirmed_at)]
    out = BytesIO(); doc = SimpleDocTemplate(out, pagesize=A4, rightMargin=15 * mm, leftMargin=15 * mm, topMargin=15 * mm, bottomMargin=15 * mm)
    styles = getSampleStyleSheet()
    table = Table([[Paragraph(f'<b>{safe(k)}</b>', styles['Normal']), Paragraph(safe(v), styles['Normal'])] for k, v in rows], colWidths=[50 * mm, 130 * mm])
    table.setStyle(TableStyle([('GRID', (0, 0), (-1, -1), .4, colors.grey), ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#EAF7FF'))]))
    doc.build([Paragraph('DAILY CONSTRUCTION PROGRESS REPORT', styles['Title']), Spacer(1, 5 * mm), table])
    log(db, u.id, 'DAILY_PROGRESS', pid, 'EXPORT_PDF', project_id=r.project_id, commit=True)
    return file_response(out.getvalue(), 'application/pdf', f'daily_progress_{pid}.pdf')
