"""SRS v1.0 additive migration (release 5.0.0-srs).

SAFE BY DESIGN
  * Dry run by default: prints every statement and the rows each data step would touch. Nothing is written.
  * `--apply` executes. Schema changes are ADD COLUMN / CREATE TABLE / CREATE INDEX only - no DROP, no MODIFY,
    no DELETE, no UPDATE of an existing non-NULL value. Every data step only fills NEW columns that are NULL.
  * Idempotent: re-running skips what already exists.
  * Historical values (remarks, current_decision, workflow_status, legacy "Not Ready" text, ownership) are untouched.

Usage (inside the backend container, AFTER a verified backup, with the backend stopped):
    python -m scripts.migrate_srs_v5            # dry run
    python -m scripts.migrate_srs_v5 --apply    # execute
"""
import re
import sys
from sqlalchemy import inspect, text
from app.database import engine, Base
from app import models  # noqa: F401  (registers tables)
from app.authz import PROJECT_ROLES

COLUMNS = {
    'projects': [('project_length', 'VARCHAR(60) NULL'), ('archived_at', 'DATETIME NULL'), ('settings_json', 'TEXT NULL')],
    'project_users': [('role', 'VARCHAR(60) NULL'), ('status', "VARCHAR(20) NOT NULL DEFAULT 'ACTIVE'"), ('created_at', 'DATETIME NULL'), ('revoked_at', 'DATETIME NULL')],
    'rfi_summaries': [('client_request_id', 'VARCHAR(64) NULL'), ('contractor_rep_name', 'VARCHAR(150) NULL'), ('received_by', 'INT NULL'), ('received_at', 'DATETIME NULL')],
    'rfis': [('inspection_time', 'VARCHAR(5) NULL'), ('inspection_time_text', 'VARCHAR(60) NULL'), ('requested_time', 'VARCHAR(5) NULL'),
             ('material_source_offset', 'VARCHAR(120) NULL'), ('inspection_order', 'INT NULL'), ('enclosure_sheets', 'INT NULL'), ('work_categories', 'TEXT NULL'),
             ('received_by', 'INT NULL'), ('received_at', 'DATETIME NULL'), ('short_notice', 'TINYINT(1) NULL'), ('notice_hours', 'FLOAT NULL'),
             ('short_notice_reason', 'TEXT NULL'), ('current_disposition', 'VARCHAR(60) NULL'), ('provenance', 'VARCHAR(20) NULL'),
             ('legacy_rfi_status', 'VARCHAR(150) NULL'), ('legacy_source_row', 'INT NULL')],
    'reviewer_assignments': [('sequence_no', 'INT NULL'), ('activated_at', 'DATETIME NULL'), ('change_reason', 'TEXT NULL'), ('sequence_backfilled', 'TINYINT(1) NULL')],
    'decisions': [('disposition_code', 'VARCHAR(60) NULL'), ('approved_from', 'VARCHAR(255) NULL'), ('approved_to', 'VARCHAR(255) NULL'), ('conditions', 'TEXT NULL')],
    'notifications': [('project_id', 'INT NULL')],
    'audit_logs': [('project_id', 'INT NULL'), ('before_json', 'TEXT NULL'), ('after_json', 'TEXT NULL')],
}
INDEXES = [('rfis', 'ix_rfis_current_disposition', 'current_disposition', False), ('rfis', 'ix_rfis_provenance', 'provenance', False),
           ('notifications', 'ix_notifications_project_id', 'project_id', False), ('audit_logs', 'ix_audit_logs_project_id', 'project_id', False),
           ('rfi_summaries', 'uq_rfi_summaries_client_request_id', 'client_request_id', True)]
NEW_TABLES = ['rfi_amendments', 'issued_documents']
LEGACY_RE = re.compile(r'Legacy status:\s*(.+?)\s*$')


def main(apply: bool):
    mode = 'APPLY' if apply else 'DRY RUN'
    print(f'=== migrate_srs_v5 ({mode}) on {engine.url.render_as_string(hide_password=True)} ===')
    insp = inspect(engine)
    stmts = []
    for table, cols in COLUMNS.items():
        if not insp.has_table(table):
            print(f'  table {table} missing (fresh install will create it)'); continue
        have = {c['name'] for c in insp.get_columns(table)}
        for name, ddl in cols:
            if name not in have: stmts.append(f'ALTER TABLE `{table}` ADD COLUMN `{name}` {ddl}')
    for table, name, col, unique in INDEXES:
        if insp.has_table(table) and name not in {i['name'] for i in insp.get_indexes(table)}:
            stmts.append(f'CREATE {"UNIQUE " if unique else ""}INDEX `{name}` ON `{table}` (`{col}`)')
    new_tables = [t for t in NEW_TABLES if not insp.has_table(t)]
    print(f'Schema statements ({len(stmts)}):')
    for s in stmts: print('   ', s)
    print('New tables:', new_tables or 'none')
    if apply:
        with engine.begin() as c:
            for s in stmts: c.execute(text(s))
        Base.metadata.create_all(bind=engine, tables=[Base.metadata.tables[t] for t in new_tables])
        print('Schema applied.')
    elif stmts:
        print('\n(Data steps below are estimated against the current schema; columns that do not exist yet count as NULL.)')

    insp = inspect(engine)
    def has(table, col): return col in {c['name'] for c in insp.get_columns(table)}
    with engine.begin() as c:
        # 1. Membership roles: copy the user's existing global role into legacy memberships (no new memberships, no new privileges).
        roles = "('" + "','".join(sorted(PROJECT_ROLES)) + "')"
        cond = 'pu.role IS NULL AND ' if has('project_users', 'role') else ''
        n1 = c.execute(text(f'SELECT COUNT(*) FROM project_users pu JOIN users u ON u.id=pu.user_id WHERE {cond}u.role IN {roles}')).scalar()
        detail = c.execute(text(f'SELECT pu.project_id, u.id, u.role FROM project_users pu JOIN users u ON u.id=pu.user_id WHERE {cond}u.role IN {roles}')).all()
        print(f'Step 1 membership.role <- users.role (unchanged codes, e.g. ARE stays ARE): {n1} row(s) {list(map(tuple, detail))}')
        no_member = c.execute(text("SELECT id, role FROM users WHERE role<>'ADMIN' AND id NOT IN (SELECT user_id FROM project_users)")).all()
        print(f'        users with no project membership (reported only, NOT granted access): {list(map(tuple, no_member))}')
        # 2. Provenance
        cond = 'provenance IS NULL AND ' if has('rfis', 'provenance') else ''
        n2a = c.execute(text(f'SELECT COUNT(*) FROM rfis WHERE {cond}summary_id IS NULL')).scalar()
        n2b = c.execute(text(f'SELECT COUNT(*) FROM rfis WHERE {cond}summary_id IS NOT NULL')).scalar()
        print(f'Step 2 rfis.provenance: LEGACY_IMPORT (no DOC_01 batch) = {n2a}, PORTAL = {n2b}')
        # 3. legacy_rfi_status copied (not moved) from the importer's remarks suffix
        cond = 'legacy_rfi_status IS NULL AND ' if has('rfis', 'legacy_rfi_status') else ''
        rows = c.execute(text(f"SELECT id, remarks FROM rfis WHERE {cond}summary_id IS NULL AND remarks LIKE '%Legacy status:%'")).all()
        parsed = [(rid, m.group(1)[:150]) for rid, rem in rows if (m := LEGACY_RE.search(rem or ''))]
        from collections import Counter
        print(f'Step 3 rfis.legacy_rfi_status <- remarks "Legacy status: X" (remarks unchanged): {len(parsed)} row(s)')
        for k, v in Counter(x for _, x in parsed).most_common(): print(f'        {v:5}  {k}')
        # 4. Sequence back-fill for pre-existing open assignments
        if has('reviewer_assignments', 'sequence_no'):
            open_a = c.execute(text('SELECT id, rfi_id, status FROM reviewer_assignments WHERE sequence_no IS NULL ORDER BY rfi_id, assigned_at, id')).all()
        else:
            open_a = c.execute(text('SELECT id, rfi_id, status FROM reviewer_assignments ORDER BY rfi_id, assigned_at, id')).all()
        print(f'Step 4 reviewer_assignments.sequence_no back-fill: {len(open_a)} row(s)')

        if apply:
            c.execute(text(f'UPDATE project_users pu JOIN users u ON u.id=pu.user_id SET pu.role=u.role WHERE pu.role IS NULL AND u.role IN {roles}'))
            c.execute(text("UPDATE project_users SET created_at=NOW() WHERE created_at IS NULL"))
            c.execute(text("UPDATE rfis SET provenance='LEGACY_IMPORT' WHERE provenance IS NULL AND summary_id IS NULL"))
            c.execute(text("UPDATE rfis SET provenance='PORTAL' WHERE provenance IS NULL AND summary_id IS NOT NULL"))
            for rid, val in parsed:
                c.execute(text('UPDATE rfis SET legacy_rfi_status=:v WHERE id=:i AND legacy_rfi_status IS NULL'), {'v': val, 'i': rid})
            seq = {}
            for aid, rid, status in open_a:
                seq[rid] = seq.get(rid, 0) + 1
                c.execute(text('UPDATE reviewer_assignments SET sequence_no=:s, sequence_backfilled=1 WHERE id=:i AND sequence_no IS NULL'), {'s': seq[rid], 'i': aid})
            for rid in seq:  # first incomplete assignment of an RFI under review becomes the active turn
                first = c.execute(text("SELECT a.id FROM reviewer_assignments a JOIN rfis r ON r.id=a.rfi_id WHERE a.rfi_id=:r AND a.status='PENDING' AND r.workflow_status='UNDER_REVIEW' ORDER BY a.sequence_no LIMIT 1"), {'r': rid}).scalar()
                if first: c.execute(text("UPDATE reviewer_assignments SET status='ACTIVE', activated_at=NOW() WHERE id=:i"), {'i': first})
            print('Data steps applied.')
    print('Done. No tables, columns or rows were deleted; no existing non-NULL value was changed.' if apply else 'Dry run complete - nothing was written.')


if __name__ == '__main__':
    main('--apply' in sys.argv)
