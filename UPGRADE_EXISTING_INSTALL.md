# Upgrade an existing RFI installation (preserve imported data)

**Do not run `docker compose down -v`. Do not rerun the historical importer on an already imported database.**

1. Back up the existing MySQL database and uploaded files before upgrading. Save backups off the Mac/server.
2. Keep the **same Docker Compose project name and named MySQL volume**. If you extracted the ZIP to a different directory, verify `docker volume ls` and Compose project name before starting.
3. Keep your existing `.env` privately; this ZIP deliberately excludes live secrets. Compare with `.env.example` for new settings.
4. Replace the application source files with this release, preserving `backend/uploads` and `.env`.
5. Build the backend: `docker compose build backend`.
6. Run the additive schema migration **before starting the updated backend**: `docker compose run --rm backend python -m scripts.migrate_release_v4`.
7. Start services: `docker compose up -d --build`.
8. Verify `docker compose ps`, `http://localhost:5173`, `http://localhost:8000/docs`.
9. Check RFI count: `docker compose exec backend python -c "from app.database import SessionLocal; from app.models import Rfi; d=SessionLocal(); print(d.query(Rfi).count()); d.close()"`.
10. Test Daily Progress draft/edit/submit/review/confirm/PDF with separate role accounts.

Important: This is a source release, **not a database snapshot**. Your 2,465 RFIs live in your existing MySQL Docker volume. New environments must import/migrate data separately.

Before internet production: change passwords/secrets, configure HTTPS/SMTP/offsite backups, verify project authorization in every module, and complete client UAT. Not certified for production without these tests.
