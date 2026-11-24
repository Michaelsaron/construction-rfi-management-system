#!/usr/bin/env bash
# Prove a backup can be restored: decrypt, restore into a THROWAWAY MySQL container, compare row counts and
# the RFI checksum with the values recorded at backup time, and check the attachments archive.
# The live database is never touched. The throwaway container is removed afterwards.
#
# Usage: scripts/backup/verify_restore.sh [backup-folder]   (default: newest folder in BACKUP_DIR)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
[ -f backups/backup.env ] && . backups/backup.env
BACKUP_DIR="${BACKUP_DIR:-./backups/scheduled}"
PASSPHRASE_FILE="${PASSPHRASE_FILE:-./backups/.backup_passphrase}"
SRC="${1:-$(ls -d "$BACKUP_DIR"/20* 2>/dev/null | sort | tail -1)}"
[ -d "$SRC" ] || { echo "no backup folder found"; exit 1; }
WORK="$(mktemp -d)"; NAME="rfi-restore-verify-$$"; PW="$(openssl rand -hex 16)"
cleanup() { docker rm -f "$NAME" >/dev/null 2>&1 || true; rm -rf "$WORK"; }
trap cleanup EXIT
echo "verifying $SRC"
(cd "$SRC" && shasum -a 256 -c SHA256SUMS >/dev/null) && echo "  checksums OK"
for f in db.sql.gz uploads.tar.gz; do
  openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -pass "file:$PASSPHRASE_FILE" -in "$SRC/$f.enc" -out "$WORK/$f"
done
echo "  decrypted OK"
tar -tzf "$WORK/uploads.tar.gz" > "$WORK/uploads.list" && echo "  uploads archive OK ($(grep -vc '/$' "$WORK/uploads.list") entries)"

docker run -d --name "$NAME" --tmpfs /var/lib/mysql -e MYSQL_ROOT_PASSWORD="$PW" -e MYSQL_DATABASE=restore_check mysql:8.4 >/dev/null
for i in $(seq 1 90); do docker exec "$NAME" mysqladmin ping -uroot -p"$PW" --silent >/dev/null 2>&1 && break; sleep 2; done
sleep 3
gunzip -c "$WORK/db.sql.gz" | docker exec -i "$NAME" sh -c "mysql -uroot -p$PW restore_check 2>/dev/null"
docker exec "$NAME" sh -c "mysql -N -uroot -p$PW restore_check --init-command='SET SESSION group_concat_max_len=1073741824' -e \"
  SELECT CONCAT('rfis ',COUNT(*)) FROM rfis UNION ALL SELECT CONCAT('rfi_summaries ',COUNT(*)) FROM rfi_summaries
  UNION ALL SELECT CONCAT('users ',COUNT(*)) FROM users UNION ALL SELECT CONCAT('projects ',COUNT(*)) FROM projects
  UNION ALL SELECT CONCAT('attachments ',COUNT(*)) FROM attachments UNION ALL SELECT CONCAT('audit_logs ',COUNT(*)) FROM audit_logs
  UNION ALL SELECT CONCAT('rfi_checksum ',MD5(GROUP_CONCAT(CONCAT_WS('|',id,project_id,rfi_number,revision_no,IFNULL(current_decision,''),workflow_status,IFNULL(remarks,'')) ORDER BY id SEPARATOR '#'))) FROM rfis\" 2>/dev/null" > "$WORK/restored.txt"
if diff "$SRC/counts.txt" "$WORK/restored.txt"; then
  echo "RESTORE VERIFIED: $(tr '\n' ' ' < "$WORK/restored.txt")"
  echo "$(date '+%F %T') restore verified for $SRC" >> "$BACKUP_DIR/backup.log"
else
  echo "RESTORE MISMATCH - see diff above"; echo "$(date '+%F %T') RESTORE MISMATCH for $SRC" >> "$BACKUP_DIR/backup.log"; exit 1
fi
