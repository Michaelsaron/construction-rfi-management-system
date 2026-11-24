# Migration and rollback runbook — release 6.0.0-ui

**Status:** rehearsed on a restored copy of the live database (24 Nov 2026). **Not applied to the live database.** Applying it requires the owner's written approval.

## What changes
- **Schema:** additive only (`02_SCHEMA_AND_ERD.md`): 2 new tables, 31 new columns, 9 indexes (2 unique), 11 foreign keys and 1 CHECK constraint.
- **Data:** existing attachments get `attachment_kind = RECORD` and their parent ids filled in (NULL-only fills). The live database has **0 attachments**, so this step changes no rows today.
- **Application:** backend 6.0.0-ui with upgraded fastapi / starlette / python-multipart, and the redesigned frontend.

## Rehearsal evidence (24 Nov 2026, isolated MySQL on :3307)

| Step | Result |
|---|---|
| Backup of live `rfi_db` + uploads (`backups/pre-ui/`, git-ignored, SHA-256 recorded) | done |
| Restore into the isolated database `restore_check`; row counts + RFI checksum compared with live | **identical** (2,467 RFIs, 461 Not-Ready values, checksum `b35e156a…580`) |
| `migrate_ui_v1` dry run | lists exactly the additive statements |
| `migrate_ui_v1 --apply` | applied |
| `migrate_ui_v1 --apply` again | 0 statements (idempotent) |
| Counts + checksum after migration | **unchanged** |
| New backend `schema_check` + `/health` on the migrated copy | OK, version 6.0.0-ui |
| Previous release insert on the migrated schema | accepted (rollback without restore possible) |

The rehearsal logs are in `backups/pre-ui/rehearsal_<stamp>/` (before, dryrun, apply, apply_again, after).

## Procedure (live), once approved

> Never run `docker compose down -v`. Never run the local and public stacks at the same time (they share the MySQL volume).

1. **Announce downtime** (about 15 minutes) to the client. The public demo URL changes when the tunnel restarts.
2. **Take a fresh verified backup** (`scripts/backup/backup.sh`, then `scripts/backup/verify_restore.sh`), or, as in the rehearsal:
   `mysqldump --single-transaction` + `tar` of `/app/uploads` into `backups/pre-ui-live/`, with SHA-256 sums.
3. **Record the baseline:** run `backups/pre-srs/verify_counts.sql` against live and save the output as `before.txt`.
4. **Stop the backend only:** `docker compose -f docker-compose.public.yml stop backend`. The database stays up.
5. **Build the new image:** `git checkout feature/ui-design-v1`, then `docker compose -f docker-compose.public.yml build backend frontend`.
6. **Dry run:**
   `docker compose -f docker-compose.public.yml run --rm backend python -m scripts.migrate_ui_v1`
   Review the output; it must list only ADD / CREATE statements.
7. **Apply:** the same command with `--apply`, then run it once more to confirm "0 statements".
8. **Verify the data:** run `verify_counts.sql` again into `after.txt`, then `diff before.txt after.txt`. **Any difference: stop and roll back.**
9. **Start:** `docker compose -f docker-compose.public.yml up -d backend frontend nginx tunnel`, then check `/health` reports `6.0.0-ui`.
10. **Smoke test (read-only first):**
    - sign in as admin: dashboard, memberships, configuration;
    - open the DOC_02 register (2,467 rows) and one legacy RFI ("File unavailable — migration required" shown, no drive path);
    - open a completed RFI's DOC_03 PDF.
11. **Record** the result in this runbook and in `docs/srs/08_MIGRATION_REPORT.md`.

## Rollback

| Situation | Action |
|---|---|
| Migration step fails or counts differ | Stop. Keep the backend stopped. Restore the database from the backup in step 2 (`mysql < rfi_db_<stamp>.sql` into a fresh database, or the documented restore script), restart the previous image. |
| New release misbehaves after start, data intact | Redeploy the previous image or commit (`2ea2c9a`, release 5.1). The additive schema is compatible with it (tested), so no database restore is needed. New evidence uploaded in the meantime stays in the database and on disk; release 5.1 ignores the new columns. |
| Data damaged | Restore the database and uploads from the step 2 backup, then redeploy release 5.1. |

Rollback commands:
```bash
docker compose -f docker-compose.public.yml stop backend frontend
git checkout 2ea2c9a          # release 5.1 with security hardening
docker compose -f docker-compose.public.yml build backend frontend
docker compose -f docker-compose.public.yml up -d
```

## Post-migration settings
Project settings get the conservative defaults automatically; no data step is needed. Review them with the client on **Configuration** (UD-04 to UD-09).
