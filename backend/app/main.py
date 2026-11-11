import asyncio
from sqlalchemy import select
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import Base,engine,SessionLocal
from app.models import User,Project,MasterData
from app.security import hash_password
from app.services.notify import create_overdue_notifications
from app.routers import auth,users,projects,master_data,summaries,rfis,attachments,daily_progress,audit,reports,system
app=FastAPI(title=settings.app_name,version='3.0.0')
app.add_middleware(CORSMiddleware,allow_origins=[settings.frontend_origin],allow_credentials=True,allow_methods=['*'],allow_headers=['*'])

async def overdue_loop():
    while True:
        await asyncio.sleep(3600)
        db=SessionLocal()
        try:create_overdue_notifications(db)
        except Exception as e:print('[OVERDUE-WARN]',e)
        finally:db.close()

@app.on_event('startup')
def startup():
    Base.metadata.create_all(bind=engine);db=SessionLocal()
    try:
        if not db.scalar(select(User).where(User.email==settings.admin_email)):db.add(User(full_name=settings.admin_name,email=settings.admin_email,password_hash=hash_password(settings.admin_password),role='ADMIN',must_change_password=True))
        if not db.scalar(select(Project).where(Project.code=='DEMO')):db.add(Project(code='DEMO',name='Demo Road & Bridge Project',project_type='ROAD_BRIDGE',employer='Employer',consultant='Consultant',contractor='Contractor'))
        db.commit();p=db.scalar(select(Project).where(Project.code=='DEMO'))
        seeds={'WORK_ITEM':['Embankment','Subgrade','SubBase','RoadBase','Asphalt','Pipe Culvert','Slab Culvert','Concrete','Reinforcement','Surveying'],'SIDE':['LHS','RHS','BHS','Centre','Full Width'],'DIRECTION':['BOP','EOP'],'ROAD_TYPE':['AC','Main Road','Service Road'],'RECOMMENDATION':['SATISFACTORY','CORRECTION_REQUIRED','REINSPECTION_REQUIRED','INFORMATION','NOT_APPLICABLE'],'WORK_STATUS':['Done','Done with Note','On_Progress','Not Done'],'RFI_DECISION':['APPROVED','REJECTED','ON_PROGRESS','INFORMATION_ONLY']}
        for cat,vals in seeds.items():
            for val in vals:
                if not db.scalar(select(MasterData).where(MasterData.project_id==p.id,MasterData.category==cat,MasterData.value==val)):db.add(MasterData(project_id=p.id,category=cat,value=val))
        db.commit()
    finally:db.close()
    try: asyncio.get_running_loop().create_task(overdue_loop())
    except RuntimeError: pass

@app.get('/health')
def health():return {'status':'ok','app':settings.app_name,'version':'3.0.0'}
for r in [auth.router,users.router,projects.router,master_data.router,summaries.router,rfis.router,attachments.router,daily_progress.router,audit.router,reports.router,system.router]:app.include_router(r)
