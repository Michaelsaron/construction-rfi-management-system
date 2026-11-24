# Production-readiness checklist — release 6.0.0-ui (24 Nov 2026)

**Overall:** ready for the owner-approved migration and client UAT. **Not ready for unrestricted production** until the items marked ✖ are closed.

| # | Item | Status |
|---|---|---|
| 1 | Backend tests (59) pass on the isolated test database | ✔ |
| 2 | Frontend type check and production build | ✔ |
| 3 | Browser workflow test, all five categories, desktop / tablet / phone, synthetic data | ✔ 72/72 |
| 4 | Migration rehearsed on a restored live copy; counts and checksum unchanged; idempotent; previous release still runs on the new schema | ✔ |
| 5 | Fresh verified backup immediately before the live migration | ◻ at migration time |
| 6 | Owner approval to migrate the live database and restart the client's application | ✖ **awaiting** |
| 7 | Client decisions UD-01…UD-15 (SRS v2.0, endorsement, visibility, attachment policy, scanning, retention, invitations, branding, legacy documents) | ✖ open; conservative defaults active |
| 8 | Client user acceptance testing with real users | ✖ |
| 9 | Real Android / iOS device testing (camera, upload on mobile networks) | ✖ (only desktop Chrome with emulated viewports was used) |
| 10 | Browsers other than Chrome (Firefox, Safari, Edge) | ✖ |
| 11 | Formal accessibility audit (WCAG 2.1 AA) and screen-reader test | ✖ (basic keyboard, label and focus checks only) |
| 12 | HTTPS on a permanent host (VPS + TLS + HSTS); no Mac-hosted tunnel | ✖ |
| 13 | SMTP configured for notifications and password reset | ✖ (OD-09) |
| 14 | Scheduled encrypted backups with off-site copy and restore drill (cron) | ◐ scripts ready; schedule not installed |
| 15 | Malware scanning (ClamAV) if the client requires it | ◐ integration ready; disabled (UD-09) |
| 16 | Dependency audit: npm clean; Python upgraded; python-jose advisory not applicable (HS256 pinned); PyJWT migration recommended | ✔ / ◐ |
| 17 | Independent penetration test | ✖ recommended |
| 18 | Expo mobile app | ◻ future (API contracts ready in `docs/api/`) |
