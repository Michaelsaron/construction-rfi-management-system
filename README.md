# Construction RFI Management System - Client Upgrade v3

React PWA + FastAPI + MySQL for RFI summaries, individual RFIs, technical review, RE/ARE decisions, attachments, Daily Progress, reports, notifications and audit history.

## Important
- Keep the existing MySQL volume. **Do not run `docker compose down -v`.**
- This package is production-oriented, but public production still requires a VPS, domain/hostname, HTTPS certificate, SMTP account and off-server backup destination.
- The supplied client data belongs to the Dubti-Arrisa-Adigala-Biyokebob Lot II project.

## 1. Local startup
```bash
docker compose build --no-cache backend frontend
docker compose up -d
docker compose logs -f backend
```
Open:
- App: http://localhost:5173
- API docs: http://localhost:8000/docs

## 2. Import the real client project + Excel reference data + historical RFIs
Run after the containers are up:
```bash
docker compose exec backend python scripts/import_client_bundle.py
```
This creates/updates:
- project `DUBTI-LOT-II`
- ARE account `frew99@gmail.com`
- Work_List / structure types / dependent descriptions
- road types, directions, sides, work statuses
- material-source types and dependent material sources
- ROW locations
- earthwork lists
- Daily Progress items and dependent statuses
- actual historical Test values
- concrete-mix designation values that exist in the source file
- historical RFI register

Temporary local ARE password created by the importer:
`ChangeMe_ARE_2026!`

Change it immediately before real use. The importer writes `backend/migration_conflicts.csv` inside the container when duplicate legacy RFI numbers are found.

## 3. Workflow
1. Contractor / Site Engineer creates RFI Summary.
2. Add one or more individual RFIs using the imported dependent dropdowns.
3. Submit Summary; it becomes locked.
4. RE/ARE opens an RFI and Accepts/Activates it.
5. RE/ARE assigns the required technical reviewers.
6. Reviewer uses **My Inspections** and submits recommendation + comment.
7. When required reviews are complete, RFI becomes **AWAITING_DECISION**.
8. RE/ARE selects final decision: APPROVED / REJECTED / ON_PROGRESS / INFORMATION_ONLY.
9. Completed RFIs are locked for ordinary users and status history is preserved.
10. Rejected RFI can be resubmitted using the same RFI number and the next revision number.

## 4. Attachments
Allowed: PDF, JPG/JPEG, PNG, XLS/XLSX, DOC/DOCX, DWG, DXF, DGN. Maximum upload size defaults to 50 MB. Phone file input supports taking a photo. Offline attachments and new records are queued in IndexedDB and sync when the browser reconnects.

## 5. PWA installation
The manifest, icons and service worker are included. On localhost it can be tested in Chrome. In production a valid HTTPS address is required. Use the **Install App** button or the browser's **Add to Home Screen / Install App** command.

## 6. Email / password reset
Set SMTP values in `.env`:
```env
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=...
SMTP_PASSWORD=...
SMTP_FROM=rfi@example.com
SMTP_TLS=true
FRONTEND_ORIGIN=https://rfi.yourcompany.com
```
Without SMTP, email bodies are printed in backend logs for development.

## 7. Backups
Manual backup:
```bash
./scripts/backup.sh
```
Restore:
```bash
./scripts/restore.sh backups/daily/rfi_YYYYMMDD_HHMMSS.sql
```
The backup script keeps approximately 7 daily, 4 weekly and 12 monthly generations. Set `BACKUP_OFFSITE_DIR` to copy to a second location.

## 8. Production
1. Buy/create a small Ubuntu VPS.
2. Point a domain/subdomain to its public IP.
3. Install Docker + Docker Compose.
4. Copy this folder to the server.
5. Change all passwords and `JWT_SECRET` in `.env`.
6. Set `FRONTEND_ORIGIN=https://your-domain`.
7. Obtain TLS files and place them as `nginx/certs/fullchain.pem` and `nginx/certs/privkey.pem`.
8. Run:
```bash
docker compose -f docker-compose.prod.yml up -d --build
```
9. Run the client import once:
```bash
docker compose -f docker-compose.prod.yml exec backend python scripts/import_client_bundle.py
```
10. Schedule `scripts/backup.sh` using cron and copy backups off the VPS.

See `docs/PC_STEPS.md` for the shortest step-by-step checklist.

## Release update (November 2026)

This release adds Daily Progress draft editing, inspector and RE/ARE comments,
searchable RFI linking, individual Daily Progress PDF, project-aware Daily Progress
API filtering, and additive migration script `backend/scripts/migrate_release_v4.py`.

**Existing deployments:** read `UPGRADE_EXISTING_INSTALL.md` before upgrading.
The ZIP deliberately omits `.env`, the live MySQL volume, and uploaded user files.
The historical importer has been corrected to read the real RFI header (row 8).
Do not rerun the importer on an existing populated database.

**Verification:** Python backend files passed compileall syntax validation.
Frontend npm build and Docker runtime tests were not possible in this packaging
session; run them locally before production. Project-wide access controls,
backup/restore, email and HTTPS need independent UAT/security verification.

## Public demo link (free, from this computer)
Runs the production build behind nginx and exposes it over HTTPS with a free Cloudflare quick tunnel. Uses the same database and uploads as local.
```bash
docker compose down                                   # stop local dev stack (never add -v)
docker compose -f docker-compose.public.yml up -d --build
docker compose -f docker-compose.public.yml logs tunnel | grep trycloudflare   # your public https link
caffeinate -dis                                       # keep the Mac awake while the demo is live
```
The link changes every time the tunnel restarts. Stop: `docker compose -f docker-compose.public.yml down`. Back to local dev: `docker compose up -d`.
Demo credentials are in `DEMO_CREDENTIALS.txt` (private, git-ignored).

## Automated API test
`python3 scripts/e2e_api_test.py http://localhost:8001` runs every backend function across all roles (181 checks).
Point it ONLY at a throwaway test database — it creates users, projects and RFIs.
