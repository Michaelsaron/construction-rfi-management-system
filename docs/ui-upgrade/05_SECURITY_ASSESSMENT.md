# Security assessment — release 6.0.0-ui

Scope: the evidence architecture, new endpoints, redesigned web app and the sign-in hardening committed on 24 Nov 2026 (`2ea2c9a`). This is a developer self-assessment backed by automated tests. **It is not an independent penetration test.**

## Controls in place

| Area | Control | Verified by |
|---|---|---|
| Sessions | HttpOnly, SameSite=Strict session cookie; CSRF header required for cookie writes (including multipart uploads); Bearer only for API clients | `test_security.py` |
| Sign-in abuse | Per-account lockout, per-IP failure ceiling, password-reset throttling without account enumeration | `test_security.py` |
| Account lifecycle | Temporary passwords must be changed; a password change ends other sessions; deactivated users are rejected immediately | `test_security.py` |
| Secrets | Production refuses weak or example JWT secrets | `test_production_refuses_weak_jwt_secret` |
| Project isolation | Every endpoint resolves project membership; cross-project reads, writes, downloads and bundles return 403 | `test_uat12…`, `test_submission_locks_review_and_evidence`, `test_completed_record_issued_snapshot_and_bundle` |
| Evidence ownership | Only the remark author / active inspector may upload; only the uploader may remove, and only before locking; drafts are private | `test_only_active_inspector…`, `test_management_remark_ownership…` |
| Out-of-turn actions | Pending, replaced and completed assignments refuse uploads, drafts and submissions | as above |
| Locking / version preservation | Submitted reviews, remarks and DOC_01 enclosures are locked; corrections only through approved amendments; superseded files kept | `test_submission_locks…`, `test_evidence_amendment…`, `test_record_attachments_lock_on_submission` |
| Database integrity | Composite FKs and a CHECK constraint prevent mis-attached evidence even with direct SQL | `test_database_constraints_reject_invalid_evidence_relationships` |
| Upload validation | Policy extension list, size limit while streaming, count limit, empty-file rejection, content signature check, optional ClamAV; partial files removed | `test_invalid_oversized_mismatched_and_empty_files_are_rejected`, `test_interrupted_upload…` |
| Duplicate prevention | `UNIQUE(uploaded_by, upload_token)`; the race is handled | `test_duplicate_upload_token…`, `test_concurrent_uploads_with_same_token_store_one` |
| No path disclosure | Storage names never returned; legacy drive paths never returned (status label instead); download only by id with access check | `test_hidden_fields_and_legacy_paths`, test assertions on payloads |
| File integrity | SHA-256 recorded at upload; verified on every download and bundle; tampering refused and audited | `test_completed_record_issued_snapshot_and_bundle` |
| Safe preview | Inline only for PDF and images, `Content-Security-Policy: sandbox`, `nosniff`, content type from the extension | code review |
| Issued documents | DOC_03 snapshot stored with SHA-256 at decision time and served unchanged; never regenerated | `test_uat11…`, bundle test |
| Data exposure policy | Hidden workbook fields I:M and S filtered by category in the register and exports; contractor evidence access off by default | `test_hidden_fields_and_legacy_paths`, `test_contractor_evidence_access_setting` |
| Audit | Uploads, removals, downloads, previews, bundle exports, access-matrix exports, remark submissions, corrections and integrity failures are logged with project id | code review; existing audit tests |
| Response headers | `nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: same-origin`, `Cache-Control: no-store` on API responses | existing middleware |

## Dependency audit (24 Nov 2026)

| Package | Finding | Action |
|---|---|---|
| npm (production dependencies) | 0 vulnerabilities | — |
| starlette 0.47.3 (via fastapi 0.116.1) | Several advisories (multipart / request parsing) | **Upgraded** to fastapi 0.165.0 / starlette 1.10.0. All tests pass. |
| python-multipart 0.0.20 | PYSEC-2026-3039 | **Upgraded** to 0.0.34 |
| python-jose 3.5.0 | PYSEC-2026-4298: HMAC accepts DER public keys when algorithms are not restricted | Not exploitable here: decode pins `algorithms=[HS256]` and the system has no public key. **Recommendation:** migrate to PyJWT in a later release. |
| ecdsa 0.19.2 (via python-jose) | PYSEC-2026-1325 timing side channel in ECDSA signing; no upstream fix | Not used: tokens are HMAC-signed. Goes away with the PyJWT migration. |

## Residual risks and open items

| # | Risk | Severity | Mitigation / next step |
|---|---|---|---|
| R1 | Malware scanning is disabled until the client decides (UD-09) | Medium | Enable `SCAN_IF_AVAILABLE` or `REQUIRED` with a ClamAV container. Previews are sandboxed and only PDF/images are shown inline. |
| R2 | Evidence files are stored unencrypted on the server disk (backups are encrypted) | Medium | Restrict host access; use disk encryption on the VPS; object storage with server-side encryption is a later option. |
| R3 | Login throttling counters live in process memory (single uvicorn worker) | Low | Documented; move to Redis if the backend is scaled to several workers. |
| R4 | Production HTTPS depends on the hosting (Cloudflare tunnel today) | High for production | VPS with TLS certificate and HSTS before go-live (readiness checklist). |
| R5 | Electronic acknowledgements are typed names + authenticated account + server time, not certified signatures | Policy | UD-15. No certified signature is claimed anywhere. |
| R6 | No independent penetration test or formal accessibility audit | Medium | Recommended before production go-live. |
| R7 | Removed draft files stay on disk (KEEP_ALL) | Low | UD-08 retention decision. |
| R8 | python-jose is unmaintained | Low | PyJWT migration (above). |
