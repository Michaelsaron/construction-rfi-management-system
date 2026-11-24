"""Login throttling, cookie sessions, CSRF, session invalidation and enforced password change."""
import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app, security_check
from app.config import settings
from app.ratelimit import limiter
from app.database import SessionLocal
from app.models import AuditLog, User
from conftest import PW, login


@pytest.fixture(autouse=True)
def fresh_limiter():
    limiter.clear(); yield; limiter.clear()


def new_user(admin, temporary=False):
    email = f'sec.{uuid.uuid4().hex[:8]}@test.io'
    r = admin.post('/users', {'full_name': 'Sec User', 'email': email, 'password': PW, 'role': 'VIEWER', 'memberships': []})
    assert r.status_code == 200, r.text
    if not temporary:
        from conftest import clear_must_change
        clear_must_change(email)
    return email, r.json()['id']


def browser():
    return TestClient(app)  # own cookie jar, like a separate browser


def test_browser_login_uses_httponly_strict_cookie_and_no_token_in_body(admin):
    email, _ = new_user(admin)
    b = browser()
    r = b.post('/auth/login', json={'email': email, 'password': PW})
    assert r.status_code == 200 and r.json().get('access_token') is None
    raw = '\n'.join(v for k, v in r.headers.multi_items() if k.lower() == 'set-cookie')
    session = [c for c in raw.split('\n') if c.startswith(settings.session_cookie_name + '=')][0].lower()
    assert 'httponly' in session and 'samesite=strict' in session and 'path=/' in session
    csrf = [c for c in raw.split('\n') if c.startswith(settings.csrf_cookie_name + '=')][0].lower()
    assert 'httponly' not in csrf
    assert b.get('/me').json()['email'] == email


def test_cookie_session_requires_csrf_header_for_writes(admin):
    email, _ = new_user(admin)
    b = browser(); b.post('/auth/login', json={'email': email, 'password': PW})
    assert b.post('/notifications/read-all').status_code == 403
    assert b.post('/notifications/read-all', headers={'X-CSRF-Token': 'wrong'}).status_code == 403
    token = b.cookies.get(settings.csrf_cookie_name)
    assert b.post('/notifications/read-all', headers={'X-CSRF-Token': token}).status_code == 200
    # GET needs no CSRF token
    assert b.get('/notifications').status_code == 200


def test_logout_clears_the_session(admin):
    email, _ = new_user(admin)
    b = browser(); b.post('/auth/login', json={'email': email, 'password': PW})
    assert b.post('/auth/logout').status_code == 200
    assert b.get('/me').status_code == 401


def test_account_lockout_after_repeated_failures(admin):
    email, uid = new_user(admin)
    other, _ = new_user(admin)
    b = browser()
    for i in range(settings.login_max_failures - 1):
        assert b.post('/auth/login', json={'email': email, 'password': 'wrong-password'}).status_code == 401
    r = b.post('/auth/login', json={'email': email, 'password': 'wrong-password'})
    assert r.status_code == 429 and int(r.headers['Retry-After']) > 0
    # even the correct password is refused while locked
    assert b.post('/auth/login', json={'email': email, 'password': PW}).status_code == 429
    # other accounts are not affected
    assert b.post('/auth/login', json={'email': other, 'password': PW}).status_code == 200
    with SessionLocal() as db:
        actions = [a.action for a in db.query(AuditLog).filter_by(entity_type='USER', entity_id=uid)]
    assert actions.count('LOGIN_FAILED') == settings.login_max_failures - 1 and 'LOGIN_LOCKED' in actions


def test_unknown_email_is_throttled_like_a_real_one():
    b = browser()
    ghost = f'ghost.{uuid.uuid4().hex[:6]}@test.io'
    codes = [b.post('/auth/login', json={'email': ghost, 'password': 'x'}).status_code for _ in range(settings.login_max_failures)]
    assert codes == [401] * (settings.login_max_failures - 1) + [429]


def test_per_ip_ceiling(admin, monkeypatch):
    monkeypatch.setattr(settings, 'login_ip_max_attempts', 3)
    b = browser()
    codes = [b.post('/auth/login', json={'email': f'n{i}.{uuid.uuid4().hex[:4]}@test.io', 'password': 'x'}).status_code for i in range(4)]
    assert codes[:2] == [401, 401] and codes[2] == 429 and codes[3] == 429


def test_password_change_ends_other_sessions(client, admin):
    email, _ = new_user(admin)
    old = login(client, email)
    second = login(client, email)
    r = client.post('/me/password', json={'current_password': PW, 'new_password': 'BrandNewPass123!'},
                    headers={**old.h(), 'X-Auth-Mode': 'bearer'})
    assert r.status_code == 200
    client.cookies.clear()
    new_token = r.json()['access_token']
    assert old.get('/me').status_code == 401 and second.get('/me').status_code == 401
    assert client.get('/me', headers={'Authorization': f'Bearer {new_token}'}).status_code == 200


def test_deactivated_user_is_rejected_immediately(client, admin):
    email, uid = new_user(admin)
    api = login(client, email)
    assert api.get('/me').status_code == 200
    assert admin.post(f'/users/{uid}/toggle-active').status_code == 200
    assert api.get('/me').status_code == 401


def test_temporary_password_must_be_changed_before_use(client, admin):
    email, _ = new_user(admin, temporary=True)
    api = login(client, email, keep_temporary_password=True)
    assert api.get('/me').json()['must_change_password'] is True
    assert api.get('/projects').status_code == 403
    r = client.post('/me/password', json={'current_password': PW, 'new_password': 'MyOwnPassword123!'}, headers={**api.h(), 'X-Auth-Mode': 'bearer'})
    assert r.status_code == 200
    client.cookies.clear()
    assert client.get('/projects', headers={'Authorization': f"Bearer {r.json()['access_token']}"}).status_code == 200


def test_forgot_password_is_throttled_without_revealing_accounts(admin, monkeypatch):
    email, _ = new_user(admin)
    b = browser()
    msgs = {b.post('/auth/forgot-password', json={'email': email}).json()['message'] for _ in range(settings.reset_max_per_email_per_hour + 2)}
    assert msgs == {'If the email exists, reset instructions were sent.'}
    with SessionLocal() as db:
        n = db.query(AuditLog).join(User, User.id == AuditLog.entity_id).filter(User.email == email, AuditLog.action == 'PASSWORD_RESET_REQUESTED').count()
    assert n == settings.reset_max_per_email_per_hour
    monkeypatch.setattr(settings, 'reset_ip_max_per_hour', 2)
    limiter.clear()
    codes = [b.post('/auth/forgot-password', json={'email': f'x{i}@test.io'}).status_code for i in range(3)]
    assert codes[-1] == 429


def test_production_refuses_weak_jwt_secret(monkeypatch):
    monkeypatch.setattr(settings, 'environment', 'production')
    monkeypatch.setattr(settings, 'jwt_secret', 'short')
    with pytest.raises(RuntimeError):
        security_check()
    monkeypatch.setattr(settings, 'jwt_secret', 'x' * 48)
    monkeypatch.setenv('MYSQL_PASSWORD', 'ChangeMe_Rfi_123!')
    assert 'MYSQL_PASSWORD' in security_check()


def test_api_responses_are_not_cacheable(client):
    assert client.get('/health').headers.get('cache-control') == 'no-store'


def test_successful_sign_ins_from_a_shared_office_ip_are_not_limited(admin, monkeypatch):
    monkeypatch.setattr(settings, 'login_ip_max_attempts', 3)
    email, _ = new_user(admin)
    b = browser()
    assert all(b.post('/auth/login', json={'email': email, 'password': PW}).status_code == 200 for _ in range(6))
