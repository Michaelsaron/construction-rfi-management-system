# Implementation Status — branch `feature/srs-v1-upgrade` (14 Nov 2026)

**Not production-ready yet.** Update 14 Nov 2026 17:45: the migration **has been applied** to the live database and verified (see `08_MIGRATION_REPORT.md`). The UI has been browser-tested (isolated full workflow 26/26; live read-only 8/8).

## Verification actually run
| Check | Result |
|---|---|
| `pytest` (backend/tests, isolated MySQL `rfi_test` on :3307) | **23 passed**, 0 failed |
| Frontend `tsc --noEmit` / `vite build` | pass / pass (392 kB JS) |
| Backend Docker image build (separate tag) | pass; migration module and app import inside the image |
| Migration rehearsal on a clone of the real backup | pass; original counts + checksum unchanged; idempotent |
| New backend on the unmigrated backup copy | refuses to start (schema check), creates nothing |
| New backend on the migrated copy | serves 2,467 RFIs; legacy rows read-only; 461 Not-Ready values preserved; cross-project access denied |
| Live `rfi_db` | untouched (re-verified) |
| Legacy `scripts/e2e_api_test.py` | **not run**: it targets the pre-5.0 endpoints and is superseded by pytest |

## SRS acceptance tests (automated)
| UAT | Test(s) | Status |
|---|---|---|
| 01 Admin creates project, assigns roles | `test_uat01…`, `test_role_must_be_valid…` | Pass |
| 02 Contractor submits DOC_01 with multiple RFIs | `test_uat02…`, `test_doc01_validation…`, `test_short_notice…`, `test_only_contractor…` | Pass |
| 03 RE/DRE receive submission | `test_uat03…` (project-scoped notifications + dashboard) | Pass |
| 04–07 Sequence, locked field, early submit blocked, routing | `test_uat04_to_07…`, `test_assignment_validation…`, `test_concurrent_double_submission…` | Pass |
| 08 RE approves one, rejects another | `test_uat08_09…`, `test_partial_approval…` | Pass |
| 09 DOC_02 updated, no duplicates | `test_uat08_09…` | Pass |
| 10 Office exports filtered DOC_02 (Excel + PDF) | `test_uat10…` | Pass |
| 11 Completed DOC_03 PDF matches record | `test_uat11…` (SHA-256 equals issued snapshot; content checked) | Pass |
| 12 Unauthorised project/field access denied | `test_uat12…`, `test_legacy_records…`, `test_audit_access`, `test_daily_progress…` | Pass |

User acceptance by the client (real users, real devices) is still required. These are automated API-level tests.

## Implemented (summary)
- Central `authz` module; project memberships with project roles; every RFI, DOC_01, register, PDF, Excel, attachment, dashboard, notification, audit, reference-data, reviewer-rule and Daily-Progress endpoint is project-scoped. `/users` is admin-only.
- Submitted RFIs locked. Corrections go through a controlled amendment (request → RE/DRE approve/reject, original values kept, stale-value check).
- Strict sequential review: sequence numbers, a single active turn, row locks, change-after-start requires a reason, and the replaced inspector is locked out.
- Final decision RE/DRE/ARE only (Admin excluded). Configurable DOC_03 dispositions. Approved section. Issued DOC_03 snapshot with SHA-256.
- DOC_01 fields: inspection/requested time, material offset, order of inspection, BOQ, work categories, enclosures. 24 h flag (or require reason) in site time. Idempotent create/submit.
- DOC_02: paged/sorted/filtered register with total and a filtered banner. Excel in workbook column order (frozen header, autofilter). Landscape A3 PDF with repeated header and "Page x of y".
- DOC_01 and DOC_03 PDFs following the client forms; typed-name electronic acknowledgements only (no signatures or stamps generated).
- Transactional audit with project and before/after values.
- Role dashboards; project admin (edit/archive/activate/settings/members); production seeding guard; startup schema check; basic security headers.

## Not done / known limitations
1. ~~Real-database migration~~: done 14 Nov 2026.
2. ~~Browser testing~~: done (Chrome, desktop + 390 px phone). Still open: formal accessibility review, other browsers, real devices, and client UAT.
2b. Legacy RFI detail shows the importer account as "Submitted by" and an importer-copied "Requested" date (display fix pending).
3. **Legacy back-fill from the workbook** (approved chainages for 1,549 rows, inspection times for 2,127, the 4 skipped duplicate rows, correct legacy file paths): not implemented. It needs approval, because it writes into historical rows (NULL-only).
4. **Alembic** not introduced. An idempotent additive script is used instead (same safety, less tooling).
5. Security hardening still open: JWT kept in `localStorage`, no login rate-limiting, no automated backup cron or off-site copy, HTTPS only on the tunnel/VPS.
6. Email notifications fire when SMTP is configured (OD-09 unconfirmed). SMS/push not implemented.
7. Offline: create/submit are idempotent. Offline inspection drafts and the Expo app are future work.
8. Client decisions in `04_DECISION_REGISTER.md` remain open. The conservative defaults are listed there and are project settings.
