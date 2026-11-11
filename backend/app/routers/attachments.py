from pathlib import Path
from fastapi import APIRouter,Depends,UploadFile,File,Form,HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.config import settings
from app.database import get_db
from app.models import Attachment,User,Rfi,RfiSummary,DailyProgress
from app.security import current_user,require_roles
from app.services.files import save_upload
from app.services.audit import log
router=APIRouter(prefix='/attachments',tags=['Attachments'])
ENTITY={'rfi':Rfi,'summary':RfiSummary,'daily_progress':DailyProgress}
def check_entity(db,t,i):
    model=ENTITY.get(t.lower())
    if not model:raise HTTPException(400,'Unsupported attachment entity')
    if not db.get(model,i):raise HTTPException(404,'Parent record not found')
@router.get('/download/{aid}')
def download(aid:int,db:Session=Depends(get_db),_=Depends(current_user)):
    a=db.get(Attachment,aid)
    if not a or not a.is_active:raise HTTPException(404,'Attachment not found')
    p=Path(settings.upload_dir)/a.stored_name
    if not p.exists():raise HTTPException(404,'Stored file missing')
    return FileResponse(p,filename=a.original_name,media_type=a.content_type or 'application/octet-stream')
@router.get('/{entity_type}/{entity_id}')
def ls(entity_type:str,entity_id:int,db:Session=Depends(get_db),_=Depends(current_user)):
    check_entity(db,entity_type,entity_id);return list(db.scalars(select(Attachment).where(Attachment.entity_type==entity_type.lower(),Attachment.entity_id==entity_id,Attachment.is_active==True).order_by(Attachment.id.desc())))
@router.post('/{entity_type}/{entity_id}')
def upload(entity_type:str,entity_id:int,file:UploadFile=File(...),description:str|None=Form(None),db:Session=Depends(get_db),u:User=Depends(current_user)):
    entity_type=entity_type.lower();check_entity(db,entity_type,entity_id);stored,size=save_upload(file);a=Attachment(entity_type=entity_type,entity_id=entity_id,original_name=file.filename or stored,stored_name=stored,content_type=file.content_type,size_bytes=size,description=description,uploaded_by=u.id);db.add(a);db.commit();db.refresh(a);log(db,u.id,entity_type.upper(),entity_id,'UPLOAD',a.original_name);return a
@router.delete('/{aid}')
def remove(aid:int,db:Session=Depends(get_db),u:User=Depends(require_roles('ADMIN','RE','ARE','RE_ARE'))):
    a=db.get(Attachment,aid)
    if not a:raise HTTPException(404,'Attachment not found')
    a.is_active=False;db.commit();log(db,u.id,a.entity_type.upper(),a.entity_id,'REMOVE_ATTACHMENT',a.original_name);return {'ok':True}
