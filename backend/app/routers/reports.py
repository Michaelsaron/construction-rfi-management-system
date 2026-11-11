from io import BytesIO
from fastapi import APIRouter,Depends,HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from openpyxl import Workbook
from openpyxl.styles import Font,PatternFill,Alignment,Border,Side
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4,landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate,Table,TableStyle,Paragraph,Spacer,PageBreak
from reportlab.lib.units import mm
from app.database import get_db
from app.models import Rfi,Project,Decision,ReviewerAssignment,Review,RfiSummary,DailyProgress,DailyProgressRfi,AuditLog,User
from app.security import current_user
from app.services.audit import log
router=APIRouter(prefix='/reports',tags=['Reports'])

def xlsx_response(wb,name):
    out=BytesIO();wb.save(out);out.seek(0);return StreamingResponse(out,media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',headers={'Content-Disposition':f'attachment; filename={name}'})

def style_ws(ws):
    fill=PatternFill('solid',fgColor='DDEBF7');thin=Side(style='thin',color='B8C7D1')
    for c in ws[1]:c.font=Font(bold=True);c.fill=fill;c.alignment=Alignment(horizontal='center',vertical='center',wrap_text=True);c.border=Border(bottom=thin)
    ws.freeze_panes='A2';ws.auto_filter.ref=ws.dimensions
    for col in range(1,ws.max_column+1):
        width=min(max(12,max(len(str(ws.cell(r,col).value or '')) for r in range(1,min(ws.max_row,100)+1))+2),38);ws.column_dimensions[get_column_letter(col)].width=width

def page_number(canvas,doc):
    canvas.saveState();canvas.setFont('Helvetica',7);canvas.drawRightString(A4[0]-15*mm,10*mm,f'Page {doc.page}');canvas.restoreState()

@router.get('/rfi-register.xlsx')
def excel(project_id:int|None=None,db:Session=Depends(get_db),u:User=Depends(current_user)):
    q=select(Rfi).order_by(Rfi.id)
    if project_id:q=q.where(Rfi.project_id==project_id)
    rows=list(db.scalars(q));wb=Workbook();ws=wb.active;ws.title='RFI Register'
    headers=['RFI No','Revision','Contractor Request','Item','Structure Type','Description','Test','Road Type','Direction','Side','Requested From','Requested To','Inspection Date','Work Status','Workflow','Final Decision','Approved From','Approved To','Application Rate','Quantity G-40','All Quantity','Remark','Record State']
    ws.append(headers)
    for r in rows:ws.append([r.rfi_number,r.revision_no,r.contractor_request,r.work_item,r.structure_type,r.description,r.test_name,r.road_type,r.direction,r.side,r.chainage_from,r.chainage_to,r.inspection_date,r.work_status,r.workflow_status,r.current_decision,r.approved_from,r.approved_to,r.application_rate,r.quantity_g40,r.all_quantity,r.remarks,r.record_state])
    style_ws(ws);log(db,u.id,'REPORT',project_id or 0,'EXPORT_EXCEL','RFI register');return xlsx_response(wb,'rfi_register.xlsx')

@router.get('/rfi/{rid}.pdf')
def pdf(rid:int,db:Session=Depends(get_db),u:User=Depends(current_user)):
    r=db.get(Rfi,rid)
    if not r:raise HTTPException(404,'RFI not found')
    p=db.get(Project,r.project_id);assign=list(db.scalars(select(ReviewerAssignment).where(ReviewerAssignment.rfi_id==rid)));reviews=list(db.scalars(select(Review).where(Review.rfi_id==rid)));dec=list(db.scalars(select(Decision).where(Decision.rfi_id==rid).order_by(Decision.id.desc())));rm={x.assignment_id:x for x in reviews};d=dec[0] if dec else None
    out=BytesIO();doc=SimpleDocTemplate(out,pagesize=A4,rightMargin=14*mm,leftMargin=14*mm,topMargin=12*mm,bottomMargin=15*mm);styles=getSampleStyleSheet();story=[]
    story.append(Paragraph('<b>REQUEST FOR WORK INSPECTION / APPROVAL</b>',styles['Title']));story.append(Spacer(1,5*mm))
    info=[['Project',p.name if p else ''],['Employer',p.employer if p else ''],['Consultant',p.consultant if p else ''],['Contractor',p.contractor if p else ''],['RFI No.',f'{r.rfi_number} / Rev {r.revision_no}'],['Work Item',r.work_item],['Description',r.description],['Location',f'{r.chainage_from or ""} - {r.chainage_to or ""} {r.side or ""}'],['Requested / Inspection Date',f'{r.requested_date or ""} / {r.inspection_date or ""}'],['Material Source',r.material_source_designation or r.material_source or '']]
    t=Table(info,colWidths=[42*mm,135*mm]);t.setStyle(TableStyle([('GRID',(0,0),(-1,-1),.4,colors.grey),('BACKGROUND',(0,0),(0,-1),colors.HexColor('#EAF7FF')),('FONTNAME',(0,0),(0,-1),'Helvetica-Bold'),('VALIGN',(0,0),(-1,-1),'TOP'),('FONTSIZE',(0,0),(-1,-1),8)]));story.append(t);story.append(Spacer(1,5*mm))
    review_rows=[['Reviewer','Required','Recommendation','Comment','Date']]
    for a in assign:
        rv=rm.get(a.id);review_rows.append([a.reviewer_role,'Yes' if a.required else 'No',rv.recommendation if rv else 'PENDING',rv.comment if rv else '',str(rv.reviewed_at.date()) if rv else ''])
    rt=Table(review_rows,colWidths=[35*mm,18*mm,34*mm,72*mm,22*mm],repeatRows=1);rt.setStyle(TableStyle([('GRID',(0,0),(-1,-1),.4,colors.grey),('BACKGROUND',(0,0),(-1,0),colors.HexColor('#DDEBF7')),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),7),('VALIGN',(0,0),(-1,-1),'TOP')]));story.append(Paragraph('<b>Engineer Review / Comment</b>',styles['Heading3']));story.append(rt);story.append(Spacer(1,5*mm))
    decision=[['RE/ARE Final Decision',d.decision if d else 'PENDING'],['Comment',d.comment if d else ''],['Decision Date',str(d.decided_at) if d else ''],['Override',('Yes - '+(d.override_reason or '')) if d and d.override_used else 'No']]
    dt=Table(decision,colWidths=[48*mm,129*mm]);dt.setStyle(TableStyle([('GRID',(0,0),(-1,-1),.5,colors.grey),('BACKGROUND',(0,0),(0,-1),colors.HexColor('#EAF7FF')),('FONTNAME',(0,0),(0,-1),'Helvetica-Bold'),('VALIGN',(0,0),(-1,-1),'TOP'),('FONTSIZE',(0,0),(-1,-1),8)]));story.append(dt);story.append(Spacer(1,8*mm));story.append(Paragraph('RE/ARE Name / Signature: ______________________________     Date: __________________',styles['Normal']))
    doc.build(story,onFirstPage=page_number,onLaterPages=page_number);out.seek(0);log(db,u.id,'RFI',rid,'EXPORT_PDF','Official RFI approval sheet');return StreamingResponse(out,media_type='application/pdf',headers={'Content-Disposition':f'attachment; filename=rfi_{r.rfi_number}_rev{r.revision_no}.pdf'})

@router.get('/rfi-summary/{sid}.pdf')
def summary_pdf(sid:int,db:Session=Depends(get_db),u:User=Depends(current_user)):
    s=db.get(RfiSummary,sid)
    if not s:raise HTTPException(404,'Summary not found')
    p=db.get(Project,s.project_id);rows=list(db.scalars(select(Rfi).where(Rfi.summary_id==sid).order_by(Rfi.id)))
    out=BytesIO();doc=SimpleDocTemplate(out,pagesize=landscape(A4),rightMargin=10*mm,leftMargin=10*mm,topMargin=10*mm,bottomMargin=12*mm);styles=getSampleStyleSheet();story=[Paragraph('<b>DAILY REQUEST FOR INSPECTION SUMMARY SHEET</b>',styles['Title']),Paragraph(p.name if p else '',styles['Normal']),Spacer(1,4*mm)]
    data=[['RFI No.','Rev','Description','Station From','Station To','Side','Requested Date','Inspection Date','Status / Remark']]
    for r in rows:data.append([r.rfi_number,r.revision_no,r.description,r.chainage_from or '',r.chainage_to or '',r.side or '',str(r.requested_date or ''),str(r.inspection_date or ''),r.current_decision or r.workflow_status])
    t=Table(data,colWidths=[22*mm,10*mm,72*mm,25*mm,25*mm,20*mm,28*mm,28*mm,42*mm],repeatRows=1);t.setStyle(TableStyle([('GRID',(0,0),(-1,-1),.4,colors.grey),('BACKGROUND',(0,0),(-1,0),colors.HexColor('#DDEBF7')),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),7),('VALIGN',(0,0),(-1,-1),'TOP')]));story.append(t);story.append(Spacer(1,8*mm));story.append(Paragraph('Contractor Representative: __________________    Consultant Representative: __________________',styles['Normal']));doc.build(story);out.seek(0);log(db,u.id,'RFI_SUMMARY',sid,'EXPORT_PDF');return StreamingResponse(out,media_type='application/pdf',headers={'Content-Disposition':f'attachment; filename=summary_{s.summary_reference}.pdf'})

@router.get('/daily-progress.xlsx')
def daily_excel(project_id:int|None=None,db:Session=Depends(get_db),u:User=Depends(current_user)):
    q=select(DailyProgress).order_by(DailyProgress.progress_date,DailyProgress.id)
    if project_id:q=q.where(DailyProgress.project_id==project_id)
    rows=list(db.scalars(q));wb=Workbook();ws=wb.active;ws.title='Daily Progress';ws.append(['Date','Work Item','Description','From','To','Side','Quantity','Unit','Status','Remarks'])
    for p in rows:ws.append([p.progress_date,p.work_item,p.description,p.chainage_from,p.chainage_to,p.side,p.quantity,p.unit,p.status,p.remarks])
    style_ws(ws);log(db,u.id,'REPORT',project_id or 0,'EXPORT_EXCEL','Daily Progress');return xlsx_response(wb,'daily_progress.xlsx')


@router.get('/daily-progress/{pid}.pdf')
def daily_progress_pdf(pid:int,db:Session=Depends(get_db),u:User=Depends(current_user)):
    from xml.sax.saxutils import escape
    from app.models import ProjectUser
    r=db.get(DailyProgress,pid)
    if not r:raise HTTPException(404,'Daily Progress not found')
    if u.role!='ADMIN' and not db.scalar(select(ProjectUser.id).where(ProjectUser.project_id==r.project_id,ProjectUser.user_id==u.id)):
        raise HTTPException(403,'Project access required')
    project=db.get(Project,r.project_id)
    def safe(v):return escape(str(v if v is not None else ''))
    linked=list(db.scalars(select(Rfi.rfi_number).join(DailyProgressRfi,DailyProgressRfi.rfi_id==Rfi.id).where(DailyProgressRfi.daily_progress_id==pid)))
    created=db.get(User,r.created_by);reviewed=db.get(User,r.reviewed_by) if r.reviewed_by else None;confirmed=db.get(User,r.confirmed_by) if r.confirmed_by else None
    rows=[('Project',project.name if project else ''),('Report #',r.id),('Progress Date',r.progress_date),('Work Item',r.work_item),('Description / Stage',r.description),('Chainage',f'{r.chainage_from or ""} - {r.chainage_to or ""}'),('Side',r.side),('Quantity / Unit',f'{r.quantity if r.quantity is not None else ""} {r.unit or ""}'),('Status',r.status),('Linked RFI numbers',', '.join(linked) or '-'),('Remarks',r.remarks),('Created by',created.full_name if created else r.created_by),('Inspector',reviewed.full_name if reviewed else '-'),('Inspector comment',r.review_comment),('Reviewed at',r.reviewed_at),('RE/ARE',confirmed.full_name if confirmed else '-'),('Confirmation comment',r.confirmation_comment),('Confirmed at',r.confirmed_at)]
    out=BytesIO();doc=SimpleDocTemplate(out,pagesize=A4,rightMargin=15*mm,leftMargin=15*mm,topMargin=15*mm,bottomMargin=15*mm)
    styles=getSampleStyleSheet();story=[Paragraph('DAILY CONSTRUCTION PROGRESS REPORT',styles['Title']),Spacer(1,5*mm)]
    table=Table([[Paragraph(f'<b>{safe(k)}</b>',styles['Normal']),Paragraph(safe(v),styles['Normal'])] for k,v in rows],colWidths=[50*mm,130*mm])
    table.setStyle(TableStyle([('GRID',(0,0),(-1,-1),.4,colors.grey),('VALIGN',(0,0),(-1,-1),'TOP'),('BACKGROUND',(0,0),(0,-1),colors.HexColor('#EAF7FF')),('LEFTPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7)]))
    story.extend([table,Spacer(1,10*mm),Paragraph('Inspector signature: ________________________   RE/ARE signature: ________________________',styles['Normal'])]);doc.build(story,onFirstPage=page_number,onLaterPages=page_number);out.seek(0)
    log(db,u.id,'DAILY_PROGRESS',pid,'EXPORT_PDF')
    return StreamingResponse(out,media_type='application/pdf',headers={'Content-Disposition':f'attachment; filename=daily_progress_{pid}.pdf'})
