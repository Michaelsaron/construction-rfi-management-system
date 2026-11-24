from datetime import datetime, timedelta
import secrets
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User
from app.schemas import LoginIn, Token, ForgotPasswordIn, ResetPasswordIn
from app.security import verify_password, create_access_token, hash_password, set_session_cookies, clear_session_cookies
from app.services.emailer import send_email
from app.services.audit import log
from app.ratelimit import limiter, client_ip
from app.config import settings

router = APIRouter(prefix='/auth', tags=['Auth'])
GENERIC_LOGIN_ERROR = 'Invalid email or password'
# A dummy hash so unknown e-mails take as long as real ones (no account enumeration by timing).
_DUMMY_HASH = hash_password(secrets.token_urlsafe(16))


def _too_many(seconds: int, what='sign-in attempts'):
    minutes = max(1, round(seconds / 60))
    raise HTTPException(429, f'Too many {what}. Try again in about {minutes} minute(s).', headers={'Retry-After': str(seconds)})


@router.post('/login', response_model=Token, response_model_exclude_none=True)
def login(data: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    email = data.email.lower()
    ip = client_ip(request, settings.trust_proxy_headers)
    acct_key, ip_key = f'login:acct:{email}', f'login:ip:{ip}'
    for key in (acct_key, ip_key):
        wait = limiter.retry_after(key)
        if wait: _too_many(wait)
    u = db.scalar(select(User).where(User.email == email))
    ok = verify_password(data.password, u.password_hash if u else _DUMMY_HASH) and u is not None and u.is_active
    if not ok:
        wait = limiter.hit(acct_key, settings.login_max_failures, settings.login_failure_window_minutes * 60, settings.login_lockout_minutes * 60)
        # Per-IP ceiling counts FAILED attempts only, so a site office sharing one IP is never blocked by normal sign-ins.
        ip_wait = limiter.hit(ip_key, settings.login_ip_max_attempts, settings.login_ip_window_minutes * 60)
        if u:
            log(db, u.id, 'USER', u.id, 'LOGIN_LOCKED' if wait else 'LOGIN_FAILED', f'ip {ip}', commit=True)
        if wait: _too_many(wait)
        if ip_wait: _too_many(ip_wait)
        raise HTTPException(401, GENERIC_LOGIN_ERROR)
    limiter.reset(acct_key)
    u.last_login_at = datetime.utcnow()
    log(db, u.id, 'USER', u.id, 'LOGIN', f'ip {ip}')
    db.commit()
    token = create_access_token(u)
    set_session_cookies(response, token)
    # Browsers get only the HttpOnly cookie. API clients may ask for the token explicitly.
    if request.headers.get('X-Auth-Mode', '').lower() == 'bearer':
        return Token(access_token=token)
    return Token(access_token=None, token_type='cookie')


@router.post('/logout')
def logout(response: Response):
    clear_session_cookies(response)
    return {'ok': True}


@router.post('/forgot-password')
def forgot(data: ForgotPasswordIn, request: Request, db: Session = Depends(get_db)):
    email = data.email.lower()
    ip = client_ip(request, settings.trust_proxy_headers)
    wait = limiter.retry_after(f'reset:ip:{ip}') or limiter.hit(f'reset:ip:{ip}', settings.reset_ip_max_per_hour, 3600)
    if wait: _too_many(wait, 'password-reset requests')
    msg = {'message': 'If the email exists, reset instructions were sent.'}
    # Per-address limit is silent so the response never reveals whether the address exists.
    if limiter.retry_after(f'reset:acct:{email}') or limiter.hit(f'reset:acct:{email}', settings.reset_max_per_email_per_hour + 1, 3600):
        return msg
    u = db.scalar(select(User).where(User.email == email))
    if u and u.is_active:
        u.reset_token = secrets.token_urlsafe(32); u.reset_expires_at = datetime.utcnow() + timedelta(hours=1)
        log(db, u.id, 'USER', u.id, 'PASSWORD_RESET_REQUESTED', f'ip {ip}')
        db.commit()
        base = settings.frontend_origin.rstrip('/')
        send_email(u.email, 'RFI System password reset', f'Open this link within 1 hour:\n{base}/reset-password?token={u.reset_token}\n\nIf you did not request this, ignore this email.')
    return msg


@router.post('/reset-password')
def reset(data: ResetPasswordIn, request: Request, db: Session = Depends(get_db)):
    ip = client_ip(request, settings.trust_proxy_headers)
    wait = limiter.retry_after(f'resetuse:ip:{ip}') or limiter.hit(f'resetuse:ip:{ip}', settings.reset_ip_max_per_hour, 3600)
    if wait: _too_many(wait, 'password-reset attempts')
    if len(data.new_password) < 10: raise HTTPException(400, 'Password must be at least 10 characters')
    u = db.scalar(select(User).where(User.reset_token == data.token))
    if not u or not u.reset_expires_at or u.reset_expires_at < datetime.utcnow(): raise HTTPException(400, 'Invalid or expired reset token')
    u.password_hash = hash_password(data.new_password); u.reset_token = None; u.reset_expires_at = None; u.must_change_password = False
    log(db, u.id, 'USER', u.id, 'PASSWORD_RESET_COMPLETED', f'ip {ip}')
    db.commit()
    limiter.reset(f'login:acct:{u.email}')
    return {'ok': True}
