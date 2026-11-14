# DOC_01 → DOC_02 → DOC_03 Field Mapping

**Status:** proposed mapping for client sign-off (resolves OD-12 and OD-13 once confirmed).
Sources: SRS v1.0; DOC_01 sample (*Daily Request For Inspection Summary Sheet*, [client project B]); DOC_03 sample (*Request For Work Inspection/Approval*, same project); DOC_02 workbook `RFI` sheet (client template, historical data).
Project-specific values on the samples (names, logos, contract titles) are **configuration**, not code.

Legend: **E** = existing column in `rfis` · **N** = new column needed · **R** = related table · **C** = computed · **P** = project configuration

---

## 1. Document header blocks → Project configuration

| Form field | DOC_01 | DOC_03 | Workbook | Target |
|---|---|---|---|---|
| Employer name | ✔ "[employer]" | ✔ "[employer]" | `Info!C4` | `projects.employer` **E** |
| Consultant / Engineer | ✔ JV name | ✔ "ENGINEER" block | `Info!C3` | `projects.consultant` **E** |
| Contractor | ✔ | ✔ | `Info!C2` | `projects.contractor` **E** |
| Project / contract title | ✔ | ✔ "Project:" | `Info!C1` | `projects.name` **E** |
| Contract number / lot | – | (in title) | – | `projects.contract_number` **E** |
| Project length | – | ✔ "Project Length" | – | `projects.project_length` **N** |
| Logos (employer, consultant, contractor) | ✔ | ✔ | – | `project_branding` files **N** (OD-13) |

## 2. DOC_01 (batch) → `rfi_summaries` (batch) and `rfis` (one row per RFI)

### 2.1 Batch level

| DOC_01 field | Target | Notes |
|---|---|---|
| Sheet title / batch | `rfi_summaries.summary_reference` **E** | Existing manual reference. Propose auto-suggest `<PROJECT>-DRS-<yyyymmdd>-<n>`. |
| Submission date/time | `rfi_summaries.submitted_at` **E** (server timestamp) | `submission_date` **E** is user-entered; keep both. |
| Submitted by (user) | `rfi_summaries.submitted_by` **E** | Must be the authenticated user, never client-supplied. |
| Contractor Representative — Name | `rfi_summaries.contractor_rep_name` **N** | Defaults to the submitter's name. |
| Contractor Representative — Signature / Date | `rfi_summaries.contractor_ack_at` **N** + optional signature image **N** | No fabricated signatures (§12 of brief). Electronic acknowledgement = authenticated submit. |
| Consultant Representative — Name / Signature / Date (receipt) | `rfi_summaries.received_by`, `received_at` **N** | Set when RE/DRE (or office) opens/acknowledges the batch. Same concept as DOC_03 "Received by". |
| Idempotency key | `rfi_summaries.client_request_id` **N** (unique) | Prevents duplicate batches when the offline queue retries. |

### 2.2 Per-RFI rows (DOC_01 table columns)

| DOC_01 column | DOC_02 workbook column | `rfis` target | Notes |
|---|---|---|---|
| RFI No (`Fill-401/2026`, `EX-257/2026`, `CC-513/2026`, `SUB-265/2026`) | `RFI_No.` (P) | `rfi_number` **E** | Visible business key. Prefix series per work category on new forms vs plain numbers in history; see OD-01. |
| Description | `Contractor_Request` (A) | `contractor_request` **E** | DOC_01 "Description" is free text = workbook `Contractor_Request`. |
| (work item picked from list) | `Item` (B) | `work_item` **E** | Dropdown from `Work_List!F`. |
| (structure type) | `Structure_Type/Building Block` (C) | `structure_type` **E** | |
| (standard activity) | `Description` (D) | `description` **E** | Dependent list `INDIRECT(Item)`. Currently mandatory in the API; **should become optional**, because DOC_01 only has free text. |
| Station From | `Requested_From` (N) | `chainage_from` **E** | Store display text (`188+650`). Add `chainage_from_m` **N** numeric (metres) for sorting/filtering where parseable. |
| Station To | `Requested_To` (O) | `chainage_to` **E** | Same. Samples show compound values (`187+900 Junction 0+00-0+030,0+040-0+050`), so free text must remain allowed. |
| Side | `Side/Inlet/Outlet` (H) | `side` **E** | Normalise synonyms (FW, F/W, fullwidth → Full Width) in a *display* list; never rewrite historical text. |
| Material Source — Location | `Material_Source_Designation` (L) | `material_source` / `material_source_designation` **E** | Sample: `186+380&186+160 RHS`. |
| Material Source — Offset | – (encoded in designation string) | `material_source_offset` **N** | Sample: `50m & 300`. |
| Requested Date | *none* | `requested_date` **E** | Must be the contractor's real request date. Historical rows: **NULL** (see importer defect I-3). |
| Requested Time | *none* | `requested_time` **N** | |
| Inspection Date | `Inspection_Date` (Q) | `inspection_date` **E** | |
| Inspection Time | `Inspection_Time` (R) | `inspection_time` **N** (TIME) + `inspection_time_text` **N** (legacy raw text) | Historical times are messy free text; keep raw, parse where safe. |
| Remark | `Remark` (Z) | `remarks` **E** | |
| (road type) | `Road_Type` (F) | `road_type` **E** | |
| (direction) | `Direction` (G) | `direction` **E** | |
| (layer) | `Fill Layer/CheckDam/Pww` (I) | `fill_layer` **E** | |
| (material source type) | `Material_Source_or_Desitination Type` (J) | `material_source_type` **E** | |
| (cut section) | `Material_Source_Cut_Sec_[…]` (K) | `material_source_cut_section` **E** | |
| (destination) | `Material_Destination/Disposal_Designation` (M) | `material_destination_designation` **E** | |
| Short-notice flag | – | `short_notice` **C/N** (bool) + `notice_hours` **N** | Computed at submission: inspection date/time − submitted_at < 24 h (BR-09). |

## 3. DOC_03 (individual sheet) → `rfis` + related tables

| DOC_03 field | Target | Prefilled from DOC_01? | Who edits |
|---|---|---|---|
| Req No. (`AS-014/2026`) | `rfis.rfi_number` **E** | ✔ | – |
| Work category checkboxes: GPS/BM Checking (Level checking for road bed preparation / Section for dumping & placing / X-Section / Others), Earthworks (Survey, Site Clearing, Earthworks, Sub-grade, Others), Pavement (Sub-base, Base, Priming, Wearing Course, Others), Structures (Layout, Elevation, Formwork, Reinforcement, Concreting, Masonry, Bedding, Pipe laying, Backfill, Others), Ancillary works, Other work | `rfi_work_categories` **R/N** (rfi_id, category_code), with codes in `master_data` category `DOC03_WORK_CATEGORY` | Contractor ticks at submission | Contractor (before submit) |
| Works Description | `rfis.contractor_request` **E** | ✔ | – |
| BOQ Item No. (`64.02(a)`) | `rfis.boq_item` **E** (exists, not on any form yet) | Contractor | Contractor |
| Source of Material | `rfis.material_source` **E** | ✔ | – |
| Location / chainage line (`187+325-187+405 LHS`) | C from `chainage_from`, `chainage_to`, `side` | ✔ | – |
| Order of Inspection: First / Second / Third | `rfis.inspection_order` **N** (1/2/3) | Contractor | Contractor |
| Inspection date / Time | `inspection_date` **E**, `inspection_time` **N** | ✔ | – |
| Submitted by / Date / Signature | `rfi_summaries.submitted_by`, `submitted_at` | ✔ | system |
| Received by / Date / Signature (Engineer) | `rfis.received_by`, `received_at` **N** | – | RE/DRE or Office (on acceptance/assignment) |
| **Action by the Engineer**, one row per inspector role: Works Inspector (WI), Structure Inspector (SI), Surveyor, Surveyor (Senior), Material Inspector (MI), Soil Lab Technician (SLT), Material Engineer (ME) — Comments + Name/Signature/Date | `reviewer_assignments` **E** (+ `sequence_no` **N**, `doc03_slot` **N**) and `reviews` **E** (comment, reviewer_id, reviewed_at). One assignment per role slot. | – | **Only** the assigned inspector, **only** when it is their turn |
| Enclosures / Check Lists — Sheets (count) | `rfis.enclosure_sheets` **N** + attachments **E** | Contractor | Contractor |
| **Disposition** checkboxes: Information only · Activity On Progress · Approved: For further works · Approved: Compliance to Comments required · Approved: For further works for the executed section and RFI to be resubmitted for the remaining section · Not Approved: RFI to be resubmitted | `decisions.disposition_code` **N** + `decisions.decision` (canonical outcome) **E** | – | RE/DRE only |
| (approved section for partial approval) | `decisions.approved_from`, `approved_to` **N** → copied to `rfis.approved_from/to` **E** | – | RE/DRE |
| RE/DRE Sign / Date (the paper form says "RE/ARE"; DR-02: printed as RE/DRE) | `decisions.decided_by`, `decided_at` **E** | – | system |
| Remark (if any) | `decisions.comment` **E** | – | RE/DRE |
| Distribution: Original → RE; Copies → QS, DRE (form: ARE), ME, Inspectors, Surveyors, Lab Techs | `rfis.distribution` **N** (JSON list) or a fixed print block | – | Printed block; optional |
| Received by contractor — Name / Date / Signature | `rfis.returned_to_contractor_at` **N** (set when contractor first views the decided DOC_03) | – | system |
| Form notes 1–5 (24 h submission, 24 h return, rejection rules) | static text in `project_settings.doc03_notes` **P** | – | Admin |

### 3.1 DOC_03 inspector rows vs SRS role list

| DOC_03 row | SRS Category 2.2 role | Existing role code |
|---|---|---|
| Works Inspector (WI) | Work Inspector | `WORK_INSPECTOR` |
| Structure Inspector (SI) | Structure Inspector | `STRUCTURE_INSPECTOR` |
| Surveyor | Surveyor | `SURVEYOR` |
| Surveyor (Senior) | Senior Surveyor | `SENIOR_SURVEYOR` |
| Material Inspector (MI) | Material Inspector | `MATERIAL_INSPECTOR` |
| Soil Lab Technician (SLT) | Laboratory Technician | `LAB_TECHNICIAN` (label: "Soil Lab Technician") |
| Material Engineer (ME) | Material Engineer | `MATERIAL_ENGINEER` |

This is **7 fixed role rows**, which is evidence for OD-08 ("fixed by role"). The data model still stores reviews dynamically (one assignment per row with a `sequence_no`), so the PDF prints them in the fixed DOC_03 row order while the *review order* follows management's sequence. If two people with the same role are assigned, the PDF prints both under that row.

## 4. DOC_02 register columns (system view)

The register is the 32 workbook columns, in workbook order, **plus** the SRS/system columns the workbook lacks. The Excel export reproduces the workbook column order first, so existing users recognise it, then appends the system columns.

| # | Register column | Source | Populated at |
|---|---|---|---|
| 1–26 | Contractor_Request … Remark (workbook A–Z) | `rfis` columns per §2.2 | DOC_01 submission; Approved_From/To and RFI_Status at **final decision** |
| 19 | Work_Status | `rfis.work_status` **E** | Inspector/RE input (DOC_02 only; not on DOC_03) |
| 20 | RFI_Status | C: disposition label of the latest decision; for legacy rows, `legacy_rfi_status` | Final decision |
| 21–22 | Approved_From / Approved_To | `rfis.approved_from/to` **E** | Final decision (partial approval) or back-fill for legacy |
| 23–25 | Application Rate, Quantity G-40, All Quantity | `rfis.application_rate`, `quantity_g40`, `all_quantity` **E** | RE/DRE or QS after decision (empty in history) |
| 27/28 | File_Path (legacy) | `legacy_file_path` **E** = AA target path | Legacy only |
| 30 | RFI Included under IPC | `legacy_ipc_included` **E** | Legacy only. **No IPC workflow.** |
| 31/32 | File_Path[IPC] (legacy) | `legacy_ipc_file_path` **E** = AE target path | Legacy only |
| S1 | Revision | `revision_no` **E** | |
| S2 | Batch (DOC_01 ref) | `rfi_summaries.summary_reference` via `summary_id` **E** | Submission |
| S3 | Submitted at / by | batch | Submission |
| S4 | Requested date/time | `requested_date`, `requested_time` | Submission |
| S5 | Short notice (<24 h) | `short_notice` | Submission |
| S6 | Assigned inspectors (in sequence) | C from `reviewer_assignments` | Assignment |
| S7 | Workflow status | `workflow_status` **E** | Every transition |
| S8 | Decision / Disposition | `current_decision`, `current_disposition` **N** | Final decision |
| S9 | Decided by / at | latest `decisions` row | Final decision |
| S10 | Provenance | `provenance` **N** (`PORTAL` / `LEGACY_IMPORT`) | Creation |

## 5. Population rules (FR-07, FR-18, BR-02, BR-04)

1. **On DOC_01 submit** (single DB transaction): every child RFI moves to `SUBMITTED`; the batch-level timestamps are set; `short_notice` is computed; RE/DRE **of that project** are notified. The `rfis` row *is* the DOC_02 row, so no copy is made and there is no duplication risk.
2. **On assignment:** the DOC_03 becomes available, prefilled from the same row. There is no separate DOC_03 data copy. The "issued" DOC_03 is a snapshot taken at decision time (rule 4).
3. **On each review:** a `reviews` row is written against its assignment (unique per assignment), the assignment is locked, and the next sequence becomes active.
4. **On final decision** (single transaction): a `decisions` row is written, `rfis.current_decision`, `current_disposition`, `approved_from/to` and `workflow_status` are updated, a history row is added, and an **issued DOC_03 PDF snapshot** is stored (file + SHA-256 in `issued_documents` **N**) so it can be reproduced as issued (SRS §11.2).
5. **Rejected → resubmission:** a new revision row is created (`revision_no + 1`, `parent_rfi_id`). The rejected row and its decision stay untouched (BR-08). Whether the register shows one row per revision or the latest only is OD-07.
