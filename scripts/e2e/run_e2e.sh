#!/usr/bin/env bash
# Browser test on an ISOLATED stack. Steps:
#   1. run_e2e.sh reset <workdir>   - recreate the throwaway *_test database named in <workdir>/backend.env
#   2. start the backend on :8001 with that env (it creates the admin account) and the frontend on :5174
#   3. run_e2e.sh test <workdir>    - seed synthetic data and run scripts/e2e/ui_e2e.mjs
set -euo pipefail
CMD="$1"; WD="$2"; ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DB=$(grep '^DATABASE_URL=' "$WD/backend.env" | sed 's#.*/##')
case "$DB" in *_test) ;; *) echo "Refusing: database $DB is not a *_test database" >&2; exit 2;; esac
if [ "$CMD" = reset ]; then
  . "$ROOT/backups/test_db.env"
  docker exec rfi-srs-testdb mysql -uroot -p"$TEST_MYSQL_ROOT_PASSWORD" -e "DROP DATABASE IF EXISTS $DB; CREATE DATABASE $DB CHARACTER SET utf8mb4;" 2>/dev/null
  rm -rf "$WD/uploads" && mkdir -p "$WD/uploads"
  echo "reset $DB"; exit 0
fi
ADMIN=$(grep '^ADMIN_EMAIL=' "$WD/backend.env" | cut -d= -f2); APW=$(grep '^ADMIN_PASSWORD=' "$WD/backend.env" | cut -d= -f2-)
"$ROOT/backend/.venv/bin/python" "$ROOT/scripts/e2e/seed_e2e.py" http://localhost:8001 "$ADMIN" "$APW" > "$WD/seed.json"
cp "$ROOT/scripts/e2e/ui_e2e.mjs" "$WD/"
cd "$WD" && node ui_e2e.mjs http://localhost:5174 seed.json "$ROOT/docs/ui-upgrade/screenshots" results.json
