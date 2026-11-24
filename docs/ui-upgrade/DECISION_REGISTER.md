# Client decision register — UI design v1 upgrade

These items are **not decided by the developer**. Each has a conservative interim behaviour, and wherever possible it is a per-project setting, so a decision changes configuration rather than code or historical data. The earlier register (`docs/srs/04_DECISION_REGISTER.md`, OD-xx / DR-xx) still applies.

| ID | Question for the client | Interim behaviour in 6.0.0-ui | Where it lives | Status |
|---|---|---|---|---|
| UD-01 | **SRS v2.0**: the UI design is "based on Revised SRS v2.0", which has not been supplied. Please provide it. | Built against SRS v1.0 and the design document only. No claim of SRS v2.0 compliance. After review, a gap analysis against v2.0 is needed. | — | **Open** |
| UD-02 | **RE/ARE vs RE/DRE**: pages 8, 12 and 14 of the design say "RE/ARE". | "RE/DRE" everywhere, per DR-02 (client decision, Nov 2026). Please confirm the design should be corrected. | Fixed in code | Confirm |
| UD-03 | **Joint or independent final endorsement**: must the RE and the DRE both endorse a disposition, or does either decide alone? | Either RE or DRE records the decision alone. The decision-maker's name and designation are stored. No second endorsement step. | `rfis.decide` | **Open** |
| UD-04 | **Final disposition authority and contractor visibility**: who may decide (RE only? DRE?), and may contractors open inspector / management evidence? | RE and DRE may decide; Admin may not (DR-01). Contractors see the record and the DOC_03, but **not** evidence files. | Setting `contractor_evidence_access` (default false); setting `contractor_visibility` (default PROJECT) | **Open** |
| UD-05 | **Inspector DOC_02 access**: read the whole register, or only assigned RFIs? Export? | Register read-only for all inspectors, no export. Evidence only for RFIs where they hold or held a turn. | Settings `inspector_register_access` (true), `inspector_export` (false) | **Open** |
| UD-06 | **Hidden workbook fields I:M and S**: which roles may see them? | Visible to categories 1, 2.1 and 2.3; blank for 2.2 and 3 in the register and exports. | Setting `hidden_field_categories` | **Open** |
| UD-07 | **Attachment file types, size and count limits** | Release-5 list (PDF, JPG/JPEG, PNG, XLS/XLSX, DOC/DOCX, DWG, DXF, DGN); 50 MB per file; 20 files per remark / review. | Setting `attachment_policy` | **Open** |
| UD-08 | **Attachment retention**: how long to keep files and removed drafts? | Keep everything. Nothing is purged automatically; removed drafts stay in storage marked as removed. | `attachment_policy.retention = KEEP_ALL` | **Open** |
| UD-09 | **Malware scanning**: required? which scanner? | Disabled. The ClamAV integration is ready (`SCAN_IF_AVAILABLE` / `REQUIRED` with `CLAMD_HOST`). | `attachment_policy.scanning` | **Open** |
| UD-10 | **Branding and official logos**: employer / consultant / contractor logos for screens and PDFs | Text-only "RFIMS" wordmark. PDFs carry the party names from project configuration; no logos. | — | **Open** (logo files needed) |
| UD-11 | **Legacy document migration**: should the historical shared-drive documents (File_Path, IPC paths: 316 / 314 rows in the live register) be migrated? | Shown as "File unavailable — migration required". Paths are never displayed or returned by the API. | — | **Open** |
| UD-12 | **Invitation workflow**: should accounts be created by invitation (e-mail link, expiry, acceptance)? | Not implemented. The admin creates accounts with a temporary password that must be changed. The dashboard shows "Not enabled" instead of a count. | — | **Open** |
| UD-13 | **IPC reference rules**: how "RFI included under IPC" should be recorded and reported | Historical value shown read-only; no IPC workflow (as in SRS v1.0). | — | **Open** |
| UD-14 | **DOC_01-only fields in DOC_02 exports** (requested date/time, material offset, BOQ, short notice…): keep in the linked record only, or add to the export? | Exported as extra "system" columns after the workbook columns. Workbook columns A:AF keep their order and meaning. | `services/documents.REGISTER_COLUMNS` | **Open** |
| UD-15 | **Signature policy**: are typed-name electronic acknowledgements with server time acceptable, or is a certified digital signature required? | Typed name plus authenticated account plus server time. No signature images, and no claim of certified signatures. | — | **Open** |

## Other confirmations needed (from the design's s.17.2)
- Default DOC_02 visible columns. The design's own table was used: RFI No., Road type, Description, Requested From/To, Inspection, RFI status, Workflow, IPC, Document.
- Exact project/contract header content for screens. Currently project name | contract number.
