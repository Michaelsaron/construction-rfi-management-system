#!/usr/bin/env bash
set -euo pipefail
ROOT=${BACKUP_ROOT:-backups}
STAMP=$(date +%Y%m%d_%H%M%S)
DOW=$(date +%u)
DOM=$(date +%d)
mkdir -p "$ROOT/daily" "$ROOT/weekly" "$ROOT/monthly"
make_backup(){
  local dir=$1
  docker compose exec -T db sh -c 'mysqldump --single-transaction -uroot -p"$MYSQL_ROOT_PASSWORD" "$MYSQL_DATABASE"' > "$dir/rfi_${STAMP}.sql"
  docker compose exec -T backend tar -czf - -C /app uploads > "$dir/uploads_${STAMP}.tar.gz"
}
make_backup "$ROOT/daily"
if [ "$DOW" = "7" ]; then cp "$ROOT/daily/rfi_${STAMP}.sql" "$ROOT/weekly/"; cp "$ROOT/daily/uploads_${STAMP}.tar.gz" "$ROOT/weekly/"; fi
if [ "$DOM" = "01" ]; then cp "$ROOT/daily/rfi_${STAMP}.sql" "$ROOT/monthly/"; cp "$ROOT/daily/uploads_${STAMP}.tar.gz" "$ROOT/monthly/"; fi
find "$ROOT/daily" -type f -mtime +7 -delete
find "$ROOT/weekly" -type f -mtime +35 -delete
find "$ROOT/monthly" -type f -mtime +370 -delete
if [ -n "${BACKUP_OFFSITE_DIR:-}" ]; then mkdir -p "$BACKUP_OFFSITE_DIR"; cp -a "$ROOT/." "$BACKUP_OFFSITE_DIR/"; fi
echo "Backup completed: $STAMP (7 daily / 4 weekly / 12 monthly target)"
