from datetime import datetime,timedelta
import secrets
from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User
from app.schemas import LoginIn,Token,ForgotPasswordIn,ResetPasswordIn
from app.security import verify_password,create_access_token,hash_password
from app.services.emailer import send_email
from app.config import settings
router=APIRouter(prefix='/auth',tags=['Auth'])

@router.post('/login',response_model=Token)
def login(data:LoginIn,db:Session=Depends(get_db)):
    u=db.scalar(select(User).where(User.email==data.email.lower()))
    if not u or not u.is_active or not verify_password(data.password,u.password_hash):raise HTTPException(401,'Invalid email or password')
    u.last_login_at=datetime.utcnow();db.commit();return Token(access_token=create_access_token(u))

@router.post('/forgot-password')
def forgot(data:ForgotPasswordIn,db:Session=Depends(get_db)):
    u=db.scalar(select(User).where(User.email==data.email))
    if u and u.is_active:
        u.reset_token=secrets.token_urlsafe(32);u.reset_expires_at=datetime.utcnow()+timedelta(hours=1);db.commit()
        base=settings.frontend_origin.rstrip('/')
        send_email(u.email,'RFI System password reset',f'Open this link within 1 hour:\n{base}/reset-password?token={u.reset_token}\n\nIf you did not request this, ignore this email.')
    return {'message':'If the email exists, reset instructions were sent.'}

@router.post('/reset-password')
def reset(data:ResetPasswordIn,db:Session=Depends(get_db)):
    if len(data.new_password)<10: raise HTTPException(400,'Password must be at least 10 characters')
    u=db.scalar(select(User).where(User.reset_token==data.token))
    if not u or not u.reset_expires_at or u.reset_expires_at<datetime.utcnow():raise HTTPException(400,'Invalid or expired reset token')
    u.password_hash=hash_password(data.new_password);u.reset_token=None;u.reset_expires_at=None;u.must_change_password=False;db.commit();return {'ok':True}
