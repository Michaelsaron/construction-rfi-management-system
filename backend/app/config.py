from pydantic_settings import BaseSettings, SettingsConfigDict
class Settings(BaseSettings):
    app_name:str='Construction RFI Management System'; environment:str='development'; database_url:str; jwt_secret:str; jwt_algorithm:str='HS256'; access_token_expire_minutes:int=480
    admin_email:str='admin@example.com'; admin_password:str='Admin123!'; admin_name:str='System Admin'; frontend_origin:str='http://localhost:5173'; upload_dir:str='/app/uploads'; max_upload_mb:int=50
    smtp_host:str|None=None; smtp_port:int=587; smtp_user:str|None=None; smtp_password:str|None=None; smtp_from:str|None=None; smtp_tls:bool=True; overdue_hours:int=24
    model_config=SettingsConfigDict(env_file='.env',extra='ignore')
settings=Settings()
