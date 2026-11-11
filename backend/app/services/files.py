from pathlib import Path
from uuid import uuid4
from fastapi import HTTPException
from app.config import settings
ALLOWED={'.pdf','.jpg','.jpeg','.png','.xls','.xlsx','.doc','.docx','.dwg','.dxf','.dgn'}
def save_upload(file):
    ext=Path(file.filename or '').suffix.lower()
    if ext not in ALLOWED: raise HTTPException(400,f'File type {ext} not allowed')
    data=file.file.read()
    if len(data)>settings.max_upload_mb*1024*1024: raise HTTPException(400,'File too large')
    Path(settings.upload_dir).mkdir(parents=True,exist_ok=True); stored=f'{uuid4().hex}{ext}'; (Path(settings.upload_dir)/stored).write_bytes(data); return stored,len(data)
