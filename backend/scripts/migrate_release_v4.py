"""Safe additive migration for existing MySQL databases. Run once before starting updated backend."""
from sqlalchemy import inspect, text
from app.database import engine

with engine.begin() as conn:
    inspector=inspect(conn)
    if not inspector.has_table('daily_progress'):
        print('No daily_progress table yet; fresh install will create columns automatically.')
    else:
        cols={c['name'] for c in inspector.get_columns('daily_progress')}
        for name in ('review_comment','confirmation_comment'):
            if name not in cols:
                conn.execute(text(f'ALTER TABLE daily_progress ADD COLUMN {name} TEXT NULL'))
                print('Added daily_progress.'+name)
            else:print('Already exists: daily_progress.'+name)
    if inspector.has_table('rfis'):
        cols={c['name']:c for c in inspector.get_columns('rfis')}
        for name in ('chainage_from','chainage_to'):
            if name in cols and getattr(cols[name]['type'],'length',None) not in (None,255):
                conn.execute(text(f'ALTER TABLE rfis MODIFY COLUMN {name} VARCHAR(255) NULL'))
                print('Expanded rfis.'+name)
print('Migration finished. No tables or rows deleted.')
