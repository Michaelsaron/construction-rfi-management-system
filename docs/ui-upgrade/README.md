# UI design v1 upgrade — release 6.0.0-ui

Branch `feature/ui-design-v1`. Implements the *RFI Management System — Front-End UI Design v1.0* (15 Nov 2026) on top of the SRS v1.0 system (release 5.1).

**Status (24 Nov 2026):**
- Implemented and tested on isolated databases.
- **Not applied to the live database; the client application has not been restarted with this release.** Both wait for the owner's approval (see the runbook).
- SRS v2.0 has not been received, so no SRS v2.0 compliance is claimed (UD-01).

| # | Deliverable | Location |
|---|---|---|
| 1 | Source code | `backend/app` (routers `evidence`, `records`, `admin`; `services/evidence.py`), `frontend/src` |
| 2 | UI design traceability (18 pages) | [01_TRACEABILITY_MATRIX.md](01_TRACEABILITY_MATRIX.md) |
| 3 | Database schema and ERD | [02_SCHEMA_AND_ERD.md](02_SCHEMA_AND_ERD.md) |
| 4 | Attachment architecture | [03_ATTACHMENT_ARCHITECTURE.md](03_ATTACHMENT_ARCHITECTURE.md) |
| 5 | Additive migration scripts | `backend/scripts/migrate_ui_v1.py` (after `migrate_srs_v5.py`) |
| 6 | Role and permission matrix | [04_PERMISSION_MATRIX.md](04_PERMISSION_MATRIX.md); live export `/admin/access-matrix.xlsx` |
| 7 | Frontend screens | see traceability; screenshots in `screenshots/` |
| 8 | Backend APIs | `docs/api/openapi.json`, [API_CONTRACTS.md](../api/API_CONTRACTS.md) |
| 9 | Sample DOC_03 PDF and evidence bundle (synthetic) | `docs/samples/sample_DOC03_issued_with_attachment_index.pdf`, `sample_evidence_bundle.zip`, `sample_DOC02_register_v6.*` |
| 10 | Automated test results | [11_TEST_RESULTS.md](11_TEST_RESULTS.md) |
| 11 | Browser testing results | [11_TEST_RESULTS.md](11_TEST_RESULTS.md), `browser_results.json` |
| 12 | Responsive screenshots | `screenshots/` (desktop / tablet / phone) |
| 13 | Security assessment | [05_SECURITY_ASSESSMENT.md](05_SECURITY_ASSESSMENT.md) |
| 14 | Client decision register | [DECISION_REGISTER.md](DECISION_REGISTER.md) |
| 15 | Migration and rollback runbook | [07_MIGRATION_AND_ROLLBACK_RUNBOOK.md](07_MIGRATION_AND_ROLLBACK_RUNBOOK.md) |
| 16 | Administrator and user guides | [08_ADMIN_GUIDE.md](08_ADMIN_GUIDE.md), [09_USER_GUIDE.md](09_USER_GUIDE.md) |
| 17 | Production-readiness checklist | [10_PRODUCTION_READINESS.md](10_PRODUCTION_READINESS.md) |
| — | Backup / security configuration | `docs/deployment/BACKUP_AND_RECOVERY.md`, `docs/deployment/SECURITY.md` |

## Re-running the browser test
1. `scripts/e2e/run_e2e.sh reset <workdir>`
2. Start the backend on :8001 with `<workdir>/backend.env`, which must point at a `*_test` database, and the frontend on :5174 with `VITE_API_URL=http://localhost:8001`.
3. `scripts/e2e/run_e2e.sh test <workdir>`. `<workdir>` must contain `playwright-core`; the test uses the local Google Chrome.
