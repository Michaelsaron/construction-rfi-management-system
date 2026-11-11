from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import MasterData,User
from app.schemas import MasterCreate,MasterUpdate
from app.security import current_user,require_roles
from app.services.audit import log
router=APIRouter(prefix='/master-data',tags=['Master Data'])
@router.get('')
def ls(category:str|None=None,project_id:int|None=None,db:Session=Depends(get_db),_=Depends(current_user)):
    q=select(MasterData).where(MasterData.is_active==True)
    if category:q=q.where(MasterData.category==category)
    if project_id:q=q.where((MasterData.project_id==project_id)|(MasterData.project_id==None))
    return list(db.scalars(q.order_by(MasterData.category,MasterData.value)))
@router.post('')
def create(d:MasterCreate,db:Session=Depends(get_db),u:User=Depends(require_roles('ADMIN','RE','ARE','RE_ARE'))):
    m=MasterData(**d.model_dump());db.add(m)
    try:db.commit()
    except Exception:db.rollback();raise HTTPException(409,'Duplicate master data')
    db.refresh(m);log(db,u.id,'MASTER_DATA',m.id,'CREATE');return m
@router.put('/{mid}')
def update(mid:int,d:MasterUpdate,db:Session=Depends(get_db),u:User=Depends(require_roles('ADMIN','RE','ARE','RE_ARE'))):
    m=db.get(MasterData,mid)
    if not m:raise HTTPException(404,'Reference value not found')
    m.value=d.value;m.parent_value=d.parent_value;m.code=d.code;db.commit();log(db,u.id,'MASTER_DATA',m.id,'EDIT');return m
@router.delete('/{mid}')
def deactivate(mid:int,db:Session=Depends(get_db),u:User=Depends(require_roles('ADMIN','RE','ARE','RE_ARE'))):
    m=db.get(MasterData,mid)
    if not m:raise HTTPException(404,'Reference value not found')
    m.is_active=False;db.commit();log(db,u.id,'MASTER_DATA',m.id,'DEACTIVATE');return {'ok':True}
