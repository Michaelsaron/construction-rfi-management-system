# Delivery Notes

This build includes the agreed code-side workflow and the production/demo deployment structure.

## Client-specific external items still supplied at deployment time
These are not code defects and cannot be embedded safely without the client's credentials/assets:
- Client-controlled real Admin email
- Employee work email addresses
- SMTP password/server
- Domain name
- TLS certificate
- VPS/server credentials
- Off-server backup destination
- Exact official logo/form artwork
- UAT approval

The application is designed so those values are configuration, not hard-coded code changes.
