"""Import the client project, master-data lists, and historical RFI register.
Safe to run more than once: existing project/master values/RFI numbers are skipped.
Usage: python scripts/import_client_bundle.py
"""
from pathlib import Path
from datetime import datetime
import pandas as pd
from sqlalchemy import select
from app.database import SessionLocal, Base, engine
from app.models import Project,User,MasterData,Rfi
from app.security import hash_password

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data'/'client_import'
PROJECT_CODE='DUBTI-LOT-II'
PROJECT_NAME='Construction Works Of Dubti-Arrisa-Adigala-Biyokebob; Lot II: KM 72+000-KM 150+000 Design and Build Road Project'
EMPLOYER='ETHIOPIAN ROADS AUTHORITY'
CONTRACTOR='MACRO GENERAL CONTRACTOR & TRADING P.L.C.'
CONSULTANT='ELDA ENGINEERING CONSULTANTS in Sub-Consultancy with DAMARA CONSULTING ENGINEERS'
CLIENT_EMAIL='frew99@gmail.com'

STATUS_MAP={
 'accepted':'APPROVED','accepted as noted':'APPROVED','approved':'APPROVED','approved: for further works':'APPROVED','approved: compliance to comments required':'APPROVED',
 'rejected':'REJECTED','not approved':'REJECTED','not approved: rfi to be resubmitted':'REJECTED','not ready':'ON_PROGRESS','information':'INFORMATION_ONLY','information only':'INFORMATION_ONLY'
}

def clean(v):
    if pd.isna(v): return None
    s=str(v).strip()
    return s or None

def datev(v):
    if pd.isna(v) or str(v).strip()=='': return None
    for dayfirst in (False,True):
        try:
            x=pd.to_datetime(v,errors='raise',dayfirst=dayfirst)
            return x.date()
        except Exception: pass
    return None

def add_master(db,pid,cat,val,parent=None,code=None):
    val=clean(val)
    if not val:return
    q=select(MasterData).where(MasterData.project_id==pid,MasterData.category==cat,MasterData.value==val)
    if parent is not None:q=q.where(MasterData.parent_value==parent)
    if not db.scalar(q):db.add(MasterData(project_id=pid,category=cat,value=val,parent_value=parent,code=code))

def import_info(db,pid):
    df=pd.read_csv(DATA/'SRT_RFI_Summary_DG-Info.csv',header=None)
    # direction, side, work status, historical RFI status, road type
    for v in df.iloc[1:,4].tolist(): add_master(db,pid,'DIRECTION',v)
    for v in df.iloc[1:,5].tolist(): add_master(db,pid,'SIDE',v)
    for v in df.iloc[1:,6].tolist(): add_master(db,pid,'WORK_STATUS',v)
    for v in ['APPROVED','REJECTED','ON_PROGRESS','INFORMATION_ONLY']: add_master(db,pid,'RFI_DECISION',v)
    for v in df.iloc[1:,7].tolist(): add_master(db,pid,'LEGACY_RFI_STATUS',v)
    for v in df.iloc[1:,11].tolist(): add_master(db,pid,'ROAD_TYPE',v)

def import_work_list(db,pid):
    df=pd.read_csv(DATA/'SRT_RFI_Summary_DG-Work_List.csv',header=None)
    headers=[clean(x) for x in df.iloc[0].tolist()]
    # Column F is the master Item list; H is Structure_Type. Columns L+ are dependent descriptions keyed by header.
    for v in df.iloc[1:,5].tolist(): add_master(db,pid,'WORK_ITEM',v)
    for v in df.iloc[1:,7].tolist(): add_master(db,pid,'STRUCTURE_TYPE',v)
    for col in range(11,len(headers)):
        parent=headers[col]
        if not parent: continue
        parent=parent
        for v in df.iloc[1:,col].tolist(): add_master(db,pid,'WORK_DESCRIPTION',v,parent=parent)

def import_materials(db,pid):
    df=pd.read_csv(DATA/'SRT_RFI_Summary_DG-Material_Source.csv',header=None)
    headers=[clean(x) for x in df.iloc[0].tolist()]
    for v in df.iloc[1:,0].tolist(): add_master(db,pid,'MATERIAL_SOURCE_TYPE',v)
    for col in range(2,len(headers)):
        parent=headers[col]
        if not parent: continue
        p=parent
        for v in df.iloc[1:,col].tolist(): add_master(db,pid,'MATERIAL_SOURCE',v,parent=p)

def import_row(db,pid):
    df=pd.read_csv(DATA/'SRT_RFI_Summary_DG-ROW_List.csv')
    for _,r in df.iterrows(): add_master(db,pid,'ROW_LOCATION',r.get('ROW_ITEM_Designation'))

def import_earthworks(db,pid):
    df=pd.read_csv(DATA/'SRT_RFI_Summary_DG-EW_List.csv')
    mapping={'Cut_Material_Type':'EW_CUT_MATERIAL','Fill_Material_Type':'EW_FILL_MATERIAL','C_F_Status':'EW_STATUS','UC_Exc_Type':'EW_UC_EXC','UC_Replacement_Type':'EW_UC_REPLACEMENT'}
    for col,cat in mapping.items():
        for v in df[col].tolist(): add_master(db,pid,cat,v)

def import_daily(db,pid):
    df=pd.read_csv(DATA/'SRT_RFI_Summary_DG-Daily_Progress_List.csv',header=None)
    headers=[clean(x) for x in df.iloc[0].tolist()]
    for v in df.iloc[1:,0].tolist(): add_master(db,pid,'DAILY_ITEM',v)
    for col in range(2,len(headers)):
        parent=headers[col]
        if not parent: continue
        for v in df.iloc[1:,col].tolist(): add_master(db,pid,'DAILY_STATUS',v,parent=parent)


def import_test_and_mix(db,pid):
    # Test_List contains placeholder/test values, so use actual historical RFI Test values instead.
    rdf=pd.read_csv(DATA/'SRT_RFI_Summary_DG-RFI.csv',header=7)
    if 'Test' in rdf.columns:
        for v in rdf['Test'].dropna().unique().tolist(): add_master(db,pid,'TEST',v)
    cpath=DATA/'SRT_RFI_Summary_DG-Concrete_Mix_Design.csv'
    if cpath.exists():
        cdf=pd.read_csv(cpath)
        for col in cdf.columns:
            if 'Designation' in str(col) or str(col).lower().startswith('mix'):
                for v in cdf[col].dropna().tolist(): add_master(db,pid,'CONCRETE_MIX_DESIGN',v)

def import_rfis(db,pid,uid):
    df=pd.read_csv(DATA/'SRT_RFI_Summary_DG-RFI.csv',header=7)
    imported=skipped=0;conflicts=[];seen=set()
    for _,row in df.iterrows():
        no=clean(row.get('RFI_No.'))
        if not no: skipped+=1;continue
        if no in seen or db.scalar(select(Rfi).where(Rfi.project_id==pid,Rfi.rfi_number==no,Rfi.revision_no==0)):
            skipped+=1;conflicts.append({'RFI_No':no,'Reason':'Duplicate RFI number / existing Rev 0'});continue
        seen.add(no)
        raw_status=clean(row.get('RFI_Status'))
        normalized=STATUS_MAP.get((raw_status or '').lower())
        workflow='COMPLETED' if normalized else 'ARCHIVED'
        r=Rfi(project_id=pid,rfi_number=no,revision_no=0,contractor_request=clean(row.get('Contractor_Request')),work_item=clean(row.get('Item')) or 'Legacy',structure_type=clean(row.get('Structure_Type/Building Block')),description=clean(row.get('Description')) or 'Legacy imported record',test_name=clean(row.get('Test')),road_type=clean(row.get('Road_Type')),direction=clean(row.get('Direction')),side=clean(row.get('Side/Inlet/Outlet')),fill_layer=clean(row.get('Fill Layer/CheckDam/Pww')),material_source_type=clean(row.get('Material_Source_or_Desitination Type')),material_source_cut_section=clean(row.get('Material_Source_Cut_Sec_[Sta. From-Sta. To]')),material_source_designation=clean(row.get('Material_Source_Designation')),material_destination_designation=clean(row.get('Material_Destination/Disposal_Designation')),chainage_from=clean(row.get('Requested_From')),chainage_to=clean(row.get('Requested_To')),requested_date=datev(row.get('Inspection_Date')),inspection_date=datev(row.get('Inspection_Date')),work_status=clean(row.get('Work_Status')),current_decision=normalized,approved_from=clean(row.get('Approved_From')),approved_to=clean(row.get('Approved_To')),application_rate=clean(row.get('Application Rate')),quantity_g40=clean(row.get('Quantity G-40')),all_quantity=clean(row.get('All Quantity [& G-60]')),remarks=(clean(row.get('Remark')) or '') + (f' | Legacy status: {raw_status}' if raw_status else ''),legacy_file_path=clean(row.get('File_Path')),legacy_ipc_included=clean(row.get('RFI Included under IPC')),legacy_ipc_file_path=clean(row.get('File_Path[IPC]')),workflow_status=workflow,record_state='ACTIVE',created_by=uid)
        db.add(r);imported+=1
    if conflicts: pd.DataFrame(conflicts).to_csv(ROOT/'migration_conflicts.csv',index=False)
    return imported,skipped

def main():
    Base.metadata.create_all(bind=engine);db=SessionLocal()
    try:
        p=db.scalar(select(Project).where(Project.code==PROJECT_CODE))
        if not p:
            p=Project(code=PROJECT_CODE,name=PROJECT_NAME,project_type='ROAD_BRIDGE',employer=EMPLOYER,consultant=CONSULTANT,contractor=CONTRACTOR);db.add(p);db.commit();db.refresh(p)
        admin=db.scalar(select(User).where(User.role=='ADMIN'))
        if not admin: raise RuntimeError('Start the app once so an admin exists')
        are=db.scalar(select(User).where(User.email==CLIENT_EMAIL))
        if not are:
            # Safe local temporary password; user must change it immediately in Users screen.
            are=User(full_name='Client ARE',email=CLIENT_EMAIL,password_hash=hash_password('ChangeMe_ARE_2026!'),role='ARE',must_change_password=True);db.add(are);db.commit();db.refresh(are)
        import_info(db,p.id);import_work_list(db,p.id);import_materials(db,p.id);import_row(db,p.id);import_earthworks(db,p.id);import_daily(db,p.id);import_test_and_mix(db,p.id);db.commit()
        imported,skipped=import_rfis(db,p.id,admin.id);db.commit()
        print({'project_id':p.id,'client_are_email':are.email,'historical_imported':imported,'historical_skipped':skipped})
        print('TEMP password for local client account: ChangeMe_ARE_2026!  -> change immediately before production')
    finally: db.close()
if __name__=='__main__': main()
