import asyncio
from sqlalchemy import select, inspect
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import Base, engine, SessionLocal
from app.models import User, Project, MasterData
from app.security import hash_password
from app.services.notify import create_overdue_notifications
from app.routers import auth, users, projects, master_data, summaries, rfis, attachments, daily_progress, audit, reports, system, evidence, records, admin

VERSION = '6.0.0-ui'
app = FastAPI(title=settings.app_name, version=VERSION)
app.add_middleware(CORSMiddleware, allow_origins=[settings.frontend_origin], allow_credentials=True, allow_methods=['*'], allow_headers=['*'])


@app.middleware('http')
async def security_headers(request, call_next):
    resp = await call_next(request)
    resp.headers.setdefault('X-Content-Type-Options', 'nosniff')
    resp.headers.setdefault('X-Frame-Options', 'DENY')
    resp.headers.setdefault('Referrer-Policy', 'same-origin')
    resp.headers.setdefault('Cache-Control', 'no-store')  # API data must not be kept by browsers or proxies
    return resp


# Columns added by scripts/migrate_srs_v5.py. If they are missing the database has not been migrated,
# and this release must not run against it (create_all() never adds columns to existing tables).
REQUIRED_COLUMNS = {'rfis': {'inspection_time', 'provenance', 'current_disposition'}, 'reviewer_assignments': {'sequence_no', 'draft_comment'},
                    'project_users': {'role', 'status'}, 'decisions': {'disposition_code', 'designation_snapshot'}, 'audit_logs': {'project_id'},
                    # release 6.0.0-ui (scripts/migrate_ui_v1.py)
                    'attachments': {'attachment_kind', 'project_id', 'sha256', 'upload_token', 'locked_at', 'management_remark_id', 'assignment_id'},
                    'reviews': {'reviewer_name_snapshot', 'attachment_count'}, 'rfi_amendments': {'amendment_type'}}


def schema_check():
    insp = inspect(engine)
    missing = []
    for table, cols in REQUIRED_COLUMNS.items():
        if insp.has_table(table):
            have = {c['name'] for c in insp.get_columns(table)}
            missing += [f'{table}.{c}' for c in cols - have]
    if missing:
        raise RuntimeError('Database schema is older than this release. Run `python -m scripts.migrate_srs_v5 --apply` and then '
                           '`python -m scripts.migrate_ui_v1 --apply` after taking a verified backup. Missing: ' + ', '.join(missing))


async def overdue_loop():
    while True:
        await asyncio.sleep(3600)
        db = SessionLocal()
        try: create_overdue_notifications(db)
        except Exception as e: print('[OVERDUE-WARN]', e)
        finally: db.close()


# Values published in .env.example. They must never protect a production system.
EXAMPLE_SECRETS = ('ChangeMe_Rfi_123!', 'ChangeMe_Root_123!', 'Admin123!', 'change-this', 'replace-with')


def security_check():
    """Refuse to start in production with a weak JWT secret; warn about example values that must be rotated."""
    if settings.environment != 'production':
        return []
    if len(settings.jwt_secret) < 32 or any(x in settings.jwt_secret for x in EXAMPLE_SECRETS):
        raise RuntimeError('JWT_SECRET must be a random value of at least 32 characters in production')
    warnings = []
    import os
    for name in ('MYSQL_PASSWORD', 'MYSQL_ROOT_PASSWORD', 'DATABASE_URL', 'ADMIN_PASSWORD'):
        if any(x in (os.environ.get(name) or '') for x in EXAMPLE_SECRETS):
            warnings.append(name)
    if warnings:
        print('[SECURITY-WARNING] example values from .env.example are still in use for: ' + ', '.join(warnings)
              + '. Rotate them (docs/deployment/SECURITY.md).', flush=True)
    return warnings


@app.on_event('startup')
def startup():
    security_check()
    schema_check()  # refuse to start (and create nothing) on an unmigrated existing database
    Base.metadata.create_all(bind=engine)  # creates only missing NEW tables on a migrated / fresh database
    db = SessionLocal()
    try:
        if not db.scalar(select(User).where(User.email == settings.admin_email)):
            if settings.environment == 'production' and settings.admin_password == 'Admin123!':
                raise RuntimeError('Set ADMIN_PASSWORD in .env before first production start')
            db.add(User(full_name=settings.admin_name, email=settings.admin_email, password_hash=hash_password(settings.admin_password), role='ADMIN', must_change_password=True))
        if settings.environment not in ('production', 'test') and not db.scalar(select(Project).where(Project.code == 'DEMO')):
            db.add(Project(code='DEMO', name='Demo Road & Bridge Project', project_type='ROAD_BRIDGE', employer='Employer', consultant='Consultant', contractor='Contractor'))
        db.commit()
        p = db.scalar(select(Project).where(Project.code == 'DEMO'))
        if p:
            seeds = {'WORK_ITEM': ['Embankment', 'Subgrade', 'SubBase', 'RoadBase', 'Asphalt', 'Pipe Culvert', 'Slab Culvert', 'Concrete', 'Reinforcement', 'Surveying'],
                     'SIDE': ['LHS', 'RHS', 'BHS', 'Centre', 'Full Width'], 'DIRECTION': ['BOP', 'EOP'], 'ROAD_TYPE': ['AC', 'Main Road', 'Service Road'],
                     'WORK_STATUS': ['Done', 'Done with Note', 'On_Progress', 'Not Done']}
            for cat, vals in seeds.items():
                for val in vals:
                    if not db.scalar(select(MasterData).where(MasterData.project_id == p.id, MasterData.category == cat, MasterData.value == val)):
                        db.add(MasterData(project_id=p.id, category=cat, value=val))
            db.commit()
    finally:
        db.close()
    if settings.environment != 'test':
        try: asyncio.get_running_loop().create_task(overdue_loop())
        except RuntimeError: pass


@app.get('/health')
def health(): return {'status': 'ok', 'app': settings.app_name, 'version': VERSION}


for r in [auth.router, users.router, projects.router, master_data.router, summaries.router, records.router, rfis.router, attachments.router, evidence.router,
          admin.router, daily_progress.router, audit.router, reports.router, system.router]:
    app.include_router(r)
