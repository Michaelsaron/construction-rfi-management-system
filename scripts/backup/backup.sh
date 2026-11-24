#!/usr/bin/env bash
# Nightly backup of the RFI database and attachments, with verification and an optional off-site copy.
#
# READ-ONLY for the application: mysqldump --single-transaction (no table locks for InnoDB) and a tar of
# the uploads. Nothing in the database or uploads is modified.
#
# Configuration: backups/backup.env (git-ignored). See docs/deployment/BACKUP_AND_RECOVERY.md.
#   DB_CONTAINER        MySQL container name            (default rfi_production_system-db-1)
#   UPLOADS_SOURCE      path to uploads dir, or volume:NAME  (default ./backend/uploads)
#   BACKUP_DIR          local backup folder             (default ./backups/scheduled)
#   KEEP_DAYS           local retention in days         (default 14)
#   PASSPHRASE_FILE     file holding the encryption passphrase (required; keep a copy OFF this machine)
#   OFFSITE_DIR         a mounted off-site folder (NAS, synced cloud drive, USB) - optional
#   RCLONE_REMOTE       rclone destination, e.g. b2:rfi-backups/prod - optional (needs rclone)
#   OFFSITE_KEEP_DAYS   off-site retention in days      (default 90)
#   HEALTHCHECK_URL     URL pinged on success (e.g. healthchecks.io) - optional
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
[ -f backups/backup.env ] && . backups/backup.env
DB_CONTAINER="${DB_CONTAINER:-rfi_production_system-db-1}"
UPLOADS_SOURCE="${UPLOADS_SOURCE:-./backend/uploads}"
BACKUP_DIR="${BACKUP_DIR:-./backups/scheduled}"
KEEP_DAYS="${KEEP_DAYS:-14}"
OFFSITE_KEEP_DAYS="${OFFSITE_KEEP_DAYS:-90}"
PASSPHRASE_FILE="${PASSPHRASE_FILE:-./backups/.backup_passphrase}"
STAMP="$(date +%Y%m%d_%H%M%S)"
OUT="$BACKUP_DIR/$STAMP"
LOG="$BACKUP_DIR/backup.log"
umask 077
mkdir -p "$OUT"
log() { echo "$(date '+%F %T') $*" | tee -a "$LOG"; }
fail() { log "FAILED: $*"; rm -rf "$OUT"; exit 1; }
trap 'fail "unexpected error on line $LINENO"' ERR

[ -s "$PASSPHRASE_FILE" ] || fail "passphrase file $PASSPHRASE_FILE missing (create it and store a copy off this machine)"
command -v openssl >/dev/null || fail "openssl not installed"
docker inspect "$DB_CONTAINER" >/dev/null 2>&1 || fail "database container $DB_CONTAINER not found"

log "backup $STAMP started"
# 1. Database dump (consistent snapshot, no locks on InnoDB)
docker exec "$DB_CONTAINER" sh -c 'mysqldump --single-transaction --quick --routines --triggers --events --hex-blob \
  -uroot -p"$MYSQL_ROOT_PASSWORD" "$MYSQL_DATABASE" 2>/dev/null' > "$OUT/db.sql"
tail -1 "$OUT/db.sql" | grep -q "Dump completed" || fail "mysqldump did not complete"

# 2. Row counts at backup time (used by verify_restore.sh to prove the restore is complete)
docker exec "$DB_CONTAINER" sh -c 'mysql -N -uroot -p"$MYSQL_ROOT_PASSWORD" "$MYSQL_DATABASE" -e "
  SELECT CONCAT(\"rfis \",COUNT(*)) FROM rfis UNION ALL SELECT CONCAT(\"rfi_summaries \",COUNT(*)) FROM rfi_summaries
  UNION ALL SELECT CONCAT(\"users \",COUNT(*)) FROM users UNION ALL SELECT CONCAT(\"projects \",COUNT(*)) FROM projects
  UNION ALL SELECT CONCAT(\"attachments \",COUNT(*)) FROM attachments UNION ALL SELECT CONCAT(\"audit_logs \",COUNT(*)) FROM audit_logs
  UNION ALL SELECT CONCAT(\"rfi_checksum \",MD5(GROUP_CONCAT(CONCAT_WS(\"|\",id,project_id,rfi_number,revision_no,IFNULL(current_decision,\"\"),workflow_status,IFNULL(remarks,\"\")) ORDER BY id SEPARATOR \"#\"))) FROM rfis" \
  --init-command="SET SESSION group_concat_max_len=1073741824" 2>/dev/null' > "$OUT/counts.txt"
grep -q "^rfis [0-9]" "$OUT/counts.txt" || fail "could not read row counts"

# 3. Attachments
case "$UPLOADS_SOURCE" in
  volume:*) docker run --rm -v "${UPLOADS_SOURCE#volume:}:/data:ro" alpine:3.20 tar -czf - -C /data . > "$OUT/uploads.tar.gz" ;;
  *)        tar -czf "$OUT/uploads.tar.gz" -C "$UPLOADS_SOURCE" . ;;
esac
tar -tzf "$OUT/uploads.tar.gz" >/dev/null || fail "uploads archive unreadable"

# 4. Compress + encrypt (AES-256, PBKDF2). Plain files are removed.
gzip -9 "$OUT/db.sql"
for f in db.sql.gz uploads.tar.gz; do
  openssl enc -aes-256-cbc -pbkdf2 -iter 200000 -salt -pass "file:$PASSPHRASE_FILE" -in "$OUT/$f" -out "$OUT/$f.enc"
  rm -f "$OUT/$f"
done
(cd "$OUT" && shasum -a 256 db.sql.gz.enc uploads.tar.gz.enc counts.txt > SHA256SUMS)
log "local backup written: $OUT ($(du -sh "$OUT" | cut -f1)); $(tr '\n' ' ' < "$OUT/counts.txt" | cut -c1-120)"

# 5. Off-site copy (encrypted files only)
OFFSITE=0
if [ -n "${OFFSITE_DIR:-}" ]; then
  [ -d "$OFFSITE_DIR" ] || fail "OFFSITE_DIR $OFFSITE_DIR not mounted"
  mkdir -p "$OFFSITE_DIR/$STAMP" && cp "$OUT"/* "$OFFSITE_DIR/$STAMP/"
  (cd "$OFFSITE_DIR/$STAMP" && shasum -a 256 -c SHA256SUMS >/dev/null) || fail "off-site copy checksum mismatch"
  find "$OFFSITE_DIR" -mindepth 1 -maxdepth 1 -type d -name '20*' -mtime +"$OFFSITE_KEEP_DAYS" -exec rm -rf {} +
  log "off-site copy verified: $OFFSITE_DIR/$STAMP"; OFFSITE=1
fi
if [ -n "${RCLONE_REMOTE:-}" ]; then
  command -v rclone >/dev/null || fail "RCLONE_REMOTE set but rclone not installed"
  rclone copy "$OUT" "$RCLONE_REMOTE/$STAMP" && rclone check "$OUT" "$RCLONE_REMOTE/$STAMP" --one-way || fail "rclone upload/check failed"
  rclone delete "$RCLONE_REMOTE" --min-age "${OFFSITE_KEEP_DAYS}d" || log "warning: remote retention cleanup failed"
  log "off-site copy verified: $RCLONE_REMOTE/$STAMP"; OFFSITE=1
fi
[ "$OFFSITE" = 1 ] || log "WARNING: no off-site destination configured - this backup exists only on this machine"

# 6. Local retention
find "$BACKUP_DIR" -mindepth 1 -maxdepth 1 -type d -name '20*' -mtime +"$KEEP_DAYS" -exec rm -rf {} +
trap - ERR
[ -n "${HEALTHCHECK_URL:-}" ] && curl -fsS -m 10 "$HEALTHCHECK_URL" >/dev/null || true
log "backup $STAMP finished OK"
