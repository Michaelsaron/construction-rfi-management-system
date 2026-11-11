#!/usr/bin/env bash
set -euo pipefail
if [ $# -lt 1 ]; then echo "Usage: ./scripts/restore.sh backups/daily/rfi_YYYYMMDD_HHMMSS.sql [uploads_tar.gz]"; exit 1; fi
SQL=$1
cat "$SQL" | docker compose exec -T db sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" "$MYSQL_DATABASE"'
if [ $# -ge 2 ]; then cat "$2" | docker compose exec -T backend tar -xzf - -C /app; fi
echo "Restore complete. Restart with: docker compose restart backend frontend"
