"""Authentication: password hashing, session tokens, CSRF protection, current-user resolution.

Browser sessions use an HttpOnly + SameSite=Strict cookie (Secure in production), so page scripts never
see the token. Unsafe requests authenticated by that cookie must also carry the double-submit CSRF header.
API clients (and the automated tests) may still send `Authorization: Bearer <token>`; bearer requests are
not exposed to CSRF because browsers never add that header by themselves.

Every token carries a fingerprint of the user's password hash (`pv`), so changing or resetting a password
signs the user out everywhere. Deactivated users are rejected on every request.
"""
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, Request, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.config import settings, cookie_secure
from app.database import get_db
from app.models import User

pwd = CryptContext(schemes=['bcrypt'], deprecated='auto')
bearer = HTTPBearer(auto_error=False)
UNSAFE_METHODS = {'POST', 'PUT', 'PATCH', 'DELETE'}
CSRF_HEADER = 'X-CSRF-Token'
# Endpoints a user who must change their password may still call.
PASSWORD_CHANGE_ALLOWED = {'/me', '/me/password', '/auth/logout'}


def hash_password(v): return pwd.hash(v)
def verify_password(v, h): return pwd.verify(v, h)


def password_fingerprint(user: User) -> str:
    return hashlib.sha256(f'{user.id}:{user.password_hash}'.encode()).hexdigest()[:16]


def create_access_token(user):
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=settings.access_token_expire_minutes)
    return jwt.encode({'sub': str(user.id), 'pv': password_fingerprint(user), 'iat': now, 'exp': exp},
                      settings.jwt_secret, algorithm=settings.jwt_algorithm)


def set_session_cookies(response: Response, token: str):
    age = settings.access_token_expire_minutes * 60
    common = dict(max_age=age, secure=cookie_secure(), samesite='strict', path='/')
    response.set_cookie(settings.session_cookie_name, token, httponly=True, **common)
    # Readable by the page on purpose (double-submit CSRF token); worthless without the HttpOnly session cookie.
    response.set_cookie(settings.csrf_cookie_name, secrets.token_urlsafe(32), httponly=False, **common)


def clear_session_cookies(response: Response):
    for name, http_only in ((settings.session_cookie_name, True), (settings.csrf_cookie_name, False)):
        response.delete_cookie(name, path='/', secure=cookie_secure(), httponly=http_only, samesite='strict')


def _decode(token: str, db: Session) -> User:
    try:
        claims = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        uid = int(claims['sub'])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(401, 'Invalid or expired session')
    u = db.get(User, uid)
    if not u or not u.is_active:
        raise HTTPException(401, 'User inactive or missing')
    if not hmac.compare_digest(str(claims.get('pv', '')), password_fingerprint(u)):
        raise HTTPException(401, 'Session ended because the password was changed')
    return u


def authenticate(request: Request, credentials: HTTPAuthorizationCredentials | None, db: Session) -> User:
    if credentials:
        return _decode(credentials.credentials, db)
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise HTTPException(401, 'Not authenticated')
    if request.method in UNSAFE_METHODS:
        sent, expected = request.headers.get(CSRF_HEADER, ''), request.cookies.get(settings.csrf_cookie_name, '')
        if not expected or not hmac.compare_digest(sent, expected):
            raise HTTPException(403, 'Missing or invalid CSRF token')
    return _decode(token, db)


def current_user(request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)):
    u = authenticate(request, credentials, db)
    if u.must_change_password and request.url.path not in PASSWORD_CHANGE_ALLOWED:
        raise HTTPException(403, 'Password change required before using the system')
    return u


def require_roles(*roles):
    def check(user: User = Depends(current_user)):
        if user.role not in roles: raise HTTPException(403, 'Insufficient permission')
        return user
    return check
