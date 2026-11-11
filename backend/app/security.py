from datetime import datetime,timedelta,timezone
from jose import jwt,JWTError
from passlib.context import CryptContext
from fastapi import Depends,HTTPException
from fastapi.security import HTTPBearer,HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.config import settings
from app.database import get_db
from app.models import User
pwd=CryptContext(schemes=['bcrypt'],deprecated='auto'); bearer=HTTPBearer(auto_error=False)
def hash_password(v): return pwd.hash(v)
def verify_password(v,h): return pwd.verify(v,h)
def create_access_token(user):
    exp=datetime.now(timezone.utc)+timedelta(minutes=settings.access_token_expire_minutes)
    return jwt.encode({'sub':str(user.id),'role':user.role,'exp':exp},settings.jwt_secret,algorithm=settings.jwt_algorithm)
def current_user(credentials:HTTPAuthorizationCredentials|None=Depends(bearer),db:Session=Depends(get_db)):
    if not credentials: raise HTTPException(401,'Not authenticated')
    try: uid=int(jwt.decode(credentials.credentials,settings.jwt_secret,algorithms=[settings.jwt_algorithm])['sub'])
    except (JWTError,KeyError,ValueError): raise HTTPException(401,'Invalid or expired token')
    u=db.get(User,uid)
    if not u or not u.is_active: raise HTTPException(401,'User inactive or missing')
    return u
def require_roles(*roles):
    def check(user:User=Depends(current_user)):
        if user.role not in roles: raise HTTPException(403,'Insufficient permission')
        return user
    return check
