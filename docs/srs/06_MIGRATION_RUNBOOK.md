# Migration Runbook — release 5.0.0-srs (AWAITING APPROVAL — NOT YET RUN ON THE REAL DATABASE)

## 1. Backup verification (done 14 Nov 2026, 15:11 local)

| Check | Result |
|---|---|
| Source | live container `rfi_production_system-db-1`, database `rfi_db`, volume `rfi_production_system_mysql_data` (read-only `mysqldump --single-transaction --routines --triggers --events`) |
| Files (git-ignored, `chmod 600`) | `backups/pre-srs/rfi_db_20261114_151125.sql` (1,215,551 B, SHA-256 `4a1e20b1…b174`), `uploads_20261114_151125.tar.gz` (uploads hold only `.gitkeep`), `env_20261114_151125.bak` |
| Restore test | Restored into `rfi_restore_check` on a **separate** MySQL 8.4 container (`rfi-srs-testdb`, own volume `rfi_srs_test_mysql_data`, 127.0.0.1:3307) |
| Comparison | 15 table counts **identical**. The MD5 over every `rfis` row (id, project, number, revision, decision, workflow, remarks) is **identical** (`b35e156a…c580`). |
| Live data at backup | 2 projects, 2 users, 1 membership, 3 batches, **2,467 RFIs** (2,465 legacy + 2 portal), 0 assignments/reviews/decisions, 16 audit rows. Legacy breakdown: 1,573 APPROVED / 438 ON_PROGRESS / 199 INFORMATION_ONLY / 72 REJECTED / 183 no decision. **461** rows with "Not Ready / Not ready / Note ready". |
| Live DB after development | Re-checked: counts + checksum still identical, no new columns. Nothing was written to it. |

## 2. Rehearsal on a copy (done)

`rfi_migration_test` (clone of the backup) → `python -m scripts.migrate_srs_v5` (dry run) → `--apply` → re-run (no-op):
- 39 `ADD COLUMN` + 5 `CREATE INDEX` (44 statements; an earlier draft of this runbook mis-stated "33"), 2 new tables (`rfi_amendments`, `issued_documents`). No DROP/MODIFY/DELETE.
- Data steps (fill NULL new columns only): membership role `ARE` copied for the 1 existing membership; `provenance` = LEGACY_IMPORT ×2,465, PORTAL ×2; `legacy_rfi_status` copied from the importer's remarks suffix ×2,309 (all 461 Not-Ready variants verbatim); 0 assignments to back-fill.
- **All 15 original counts and the RFI checksum are unchanged after migration.** A second run makes no changes.
- The new backend **refuses to start** on the unmigrated copy (schema check) and serves all 2,467 records on the migrated copy. The ARE gets 403 on the DEMO project.

## 3. Compatibility
The migration is additive and **backward compatible**: the currently running (old) backend keeps working on the migrated schema, because the new columns are nullable/defaulted and the new tables are ignored by the old code. Rollback of the *application* therefore never needs a database restore.

## 4. Exact commands (run from `<repository root>`, after your approval)

```bash
# 0. Fresh backup immediately before (the public stack's db is the live db)
mkdir -p backups/pre-migration && STAMP=$(date +%Y%m%d_%H%M%S)
docker exec rfi_production_system-db-1 sh -c 'mysqldump --single-transaction --routines --triggers --events --hex-blob -uroot -p"$MYSQL_ROOT_PASSWORD" "$MYSQL_DATABASE" 2>/dev/null' > backups/pre-migration/rfi_db_$STAMP.sql
tail -1 backups/pre-migration/rfi_db_$STAMP.sql          # must show "-- Dump completed"

# 1. Stop the application containers; keep MySQL running. The demo link goes offline here. (Never use `down -v`.)
docker compose -f docker-compose.public.yml stop tunnel nginx frontend backend

# 2. Build the new backend image (does not start it)
docker compose -f docker-compose.public.yml build backend

# 3. Dry run against the live db (prints statements, writes nothing)
docker compose -f docker-compose.public.yml run --rm --no-deps backend python -m scripts.migrate_srs_v5

# 4. Apply
docker compose -f docker-compose.public.yml run --rm --no-deps backend python -m scripts.migrate_srs_v5 --apply

# 5. Verify: counts + checksum must equal backups/pre-srs/baseline_counts.txt
#    (the verification SQL used in the rehearsal is saved as backups/pre-srs/verify_counts.sql)
docker exec -i rfi_production_system-db-1 sh -c 'mysql -N -uroot -p"$MYSQL_ROOT_PASSWORD" "$MYSQL_DATABASE" 2>/dev/null' < backups/pre-srs/verify_counts.sql > backups/pre-migration/after_$STAMP.txt
diff backups/pre-srs/baseline_counts.txt backups/pre-migration/after_$STAMP.txt && echo OK

# 6. Start the new release (frontend rebuilt). The trycloudflare URL WILL change.
docker compose -f docker-compose.public.yml up -d --build
docker compose -f docker-compose.public.yml logs tunnel | grep trycloudflare
```

## 5. After migration — administrator actions (not automatic)
1. Projects & Members: give each existing user a project role. The existing ARE (`<client DRE email>`) keeps role **ARE** on `<PROJECT_CODE>`, with the same rights as RE/DRE. Nothing is renamed.
2. Create the inspector, office and contractor accounts, and add them to the project with their roles.
3. Confirm the client decisions in `04_DECISION_REGISTER.md`. Most are project settings and need no code change.

## 6. Rollback
- **Application rollback:** `git checkout main && docker compose -f docker-compose.public.yml up -d --build`. The old code runs on the migrated schema.
- **Full database rollback** (only if ever required, and only with explicit approval because it replaces the live database): restore `backups/pre-migration/rfi_db_<STAMP>.sql` into `rfi_db`.
