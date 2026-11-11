import sys
import pandas as pd
from sqlalchemy import select
from app.database import SessionLocal
from app.models import Project,Rfi,User

def clean(v):
    if pd.isna(v): return None
    s=str(v).strip()
    return s or None

def main(path,project_code='DEMO'):
    db=SessionLocal();df=pd.read_csv(path);p=db.scalar(select(Project).where(Project.code==project_code));u=db.scalar(select(User).where(User.role=='ADMIN'))
    if not p or not u: raise RuntimeError('Start app first so project/admin exist')
    imported=skipped=0
    for _,row in df.iterrows():
        no=clean(row.get('RFI_No.'))
        if not no: skipped+=1;continue
        if db.scalar(select(Rfi).where(Rfi.project_id==p.id,Rfi.rfi_number==no,Rfi.revision_no==0)): skipped+=1;continue
        r=Rfi(
            project_id=p.id,rfi_number=no,revision_no=0,
            contractor_request=clean(row.get('Contractor_Request')),
            work_item=clean(row.get('Item')) or 'Legacy',
            structure_type=clean(row.get('Structure_Type/Building Block')),
            description=clean(row.get('Description')) or 'Legacy imported record',
            test_name=clean(row.get('Test')),
            road_type=clean(row.get('Road_Type')),
            direction=clean(row.get('Direction')),
            side=clean(row.get('Side/Inlet/Outlet')),
            fill_layer=clean(row.get('Fill Layer/CheckDam/Pww')),
            material_source_type=clean(row.get('Material_Source_or_Desitination Type')),
            material_source_cut_section=clean(row.get('Material_Source_Cut_Sec_[Sta. From-Sta. To]')),
            material_source_designation=clean(row.get('Material_Source_Designation')),
            material_destination_designation=clean(row.get('Material_Destination/Disposal_Designation')),
            chainage_from=clean(row.get('Requested_From')),
            chainage_to=clean(row.get('Requested_To')),
            work_status=clean(row.get('Work_Status')),
            current_decision=clean(row.get('RFI_Status')),
            approved_from=clean(row.get('Approved_From')),
            approved_to=clean(row.get('Approved_To')),
            application_rate=clean(row.get('Application Rate')),
            quantity_g40=clean(row.get('Quantity G-40')),
            all_quantity=clean(row.get('All Quantity [& G-60]')),
            remarks=clean(row.get('Remark')),
            legacy_file_path=clean(row.get('File_Path')),
            legacy_ipc_included=clean(row.get('RFI Included under IPC')),
            legacy_ipc_file_path=clean(row.get('File_Path[IPC]')),
            workflow_status='COMPLETED',created_by=u.id
        )
        db.add(r);imported+=1
    db.commit();db.close();print({'source_rows':len(df),'imported':imported,'skipped':skipped})

if __name__=='__main__':
    if len(sys.argv)<2:
        print('Usage: python scripts/migrate_csv.py /path/to/RFI.csv [PROJECT_CODE]');raise SystemExit(1)
    main(sys.argv[1],sys.argv[2] if len(sys.argv)>2 else 'DEMO')
