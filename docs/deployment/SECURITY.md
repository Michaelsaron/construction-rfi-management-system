# Security configuration

## Secrets (.env, never committed)
Rotate every value copied from `.env.example` before production:
- `JWT_SECRET`: random, at least 32 characters. Production refuses to start otherwise.
- `MYSQL_PASSWORD`, `MYSQL_ROOT_PASSWORD`, `DATABASE_URL`.
- `ADMIN_PASSWORD`: used only to create the first admin, who must change it at first sign-in.

At startup the backend prints `[SECURITY-WARNING]` naming any example value still in use.

## Sessions and sign-in
- HttpOnly, SameSite=Strict session cookie; `Secure` in production (`COOKIE_SECURE` overrides it).
- CSRF header required for cookie writes.
- Sign-in throttling: `LOGIN_MAX_FAILURES`, `LOGIN_LOCKOUT_MINUTES` and `LOGIN_IP_MAX_ATTEMPTS` per window. Counters live in memory, so run one backend worker, or move the counters to Redis before scaling.
- Set `TRUST_PROXY_HEADERS=true` only when the backend is reachable solely through the bundled nginx.

## Uploads
- `MAX_UPLOAD_MB` is the server ceiling. Project attachment policies can only lower it.
- Malware scanning: run a ClamAV daemon, set `CLAMD_HOST` / `CLAMD_PORT`, then select *Scan when available* or *Required* on the project's Configuration page.
- `UPLOAD_DIR` must not be served by the web server. Files are downloaded only through the API, which checks access and integrity.

## Transport
Production needs HTTPS (TLS certificate on the VPS or a managed proxy) and HSTS at the proxy. The Cloudflare quick tunnel is for demonstrations only.

See `docs/ui-upgrade/05_SECURITY_ASSESSMENT.md` for the current assessment and residual risks.
