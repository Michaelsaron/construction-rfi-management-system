# Implementation Plan — SRS v1.0 Upgrade

**Principles:** upgrade the existing code in place; additive migrations only; no data deletion; every permission enforced on the server; nothing is reported as done until it has been run and tested.
**Defaults pending client answers:** the "Recommendation" column of `04_DECISION_REGISTER.md`, implemented as **project settings** wherever the answer could change.

---

## 1. Target role and permission matrix (server-enforced, per project membership)

| Function | Admin (C1) | RE | DRE/DRE | Inspectors (C2.2) | Office (C2.3) | Contractor (C3) |
|---|---|---|---|---|---|---|
| Create/edit/archive projects, users, memberships | ✔ | – | – | – | – | – |
| Reference data / reviewer rules | ✔ | ✔ | ✔ | – | – | – |
| Create/edit **draft** DOC_01, add RFIs, submit | – (oversight read) | – | – | – | – | ✔ own project |
| Return a submitted batch (before assignment) | – | ✔ | ✔ | – | – | – |
| Acknowledge receipt | – | ✔ | ✔ | – | ✔ (Secretary) | – |
| Assign inspectors + sequence | – | ✔ | ✔ | – | – | – |
| Change sequence after review started (reason + audit) | – | ✔ | ✔ | – | – | – |
| Submit own review (only when active) | – | – | – | ✔ own assignment | – | – |
| Final decision | **– (DR-01)** | ✔ | ✔ | – | – | – |
| Controlled amendment of submitted data | – | approve | approve | – | – | request |
| View DOC_02 register | ✔ all | ✔ | ✔ | read-only (OD-04) | ✔ | ✔ (OD-03 scope) |
| Export DOC_02 Excel/PDF | ✔ | ✔ | ✔ | – (configurable) | ✔ | ✔ (scoped) |
| Completed DOC_03 PDF | ✔ | ✔ | ✔ | own reviewed RFIs | ✔ | ✔ (scoped) |
| Audit log | ✔ all | project | project | – | – | – |

Role codes (per membership): `RE`, `DRE` (fixed label, DR-02 decided), `WORK_INSPECTOR`, `STRUCTURE_INSPECTOR`, `MATERIAL_INSPECTOR`, `SURVEYOR`, `SENIOR_SURVEYOR`, `LAB_TECHNICIAN`, `MATERIAL_ENGINEER`, `QUANTITY_SURVEYOR`, `DRAFTSPERSON`, `SECRETARY`, `DATA_ENCODER`, `OFFICE_ENGINEER`. Legacy accepted: `ARE`→treated as DRE, `RE_ARE`→RE, `CONTRACTOR`/`SITE_ENGINEER`→Category 3, `PROJECT_MANAGER`/`VIEWER`→read-only. `ADMIN` stays a global flag.

Implementation: one `authz` module with `require_project_role(project_id, *roles)` and `visible_rfi_filter(user, project_id)`. Every router (RFIs, summaries, reports, attachments, notifications, dashboard, audit, master data, users) goes through it. Exports reuse the exact same query builder as the screen.

## 2. Workflow state machine (per RFI revision)

```mermaid
stateDiagram-v2
    [*] --> DRAFT: contractor adds RFI to batch
    DRAFT --> SUBMITTED: batch submitted (tx; short-notice flag; notify project RE/DRE)
    SUBMITTED --> DRAFT: RE/DRE returns batch (reason) [no RFI assigned yet]
    SUBMITTED --> ASSIGNED: RE/DRE saves inspector sequence (≥1)
    ASSIGNED --> UNDER_REVIEW: seq 1 active (automatic)
    UNDER_REVIEW --> UNDER_REVIEW: inspector n submits → n+1 active
    UNDER_REVIEW --> AWAITING_DECISION: last inspector submits
    AWAITING_DECISION --> COMPLETED: RE/DRE decision (tx; DOC_02 update; DOC_03 snapshot)
    COMPLETED --> [*]
    COMPLETED --> SUBMITTED: resubmission creates revision n+1 (new row)
    SUBMITTED --> CANCELLED: RE/DRE cancel (reason)
    ASSIGNED --> CANCELLED
    UNDER_REVIEW --> CANCELLED
```
`COMPLETED` carries the decision (`APPROVED`, `PARTIALLY_APPROVED`, `REJECTED`, `NO_APPROVAL_REQUIRED`, `ON_PROGRESS`) plus `disposition_code`. Existing `ACTIVATED` rows are treated as `ASSIGNED`/`SUBMITTED` depending on whether assignments exist. Legacy `ARCHIVED`-workflow rows become `LEGACY_NO_DECISION`. All transitions go through one `transition(rfi, to, actor, reason)` function: it validates against this table, locks the row (`SELECT … FOR UPDATE`), writes history and audit **in the same transaction**, and bumps `version`.

**Sequence rules:** `reviewer_assignments.sequence_no` is unique per (rfi, active cycle). The active assignment = the lowest pending `sequence_no`. `POST /rfis/{id}/review` is rejected with 409 unless the caller owns the active assignment. Concurrent submits are serialised by the row lock, and a unique constraint on `reviews.assignment_id` (already present) makes double-submits idempotent. Re-ordering or replacing **pending** assignments after review started requires a reason (audit, with old/new sequence). **Submitted** reviews are never edited: a correction creates a `review_amendments` row (original kept).

## 3. Schema changes (all additive; Alembic)

| Table | New columns / tables |
|---|---|
| `alembic_version` | Introduced with a **baseline revision = current schema** (no-op on existing DB). |
| `project_users` → used as **project_memberships** | `role VARCHAR(60) NULL`, `category VARCHAR(10) NULL`, `status VARCHAR(20) DEFAULT 'ACTIVE'`, `created_at`, `revoked_at` |
| `projects` | `status` (ACTIVE/ARCHIVED; `is_active` kept in sync), `project_length`, `settings_json` (notice_policy, contractor_visibility, inspector_register_access, deputy_label, email_enabled, overdue_hours, doc03_notes) |
| `rfi_summaries` | `client_request_id` (unique NULL), `contractor_rep_name`, `received_by`, `received_at`, `proposed_inspection_date`, `proposed_inspection_time` |
| `rfis` | `inspection_time TIME NULL`, `inspection_time_text`, `requested_time`, `material_source_offset`, `inspection_order`, `enclosure_sheets`, `received_by`, `received_at`, `short_notice BOOL`, `notice_hours`, `current_disposition`, `chainage_from_m`/`chainage_to_m` (DECIMAL, nullable), `provenance` (PORTAL / LEGACY_IMPORT), `legacy_rfi_status`, `legacy_source_row`, `client_request_id` |
| `rfi_work_categories` (new) | `rfi_id`, `category_code` (unique pair) |
| `reviewer_assignments` | `sequence_no INT NULL`, `activated_at`, `cycle_no`, `replaced_by_id`, `change_reason`, `sequence_backfilled BOOL` |
| `review_amendments` (new) | `review_id`, original/amended comment, editor, reason, timestamp |
| `decisions` | `disposition_code`, `approved_from`, `approved_to`, `conditions` |
| `issued_documents` (new) | `rfi_id`, `revision_no`, `doc_type` (DOC03/DOC01), `stored_name`, `sha256`, `issued_at`, `issued_by` |
| `rfi_amendments` (new) | controlled amendment: field, old, new, requested_by, approved_by, reason, timestamps |
| `notifications` | `project_id` |
| `audit_logs` | `project_id`, `before_json`, `after_json`, `ip`; append-only (no update/delete endpoints; DB user grants reviewed for production) |

**Data migrations (separate, reversible, logged):**
1. Membership roles: for each existing `project_users` row set `role = users.role` (codes copied unchanged; ARE later renamed to DRE by `migrate_dre_rename.py`). No new memberships are created; users without one are reported.
2. Back-fill `sequence_no` for open assignments by `assigned_at`, flag `sequence_backfilled`.
3. Normalise legacy `workflow_status='ARCHIVED'` with `record_state='ACTIVE'` → `LEGACY_NO_DECISION`.
4. Set `provenance='LEGACY_IMPORT'` for rows with no `summary_id` that were created by the importer (created_by = admin, created before the cut-over date).
5. **Workbook back-fill script** (new, `scripts/backfill_legacy_from_workbook.py`): reads the original `.xlsx` (header row 8, bounded to the last data row) and matches `(project, trimmed RFI_No., revision 0)`. It fills **only NULL** fields: `approved_from/to`, `inspection_time_text`/`inspection_time`, `legacy_rfi_status`, `legacy_source_row`, legacy path targets from AA/AE. It clears `requested_date` **only where it equals the inspection date and the row is LEGACY_IMPORT** (it was invented by I-3; the old value goes into the audit). Dry-run by default; writes `backfill_report.csv`. **Never overwrites** a non-null value that differs from the workbook; it lists those as conflicts.

## 4. Migration safety procedure (run for every schema/data step)

1. `docker compose ps`. Confirm which stack is running (never local + public on the same volume).
2. **Backup:** `./scripts/backup.sh`. Verify the dump is non-empty, that it restores into a scratch DB `rfi_restore_check`, and that the row counts match.
3. Record baseline counts: projects, users, project_users, rfi_summaries, rfis (by workflow/decision/record_state), assignments, reviews, decisions, attachments, audit_logs, plus checksums of `rfis(id, rfi_number, revision_no, current_decision)`.
4. Clone into `rfi_migration_test`, run `alembic upgrade head` + the data scripts there, compare counts (must be equal, or exactly the documented additions), and run the API test suite against it.
5. Only then apply to the real DB, with the stack stopped (`docker compose stop backend`, never `down -v`).
6. Re-count, compare, keep the report under `docs/migration_reports/` (git-ignored if it contains client data).

## 5. Phased work packages

| Phase | Work package | Depends on client? | Output / verification |
|---|---|---|---|
| **3a** | Alembic baseline; settings; production seeding guard (DR-12) | No | `alembic upgrade head` on a copy = no-op diff |
| **3b** | `authz` module; project membership roles; scope **every** endpoint (S-1, S-2, S-7, S-9); project-scoped notifications (S-4) | No (defaults most restrictive) | New tests: cross-project read/write/export/download denied |
| **3c** | Transition engine + transactional audit (S-8) + submitted-data lock and amendment flow (S-3) | No | State-table unit tests; audit-on-rollback test |
| **3d** | Sequential review: `sequence_no`, active turn, row locking, reassignment with reason, turn notifications (S-5) | No | UAT-04/05/06/07; concurrency test (two parallel submits) |
| **3e** | Decision model with disposition codes, approved section, issued DOC_03 snapshot; Admin decision removed (S-6) | **OD-06, DR-01, DR-04** | UAT-08/09/11 |
| **3f** | DOC_01 fields (time, offset, requested time, order, BOQ, work categories, enclosures), 24 h flag, idempotency keys | OD-11 (default flag) | UAT-02; retry test creates no duplicate |
| **3g** | Projects edit/activate/archive; membership UI; RE/DRE label | DR-02 for labels | UAT-01 |
| **3h** | Legacy back-fill script (dry-run first) + reconciliation report | DR-15/16/17 for labels only | Report reviewed before a real run |
| **4** | Frontend: DOC_01 batch editor (multi-row grid, draft/validate/submit), management assignment grid (DOC_01 + inspector/order columns), inspector DOC_03 review screen (only own field editable; waiting state), RE/DRE decision panel (six dispositions), DOC_02 register (32 + system columns, sort, filters, count, clear, "filtered" banner), role dashboards, project admin | as above | Build passes; responsive check at 360/768/1280 px |
| **5** | PDFs: DOC_01 landscape sheet (client columns + signatory block), DOC_03 client layout (header blocks, category checkboxes, 7 role rows, six disposition boxes, notes, distribution), DOC_02 landscape PDF (repeated header, page x/y, filters printed), Excel (workbook order, frozen header, autofilter, widths) | OD-13 for logos | Sample outputs committed under `docs/samples/` with **synthetic** data only |
| **6** | Tests: pytest suite on a throwaway MySQL DB (`rfi_test`), covering FR/BR/UAT-01…12, migration-safety, duplicates, revisions, isolation, concurrency, attachments, dates/times, exports; extend `e2e_api_test.py`; frontend build + smoke | No | Actual results recorded, including failures |
| **7** | Deployment: prod compose hardening (no exposed DB, secrets via env, HTTPS, security headers, rate-limited login), backup cron + restore drill doc | OD-14 | Checklist |
| **8** | Docs: admin guide, user guides per role, deployment/backup/restore, data dictionary + ERD, final production-readiness checklist | No | |

## 6. What can start now vs. what waits

- **Start immediately (no client answer needed, all strictly safer than today):** 3a, 3b, 3c, 3d, 3f (flag mode), 3g (without the label decision), 3h dry-run, the register/export work, and the test suite.
- **Build behind settings, finalise after the client answers:** OD-03, OD-04, OD-05, OD-07, OD-09, OD-11.
- **Wait for the client:** final disposition list and legacy mapping (OD-06/DR-17), the Admin authority policy (DR-01, default = no decision rights), the ARE↔DRE per-user mapping (DR-02), the historical project ownership (DR-15), and logos/templates (OD-13).

## 7. Environment prerequisites before Phase 3 touches any database
- Docker Desktop running; confirm whether the **public demo stack** is up (it shares the MySQL volume).
- A verified backup of the live DB + uploads (procedure §4).
- A throwaway `rfi_test` DB for automated tests (backend on :8001, frontend on :5174), never the real DB.
