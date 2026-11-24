from pydantic_settings import BaseSettings, SettingsConfigDict
class Settings(BaseSettings):
    app_name:str='Construction RFI Management System'; environment:str='development'; database_url:str; jwt_secret:str; jwt_algorithm:str='HS256'; access_token_expire_minutes:int=480
    admin_email:str='admin@example.com'; admin_password:str='Admin123!'; admin_name:str='System Admin'; frontend_origin:str='http://localhost:5173'; upload_dir:str='/app/uploads'; max_upload_mb:int=50
    smtp_host:str|None=None; smtp_port:int=587; smtp_user:str|None=None; smtp_password:str|None=None; smtp_from:str|None=None; smtp_tls:bool=True; overdue_hours:int=24; site_timezone:str='Africa/Addis_Ababa'
    # Sessions: HttpOnly cookie (browser) or Bearer header (API clients). cookie_secure=None -> Secure in production.
    session_cookie_name:str='rfi_session'; csrf_cookie_name:str='rfi_csrf'; cookie_secure:bool|None=None
    # Trust X-Real-IP / X-Forwarded-For only when the backend is reachable ONLY through our nginx.
    trust_proxy_headers:bool=False
    # Login throttling (per account and per IP) and password-reset throttling.
    login_max_failures:int=5; login_failure_window_minutes:int=15; login_lockout_minutes:int=15
    login_ip_max_attempts:int=30;  # failed attempts per IP per window
    login_ip_window_minutes:int=15
    reset_max_per_email_per_hour:int=3; reset_ip_max_per_hour:int=10
    model_config=SettingsConfigDict(env_file='.env',extra='ignore')
settings=Settings()


def cookie_secure() -> bool:
    return settings.cookie_secure if settings.cookie_secure is not None else settings.environment == 'production'
