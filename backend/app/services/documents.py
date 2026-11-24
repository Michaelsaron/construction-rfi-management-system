"""Generated documents: DOC_01 (Daily Request For Inspection Summary Sheet), DOC_03 (Request For Work
Inspection/Approval), DOC_02 register (Excel + PDF). Layouts follow the client's supplied forms; all
project names/parties come from project configuration. No handwritten signatures or stamps are ever
generated - only typed names with system timestamps ("electronically recorded")."""
import hashlib
from datetime import datetime
from io import BytesIO
from pathlib import Path
from uuid import uuid4
from xml.sax.saxutils import escape
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, A3, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from sqlalchemy import select
from app.config import settings as app_settings
from app.models import Project, RfiSummary, ReviewerAssignment, Review, Decision, User, IssuedDocument, Rfi, Attachment, ManagementRemark
from app.project_settings import get_settings, disposition, DOC03_WORK_CATEGORIES
from app.services.workflow import parse_categories, STATUS_LABELS, display_requested_date, LEGACY_FILE_UNAVAILABLE

SS = getSampleStyleSheet()
P7 = ParagraphStyle('p7', parent=SS['Normal'], fontSize=7, leading=8.5)
P8 = ParagraphStyle('p8', parent=SS['Normal'], fontSize=8, leading=10)
P8B = ParagraphStyle('p8b', parent=P8, fontName='Helvetica-Bold')
P9B = ParagraphStyle('p9b', parent=SS['Normal'], fontSize=9, leading=11, fontName='Helvetica-Bold', alignment=1)
TITLE = ParagraphStyle('t', parent=SS['Normal'], fontSize=11, leading=14, fontName='Helvetica-Bold', alignment=1)
GRID = [('GRID', (0, 0), (-1, -1), .5, colors.black), ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 3), ('RIGHTPADDING', (0, 0), (-1, -1), 3), ('TOPPADDING', (0, 0), (-1, -1), 2), ('BOTTOMPADDING', (0, 0), (-1, -1), 2)]
SHADE = colors.HexColor('#E8EEF4')


def e(v):
    return escape('' if v is None else str(v))


def p(v, style=P8):
    return Paragraph(e(v).replace('\n', '<br/>'), style)


def box(checked: bool):
    # Plain-text markers render identically in every PDF viewer and printer (glyph fonts such as
    # ZapfDingbats are not reliably rendered, which would make ticked and empty boxes look alike).
    return '<font name="Courier-Bold">[X]</font>' if checked else '<font name="Courier">[&nbsp;&nbsp;]</font>'


def fmt_dt(v):
    if not v: return ''
    if isinstance(v, datetime): return v.strftime('%d/%m/%Y %H:%M') + ' UTC'
    return v.strftime('%d/%m/%Y') if hasattr(v, 'strftime') else str(v)


def fmt_d(v):
    return v.strftime('%d/%m/%Y') if v and hasattr(v, 'strftime') else (v or '')


class NumberedCanvas(rl_canvas.Canvas):
    """Adds 'Page x of y' plus a footer line on every page."""
    footer = ''

    def __init__(self, *a, **k):
        super().__init__(*a, **k); self._saved = []

    def showPage(self):
        self._saved.append(dict(self.__dict__)); self._startPage()

    def save(self):
        n = len(self._saved)
        for st in self._saved:
            self.__dict__.update(st)
            w, _ = self._pagesize
            self.setFont('Helvetica', 7)
            self.drawRightString(w - 10 * mm, 7 * mm, f'Page {self._pageNumber} of {n}')
            self.drawString(10 * mm, 7 * mm, self.footer[:180])
            super().showPage()
        super().save()


def canvas_with(footer):
    return type('C', (NumberedCanvas,), {'footer': footer})


def party_header(project, left_label, mid_label, right_label, left, mid, right):
    t = Table([[p(left_label, P9B), p(mid_label, P9B), p(right_label, P9B)], [p(left, P8), p(mid, P8), p(right, P8)]])
    t.setStyle(TableStyle(GRID + [('BACKGROUND', (0, 0), (-1, 0), SHADE)]))
    return t


# --------------------------------------------------------------------------------------------- DOC_03
DOC03_ROWS = [('WORK_INSPECTOR', 'Works Inspector (WI)'), ('STRUCTURE_INSPECTOR', 'Structure Inspector (SI)'), ('SURVEYOR', 'Surveyor'),
              ('SENIOR_SURVEYOR', 'Surveyor (Senior)'), ('MATERIAL_INSPECTOR', 'Material Inspector (MI)'), ('LAB_TECHNICIAN', 'Soil Lab Technician (SLT)'),
              ('MATERIAL_ENGINEER', 'Material Engineer (ME)')]


def build_doc03_pdf(db, r: Rfi) -> bytes:
    project = db.get(Project, r.project_id); st = get_settings(project)
    batch = db.get(RfiSummary, r.summary_id) if r.summary_id else None
    assigns = list(db.scalars(select(ReviewerAssignment).where(ReviewerAssignment.rfi_id == r.id, ReviewerAssignment.status != 'REPLACED').order_by(ReviewerAssignment.sequence_no)))
    reviews = {x.assignment_id: x for x in db.scalars(select(Review).where(Review.rfi_id == r.id))}
    dec = db.scalar(select(Decision).where(Decision.rfi_id == r.id, Decision.revision_no == r.revision_no).order_by(Decision.id.desc()))
    uids = {a.user_id for a in assigns} | {x.reviewer_id for x in reviews.values()} | {r.received_by, dec.decided_by if dec else None, batch.submitted_by if batch else None, batch.received_by if batch else None}
    nm = {u.id: u.full_name for u in db.scalars(select(User).where(User.id.in_(uids - {None})))}
    out = BytesIO()
    doc = SimpleDocTemplate(out, pagesize=A4, leftMargin=10 * mm, rightMargin=10 * mm, topMargin=9 * mm, bottomMargin=13 * mm,
                            title=f'DOC_03 {r.rfi_number} Rev {r.revision_no}')
    W = A4[0] - 20 * mm
    story = []
    hdr = Table([[p('EMPLOYER', P9B), p('ENGINEER', P9B), p('CONTRACTOR', P9B)],
                 [p(project.employer), p(project.consultant), p(project.contractor)],
                 [Paragraph(f'<b>Project:</b> {e(project.name)}' + (f' &nbsp; <b>Contract:</b> {e(project.contract_number)}' if project.contract_number else '') + (f' &nbsp; <b>Project Length:</b> {e(project.project_length)}' if project.project_length else ''), P8), '', '']],
                colWidths=[W / 3] * 3)
    hdr.setStyle(TableStyle(GRID + [('SPAN', (0, 2), (2, 2)), ('BACKGROUND', (0, 0), (-1, 0), SHADE)]))
    story += [hdr, Spacer(1, 2 * mm), Paragraph('Request For Work Inspection/Approval', TITLE)]
    t = Table([[p('To be submitted by CONTRACTOR', P8B), Paragraph(f'<b>Req No.</b> {e(r.rfi_number)}' + (f' &nbsp; Rev {r.revision_no}' if r.revision_no else ''), P8)]], colWidths=[W * .6, W * .4])
    t.setStyle(TableStyle(GRID + [('BACKGROUND', (0, 0), (0, 0), SHADE)])); story.append(t)
    cats = set(parse_categories(r.work_categories))
    cols = []
    for _, title, items in DOC03_WORK_CATEGORIES:
        cols.append(Paragraph(f'<b>{e(title)}</b><br/>' + '<br/>'.join(f'{box(c in cats)} {e(lbl)}' for c, lbl in items), P7))
    t = Table([cols], colWidths=[W * .2, W * .16, W * .16, W * .24, W * .12, W * .12]); t.setStyle(TableStyle(GRID)); story.append(t)
    loc = f"{r.chainage_from or ''}{(' - ' + r.chainage_to) if r.chainage_to else ''} {r.side or ''}".strip() or (r.location_text or '')
    order = r.inspection_order
    t = Table([
        [p('Works Description', P8B), p(r.contractor_request or r.description), p('BOQ Item No.', P8B), p(r.boq_item)],
        [p('Work item / activity', P8B), p(' / '.join(x for x in [r.work_item, r.description if r.contractor_request else None, r.structure_type] if x)), p('Source of Material', P8B), p(' '.join(x for x in [r.material_source or r.material_source_designation, r.material_source_offset] if x))],
        [p('Location / Chainage', P8B), p(loc), p('Road type / Layer', P8B), p(' / '.join(x for x in [r.road_type, r.fill_layer] if x))],
        [p('Order of Inspection', P8B), Paragraph(f'{box(order == 1)} First &nbsp;&nbsp; {box(order == 2)} Second &nbsp;&nbsp; {box(order == 3)} Third', P8), p('Inspection date / Time', P8B), p(f'{fmt_d(r.inspection_date)}  {r.inspection_time or r.inspection_time_text or ""}')],
        [p('Submitted by', P8B), p(nm.get(batch.submitted_by) if batch else ''), p('Date', P8B), p(fmt_dt(batch.submitted_at) if batch else '')],
    ], colWidths=[W * .18, W * .42, W * .17, W * .23])
    t.setStyle(TableStyle(GRID + [('BACKGROUND', (0, 0), (0, -1), SHADE), ('BACKGROUND', (2, 0), (2, -1), SHADE)])); story.append(t)
    if batch and batch.submitted_at:
        story.append(Paragraph(f'Signature: electronically submitted via RFIMS by {e(nm.get(batch.submitted_by))} on {fmt_dt(batch.submitted_at)} (DOC_01 {e(batch.summary_reference)})'
                               + (f' &nbsp; <b>Short notice:</b> {r.notice_hours} h before inspection' if r.short_notice else ''), P7))
    story += [Spacer(1, 1.5 * mm), Paragraph('To be filled by the ENGINEER', TITLE)]
    rec_by = nm.get(r.received_by) or (nm.get(batch.received_by) if batch else None)
    rec_at = r.received_at or (batch.received_at if batch else None)
    t = Table([[p('Received by', P8B), p(rec_by), p('Date', P8B), p(fmt_dt(rec_at))]], colWidths=[W * .18, W * .42, W * .17, W * .23])
    t.setStyle(TableStyle(GRID + [('BACKGROUND', (0, 0), (0, -1), SHADE), ('BACKGROUND', (2, 0), (2, -1), SHADE)])); story.append(t)
    rows = [[p('Action by the Engineer', P8B), p('Comments', P8B), p('Name / Signature / Date', P8B)]]
    by_role = {}
    for a in assigns: by_role.setdefault(a.reviewer_role, []).append(a)
    for code, label in DOC03_ROWS:
        items = by_role.get(code, [])
        if not items:
            rows.append([Paragraph(f'{box(False)} {e(label)}', P8), '', '']); continue
        for a in items:
            rv = reviews.get(a.id)
            status = '' if rv else ('Pending - current turn' if a.status == 'ACTIVE' else 'Pending - waiting')
            rows.append([Paragraph(f'{box(True)} {e(label)}<br/><font size="6">Sequence {a.sequence_no}</font>', P8),
                         p(rv.comment if rv else status),
                         p(f'{nm.get(rv.reviewer_id)}\nElectronically recorded\n{fmt_dt(rv.reviewed_at)}' if rv else nm.get(a.user_id, ''), P7)])
    t = Table(rows, colWidths=[W * .25, W * .5, W * .25], repeatRows=1)
    t.setStyle(TableStyle(GRID + [('BACKGROUND', (0, 0), (-1, 0), SHADE)])); story.append(t)
    dsel = dec.disposition_code if dec else None
    dl = st['deputy_label']
    disp_lines = '<br/>'.join(f'{box(d["code"] == dsel)} {e(d["label"])}' for d in st['dispositions'])
    if dec and not any(d['code'] == dsel for d in st['dispositions']):
        disp_lines += f'<br/>{box(True)} {e(dsel or dec.decision)}'
    sign = ''
    if dec:
        sign = f'{e(nm.get(dec.decided_by))}<br/>Electronically recorded<br/>{fmt_dt(dec.decided_at)}'
        if dec.approved_from or dec.approved_to: sign += f'<br/>Approved section: {e(dec.approved_from)} - {e(dec.approved_to)}'
    t = Table([[Paragraph(f'<b>Enclosures / Check Lists</b> &nbsp; Sheets: {e(r.enclosure_sheets if r.enclosure_sheets is not None else "")}<br/>' + disp_lines, P8),
                Paragraph(f'<b>RE/{e(dl)}</b><br/>{sign or "Sign: ____________<br/>Date: ____________"}', P8)]], colWidths=[W * .72, W * .28])
    t.setStyle(TableStyle(GRID)); story.append(t)
    remark = ' '.join(x for x in [dec.comment if dec else None, ('Conditions: ' + dec.conditions) if dec and dec.conditions else None] if x)
    t = Table([[p('Remark (if any):', P8B)], [p(remark or ' ')]], colWidths=[W]); t.setStyle(TableStyle(GRID)); story.append(t)
    notes = '<br/>'.join(f'{i}- {e(n)}' for i, n in enumerate(st['doc03_notes'], 1))
    dist = f'<b>Distribution</b><br/>Original - RE<br/>Copies - QS, {e(dl)} (as appropriate), ME (as appropriate), Inspectors, Surveyors, Lab Techs (as appropriate)'
    t = Table([[Paragraph('<b>Note</b><br/>' + notes, P7), Paragraph(dist, P7)]], colWidths=[W * .7, W * .3]); t.setStyle(TableStyle(GRID)); story.append(t)
    story.append(Spacer(1, 1.5 * mm))
    story.append(Paragraph(f'Received by contractor: ______________________ &nbsp; Date: __________ &nbsp; Signature: __________', P8))
    story += evidence_index(db, r, W)
    status = STATUS_LABELS.get(r.workflow_status, r.workflow_status)
    footer = f'{project.code} | DOC_03 RFI {r.rfi_number} Rev {r.revision_no} | Status: {status} | Generated {datetime.utcnow():%d/%m/%Y %H:%M} UTC by RFIMS'
    doc.build(story, canvasmaker=canvas_with(footer))
    return out.getvalue()


STAGE_TEXT = {'DOC01_REVIEW': 'DOC_01 review', 'ASSIGNMENT': 'Inspector assignment', 'SEQUENCE_CHANGE': 'Sequence change',
              'REASSIGNMENT_RETURN': 'Reassignment / return', 'FINAL_DISPOSITION': 'Final disposition', 'DOC01_ENCLOSURE': 'DOC_01 enclosure'}


def stage_text(a) -> str:
    st = a.workflow_stage or ''
    if st.startswith('INSPECTOR_REVIEW#'): return f'Inspector review #{st.split("#", 1)[1]}'
    return STAGE_TEXT.get(st, st.replace('_', ' ').title() or 'Record')


def evidence_index(db, r: Rfi, W) -> list:
    """Management remarks and the attachment index appended to the DOC_03 (UI design s.17.1). Only submitted (locked) items."""
    from sqlalchemy import or_, and_, func
    remarks = list(db.scalars(select(ManagementRemark).where(ManagementRemark.status == 'SUBMITTED', or_(ManagementRemark.rfi_id == r.id,
                   and_(ManagementRemark.rfi_id.is_(None), ManagementRemark.summary_id == r.summary_id) if r.summary_id else ManagementRemark.id == -1))
                   .order_by(ManagementRemark.submitted_at)))
    files = list(db.scalars(select(Attachment).where(Attachment.is_active == True, Attachment.removed_at.is_(None), Attachment.locked_at.is_not(None),
                 func.coalesce(Attachment.upload_status, 'COMPLETE') == 'COMPLETE', Attachment.superseded_at.is_(None),
                 or_(Attachment.rfi_id == r.id, and_(Attachment.entity_type == 'rfi', Attachment.entity_id == r.id),
                     and_(Attachment.summary_id == r.summary_id, Attachment.rfi_id.is_(None), Attachment.attachment_kind == 'MANAGEMENT_REMARK') if r.summary_id else Attachment.id == -1))
                 .order_by(Attachment.uploaded_at, Attachment.id)))
    if not remarks and not files:
        return []
    nm = {u.id: u.full_name for u in db.scalars(select(User).where(User.id.in_({x.author_id for x in remarks} | {f.uploaded_by for f in files} or {-1})))}
    out = [Spacer(1, 3 * mm)]
    if remarks:
        rows = [[p('Management remark', P8B), p('By', P8B), p('Date', P8B), p('Remark', P8B)]]
        for m in remarks:
            rows.append([p(STAGE_TEXT.get(m.stage, m.stage), P7), p(f'{m.author_name_snapshot or nm.get(m.author_id, "")} ({m.author_role})', P7), p(fmt_dt(m.submitted_at), P7), p(m.body, P7)])
        t = Table(rows, colWidths=[W * .17, W * .2, W * .13, W * .5], repeatRows=1)
        t.setStyle(TableStyle(GRID + [('BACKGROUND', (0, 0), (-1, 0), SHADE)])); out += [t, Spacer(1, 2 * mm)]
    if files:
        rows = [[p('#', P8B), p('Attachment index - stage', P8B), p('File', P8B), p('Added by', P8B), p('Uploaded', P8B), p('SHA-256', P8B)]]
        for i, f in enumerate(files, 1):
            rows.append([p(i, P7), p(stage_text(f), P7), p(f'{f.original_name} ({max(1, round((f.size_bytes or 0) / 1024))} KB)' + (f' v{f.version_no}' if (f.version_no or 1) > 1 else ''), P7),
                         p(f'{nm.get(f.uploaded_by, "")} ({f.author_role or "-"})', P7), p(fmt_dt(f.uploaded_at), P7), p((f.sha256 or 'not recorded')[:32], P7)])
        t = Table(rows, colWidths=[W * .04, W * .17, W * .3, W * .19, W * .12, W * .18], repeatRows=1)
        t.setStyle(TableStyle(GRID + [('BACKGROUND', (0, 0), (-1, 0), SHADE)])); out.append(t)
        out.append(Paragraph('Original files are kept in RFIMS and are released according to project and record permissions. The SHA-256 value identifies each file exactly.', P7))
    return out


def issue_doc03(db, r: Rfi, user: User):
    data = build_doc03_pdf(db, r)
    folder = Path(app_settings.upload_dir) / 'issued'
    folder.mkdir(parents=True, exist_ok=True)
    name = f'issued/doc03_{r.project_id}_{r.id}_rev{r.revision_no}_{uuid4().hex[:8]}.pdf'
    (Path(app_settings.upload_dir) / name).write_bytes(data)
    doc = IssuedDocument(rfi_id=r.id, project_id=r.project_id, revision_no=r.revision_no, doc_type='DOC03', stored_name=name,
                         sha256=hashlib.sha256(data).hexdigest(), issued_by=user.id)
    db.add(doc); db.flush()
    return doc


# --------------------------------------------------------------------------------------------- DOC_01
def build_doc01_pdf(db, s: RfiSummary, rows: list) -> bytes:
    project = db.get(Project, s.project_id)
    nm = {u.id: u.full_name for u in db.scalars(select(User).where(User.id.in_({s.submitted_by, s.received_by} - {None})))}
    out = BytesIO()
    doc = SimpleDocTemplate(out, pagesize=landscape(A4), leftMargin=8 * mm, rightMargin=8 * mm, topMargin=8 * mm, bottomMargin=13 * mm, title=f'DOC_01 {s.summary_reference}')
    W = landscape(A4)[0] - 16 * mm
    story = []
    t = Table([[p('Consultant', P9B), p('Employer', P9B), p('Contractor', P9B)], [p(project.consultant), p(project.employer), p(project.contractor)],
               [p(project.name, P8B), '', '']], colWidths=[W / 3] * 3)
    t.setStyle(TableStyle(GRID + [('SPAN', (0, 2), (2, 2)), ('BACKGROUND', (0, 0), (-1, 0), SHADE)]))
    story += [t, Spacer(1, 2 * mm), Paragraph('Daily Request For Inspection Summary Sheet', TITLE),
              Paragraph(f'Batch: {e(s.summary_reference)} &nbsp; Status: {e(s.workflow_status)} &nbsp; Submitted: {fmt_dt(s.submitted_at) or "not submitted"}', P8), Spacer(1, 1.5 * mm)]
    head1 = [p('RFI No', P8B), p('Description', P8B), p('Station', P8B), '', '', p('Material Source', P8B), '', p('Requested Date', P8B), '', p('Inspection Date', P8B), '', p('Remark', P8B)]
    head2 = ['', '', p('From', P8B), p('to', P8B), p('Side', P8B), p('Location', P8B), p('offset', P8B), p('Date', P8B), p('Time', P8B), p('Date', P8B), p('Time', P8B), '']
    data = [head1, head2]
    for r in rows:
        rem = ' '.join(x for x in [r.remarks, '[SHORT NOTICE]' if r.short_notice else None, f'Rev {r.revision_no}' if r.revision_no else None] if x)
        data.append([p(r.rfi_number, P7), p(r.contractor_request or r.description, P7), p(r.chainage_from, P7), p(r.chainage_to, P7), p(r.side, P7),
                     p(r.material_source or r.material_source_designation, P7), p(r.material_source_offset, P7), p(fmt_d(r.requested_date), P7), p(r.requested_time, P7),
                     p(fmt_d(r.inspection_date), P7), p(r.inspection_time, P7), p(rem, P7)])
    cw = [22, 70, 20, 20, 13, 30, 15, 18, 13, 18, 13, 29]
    k = W / (sum(cw) * mm)
    t = Table(data, colWidths=[c * mm * k for c in cw], repeatRows=2)
    t.setStyle(TableStyle(GRID + [('SPAN', (0, 0), (0, 1)), ('SPAN', (1, 0), (1, 1)), ('SPAN', (2, 0), (4, 0)), ('SPAN', (5, 0), (6, 0)), ('SPAN', (7, 0), (8, 0)),
                                  ('SPAN', (9, 0), (10, 0)), ('SPAN', (11, 0), (11, 1)), ('BACKGROUND', (0, 0), (-1, 1), SHADE)]))
    story += [t, Spacer(1, 5 * mm)]
    sub = f'Name: {e(s.contractor_rep_name or nm.get(s.submitted_by))}<br/>Signature: ' + (f'electronically submitted via RFIMS<br/>Date: {fmt_dt(s.submitted_at)}' if s.submitted_at else '____________<br/>Date: ____________')
    rec = f'Name: {e(nm.get(s.received_by))}<br/>Signature: electronically acknowledged<br/>Date: {fmt_dt(s.received_at)}' if s.received_at else 'Name: ____________<br/>Signature: ____________<br/>Date: ____________'
    t = Table([[Paragraph('<b>Contractor Representative</b><br/>' + sub, P8), Paragraph('<b>Consultant Representative</b><br/>' + rec, P8)]], colWidths=[W / 2] * 2)
    story.append(t)
    doc.build(story, canvasmaker=canvas_with(f'{project.code} | DOC_01 {s.summary_reference} | Generated {datetime.utcnow():%d/%m/%Y %H:%M} UTC by RFIMS'))
    return out.getvalue()


# --------------------------------------------------------------------------------------------- DOC_02
# Workbook `RFI` sheet columns (header row 8) in their original order, then system columns.
REGISTER_COLUMNS = [
    ('Contractor_Request', lambda r, x: r.contractor_request), ('Item', lambda r, x: r.work_item), ('Structure_Type/Building Block', lambda r, x: r.structure_type),
    ('Description', lambda r, x: r.description), ('Test', lambda r, x: r.test_name), ('Road_Type', lambda r, x: r.road_type), ('Direction', lambda r, x: r.direction),
    ('Side/Inlet/Outlet', lambda r, x: r.side), ('Fill Layer/CheckDam/Pww', lambda r, x: r.fill_layer),
    ('Material_Source_or_Desitination Type', lambda r, x: r.material_source_type), ('Material_Source_Cut_Sec_[Sta. From-Sta. To]', lambda r, x: r.material_source_cut_section),
    ('Material_Source_Designation', lambda r, x: r.material_source_designation or r.material_source), ('Material_Destination/Disposal_Designation', lambda r, x: r.material_destination_designation),
    ('Requested_From', lambda r, x: r.chainage_from), ('Requested_To', lambda r, x: r.chainage_to), ('RFI_No.', lambda r, x: r.rfi_number),
    ('Inspection_Date', lambda r, x: r.inspection_date), ('Inspection_Time', lambda r, x: r.inspection_time or r.inspection_time_text), ('Work_Status', lambda r, x: r.work_status),
    ('RFI_Status', lambda r, x: x['rfi_status']), ('Approved_From', lambda r, x: r.approved_from), ('Approved_To', lambda r, x: r.approved_to),
    ('Application Rate', lambda r, x: r.application_rate), ('Quantity G-40', lambda r, x: r.quantity_g40), ('All Quantity [& G-60]', lambda r, x: r.all_quantity),
    ('Remark', lambda r, x: r.remarks), ('File_Path', lambda r, x: LEGACY_FILE_UNAVAILABLE if r.legacy_file_path else x.get('doc_link', '')),
    ('RFI Included under IPC', lambda r, x: r.legacy_ipc_included), ('IPC File_Path', lambda r, x: LEGACY_FILE_UNAVAILABLE if r.legacy_ipc_file_path else ''),
    # system columns
    ('Revision', lambda r, x: r.revision_no), ('DOC_01 Batch', lambda r, x: x['batch']), ('Submitted At', lambda r, x: x['submitted_at']),
    ('Requested Date', lambda r, x: display_requested_date(r)), ('Requested Time', lambda r, x: r.requested_time), ('Material Source Offset', lambda r, x: r.material_source_offset),
    ('BOQ Item', lambda r, x: r.boq_item), ('Short Notice', lambda r, x: 'Yes' if r.short_notice else ('No' if r.short_notice is False else '')),
    ('Assigned Inspectors (sequence)', lambda r, x: x['inspectors']), ('Workflow Status', lambda r, x: STATUS_LABELS.get(r.workflow_status, r.workflow_status)),
    ('Decision', lambda r, x: r.current_decision), ('Decided By', lambda r, x: x['decided_by']), ('Decided At', lambda r, x: x['decided_at']),
    ('Provenance', lambda r, x: r.provenance), ('Record State', lambda r, x: r.record_state),
]


def register_extras(db, rows):
    ids = [r.id for r in rows]
    if not ids: return {}
    project_settings = {}
    batches = {b.id: b for b in db.scalars(select(RfiSummary).where(RfiSummary.id.in_({r.summary_id for r in rows if r.summary_id} or {-1})))}
    assigns = list(db.scalars(select(ReviewerAssignment).where(ReviewerAssignment.rfi_id.in_(ids), ReviewerAssignment.status != 'REPLACED').order_by(ReviewerAssignment.sequence_no)))
    decs = {}
    for d in db.scalars(select(Decision).where(Decision.rfi_id.in_(ids)).order_by(Decision.id)): decs[d.rfi_id] = d
    uids = {a.user_id for a in assigns} | {d.decided_by for d in decs.values()}
    nm = {u.id: u.full_name for u in db.scalars(select(User).where(User.id.in_(uids or {-1})))}
    ins = {}
    for a in assigns: ins.setdefault(a.rfi_id, []).append(f'{a.sequence_no}. {nm.get(a.user_id, "")} ({a.reviewer_role.replace("_", " ").title()})')
    out = {}
    for r in rows:
        if r.project_id not in project_settings: project_settings[r.project_id] = get_settings(db.get(Project, r.project_id))
        d = decs.get(r.id)
        legacy = r.provenance == 'LEGACY_IMPORT' or r.summary_id is None
        disp = disposition(project_settings[r.project_id], r.current_disposition) if r.current_disposition else None
        b = batches.get(r.summary_id)
        out[r.id] = {'rfi_status': (r.legacy_rfi_status if legacy else (disp['label'] if disp else r.current_decision)) or '',
                     'batch': b.summary_reference if b else '', 'submitted_at': b.submitted_at if b else None,
                     'inspectors': '; '.join(ins.get(r.id, [])), 'decided_by': (d.decided_by_name_snapshot or nm.get(d.decided_by)) if d else '', 'decided_at': d.decided_at if d else None,
                     'doc_link': f'Completed DOC_03 in RFIMS (record {r.id})' if (r.workflow_status == 'COMPLETED' and not legacy) else ''}
    return out


# Workbook columns I:M and S are hidden in the client's workbook. Their values are kept; who may see them is a project setting (UD-06).
HIDDEN_HEADERS = {'Fill Layer/CheckDam/Pww', 'Material_Source_or_Desitination Type', 'Material_Source_Cut_Sec_[Sta. From-Sta. To]',
                  'Material_Source_Designation', 'Material_Destination/Disposal_Designation', 'Work_Status'}


def register_xlsx(db, rows, project_label: str, filters: dict, user: User, hidden_allowed=lambda r: True, show_hidden: bool = False) -> bytes:
    wb = Workbook(); ws = wb.active; ws.title = 'RFI'
    ncol = len(REGISTER_COLUMNS)
    ws.cell(1, 1, f'PROJECT:- {project_label}').font = Font(bold=True, size=12)
    ws.cell(2, 1, f'DOC_02 Main RFI Record Sheet - exported {datetime.utcnow():%d/%m/%Y %H:%M} UTC by {user.full_name} - {len(rows)} record(s)')
    restricted = any(not hidden_allowed(r) for r in rows)
    ws.cell(3, 1, (('Filters: ' + '; '.join(f'{k}={v}' for k, v in filters.items())) if filters else 'Filters: none (all authorised records)')
            + (' | Workbook columns I:M and S are restricted for your role and left blank.' if restricted else ''))
    hdr_row = 4
    fill = PatternFill('solid', fgColor='DDEBF7'); thin = Side(style='thin', color='9FB3C8')
    for i, (h, _) in enumerate(REGISTER_COLUMNS, 1):
        c = ws.cell(hdr_row, i, h); c.font = Font(bold=True); c.fill = fill; c.alignment = Alignment(wrap_text=True, vertical='center', horizontal='center'); c.border = Border(bottom=thin, top=thin, left=thin, right=thin)
    ex = register_extras(db, rows)
    for ri, r in enumerate(rows, hdr_row + 1):
        x = ex[r.id]
        ok = hidden_allowed(r)
        for ci, (h, fn) in enumerate(REGISTER_COLUMNS, 1):
            v = fn(r, x) if (ok or h not in HIDDEN_HEADERS) else None
            c = ws.cell(ri, ci, v)
            if hasattr(v, 'year') and hasattr(v, 'hour'): c.number_format = 'dd/mm/yyyy hh:mm'
            elif hasattr(v, 'year'): c.number_format = 'dd/mm/yyyy'
    widths = {'Contractor_Request': 48, 'Description': 34, 'Remark': 30, 'Assigned Inspectors (sequence)': 40, 'File_Path': 34, 'IPC File_Path': 34}
    for i, (h, _) in enumerate(REGISTER_COLUMNS, 1):
        ws.column_dimensions[get_column_letter(i)].width = widths.get(h, max(11, min(24, len(h) + 2)))
        if h in HIDDEN_HEADERS and not show_hidden:
            ws.column_dimensions[get_column_letter(i)].hidden = True  # as in the client's workbook; values stay in the file
    ws.row_dimensions[hdr_row].height = 32
    ws.freeze_panes = ws.cell(hdr_row + 1, 1)
    ws.auto_filter.ref = f'A{hdr_row}:{get_column_letter(ncol)}{max(hdr_row, hdr_row + len(rows))}'
    out = BytesIO(); wb.save(out); return out.getvalue()


# key -> (header, width, value). Keys match the register screen's column ids, so the PDF follows the user's visible columns.
PDF_CATALOG = {
    'rfi_number': ('RFI No.', 26, lambda r, x: r.rfi_number), 'revision_no': ('Rev', 7, lambda r, x: r.revision_no),
    'inspection_date': ('Insp. Date', 17, lambda r, x: fmt_d(r.inspection_date)), 'inspection_time': ('Time', 11, lambda r, x: r.inspection_time or r.inspection_time_text),
    'work_item': ('Item', 26, lambda r, x: r.work_item), 'contractor_request': ('Contractor Request / Works Description', 70, lambda r, x: r.contractor_request or r.description),
    'description': ('Description', 40, lambda r, x: r.description), 'structure_type': ('Structure type', 24, lambda r, x: r.structure_type),
    'chainage_from': ('From', 18, lambda r, x: r.chainage_from), 'chainage_to': ('To', 18, lambda r, x: r.chainage_to), 'side': ('Side', 12, lambda r, x: r.side),
    'road_type': ('Road Type', 15, lambda r, x: r.road_type), 'direction': ('Direction', 12, lambda r, x: r.direction),
    'rfi_status': ('RFI Status / Disposition', 42, lambda r, x: x['rfi_status']), 'approved_from': ('Appr. From', 17, lambda r, x: r.approved_from),
    'approved_to': ('Appr. To', 17, lambda r, x: r.approved_to), 'inspectors': ('Inspectors (sequence)', 50, lambda r, x: x['inspectors']),
    'workflow_status': ('Workflow', 24, lambda r, x: STATUS_LABELS.get(r.workflow_status, r.workflow_status)), 'batch': ('Batch', 22, lambda r, x: x['batch']),
    'remarks': ('Remark', 30, lambda r, x: r.remarks), 'boq_item': ('BOQ', 14, lambda r, x: r.boq_item),
    'fill_layer': ('Fill Layer', 18, lambda r, x: r.fill_layer), 'material_source_type': ('Mat. Source Type', 20, lambda r, x: r.material_source_type),
    'material_source_cut_section': ('Mat. Cut Sec.', 20, lambda r, x: r.material_source_cut_section),
    'material_source_designation': ('Mat. Source Desig.', 24, lambda r, x: r.material_source_designation or r.material_source),
    'material_destination_designation': ('Mat. Destination', 22, lambda r, x: r.material_destination_designation), 'work_status': ('Work_Status', 18, lambda r, x: r.work_status),
}
HIDDEN_KEYS = {'fill_layer', 'material_source_type', 'material_source_cut_section', 'material_source_designation', 'material_destination_designation', 'work_status'}
PDF_DEFAULT = ['rfi_number', 'revision_no', 'inspection_date', 'inspection_time', 'work_item', 'contractor_request', 'chainage_from', 'chainage_to', 'side', 'road_type',
               'rfi_status', 'approved_from', 'approved_to', 'inspectors', 'workflow_status', 'batch', 'remarks']
PDF_COLS = [(PDF_CATALOG[k][0], PDF_CATALOG[k][1]) for k in PDF_DEFAULT]


def register_pdf(db, rows, project_label: str, filters: dict, user: User, columns: list | None = None, hidden_allowed=lambda r: True) -> bytes:
    out = BytesIO()
    size = landscape(A3)
    doc = SimpleDocTemplate(out, pagesize=size, leftMargin=8 * mm, rightMargin=8 * mm, topMargin=8 * mm, bottomMargin=12 * mm, title='DOC_02 RFI Register')
    W = size[0] - 16 * mm
    ex = register_extras(db, rows)
    story = [Paragraph(f'PROJECT:- {e(project_label)}', P9B), Paragraph('DOC_02 - Main RFI Record Sheet', TITLE),
             Paragraph(f'Exported {datetime.utcnow():%d/%m/%Y %H:%M} UTC by {e(user.full_name)} - {len(rows)} record(s). '
                       + ('Filters: ' + e('; '.join(f'{k}={v}' for k, v in filters.items())) if filters else 'Filters: none (all authorised records)'), P8), Spacer(1, 2 * mm)]
    keys = [c for c in (columns or PDF_DEFAULT) if c in PDF_CATALOG] or PDF_DEFAULT
    if any(not hidden_allowed(r) for r in rows):
        keys = [c for c in keys if c not in HIDDEN_KEYS]  # restricted hidden workbook fields are never printed
    cols = [PDF_CATALOG[k] for k in keys]
    data = [[p(h, P7) for h, _, _ in cols]]
    for r in rows:
        x = ex[r.id]
        data.append([p(fn(r, x), P7) for _, _, fn in cols])
    k = W / (sum(w for _, w, _ in cols) * mm)
    t = Table(data, colWidths=[w * mm * k for _, w, _ in cols], repeatRows=1)
    t.setStyle(TableStyle(GRID + [('BACKGROUND', (0, 0), (-1, 0), SHADE), ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F6F8FA')])]))
    story.append(t)
    doc.build(story, canvasmaker=canvas_with(f'{project_label[:90]} | DOC_02 register | Generated by RFIMS'))
    return out.getvalue()
