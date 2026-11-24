# Administrator guide (Category 1) — release 6.0.0-ui

## Dashboard
Shows active projects, active accounts, inactive accounts and the membership table, all read live from the database. "Pending invitations" shows **Not enabled**: accounts are created by you, not by invitation (decision UD-12). Below the KPIs, notes flag accounts with no project and accounts still using a temporary password.

## Projects
Create a project with its code, name, contract number and the employer, consultant and contractor names. These names appear on DOC_01, DOC_03 and DOC_02 exports. Archive a project to make it read-only; nothing is deleted.

## Users
1. **+ Add user**: full name, e-mail and a temporary password of at least 10 characters. Give the password to the user privately; they must change it at first sign-in.
2. **Reset password** sets a new temporary password and ends their sessions.
3. **Deactivate** blocks the account immediately on every project. Their submissions, reviews, remarks and attachments are kept and still show their name.

## Project memberships
A user holds **one role per project**. Assigning a new role replaces the old one; the audit log keeps the history.
- Category 2.1: Resident Engineer (RE), Deputy Resident Engineer (DRE).
- Category 2.2: Works / Structure / Material Inspector, Surveyor, Senior Surveyor, Soil Lab Technician, Material Engineer.
- Category 2.3: Quantity Surveyor, Draftsperson, Secretary, Project Manager (read-only), Viewer.
- Category 3: Data Encoder, Office Engineer.

**Revoke** removes access to that project only. **Export access matrix** downloads every active membership with the capabilities it gives under that project's settings.

## Roles
A reference of each role and what it may do with the default settings.

## Configuration (per project)
Each setting shows the decision-register id it is waiting on:
- **24-hour rule** (flag or require a reason), notice hours, overdue hours.
- **DOC_03 dispositions** (JSON). Keep the client's exact wording.
- **Visibility:** contractor scope, contractor access to evidence files, inspector register read / export, and which categories see the hidden workbook columns I:M and S.
- **Attachments:** allowed types, size per file (never above the server's `MAX_UPLOAD_MB`), files per remark / review, malware scanning (needs ClamAV at `CLAMD_HOST`). Retention is fixed to "keep all".

## Audit log
Every submission, assignment, review, remark, upload, removal, download, preview, export, correction, integrity failure and administrative change is recorded with the user and the project.

## Things only the administrator should know
- Never run `docker compose down -v`; it deletes the database volume.
- Backups: `scripts/backup/backup.sh` (encrypted, optional off-site copy) and `scripts/backup/verify_restore.sh` (restores into a throwaway container). See `docs/deployment/BACKUP_AND_RECOVERY.md`.
- The administrator has **no** inspection or final-decision authority (DR-01).
