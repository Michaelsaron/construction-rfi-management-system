"""UI design v1 additive migration (release 6.0.0-ui). Run AFTER migrate_srs_v5.

SAFE BY DESIGN (same rules as migrate_srs_v5)
  * Dry run by default: prints every statement and the rows each data step would touch. Nothing is written.
  * `--apply` executes. Only CREATE TABLE / ADD COLUMN / ADD INDEX / ADD UNIQUE / ADD FOREIGN KEY / ADD CHECK. No DROP, no MODIFY,
    no DELETE. Data steps only fill NEW columns that are NULL. Historical RFIs, decisions, accounts and issued documents are untouched.
  * Idempotent: re-running skips what already exists.
  * Existing attachments become RECORD evidence. Their uploader is kept as recorded; they are never attributed to an inspector
    or a management remark.

Usage (inside the backend container, AFTER a verified backup, with the backend stopped):
    python -m scripts.migrate_ui_v1            # dry run
    python -m scripts.migrate_ui_v1 --apply    # execute
"""
import hashlib
import sys
from pathlib import Path
from sqlalchemy import inspect, text
from app.config import settings
from app.database import engine, Base
from app import models  # noqa: F401

NEW_TABLES = ['management_remarks', 'register_views']
COLUMNS = {
    'reviewer_assignments': [('draft_comment', 'TEXT NULL'), ('draft_saved_at', 'DATETIME NULL')],
    'reviews': [('reviewer_name_snapshot', 'VARCHAR(150) NULL'), ('reviewer_role_snapshot', 'VARCHAR(60) NULL'), ('attachment_count', 'INT NULL')],
    'decisions': [('decided_by_name_snapshot', 'VARCHAR(150) NULL'), ('designation_snapshot', 'VARCHAR(100) NULL')],
    'rfi_amendments': [('amendment_type', 'VARCHAR(20) NULL'), ('target_assignment_id', 'INT NULL'), ('target_remark_id', 'INT NULL')],
    'attachments': [('attachment_kind', 'VARCHAR(30) NULL'), ('project_id', 'INT NULL'), ('rfi_id', 'INT NULL'), ('summary_id', 'INT NULL'),
                    ('management_remark_id', 'INT NULL'), ('assignment_id', 'INT NULL'), ('review_id', 'INT NULL'), ('amendment_id', 'INT NULL'),
                    ('workflow_stage', 'VARCHAR(40) NULL'), ('author_role', 'VARCHAR(60) NULL'), ('sha256', 'VARCHAR(64) NULL'),
                    ('upload_status', 'VARCHAR(20) NULL'), ('scan_status', 'VARCHAR(20) NULL'), ('scanned_at', 'DATETIME NULL'),
                    ('version_no', 'INT NULL'), ('supersedes_id', 'INT NULL'), ('superseded_at', 'DATETIME NULL'), ('locked_at', 'DATETIME NULL'),
                    ('upload_token', 'VARCHAR(64) NULL'), ('removed_at', 'DATETIME NULL'), ('removed_by', 'INT NULL')],
}
# (table, name, columns, unique)
INDEXES = [
    ('reviewer_assignments', 'uq_assignment_id_rfi', 'id, rfi_id', True),
    ('attachments', 'uq_attachment_upload_token', 'uploaded_by, upload_token', True),
    ('attachments', 'ix_attachments_attachment_kind', 'attachment_kind', False), ('attachments', 'ix_attachments_project_id', 'project_id', False),
    ('attachments', 'ix_attachments_rfi_id', 'rfi_id', False), ('attachments', 'ix_attachments_summary_id', 'summary_id', False),
    ('attachments', 'ix_attachments_management_remark_id', 'management_remark_id', False), ('attachments', 'ix_attachments_assignment_id', 'assignment_id', False),
    ('attachments', 'ix_attachments_amendment_id', 'amendment_id', False),
]
# (table, name, local cols, ref table, ref cols)
FOREIGN_KEYS = [
    ('attachments', 'fk_attachment_project', 'project_id', 'projects', 'id'),
    ('attachments', 'fk_attachment_rfi', 'rfi_id', 'rfis', 'id'),
    ('attachments', 'fk_attachment_summary', 'summary_id', 'rfi_summaries', 'id'),
    ('attachments', 'fk_attachment_review', 'review_id', 'reviews', 'id'),
    ('attachments', 'fk_attachment_amendment', 'amendment_id', 'rfi_amendments', 'id'),
    ('attachments', 'fk_attachment_supersedes', 'supersedes_id', 'attachments', 'id'),
    ('attachments', 'fk_attachment_removed_by', 'removed_by', 'users', 'id'),
    ('attachments', 'fk_attachment_remark_project', 'management_remark_id, project_id', 'management_remarks', 'id, project_id'),
    ('attachments', 'fk_attachment_assignment_rfi', 'assignment_id, rfi_id', 'reviewer_assignments', 'id, rfi_id'),
    ('rfi_amendments', 'fk_amendment_target_assignment', 'target_assignment_id', 'reviewer_assignments', 'id'),
    ('rfi_amendments', 'fk_amendment_target_remark', 'target_remark_id', 'management_remarks', 'id'),
]
CHECK_NAME = 'ck_attachment_path'
CHECK_SQL = ("(attachment_kind='MANAGEMENT_REMARK' AND management_remark_id IS NOT NULL AND assignment_id IS NULL AND project_id IS NOT NULL)"
             " OR (attachment_kind='INSPECTOR_REVIEW' AND assignment_id IS NOT NULL AND rfi_id IS NOT NULL AND management_remark_id IS NULL AND project_id IS NOT NULL)"
             " OR (attachment_kind='RECORD' AND management_remark_id IS NULL AND assignment_id IS NULL)")


def _fks(insp, table):
    return {fk['name'] for fk in insp.get_foreign_keys(table)}


def _checks(c, table):
    return {r[0] for r in c.execute(text("SELECT CONSTRAINT_NAME FROM information_schema.TABLE_CONSTRAINTS WHERE TABLE_SCHEMA=DATABASE() "
                                         "AND TABLE_NAME=:t AND CONSTRAINT_TYPE='CHECK'"), {'t': table})}


def main(apply: bool):
    mode = 'APPLY' if apply else 'DRY RUN'
    print(f'=== migrate_ui_v1 ({mode}) on {engine.url.render_as_string(hide_password=True)} ===')
    insp = inspect(engine)
    if not insp.has_table('reviewer_assignments') or 'sequence_no' not in {c['name'] for c in insp.get_columns('reviewer_assignments')}:
        sys.exit('migrate_srs_v5 has not been applied to this database. Run it first.')
    new_tables = [t for t in NEW_TABLES if not insp.has_table(t)]
    print('New tables:', new_tables or 'none')
    if apply and new_tables:
        Base.metadata.create_all(bind=engine, tables=[Base.metadata.tables[t] for t in new_tables])
        print('  created.')

    insp = inspect(engine)
    stmts = []
    for table, cols in COLUMNS.items():
        have = {c['name'] for c in insp.get_columns(table)}
        stmts += [f'ALTER TABLE `{table}` ADD COLUMN `{n}` {ddl}' for n, ddl in cols if n not in have]
    for table, name, cols, unique in INDEXES:
        names = {i['name'] for i in insp.get_indexes(table)} | {u['name'] for u in insp.get_unique_constraints(table)}
        if name not in names:
            stmts.append(f'ALTER TABLE `{table}` ADD {"UNIQUE " if unique else ""}INDEX `{name}` ({cols})')
    print(f'Schema statements ({len(stmts)}):')
    for s in stmts: print('   ', s)
    if apply:
        with engine.begin() as c:
            for s in stmts: c.execute(text(s))
        print('  applied.')

    # ---- data: describe existing attachments as RECORD evidence (NULL-only fills)
    insp = inspect(engine)
    att_cols = {c['name'] for c in insp.get_columns('attachments')}
    with engine.begin() as c:
        total = c.execute(text('SELECT COUNT(*) FROM attachments')).scalar()
        if 'attachment_kind' in att_cols:
            todo = c.execute(text('SELECT id, entity_type, entity_id, stored_name, sha256 FROM attachments WHERE attachment_kind IS NULL')).all()
        else:
            todo = c.execute(text('SELECT id, entity_type, entity_id, stored_name, NULL FROM attachments')).all()
        print(f'Data step 1: existing attachments -> RECORD evidence (uploader unchanged): {len(todo)} of {total} row(s)')
        base = Path(settings.upload_dir).resolve()
        hashed = missing = 0
        plan = []
        for aid, et, eid, stored, sha in todo:
            path = (base / stored).resolve()
            digest = None
            if base in path.parents and path.exists():
                h = hashlib.sha256()
                with open(path, 'rb') as f:
                    while chunk := f.read(1 << 20): h.update(chunk)
                digest = h.hexdigest(); hashed += 1
            else:
                missing += 1
            plan.append((aid, (et or '').lower(), eid, digest))
        print(f'        SHA-256 computed for {hashed} stored file(s); {missing} file(s) not found on disk (left NULL, reported only)')
        if apply and todo:
            for aid, et, eid, digest in plan:
                c.execute(text("UPDATE attachments SET attachment_kind='RECORD' WHERE id=:i AND attachment_kind IS NULL"), {'i': aid})
                c.execute(text("UPDATE attachments SET upload_status='COMPLETE' WHERE id=:i AND upload_status IS NULL"), {'i': aid})
                c.execute(text("UPDATE attachments SET scan_status='NOT_SCANNED' WHERE id=:i AND scan_status IS NULL"), {'i': aid})
                c.execute(text("UPDATE attachments SET version_no=1 WHERE id=:i AND version_no IS NULL"), {'i': aid})
                if digest: c.execute(text('UPDATE attachments SET sha256=:h WHERE id=:i AND sha256 IS NULL'), {'h': digest, 'i': aid})
                if et == 'rfi':
                    c.execute(text('UPDATE attachments a JOIN rfis r ON r.id=:e SET a.rfi_id=r.id WHERE a.id=:i AND a.rfi_id IS NULL'), {'e': eid, 'i': aid})
                    c.execute(text('UPDATE attachments a JOIN rfis r ON r.id=:e SET a.summary_id=r.summary_id WHERE a.id=:i AND a.summary_id IS NULL'), {'e': eid, 'i': aid})
                    c.execute(text('UPDATE attachments a JOIN rfis r ON r.id=:e SET a.project_id=r.project_id WHERE a.id=:i AND a.project_id IS NULL'), {'e': eid, 'i': aid})
                    # files of an RFI that has left the draft stage are locked (version preservation)
                    c.execute(text("UPDATE attachments a JOIN rfis r ON r.id=:e SET a.locked_at=COALESCE(r.updated_at, NOW()) WHERE a.id=:i AND a.locked_at IS NULL AND r.workflow_status<>'DRAFT'"), {'e': eid, 'i': aid})
                elif et == 'summary':
                    c.execute(text('UPDATE attachments a JOIN rfi_summaries s ON s.id=:e SET a.summary_id=s.id WHERE a.id=:i AND a.summary_id IS NULL'), {'e': eid, 'i': aid})
                    c.execute(text('UPDATE attachments a JOIN rfi_summaries s ON s.id=:e SET a.project_id=s.project_id WHERE a.id=:i AND a.project_id IS NULL'), {'e': eid, 'i': aid})
                    c.execute(text("UPDATE attachments a JOIN rfi_summaries s ON s.id=:e SET a.locked_at=s.submitted_at WHERE a.id=:i AND a.locked_at IS NULL AND s.submitted_at IS NOT NULL AND s.workflow_status NOT IN ('DRAFT','RETURNED')"), {'e': eid, 'i': aid})
                elif et == 'daily_progress':
                    c.execute(text('UPDATE attachments a JOIN daily_progress d ON d.id=:e SET a.project_id=d.project_id WHERE a.id=:i AND a.project_id IS NULL'), {'e': eid, 'i': aid})
            print('  data applied.')

    # ---- constraints (after the data step, so existing rows satisfy them)
    insp = inspect(engine)
    stmts = []
    for table, name, cols, ref, refcols in FOREIGN_KEYS:
        if insp.has_table(table) and insp.has_table(ref) and name not in _fks(insp, table):
            stmts.append(f'ALTER TABLE `{table}` ADD CONSTRAINT `{name}` FOREIGN KEY ({cols}) REFERENCES `{ref}` ({refcols})')
    with engine.connect() as c:
        if CHECK_NAME not in _checks(c, 'attachments'):
            stmts.append(f'ALTER TABLE `attachments` ADD CONSTRAINT `{CHECK_NAME}` CHECK ({CHECK_SQL})')
        if apply is False and 'attachment_kind' in att_cols:
            bad = c.execute(text(f'SELECT COUNT(*) FROM attachments WHERE NOT ({CHECK_SQL})')).scalar()
            print(f'Rows that would violate {CHECK_NAME} today: {bad}')
    print(f'Constraint statements ({len(stmts)}):')
    for s in stmts: print('   ', s)
    if apply:
        with engine.begin() as c:
            for s in stmts: c.execute(text(s))
        print('  applied.')
    print('Done. No tables, columns or rows were deleted; no existing non-NULL value was changed.' if apply else 'Dry run complete - nothing was written.')


if __name__ == '__main__':
    main('--apply' in sys.argv)
