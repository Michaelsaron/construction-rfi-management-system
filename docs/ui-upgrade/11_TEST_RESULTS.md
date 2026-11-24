# Test results — release 6.0.0-ui (24 Nov 2026)

All tests ran against **isolated, throwaway databases** in the separate MySQL container `rfi-srs-testdb` (127.0.0.1:3307): `rfi_test` for pytest and `rfi_e2e_test` for the browser run. The live database and the client's running application were not touched.

## Summary

| Suite | Result |
|---|---|
| Backend pytest (`backend/tests`, 59 tests: SRS v1.0 UAT, DRE rename, legacy display, security hardening, evidence architecture) | **59 passed, 0 failed** |
| Frontend `tsc --noEmit` | pass |
| Frontend production build (`vite build`) | pass (481 kB JS, 139 kB gzip) |
| Browser workflow test (`scripts/e2e/ui_e2e.mjs`, Chrome 1440×900 / 820×1180 / 390×844, synthetic data) | **72 passed, 0 failed** (`browser_results.json`) |
| Migration rehearsal on a restored live copy | counts and RFI checksum unchanged; idempotent; see runbook |
| Dependency audit | npm: 0. Python: upgraded fastapi/starlette/python-multipart; remaining python-jose/ecdsa advisories assessed as not applicable (security assessment) |

## Not tested (and not claimed)
- Real phones or tablets (Android / iOS). Mobile layouts were tested with Chrome's emulated viewports only.
- Browsers other than Chrome.
- Screen readers / formal WCAG audit.
- Client user acceptance testing.
- Production hosting (HTTPS, SMTP).

## Phase 12 coverage

| Requirement | Test(s) |
|---|---|
| Cross-project access denial | `test_uat12…`, `test_submission_locks…` (other-project users 403), bundle test |
| Unauthorized attachment downloads | `test_submission_locks…`, `test_contractor_evidence_access_setting`, `test_management_remark_ownership…` (drafts private) |
| Unauthorized evidence uploads | `test_only_active_inspector…` (RE, contractor, other inspector, other project, outsider) |
| Out-of-turn uploads and submissions | `test_only_active_inspector…`; browser "Pending inspector sees Awaiting previous reviewer" |
| Management remark ownership | `test_management_remark_ownership_and_final_disposition` |
| Inspector review ownership | `test_only_active_inspector…`, `test_evidence_amendment…` |
| Submitted attachment locking | `test_submission_locks…`, `test_record_attachments_lock_on_submission`, remark tests |
| Duplicate upload prevention | `test_duplicate_upload_token…`, `test_concurrent_uploads_with_same_token_store_one`; browser "Retry stores the file once" |
| Concurrent submissions | `test_concurrent_double_submission_is_serialised`, concurrent upload test |
| Interrupted uploads | `test_interrupted_upload_leaves_nothing_and_retry_is_clean`; browser network-interruption check |
| Invalid and oversized files | `test_invalid_oversized_mismatched_and_empty_files_are_rejected`; browser ".exe rejected" |
| Controlled amendments | `test_evidence_amendment_supersedes_without_deleting`, existing amendment UAT |
| Completed DOC_03 snapshot preservation | `test_uat11…`, `test_completed_record_issued_snapshot_and_bundle` |
| Evidence bundle permissions | `test_completed_record_issued_snapshot_and_bundle` |
| DOC_02 hidden-field permissions | `test_hidden_fields_and_legacy_paths` |
| Historical data preservation | `test_legacy_records…`, `test_hidden_fields_and_legacy_paths`, migration rehearsal |
| Role-specific navigation | browser "… navigation follows s.12" ×5 |
| Desktop and mobile layouts | browser phone checks (no horizontal scroll, sticky actions, record cards) + 30 screenshots |
| Keyboard accessibility | browser skip link, keyboard sorting, Esc closes dialog, labelled controls |
| Camera permission denial | browser "Camera without permission falls back to file selection" |
| PDF and Excel generation | `test_uat10…`, `test_register_pdf_columns_and_saved_views`, browser exports |
| Existing SRS acceptance tests | `test_uat01…`–`test_uat12…` all pass |
| DB-level relationship integrity | `test_database_constraints_reject_invalid_evidence_relationships` |

## Backend tests (pytest -rA)
- tests/test_dre_rename.py::test_legacy_are_account_is_presented_and_authorised_as_dre
- tests/test_dre_rename.py::test_are_can_no_longer_be_assigned_and_is_not_offered
- tests/test_dre_rename.py::test_rename_script_dry_run_apply_idempotent
- tests/test_evidence.py::test_only_active_inspector_uploads_to_own_review
- tests/test_evidence.py::test_submission_locks_review_and_evidence
- tests/test_evidence.py::test_duplicate_upload_token_creates_one_record
- tests/test_evidence.py::test_invalid_oversized_mismatched_and_empty_files_are_rejected
- tests/test_evidence.py::test_interrupted_upload_leaves_nothing_and_retry_is_clean
- tests/test_evidence.py::test_concurrent_uploads_with_same_token_store_one
- tests/test_evidence.py::test_management_remark_ownership_and_final_disposition
- tests/test_evidence.py::test_doc01_review_assignment_and_return_remarks
- tests/test_evidence.py::test_evidence_amendment_supersedes_without_deleting
- tests/test_evidence.py::test_completed_record_issued_snapshot_and_bundle
- tests/test_evidence.py::test_contractor_evidence_access_setting
- tests/test_evidence.py::test_timeline_shows_sequence_and_locks_decision
- tests/test_evidence.py::test_hidden_fields_and_legacy_paths
- tests/test_evidence.py::test_register_pdf_columns_and_saved_views
- tests/test_evidence.py::test_admin_overview_memberships_and_access_matrix
- tests/test_evidence.py::test_record_attachments_lock_on_submission
- tests/test_evidence.py::test_database_constraints_reject_invalid_evidence_relationships
- tests/test_legacy_display.py::test_legacy_detail_does_not_show_importer_as_submitter_or_copied_request_date
- tests/test_legacy_display.py::test_portal_rfi_keeps_real_request_date_and_submitter
- tests/test_legacy_display.py::test_register_export_blanks_copied_request_date_and_filter_ignores_import_account
- tests/test_security.py::test_browser_login_uses_httponly_strict_cookie_and_no_token_in_body
- tests/test_security.py::test_cookie_session_requires_csrf_header_for_writes
- tests/test_security.py::test_logout_clears_the_session
- tests/test_security.py::test_account_lockout_after_repeated_failures
- tests/test_security.py::test_unknown_email_is_throttled_like_a_real_one
- tests/test_security.py::test_per_ip_ceiling
- tests/test_security.py::test_password_change_ends_other_sessions
- tests/test_security.py::test_deactivated_user_is_rejected_immediately
- tests/test_security.py::test_temporary_password_must_be_changed_before_use
- tests/test_security.py::test_forgot_password_is_throttled_without_revealing_accounts
- tests/test_security.py::test_production_refuses_weak_jwt_secret
- tests/test_security.py::test_api_responses_are_not_cacheable
- tests/test_security.py::test_successful_sign_ins_from_a_shared_office_ip_are_not_limited
- tests/test_timezone.py::test_site_now_is_addis_ababa_wall_clock
- tests/test_timezone.py::test_short_notice_uses_site_time
- tests/test_uat.py::test_uat01_admin_creates_project_and_assigns_project_roles
- tests/test_uat.py::test_role_must_be_valid_and_admin_has_no_project_role
- tests/test_uat.py::test_uat02_contractor_submits_doc01_with_multiple_rfis
- tests/test_uat.py::test_doc01_validation_and_duplicates
- tests/test_uat.py::test_short_notice_flag_and_override_policy
- tests/test_uat.py::test_only_contractor_members_create_doc01
- tests/test_uat.py::test_uat03_management_receives_submission_project_scoped
- tests/test_uat.py::test_uat04_to_07_sequential_review
- tests/test_uat.py::test_assignment_validation_and_change_control
- tests/test_uat.py::test_concurrent_double_submission_is_serialised
- tests/test_uat.py::test_uat08_09_decisions_update_register_without_duplicates
- tests/test_uat.py::test_partial_approval_requires_section_and_configurable_dispositions
- tests/test_uat.py::test_uat10_office_exports_filtered_register
- tests/test_uat.py::test_uat11_completed_doc03_pdf_matches_issued_record
- tests/test_uat.py::test_uat12_unauthorised_project_and_field_access_denied
- tests/test_uat.py::test_legacy_records_are_read_only_and_keep_not_ready
- tests/test_uat.py::test_draft_editing_and_audit_is_transactional
- tests/test_uat.py::test_returned_batch_and_overdue
- tests/test_uat.py::test_role_dashboards
- tests/test_uat.py::test_daily_progress_and_reference_data_scoped
- tests/test_uat.py::test_audit_access

## Browser checks
- PASS Admin navigation follows s.12
- PASS Admin KPIs come from the database
- PASS Pending invitations are not fabricated
- PASS Header shows category and role
- PASS Access matrix export downloads
- PASS Memberships page lists roles
- PASS Roles page loads
- PASS Configuration shows attachment policy
- PASS Admin /users renders
- PASS Admin /projects renders
- PASS Admin /audit renders
- PASS Admin /master-data renders
- PASS Admin /reports renders
- PASS Admin /daily-progress renders
- PASS Admin /notifications renders
- PASS Admin pages have no script errors
- PASS RE/DRE navigation follows s.12
- PASS Management dashboard KPIs and batch table
- PASS 24-hour notice legend shown
- PASS DOC_01 review remark recorded with evidence
- PASS Assignment confirmation lists sequence and evidence
- PASS Assignment saved
- PASS Timeline shows received, assignment, active and pending inspectors, locked decision
- PASS Completed stage shows evidence to RE
- PASS Partial approval requires the executed section
- PASS Disposition confirmation shows disposition, remarks, evidence, decision-maker and sections
- PASS Escape closes the confirmation
- PASS Recording the disposition opens the completed DOC_03
- PASS RE pages have no script errors
- PASS Inspector navigation follows s.12
- PASS Active turn badge
- PASS Draft comment saved
- PASS Camera without permission falls back to file selection; upload works
- PASS Camera fallback hint shown
- PASS Unsupported file rejected with explanation; comment kept
- PASS Network interruption shows failure and keeps the comment
- PASS Submit disabled? (no upload running after failure)
- PASS Retry stores the file once
- PASS Review confirmation shows RFI, role, sequence, comment, attachments, name, sign-off
- PASS Submitted review becomes read-only
- PASS Attachments menu lists own evidence as locked
- PASS Inspector pages have no script errors
- PASS Pending inspector sees "Awaiting previous reviewer" and no upload controls
- PASS Next inspector (mobile) has camera / gallery / files controls
- PASS Mobile Save draft / Submit review bar is sticky
- PASS Mobile review page has no horizontal scroll
- PASS Office navigation follows s.12
- PASS Office lands on DOC_02 register
- PASS Advanced toggle shows hidden workbook fields I:M and S
- PASS Legacy drive paths are not shown
- PASS Saved view created
- PASS Register Excel export
- PASS Register PDF export (visible columns)
- PASS Completed DOC_03 shows sections, disposition and attachment index
- PASS Evidence bundle downloads
- PASS Issued DOC_03 PDF downloads
- PASS Office record is read-only (no edit controls)
- PASS Search finds RFI
- PASS Office pages have no script errors
- PASS Phone register uses record cards
- PASS Phone register has no horizontal scroll
- PASS Contractor navigation follows s.12
- PASS New DOC_01 shows project and contract
- PASS DOC_01 confirmation shows project, batch, row count and inspection times
- PASS DOC_01 submitted and locked
- PASS Contractor RFI view has no inspector-evidence download panel
- PASS Contractor pages have no script errors
- PASS Phone DOC_01 has no horizontal scroll
- PASS First Tab reaches the skip link
- PASS Skip link moves to main content
- PASS Register columns sort by keyboard
- PASS Register form controls are labelled

## Screenshots
Located in `docs/ui-upgrade/screenshots/`; synthetic data only: desktop_*, tablet_*, phone_*.
