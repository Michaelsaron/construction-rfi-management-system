# Migration Report: release 5.0.0-srs applied to the live database (14 Nov 2026)
> **Note (DR-02, decided Nov 2026):** the client chose "DRE" everywhere. Mentions of ARE below describe the system/data *as it was* at the time of writing. The application now presents and authorises ARE as DRE.

Executed per `06_MIGRATION_RUNBOOK.md` after written approval. **Result: success. No rollback was needed.**

## Timeline (local time, EAT)
| Step | Result |
|---|---|
| Fresh backup 17:14 (`backups/pre-migration/rfi_db_20261114_171411.sql`, 1,215,551 B, "Dump completed") | OK |
| Backup restored into isolated `rfi_premig_restore` (container `rfi-srs-testdb`) and compared | Counts + RFI checksum identical |
| Rollback path tested: the **old** deployed backend image run against the migrated clone | health 200, register 200, dashboard total 2,467, Excel export 200, no errors |
| Stop `tunnel nginx frontend backend` (db kept running, volume untouched) | OK |
| Build new backend; dry run on live `rfi_db` | 39 ADD COLUMN + 5 indexes + 2 tables; data steps identical to the rehearsal |
| `--apply` | "No tables, columns or rows were deleted; no existing non-NULL value was changed." |
| Verify against the pre-SRS baseline | **All 15 counts and the RFI checksum identical** |
| Idempotency re-run | 0 statements, 0 rows |
| `up -d --build` (all services) | Startup schema check passed; `/api/health` → `5.0.0-srs`; frontend 200 |
| Post-startup and final integrity checks | Identical to baseline |

## Database counts (before = after)
projects 2 · users 2 · project_users 1 · rfi_summaries 3 · **rfis 2,467** · reviewer_assignments 0 · reviews 0 · decisions 0 · attachments 0 · audit_logs 16 · notifications 2 · master_data 1,957 · daily_progress 1 · rfi_status_history 4 · reviewer_rules 1.
RFI checksum `b35e156a09cc1342f50d7e444232c580`, unchanged.

New derived fields: provenance LEGACY_IMPORT 2,465 / PORTAL 2. `legacy_rfi_status` copied for 2,309 rows. **461** Not-Ready variants preserved (429 "Not Ready", 9 "Not ready", 23 "Note ready"); the original remarks text is unchanged. The ARE membership keeps the role `ARE`. No user was renamed or granted new access.

## Browser testing
**A. Full workflow on an isolated stack** (new backend :8001 + frontend :5174 + fresh DB `rfi_browser_test`, headless Google Chrome via Playwright): **26/26 checks passed**, plus 1 informational check.
Covered: admin creates project and contractor in the UI → forced password change → DOC_01 batch with 2 RFIs (missing field flagged, then completed) → submit locks the batch → DOC_01 PDF → RE dashboard shows the batch → RE sets the sequence Surveyor → Works Inspector → the 2nd inspector cannot submit early → Surveyor submits (locked) → WI submits → Awaiting Final Decision → RE records "Approved: Compliance to Comments required" (DOC_03 issued with SHA-256) → DOC_03 PDF → QS filters the DOC_02 register (filtered banner) and exports Excel + PDF → QS has no assign/decision controls → a user of another project is denied the RFI URL → Admin sees no decision/review controls → phone width 390 px renders without horizontal scroll. No JavaScript errors.

**B. Read-only checks on the live public URL** (admin; no creates/edits/exports): **8/8 passed**. HTTPS login page; project `<PROJECT_CODE>`; dashboard and register show 2,467; historical "Not Ready" 438 + "Note ready" 23 = 461; legacy RFI read-only with its status preserved; existing DOC_01 batch visible; no JS errors. The ARE account was **not** used, because its first sign-in forces a password change.

## Deployment status
Public demo: running (`docker-compose.public.yml`) with release 5.0.0-srs. The quick-tunnel URL changed with the restart (see the chat report; it changes again on every tunnel restart).

## Issues found during this exercise
1. Legacy RFI detail labels: "Submitted by" shows the importer account (System Admin), and "Requested" shows the date the old importer copied from the inspection date (defect I-3). Display-only; the data itself is unchanged. Needs a UI label fix plus the decision on the workbook back-fill.
2. The runbook miscounted the ADD COLUMN statements (33 instead of 39). Documentation only; corrected.
3. Everything listed in `07_IMPLEMENTATION_STATUS.md` under "Not done / known limitations" (except items 1 and 2 there, now done) remains open.
