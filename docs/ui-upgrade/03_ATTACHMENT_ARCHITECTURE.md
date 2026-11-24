# Attachment architecture

## Permission paths

| Path | Who | Attaches to | Entry points | Locked when |
|---|---|---|---|---|
| **MANAGEMENT_REMARK** (Category 2.1) | RE / DRE of the project; only the author of the remark | Their own `management_remarks` row | DOC_01 review (batch or RFI), inspector assignment, sequence change, controlled return, final disposition | The workflow action records the remark: assignment saved, sequence changed, batch returned, disposition recorded. A DOC_01 review remark can also be recorded on its own. |
| **INSPECTOR_REVIEW** (Category 2.2) | The assigned inspector, only while their turn is ACTIVE and the RFI is under review | Their own `reviewer_assignments` row (the DOC_03 field) | Inspector review screen (desktop / mobile) | The review is submitted; the files get `review_id` and `locked_at` |
| **RECORD** | Contractor (DOC_01 enclosures, batch files), Daily Progress users | RFI / DOC_01 batch / Daily Progress record | Existing pages | DOC_01 submission (later enclosures are locked as they are added) |

- Management and inspectors **can no longer** use the generic `/attachments/rfi/...` path for evidence; it returns 403 and names the correct path.
- Files stored before release 6 stay as **RECORD** evidence. Their uploader is kept as recorded; they are never attributed to an inspector or a remark. (The live database has none today.)

## Rules enforced by the server

1. **Ownership.** Only the uploader may remove a file, only before it is locked. Only the remark author may edit, discard or add files to a draft remark. A remark draft can be used only by its author's own action. For example, a DRE cannot record a decision with the RE's draft; this returns 403.
2. **Turn.** Pending inspectors get 409 ("not your turn"), replaced inspectors 403, completed reviews 409 (locked). The same applies to draft comments and to submissions.
3. **Visibility.** Drafts are visible only to their author. Submitted evidence is visible to:
   - Admin, RE/DRE and Office;
   - inspectors who hold or held a turn on that RFI (not a replaced inspector, and register read access alone is not enough);
   - contractors only if `contractor_evidence_access` is enabled (default off, UD-04).

   One function, `services/evidence.can_view_attachment`, decides this for lists, metadata, preview, download and bundles.
4. **Consistency checks.** Review submission and final disposition can carry the number of files the user saw in the confirmation dialog (`attachment_count`, `evidence_count`). If the server holds a different number, for example because an upload was still running, the action is refused with 409 and nothing is locked.
5. **Database constraints.** Composite foreign keys tie remark files to the remark's project and review files to the review's RFI, and a CHECK constraint ties each kind to exactly one owner (see `02_SCHEMA_AND_ERD.md`).

## Storage and download

- Files are streamed to `UPLOAD_DIR/evidence/p<project>/<random>.<ext>` through a `.part` file, renamed only after every check passes. A failed or interrupted upload leaves nothing behind (tested).
- The checks are:
  - extension allowed by project policy;
  - size limit, enforced while streaming (`min(policy, MAX_UPLOAD_MB)`);
  - per-record file-count limit;
  - empty-file rejection;
  - content signature for PDF, JPEG, PNG, WebP, Office (OLE/ZIP) and DWG — a `.pdf` that isn't a PDF is refused with 422;
  - optional ClamAV scan.
- The SHA-256 is computed while streaming and stored. Every download and bundle re-verifies it. A mismatch is refused (409) and audited as `INTEGRITY_FAILURE`.
- The storage name never leaves the server; responses use `services/evidence.out()`. Downloads go through `GET /evidence/files/{id}/download` and are audited. Preview (`?inline=1`) is allowed only for PDF and images, served with `Content-Security-Policy: sandbox` and `nosniff`. The web app opens previews from a local blob, so no storage URL is ever shown.
- Content type is derived from the extension, not from what the client claims.

## Idempotent uploads

The client sends an `upload_token` (UUID) per selected file and reuses it on retry. `UNIQUE(uploaded_by, upload_token)` guarantees one row. A repeated token returns the stored file with `duplicate: true`. If two parallel requests race, the loser's file is discarded and the winner's row returned (tested with 4 parallel requests). Reusing a token for a different record is refused (409).

## Versions and corrections (controlled amendment)

A locked review or remark is corrected through an **evidence amendment** (`rfi_amendments.amendment_type = REVIEW | REMARK`):
1. The author (or RE/DRE) creates a draft with a reason and, optionally, corrected text.
2. They upload correction files. These are `PENDING_APPROVAL`, optionally `supersedes_id` an existing file, with `version_no = old + 1`.
3. They send the amendment for approval, which locks its files.
4. RE/DRE approves or rejects. On approval, the new files become current and locked; superseded files get `superseded_at` but are **never deleted** and stay downloadable for history. Corrected text replaces the current text; the original is kept in the amendment and the audit log. On rejection, the files are marked `REJECTED`.

Corrections are refused once the DOC_03 has been issued. Issued records change only through a new RFI revision.

## Policy (per project, pending client decisions)

`attachment_policy` in project settings, edited on the Configuration page:

| Key | Default | Decision |
|---|---|---|
| allowed_extensions | PDF, JPG/JPEG, PNG, XLS/XLSX, DOC/DOCX, DWG, DXF, DGN (release 5 list) | UD-07 |
| max_file_mb | 50 (never above `MAX_UPLOAD_MB`) | UD-07 |
| max_files_per_record | 20 | UD-07 |
| retention | `KEEP_ALL`, the only value implemented: nothing is purged | UD-08 |
| scanning | `DISABLED`; `SCAN_IF_AVAILABLE` / `REQUIRED` use ClamAV at `CLAMD_HOST:CLAMD_PORT` | UD-09 |

## Completed DOC_03 and evidence bundle

- `GET /rfis/{id}/completed-record` returns sections, management remarks, attachment index (author, stage, time, SHA-256), issued-document hash and the legacy-document status.
- The DOC_03 PDF issued at the final decision is stored with its SHA-256 and **served unchanged**; it is never regenerated. PDFs issued from release 6 onwards append the management remarks and the attachment index. PDFs issued earlier are not touched.
- `GET /rfis/{id}/evidence-bundle.zip` (completed RFIs) contains:
  - the issued PDF, checked against its stored hash;
  - every original file the requester may open, checked again per file and integrity-verified;
  - `manifest.json` and `manifest.csv` (author, role, stage, UTC time, size, SHA-256, version);
  - a README.

  Missing or tampered files are left out and listed under `excluded`. If no issued snapshot exists, nothing is regenerated and the manifest says so.
