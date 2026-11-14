# Client Decision Register

Each item lists: **SRS** (what the SRS says) · **Docs** (what DOC_01/02/03 show) · **Now** (what the application currently does) · **Recommendation** · **Confirm?** · **Impact**.
The recommended options are written so that implementation can start safely: each one is either the most restrictive choice or a configurable setting, so a later client answer changes configuration, not the schema.

---

## A. SRS open decisions

### OD-01 — RFI number uniqueness scope
- **SRS:** provisionally unique per project.
- **Docs:** DOC_01/DOC_03 use prefix series per work category with the year (`Fill-401/2026`, `EX-257/2026`, `CC-513/2026`, `SUB-265/2026`, `AS-014/2026`). The DOC_02 history uses plain integers 1…2470 with 3 duplicates.
- **Now:** unique on (project, rfi_number, revision_no).
- **Recommendation:** unique **per project** (case- and whitespace-insensitive comparison) with revisions for resubmission. Optionally validate a project-configurable prefix pattern (`^[A-Z]+-\d+/\d{4}$`) as a warning, not a block.
- **Confirm:** yes. **Impact:** low; matches the current constraint.

### OD-02 — Assignment per RFI or per batch
- **SRS:** assumes per RFI. **Docs:** DOC_03 is per RFI with per-RFI inspector rows. **Now:** per RFI.
- **Recommendation:** per RFI, with a **"apply this sequence to selected RFIs"** shortcut on the batch screen.
- **Confirm:** yes (low risk). **Impact:** UI only.

### OD-03 — Contractor visibility
- **SRS:** "own submissions only, or all project RFIs". **Now:** sees all RFIs in all projects (defect S-1).
- **Recommendation:** default **all RFIs of projects they are a member of** (DOC_01 is a shared site document), with a per-project setting `contractor_visibility = PROJECT | OWN`.
- **Confirm:** yes. **Impact:** a query filter only.

### OD-04 — Inspector read access to DOC_02
- **SRS:** not specified. **Now:** everyone can read everything.
- **Recommendation:** **read-only access to their projects' register** (inspectors need history to judge layers and chainages), with no export by default. Configurable.
- **Confirm:** yes. **Impact:** permission matrix only.

### OD-05 — RE/DRE independent or joint approval
- **SRS:** asks. **Docs:** DOC_03 has a single "RE/ARE Sign / Date" block, which implies one signatory. **Now:** any RE/ARE/RE_ARE (or Admin) alone.
- **Recommendation:** **either RE or DRE independently**, recorded by name. Joint endorsement can be added later as a project setting.
- **Confirm:** yes. **Impact:** low.

### OD-06 — Decision / disposition values
- **SRS:** Approved/Rejected (+ asks about Returned, On Progress, Information Only).
- **Docs:** DOC_03 has six dispositions. History has 16 spellings mapping to them (workbook analysis §3).
- **Now:** APPROVED / REJECTED / ON_PROGRESS / INFORMATION_ONLY.
- **Recommendation:** two fields per decision.
  - `disposition_code` — the six DOC_03 boxes: `INFORMATION_ONLY`, `ACTIVITY_ON_PROGRESS`, `APPROVED_FURTHER_WORKS`, `APPROVED_COMPLY_COMMENTS`, `APPROVED_PARTIAL_RESUBMIT_REMAINDER` (requires the approved section), `NOT_APPROVED_RESUBMIT`.
  - `decision` (canonical outcome for reporting): `APPROVED` (further works, comply comments), `PARTIALLY_APPROVED` (partial), `REJECTED` (not approved), `NO_APPROVAL_REQUIRED` (information only), `ON_PROGRESS` (activity on progress).
  - The existing four values remain valid for historical rows.
- **Legacy mapping proposal** (raw text always kept in `legacy_rfi_status`): Accepted/Approved → APPROVED (disposition unknown); Accepted as Noted → APPROVED_COMPLY_COMMENTS; Information* → INFORMATION_ONLY; Rejected / Not Approved → NOT_APPROVED_RESUBMIT; **Not Ready / Note ready → needs client answer** (Activity on progress? Not approved?); blank → no decision.
- **Confirm:** **yes — blocking for the decision screen.** **Impact:** medium (new columns, PDF checkboxes, reports).

### OD-07 — Resubmission and cycles
- **SRS:** asks. **Docs:** DOC_03 says "Not Approved: RFI to be resubmitted" and "resubmitted for the remaining section". **Now:** same RFI No., `revision_no + 1`, `parent_rfi_id`.
- **Recommendation:** keep the revision model. Allow resubmission after `NOT_APPROVED_RESUBMIT` **and** `APPROVED_PARTIAL_RESUBMIT_REMAINDER`, by the original batch's contractor team only. The register shows all revisions, with a "latest only" filter.
- **Confirm:** yes. **Impact:** low.

### OD-08 — DOC_03 comment fields: fixed or dynamic
- **SRS:** asks. **Docs:** DOC_03 has **7 fixed role rows** (WI, SI, Surveyor, Senior Surveyor, MI, Soil Lab Tech, ME). **Now:** dynamic assignments.
- **Recommendation:** store dynamically (one assignment per inspector with a sequence) and **print in the 7 fixed DOC_03 rows**. This satisfies both.
- **Confirm:** yes (evidence strongly supports it). **Impact:** PDF layout only.

### OD-09 — Notification channels
- **SRS:** in-app minimum. **Now:** in-app + email when SMTP is configured (it fires on every notification).
- **Recommendation:** in-app always; email opt-in per project; SMS/push deferred to the Expo app.
- **Confirm:** yes. **Impact:** config.

### OD-10 — Attachments
- **SRS:** optional. **Docs:** DOC_03 "Enclosures / Check Lists — Sheets". **Now:** implemented for RFI, summary and daily progress.
- **Recommendation:** keep enabled; record the enclosure sheet count on DOC_03; a project-configurable type/size list.
- **Confirm:** yes. **Impact:** low.

### OD-11 — 24-hour rule
- **SRS:** flag, or require an override. **Docs:** DOC_03 note 4 says "RFI to be submitted … a minimum of 24 hrs in advance from the date of inspection". Note 5 says "returned … within 24 hr's of Request".
- **Now:** nothing.
- **Recommendation:** **flag only** by default (`short_notice = true`, a visible badge, included in the RE/DRE notification), with a project setting `notice_policy = FLAG | REQUIRE_OVERRIDE`. Also use note 5 for overdue: an RFI not decided within 24 h of inspection is flagged overdue.
- **Confirm:** yes. **Impact:** low.

### OD-12 — DOC_02 columns and order
- **SRS:** confirm the headings. **Docs:** the workbook `RFI` sheet has 32 columns (header row 8).
- **Recommendation:** register and Excel export = the 32 workbook columns in workbook order, then system columns (field mapping §4). Unnamed helper columns are exported as "Legacy File Path" / "Legacy IPC Path".
- **Confirm:** yes. **Impact:** export layout.

### OD-13 — Templates, logos, signatures, checkboxes
- **SRS:** provide them. **Docs:** DOC_01 and DOC_03 samples supplied (photos, [client project B]).
- **Recommendation:** reproduce the **structure and wording** in generated PDFs. Logos are uploaded per project (no third-party logos are bundled in the code). Signatures appear as **typed name + timestamp + "electronically submitted via RFIMS"**, never as images unless an authorised scanned signature is uploaded by its owner. Stamps are never generated.
- **Confirm:** yes. Ask for the original editable templates (Word/Excel) for exact fidelity. **Impact:** PDF work.

### OD-14 — Hosting and language
- **SRS:** asks. **Now:** Docker on the user's Mac with a Cloudflare quick tunnel for demos; a prod compose file for a VPS.
- **Recommendation:** an Ubuntu VPS (or the client's server) with a domain + TLS. English UI first; strings structured for an Amharic translation later.
- **Confirm:** yes. **Impact:** deployment only.

## B. Additional conflicts and decisions found during the audit

| ID | Topic | Evidence | Recommendation | Blocking? |
|---|---|---|---|---|
| **DR-01 / C-1** | **Admin authority.** The SRS §7 table gives Admin "Full access" to inspector comments and the final decision, while §7.1 / BR-07 say *only RE/DRE* may decide. The current code lets Admin decide and submit reviews for others. | SRS p.7 vs p.7/11 | Admin = configuration and oversight (read everything, manage users/projects/assignments). **No official review or decision authority** unless the client explicitly confirms otherwise. | Yes |
| **DR-02 / C-2** | **RE/ARE vs RE/DRE.** The SRS says DRE; the client's own DOC_03 says "RE/ARE" and distributes copies to "ARE". The current system and data use ARE (and RE_ARE). | DOC_03 footer | Treat DRE and ARE as **the same Category 2.1 deputy role**, with a display label configurable per project ("DRE" or "ARE"). Do **not** rename existing users automatically; Admin confirms each mapping. `RE_ARE` stays as a legacy combined code with the same rights as RE. | Yes (label + mapping) |
| DR-03 | Existing role codes with no SRS equivalent: `SITE_ENGINEER`, `CONTRACTOR`, `PROJECT_MANAGER`, `VIEWER` | `users.ROLES` | `CONTRACTOR`/`SITE_ENGINEER` → Category 3 (proposed `OFFICE_ENGINEER`); `PROJECT_MANAGER`/`VIEWER` → read-only Category 2.3-like access. Per-user confirmation, no automatic privilege gain. | No |
| DR-04 | Decision override (skip pending reviews) | `rfis.decide` | Remove from the normal flow. If kept, RE only, with a mandatory reason, audited, and shown on the DOC_03 PDF. | Yes |
| DR-05 | "Activate/Accept" step before assignment (not in the SRS) | `rfis.activate` | Merge into assignment: saving the first sequence = "Received + Assigned". Keep "Return batch to contractor" before assignment. | No |
| DR-06 | Reviewer recommendation codes (SATISFACTORY …) are not on DOC_03 | `MyInspections.tsx` | Keep as an *optional* structured field next to the mandatory comment; not printed unless confirmed. | No |
| DR-07 | Who records "Received by" on DOC_01/DOC_03 | DOC_01/03 | Office (Secretary) or RE/DRE acknowledgement; auto-filled on assignment if nobody acknowledged. | No |
| DR-08 | Work_Status (DOC_02 col 19) has no DOC_03 field | Workbook | Editable by RE/DRE at decision (optional). | No |
| DR-09 | Application Rate / Quantities (cols 23–25) | Workbook, empty | Optional fields editable by RE/DRE or QS after decision. | No |
| DR-10 | `description` mandatory today; DOC_01 has free text only | `rfis.create` | Make it optional; `contractor_request` (works description) becomes mandatory. | No |
| DR-11 | Can a contractor edit the batch after submission? | Brief §3 | Locked after submit. Corrections go through **Return to contractor** (before assignment) or **controlled amendment** (after: request → RE/DRE approves → old/new stored). | No |
| DR-12 | DEMO project + default admin seeded in prod | `main.startup` | Seed only when `ENVIRONMENT != production`; production requires `ADMIN_PASSWORD` to be set. | No |
| DR-13 | Overdue timer basis | form note 5 | Inspector overdue = 24 h after their turn activates; decision overdue = 24 h after the last review. Configurable. | No |
| DR-14 | Inspection Time format | Workbook | Store a parsed TIME where unambiguous; keep the raw text for legacy rows. | No |
| **DR-15** | **Project ownership of the 2,465 historical RFIs.** Info sheet = project A; the data content suggests a different project (workbook analysis §4). | Workbook | Leave in place; ask the client. If confirmed different: create the correct project and move records with an audited, reversible script. | Yes (for data labelling) |
| **DR-16** | **4 skipped duplicate rows** (RFI 34 ×2, 79 ×1, 154 ×1) are missing from the DB. | Workbook §5 | Import them as flagged legacy revisions after confirmation. | No |
| DR-17 | `Not Ready` legacy meaning (461 rows) | Workbook §3 | Client to choose: Activity on progress, or Not approved. | Yes for legacy reports |
| DR-18 | Legal status of electronic acknowledgement | Brief §12 | Document as "system audit evidence, not a certified digital signature". | No |
