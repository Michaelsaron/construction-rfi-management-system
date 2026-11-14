# Repository Audit, Gap Analysis and Requirements Traceability Matrix
> **Note (DR-02, decided Nov 2026):** the client chose "DRE" everywhere. Mentions of ARE below describe the system/data *as it was* at the time of writing. The application now presents and authorises ARE as DRE.

**Baseline audited:** commit `583b6d3` ("Construction RFI management system"), clean working tree, 14 Nov 2026.
**Method:** every backend router, model, schema, service and script was read in full. The frontend routing, workflow pages, API client and offline queue were read. The client workbook was profiled (see `01_DOC02_WORKBOOK_ANALYSIS.md`).
**Not verified at runtime:** Docker was not running during this audit, so the live MySQL database (and its reported 2,465 RFIs) could **not** be inspected, counted or backed up. Every statement below about behaviour comes from reading the code. Nothing was executed against a database.

Classification: **Implemented** · **Partial** · **Missing** · **Conflicting** (existing behaviour contradicts the SRS) · **Confirm** (needs a client decision).

---

## 1. What exists today (summary)

| Area | Current implementation |
|---|---|
| Stack | FastAPI + SQLAlchemy 2 + MySQL 8.4; React 19 + Vite + TS; nginx; Docker Compose (dev / prod / demo / public). Matches the brief and is retained. |
| Schema management | `Base.metadata.create_all()` at startup + one ad-hoc additive script (`migrate_release_v4.py`). **No migration framework (Alembic) and no schema version table.** |
| Auth | bcrypt hashing, JWT HS256 (8 h) stored in `localStorage`, forced password change, email reset tokens (1 h). No login throttling. |
| Roles | **One global `users.role`** string. Codes: `ADMIN, RE, ARE, RE_ARE, CONTRACTOR, SITE_ENGINEER, WORK_INSPECTOR, STRUCTURE_INSPECTOR, SURVEYOR, SENIOR_SURVEYOR, MATERIAL_INSPECTOR, LAB_TECHNICIAN, MATERIAL_ENGINEER, PROJECT_MANAGER, VIEWER`. No DRE, Data Encoder, Office Engineer, QS, Draftsperson, Secretary. |
| Project membership | `project_users(project_id, user_id)` with **no role column**. Checked **only** in Daily Progress and the Daily Progress PDF. |
| DOC_01 | `rfi_summaries` + child `rfis`: draft → add RFIs → submit (locks the batch) → RE/ARE may return. Summary PDF exists. |
| DOC_02 | `rfis` table = register. List with filters (project, status, decision, work item, side, date range, text search), "load more" paging, Excel export (project filter only). |
| DOC_03 | Activate → assign reviewers (**parallel, unordered**) → each reviewer submits recommendation + comment → when all *required* reviews are done → `AWAITING_DECISION` → RE/ARE decides (APPROVED/REJECTED/ON_PROGRESS/INFORMATION_ONLY), **with an override that can skip pending reviews**. Generic A4 "approval sheet" PDF. |
| Resubmission | A rejected RFI can create revision N+1 (same RFI No.). |
| Other modules | Daily Progress (draft/submit/review/confirm + PDF/Excel), Reference Data, Reviewer Rules, Notifications (in-app + email when SMTP set), Overdue reminders (hourly, by assignment age), Attachments (type/size limits), Audit Log, PWA + IndexedDB offline write queue. |
| Tests | `scripts/e2e_api_test.py` (≈151 checks across roles, needs a running throwaway stack) and `e2e_smoke.sh`. **No unit/integration test suite runs without Docker.** |
| Data | Historical importer for the client workbook (defects I-1…I-9 in the workbook analysis). |

## 2. Critical findings (fix before any production use)

| # | Finding | Evidence | SRS ref |
|---|---|---|---|
| **S-1** | **No project isolation on the RFI core.** Any authenticated user (including a contractor or a user with no project) can list and read **every** RFI and summary in **every** project, export the full register, download any RFI/summary PDF, and list/download any attachment. | `rfis.ls`, `rfis.one`, `summaries.ls/one`, `reports.excel/pdf/summary_pdf`, `attachments.download/ls` use only `current_user` | FR-23, BR-10, §7, UAT-12 |
| **S-2** | **Anyone can create RFIs/summaries in any project and submit any summary.** `POST /rfis`, `POST /rfi-summaries`, `POST /rfi-summaries/{id}/submit` have no role, membership or ownership check. | `rfis.create`, `summaries.create/submit` | FR-04, §7 |
| **S-3** | **Submitted data can be silently edited.** `PUT /rfis/{id}` lets *any* user edit any non-completed RFI (including one under inspector review), with no reason and no old/new values. | `rfis.update` | §5.4, §7.1, §11.1 |
| **S-4** | **Notifications leak across projects.** `notify_roles` sends to every active user with the role, system-wide (e.g. every RE/ARE on every project receives every submission). | `services/notify.notify_roles` | §11 ("must not expose records") |
| **S-5** | **Reviews are parallel, not sequential.** There is no sequence field, and any assigned reviewer can submit at any time. | `ReviewerAssignment` has no order; `rfis.review` | FR-13, BR-05, BR-06, UAT-06 |
| **S-6** | **The final decision can bypass inspector reviews** (`override_used`), and **Admin can decide and can submit reviews on behalf of inspectors.** | `rfis.decide` (`DECISION_ROLES` includes ADMIN), `rfis.review` (`u.role!='ADMIN'`) | FR-15, BR-07, §7.1 (conflict C-1) |
| **S-7** | **The user directory is readable by every user** (`GET /users`): names, emails, roles and project ids of all users across all projects. | `users.ls` | §7.1 least privilege |
| **S-8** | **Audit is not transactional.** `log()` commits separately *after* the business commit, so a failure loses the audit record. Audit rows have no project, no old/new values, and no protection beyond the API. | `services/audit.log` | FR-25, §11.1 |
| **S-9** | **Any user can resubmit any rejected RFI** (no ownership/project check). | `rfis.resubmit` | §7 |
| **S-10** | The startup hook seeds a `DEMO` project and a default admin (`Admin123!`) in **every** environment, including production. | `main.startup` | §12 Security |

## 3. Requirements traceability matrix

### 3.1 Functional requirements (FR-01 … FR-28)

| ID | Requirement (short) | Status | Evidence / gap | Planned change |
|---|---|---|---|---|
| FR-01 | Admin create/edit/activate/archive projects | **Partial** | Create + list only. No edit, activate or archive endpoint or UI. | Add `PUT /projects/{id}`, `/activate`, `/archive`; archived = read-only. |
| FR-02 | Admin creates users, assigns to projects **with category and role** | **Partial / Conflicting** | User has one global role; membership has no role. | Add `project_memberships.role/category/status` (additive). Keep `users.role` only for `ADMIN` and as a legacy fallback. |
| FR-03 | Only Admin creates projects / categorises users | **Implemented** | `require_roles('ADMIN')` on project/user create. | Keep; extend to the membership endpoints. |
| FR-04 | Category 3 creates/submits DOC_01 for an authorised project | **Missing** (no role/project check, S-2) | | Membership + role `DATA_ENCODER`/`OFFICE_ENGINEER` required. Batch ownership enforced. |
| FR-05 | Validate mandatory DOC_01 fields; detect duplicate RFI No. | **Partial** | Number/item/description required; DB unique on (project, number, revision). No inspection date/time requirement, no in-batch duplicate check before save, generic 409 message. | Field-level validation, named duplicates, pre-submit validation report. |
| FR-06 | Record submitter, project, submission timestamp, batch ref | **Implemented** | `rfi_summaries.submitted_by/submitted_at/summary_reference`. | Add `client_request_id`; record proposed inspection date/time on rows. |
| FR-07 | Create DOC_02 row(s) from DOC_01 submission | **Implemented (by design)** | Child `rfis` rows *are* the register. | Add the missing DOC_01 columns (time, offset, requested time). |
| FR-08 | Notify Cat 2.1 + display pending submissions | **Partial / Conflicting** | Notifies globally by role (S-4); no RE/DRE "new batches" dashboard panel. | Project-scoped recipients; management dashboard. |
| FR-09 | RE/DRE assign one or more Cat 2.2 inspectors per RFI | **Implemented (basic)** | Single-assignment endpoint; any active user with an inspector *global* role. Requires a separate "Activate" step. | Batch assignment screen (DOC_01 + assignment columns); restrict to project members holding an inspector role. |
| FR-10 | Set/change review sequence subject to audit | **Missing** | No sequence. | `sequence_no` (unique per RFI); re-order/replace after start requires reason + audit. |
| FR-11 | Generate one prefilled DOC_03 per RFI | **Partial** | The RFI detail page acts as DOC_03; the PDF is generic, not the client form. | DOC_03 screen + PDF reproducing the client layout (role rows, checkboxes, dispositions). |
| FR-12 | Inspector edits only their designated field | **Partial** | A review is bound to the assignment owner, but Admin may submit for anyone. | Remove the Admin bypass (C-1); a field is bound to the assignment. |
| FR-13 | Enforce sequential review; prevent out-of-turn | **Missing** (S-5) | | Backend: only the lowest-sequence pending assignment may submit. Row lock (`SELECT … FOR UPDATE`) against races. |
| FR-14 | Record inspector identity, comments, sequence, time | **Partial** | Identity, comment, time recorded; no sequence. | Add sequence. |
| FR-15 | Route to Cat 2.1 after all reviews complete | **Partial / Conflicting** | Auto `AWAITING_DECISION` works, but the decision can be taken earlier via override; "required=false" reviewers are advisory. | Decision allowed only when all assigned reviews are complete (override removed or kept as a configurable, audited emergency path, pending confirmation). |
| FR-16 | RE or DRE records approval/rejection | **Partial / Conflicting** | RE/ARE/RE_ARE **and ADMIN** can decide; no DRE role. | Decision restricted to project members with role RE/DRE (C-1, C-2). |
| FR-17 | Record decision-maker, decision, date/time | **Implemented** | `decisions` table. | Add disposition code, approved section, conditions. |
| FR-18 | Update the same DOC_02 row with DOC_03/decision data | **Implemented (basic)** | `current_decision`, `workflow_status` updated in the same row. Approved_From/To not captured at decision. | Transactional update of approved section/disposition; issued-PDF snapshot. |
| FR-19 | Link DOC_01/02/03 via RFI No. + project | **Implemented** | `summary_id`, `project_id`, `rfi_number`, internal id. | Show links in UI and exports. |
| FR-20 | Searchable DOC_02 with column filters | **Partial** | 7 filters + text search; no sort control, no total count, no inspector/contractor filter, no "filtered" indicator, no clear-filters button verified. | Server-side sort + count + paging; full filter set. |
| FR-21 | Export full or filtered DOC_02 to Excel **and PDF** | **Partial** | Excel ignores all filters except project and is not access-scoped; **no register PDF**. | Same filter object for screen/Excel/PDF; landscape PDF with repeated header. |
| FR-22 | Downloadable PDF of completed DOC_03 | **Partial** | Generic PDF, regenerated on each download (not "as issued"). | Client-layout PDF; stored issued snapshot. |
| FR-23 | DOC_02 available to Cat 1, 2.1, 2.3, 3, project-scoped | **Conflicting** (S-1) | Everyone sees everything. | Project + role scoping; contractor visibility per OD-03. |
| FR-24 | Completed DOC_03 PDF available to Cat 1, 2.1, 2.3, 3 | **Conflicting** (S-1) | | Same as FR-23. |
| FR-25 | Time-stamped audit of workflow and admin actions | **Partial** (S-8) | Many actions logged; not transactional; no project; no old/new values. | Transactional audit with project_id and before/after JSON. |
| FR-26 | Show RFI status and pending actions | **Partial** | Status chips, generic dashboard, My Inspections. No per-role pending-action lists. | Role dashboards (§8 of brief). |
| FR-27 | Retain completed/rejected records; prevent unauthorised deletion | **Implemented (mostly)** | No delete endpoints for RFIs (archive/cancel only, manager role, with reason). Attachments soft-deleted. | Archive/cancel restricted to project RE/DRE/Admin with reason; keep. |
| FR-28 | Attachments if enabled; configurable types/size | **Partial** | Types fixed in code, size via env; no per-project/RFI permission check (S-1). | Config-driven limits; permission checks via parent record. |

### 3.2 Business rules (BR-01 … BR-10)

| ID | Rule | Status | Notes |
|---|---|---|---|
| BR-01 | Batch may contain multiple RFIs; each processed independently | **Implemented** | Per-RFI activation/assignment/decision. |
| BR-02 | One DOC_02 row + one DOC_03 per RFI review cycle | **Implemented** | Unique (project, number, revision). |
| BR-03 | RFI No. visible key; uniqueness scope to confirm | **Implemented (per project + revision)** / **Confirm** | OD-01. |
| BR-04 | DOC_02 populated at submission, enriched after decision | **Partial** | Approved section and disposition not captured. |
| BR-05 | Inspectors review in exact assigned order | **Missing** | S-5. |
| BR-06 | Only the active assigned inspector may submit | **Missing** | S-5. |
| BR-07 | Only RE or DRE make the final decision | **Conflicting** | ADMIN can decide; no DRE (C-1, C-2). |
| BR-08 | Rejected records and history retained | **Implemented** | Revision model preserves the old row, decision and history. |
| BR-09 | 24 h notice preferred; shorter flagged | **Missing** | No time capture, no flag. |
| BR-10 | Viewing and exports respect project/record permissions | **Conflicting** | S-1. |

### 3.3 Open decisions (OD-01 … OD-14)

See `04_DECISION_REGISTER.md`. All 14 are **Confirm**. The supplied documents give strong evidence for OD-08, OD-12 and OD-13 but do not replace sign-off.

### 3.4 Acceptance tests (UAT-01 … UAT-12): can they pass on the current code?

| ID | Test | Current result (code reading) | Blocker |
|---|---|---|---|
| UAT-01 | Admin creates project, assigns roles | **Fail (partial)** | No project-specific roles; no project edit/archive. |
| UAT-02 | Contractor submits DOC_01 with multiple RFIs | **Pass (basic)** | Missing inspection time, offset, 24 h flag. |
| UAT-03 | RE/DRE dashboard shows new batch | **Fail** | No DRE; no batch panel; global notifications. |
| UAT-04 | Assign three inspectors in sequence | **Fail** | No sequence. |
| UAT-05 | First inspector: only designated field, locked + time-stamped | **Partial** | Locked + time-stamped, but Admin bypass. |
| UAT-06 | Second inspector blocked early | **Fail** | Parallel reviews allowed. |
| UAT-07 | All submit → routed to RE/DRE | **Pass (basic)** | Override can pre-empt. |
| UAT-08 | RE approves one, rejects another; details recorded | **Pass (basic)** | Disposition detail and approved section missing. |
| UAT-09 | DOC_02 updated, no duplicate rows | **Pass** | |
| UAT-10 | Office user exports filtered DOC_02 (Excel/PDF), only authorised rows | **Fail** | No Office roles, filters ignored, no PDF, not scoped. |
| UAT-11 | Completed DOC_03 PDF legible and matches record | **Partial** | Not the client layout; not "as issued". |
| UAT-12 | Unauthorised project/field access denied | **Fail** | S-1, S-2, S-3, S-7. |

## 4. Existing complementary features (preserve; not part of the mandatory SRS)

| Feature | Classification | Action |
|---|---|---|
| Daily Progress (+ PDF/Excel) | Complementary (sourced from workbook `Daily_Progress_List`) | Keep. Apply the same project/role scoping. |
| Reference Data (master_data) | Supports DOC_01 dropdowns, so core-enabling | Keep; scope edits to Admin/RE/DRE of the project. |
| Reviewer Rules | Complementary (suggests inspectors per work item) | Keep; use it to pre-fill the sequence suggestion. |
| Overdue reminders | Supports §13.1 "overdue inspector action" | Keep; base the timer on turn activation and inspection time (form note 5: "return within 24 h"). |
| Attachments | FR-28 (optional) | Keep; add permission checks. |
| PWA + offline queue | Complementary | Keep. Add idempotency keys so replays cannot duplicate. **Do not claim offline inspection works** until tested. |
| `ON_PROGRESS` / `INFORMATION_ONLY` decisions | Pre-figure the DOC_03 dispositions | Migrate into the disposition model (OD-06). |
| RFI archive/cancel | Complementary | Keep, with reason + audit. |

## 5. Breaking-change risks

| Change | Risk | Mitigation |
|---|---|---|
| Project-scoped roles | Existing users have only a global role, and only some have `project_users` rows. Enforcing membership could lock users out. | Migration creates membership rows with `role = users.role` for every existing (user, project) pair. **No privilege is added.** Users with no membership get a report, not auto-access. |
| RE/ARE → RE/DRE | Silent renaming would change historical meaning and could widen approval rights. | Keep `ARE` as a distinct legacy code; add `DRE`. Map ARE→DRE **only** per user after client confirmation (DR-02). |
| Removing the Admin decision/review bypass | Admin currently "rescues" stuck RFIs. | Replace with controlled reassignment (management) + audit. Admin keeps oversight read access. |
| Sequential reviews on in-flight RFIs | Existing `UNDER_REVIEW` RFIs have unordered assignments. | Back-fill `sequence_no` by `assigned_at` order, flagged `sequence_backfilled`; management can re-order with reason. |
| Status model changes | Front-end and exports read the current codes. | Additive: keep existing codes, add `ASSIGNED`, `RETURNED`; map in one place. Legacy `ARCHIVED` workflow value normalised to `LEGACY_NO_DECISION` (data migration, reversible). |
| `description` becoming optional | API currently rejects empty values. | Additive relaxation only. |
| Schema migrations | `create_all` never alters existing tables. | Introduce Alembic with a baseline revision equal to the current schema; all new revisions additive. |
