# API contracts for the web app and the future Expo mobile app

Both clients use **the same FastAPI backend, MySQL database, accounts, permissions and workflow**. There is no second database and no separate approval flow. The full machine-readable schema is in [`openapi.json`](openapi.json) (91 paths, exported from release 6.0.0-ui). TypeScript payload types shared by both clients are in [`frontend/src/lib/contracts.ts`](../../frontend/src/lib/contracts.ts).

## Authentication
- **Web (browser):** `POST /auth/login` sets an HttpOnly session cookie plus a CSRF cookie. Every unsafe request sends `X-CSRF-Token`.
- **Mobile / API clients:** `POST /auth/login` with header `X-Auth-Mode: bearer` returns `access_token`. Send `Authorization: Bearer <token>`. Store it in the platform's secure storage (Expo SecureStore), never in plain storage.
- `GET /me` returns the user, their memberships, the role and category for each project, and whether a password change is required.

## Core flows used by the mobile app (inspector first)

| Step | Endpoint |
|---|---|
| My turns | `GET /rfis/my-inspections` (assignment status ACTIVE / PENDING / COMPLETED, `waiting_for`) |
| RFI context | `GET /rfis/{id}` (DOC_01 data, assignments, permissions incl. `review_assignment_id`) |
| Review workspace | `GET /evidence/assignments/{aid}` (draft, files, `can_edit`, upload `policy`) |
| Save draft | `PUT /evidence/assignments/{aid}/draft` `{comment}` |
| Upload evidence | `POST /evidence/assignments/{aid}/files` multipart `file`, `upload_token` (UUID per file; **reuse on retry**) |
| Remove before submit | `DELETE /evidence/files/{fid}` |
| Submit | `POST /rfis/{id}/review` `{assignment_id, comment, attachment_count}`; 409 if the count differs from the server |
| Download / preview | `GET /evidence/files/{fid}/download[?inline=1]` |
| Correction | `POST /evidence/amendments` → `POST /evidence/amendments/{aid}/files` → `POST /evidence/amendments/{aid}/send` |

Management, office and contractor flows: `/rfi-summaries`, `/rfis/{id}/assignments`, `/evidence/remarks*`, `/rfis/{id}/decision`, `/rfis/{id}/timeline`, `/rfis/{id}/completed-record`, `/rfis/{id}/evidence-bundle.zip`, `/rfis` (register), `/reports/*`.

## Error model
FastAPI JSON: `{"detail": "<readable message>"}`. Status codes:
- 400 invalid input;
- 401 not signed in;
- 403 role, project or ownership;
- 404 not found;
- 409 state or turn conflict, locked record, count mismatch, token reuse, integrity failure;
- 413 too large;
- 422 content does not match type, or the scanner rejected the file;
- 429 throttled;
- 503 scanner unavailable when scanning is required.

Clients show `detail` as-is. It is written for end users.

## Offline and interrupted uploads
Interrupted uploads are recovered by retrying with the same `upload_token`; the server returns the stored file (`duplicate: true`) instead of creating a second one. This is **not** full offline operation. Creating DOC_01 records offline uses the existing `client_request_id` idempotency, and inspector reviews are submitted online.

## Expo rollout (after the web release is verified)
1. An Expo app using the endpoints above, with bearer authentication and SecureStore.
2. EAS Build for Android / iOS; EAS Update for JavaScript-only fixes.
3. The same role rules apply automatically, because every check is on the server.
