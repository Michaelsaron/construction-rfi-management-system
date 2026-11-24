# Backup and recovery

## Nightly backup — `scripts/backup/backup.sh`
Read-only for the application. It produces:
- `mysqldump --single-transaction` (no table locks for InnoDB);
- a tar archive of the uploads (evidence, issued DOC_03 PDFs);
- both encrypted with AES-256 (`openssl enc -pbkdf2 -iter 200000`) using the passphrase file;
- SHA-256 sums.

Optional copies go to a mounted off-site folder and/or an rclone remote (verified with `rclone check`), and a health-check URL can be pinged on success.

Configuration: `backups/backup.env` (git-ignored)

| Variable | Default | Meaning |
|---|---|---|
| DB_CONTAINER | rfi_production_system-db-1 | MySQL container |
| UPLOADS_SOURCE | ./backend/uploads | Folder, or `volume:NAME` |
| BACKUP_DIR | ./backups/scheduled | Local backups |
| KEEP_DAYS | 14 | Local retention |
| PASSPHRASE_FILE | ./backups/.backup_passphrase | **Keep a copy off this machine.** Without it the backups cannot be decrypted. |
| OFFSITE_DIR / RCLONE_REMOTE / OFFSITE_KEEP_DAYS | — / — / 90 | Off-site copy |
| HEALTHCHECK_URL | — | Pinged on success |

Schedule (example, 02:30 daily):
```
30 2 * * * cd /opt/rfi && scripts/backup/backup.sh >> backups/backup.log 2>&1
```

## Restore drill — `scripts/backup/verify_restore.sh [folder]`
Decrypts, checks the SHA-256 sums, restores into a **throwaway** MySQL container, compares row counts and the RFI checksum with the values recorded at backup time, checks the uploads archive, then removes the container. The live database is never touched. Run it monthly and after every migration.

## Full recovery
1. Stop the backend.
2. Decrypt `db.sql.gz.enc` and `uploads.tar.gz.enc` with the passphrase.
3. Restore the database: create an empty database, then `gunzip -c db.sql.gz | mysql …`.
4. Extract the uploads into the uploads volume.
5. Start the backend, then check `/health` and the counts.

Never use `docker compose down -v`: it deletes the database volume.
