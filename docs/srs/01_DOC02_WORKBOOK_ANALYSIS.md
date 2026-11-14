# DOC_02 Workbook Analysis — `SRT_RFI_Summary_DG.xlsx`

**Status:** analysis only. Nothing in the application or database was changed while this was produced.
**Analysed:** 14 Nov 2026, using Python 3.12 / openpyxl 3.1.5 / pandas 2.3.3, read-only.
**Source file:** `client_source/SRT_RFI_Summary_DG.xlsx` (2,141,126 bytes).
`client_source/SRT_RFI_Summary_DG(DOC_02 ).xlsx` has the identical MD5 (`cbfe935a7a4acb65932103d45e0f8427`), so there is one source workbook, not two.
The original file was not modified, converted, or re-saved.

---

## 1. Workbook-level findings

| Item | Finding | Impact |
|---|---|---|
| Worksheets | 11: `Info`, `Work_List`, `Test_List`, `ROW_List`, `Material_Source`, `Concrete_Mix_Design`, `Asphalt_Mix_Design`, `EW_List`, `RFIxx` (**hidden**), `Daily_Progress_List`, `RFI` | `RFIxx` is a hidden older copy of the register (318 rows, header row 8, freeze Z10). It must not be imported as a second register. |
| Defined names | 243 named ranges. They drive the dependent dropdowns (e.g. `Item` → `Work_List!$F$2:$F$78`, and each item name → its own description list). | The dropdown hierarchy is the real reference-data model. The current importer reproduces it partly through `master_data.parent_value`. |
| Broken names | `Earthwork`, `Earthwork_C_F_Type`, `EW_Progress_Type`, `Rock_Fill`, `Rock_Undercut`, `Undercut_0.6m`, `Undercut_1m` → `#REF!`; `R_2` → external workbook `[1]Info!$H$2:$H$15` | Do not depend on these names. Report them to the client as workbook defects. |
| External link | `SRT_Site Report/Secretery/2.0_RFI Summary April 01 2025/RFI_Summary_DG (4).xlsx` | The workbook was copied from another RFI summary file. Supports the provenance concern in §4. |
| Comments | 11 cell comments (author "Windows User"), e.g. "Lentgth measured at 3+420". They sit on the hidden `RFIxx` sheet. | Informational only. Not migrated. |
| Conditional formatting | `RFI`: 10 rules, `RFIxx`: 119 rules (an extension openpyxl cannot read is dropped on load). | Presentation only. Not migrated. |
| Used range | `RFIxx` reports `A1:XFC1048576` and `RFI` reports `A8:AF1048576`, because formatting runs to the end of the sheet. | Parsers must bound row scans. Real data ends at Excel row **2477** on `RFI`. |

## 2. Sheet-by-sheet

### 2.1 `Info` — project header and short lists (A1:V41, no validation)
- `C1` project name: *[client contract title, redacted]*.
- `C2` contractor, `C3` consultant, `C4` employer. Note that the column-A labels (Employer/Consultant/Contractor) do **not** line up with the column-B labels (Contractor/Consultant/Employer). Column B is the correct one.
- `J1:K3` reporting period "Date [Including]" From 26/12/2019 To 25/01/2020, used by the `RFIxx!A6` title formula (now `#REF!`).
- Column lists used by validation: `E` Direction (BOP, EOP), `F` Side_Inlet_Outlet (LHS, RHS, BHS, Centre, Centre_LHS …, 13 values), `G` Work_Status (Done, Done with Note, On_Progress, Not Done), `H` RFI_Status (named `RFI_Status`/`Result`: Accepted, Accepted as Noted, Rejected, Not Ready, Information …), `I` Staff_Name (empty), `L` Road_Type (AC, LK-01, VA-01, VA-02, BC-01&06 …).
- Formulas: `N1 = CONCATENATE("PROJECT:- ",$C$1)`, `P4 = C3`, `U4 = C4` (print header block).

### 2.2 `Work_List` — BOQ and work hierarchy (A1:CQ447, no formulas)
- `A:D` Pay_Item, Pay_Item_Description, Unit, Rate (BOQ). **This is the only BOQ source in the workbook.** DOC_03 needs a BOQ Item No., but the historical `RFI` sheet has no BOQ column.
- `F` **Item** (77 work items, named range `Item`).
- `H` **Structure_Type** (≈405 values such as `Housing_Type_A_Block_1`).
- `I`/`J` Weather / Terrain lists (not used by the RFI sheet).
- `L:CQ`: one column per Item, headed by the Item name. Each holds that Item's allowed **Description** values (named range per Item, used by `INDIRECT($B9)`).

### 2.3 `Test_List` — tests per Item (H1:CK50)
Headers are `T_<Item>`. The data is **placeholder junk** (`1, 2, 3`, `lkj`, `jlk`, `gh`, `jkl`), and the `RFI!Test` column is empty for all 2,469 rows. The existing importer already ignores it, which is correct. **No real test list exists. Ask the client for one.**

### 2.4 `ROW_List` (A1:F21)
`Row_Item_No, Location, Offset, Side`, plus formula `F = CONCATENATE("ROW_",A,"_",B,"_",C,"_",D)`. The 20 rows look like sample data (00+000.00 … 00+000.19, all 900m LHS).

### 2.5 `Material_Source` (A1:T20)
- `A` source/destination types (Roadbed_Sampling, Borrow_Pit, Quarry_Site, Spoil_Pit, Crusher_Site, Water_Source, CMD, Cement, Reinforcment …).
- `C:T`: one column per type with designations, e.g. `BP_01_85+700.00_1.5km_RHS` (pattern **Type_No_Chainage_Offset_Side**). Many are unfilled templates (`WRS_01_"Location"_"Offset"_"Side"`).
- The pattern maps directly to DOC_01's *Material Source — Location / offset*.

### 2.6 `Concrete_Mix_Design` (A1:U2)
Header only, plus one row (`MD_1`). Columns cover submission/approval letter refs and dates, w/c ratio, and mix proportions. **This is not RFI data.** Treat it as future reference data.

### 2.7 `Asphalt_Mix_Design`
Empty (A1 only).

### 2.8 `EW_List` (A1:E4)
Earthwork lists: Cut_Material_Type, Fill_Material_Type, C_F_Status, UC_Exc_Type, UC_Replacement_Type.

### 2.9 `Daily_Progress_List` (A1:BA265)
`A` Daily_Item (51 values). Columns `C:BA` hold dependent status lists per item (e.g. `D_Earth_Fill` → 1st_Layer_On_Progress …). This drives the existing Daily Progress module.

### 2.10 `RFIxx` — hidden legacy register
Same 32 columns as `RFI`, with the header at row 8 and 318 data rows (RFI 1 to about 320). It has 14 validation rules, including dependent `INDIRECT` lists for Description, Test and Material Source. It is an **earlier snapshot** of the first ~318 rows of `RFI`. **Do not import it.** It is useful only as evidence of how the validation chain was designed.

### 2.11 `RFI` — the historical master register (the real DOC_02)
- Header at **Excel row 8**. Data rows 9 to 2477 = **2,469 rows**, every one with an RFI number.
- Freeze panes at `N1974` (a working position, not a header freeze).
- Data validation: `B` Item → `Item`; `C` → `Structure_Type`; `D` → `INDIRECT($B9)` (description depends on item); `F` → `Road_Type`; `G` → `Direction`; `S` → `Work_Status`; `T` → `RFI_Status`.
- Formulas: `AA = CONCATENATE("i:\<PROJECT_X>_Project\Main\Change\RFI\",$P)`, `AB = HYPERLINK($AA,$P)`, `AE` = the IPC folder path, `AF = HYPERLINK($AE,$P)`, applied to the first 318–320 rows only. `P491 = P490+1` (15 auto-incremented RFI numbers).
- Number formats: chainage columns `N, O, U, V` use the custom format `00\+000.00`. The stored value is **metres as a number** (e.g. `520`) and displays as `00+520.00`. `Q` uses `dd/mmmm/yyyy`. `P` is a mix of Text (`@`) and General.

#### Column profile (2,469 data rows)

| # | Col | Header (exact, including stray spaces) | Non-null | Type / notes |
|---|---|---|---|---|
| 1 | A | `Contractor_Request` | 2,466 | Free text, 1,294 distinct. In practice this is the **work description offered for inspection** (DOC_01 "Description"). |
| 2 | B | `Item` | 2,463 | 19 distinct (Embankment 549, Slab_Culvert 318, SubBase 274 …). Plus `Channeling` (typo of `Channelling`) and `Utility`, which are **not** in `Work_List!F`. |
| 3 | C | `Structure_Type/Building Block` | 266 | Only `Kerbing_TY_B` (141) and `Walkway` (125). |
| 4 | D | `Description` | 1,341 | 85 distinct, from the dependent list (e.g. "Mixing, & Placing Inspection & FDT"). |
| 5 | E | `Test` | **0** | Empty. |
| 6 | F | `Road_Type` | 2,292 | 34 distinct. Inconsistent forms (`BC-3`/`BC-03`/`Bc-3`, `LK-1`/`LK-01`) and some non-road values ("Borrow pit 1", "old crusher"). |
| 7 | G | `Direction` | 1 | Effectively unused. |
| 8 | H | `Side/Inlet/Outlet` | 1,853 | 15 variants of a few concepts: `F/W`, `FW`, `fullwidth`, `Fullwidth` = Full Width; `B/S`, `both Side`; `RHS/LHS` … |
| 9 | I | `Fill Layer/CheckDam/Pww` | 126 | ints `1/2/3`, text `1st-3rd`, and **one date-typed cell** (Excel auto-conversion error). |
| 10 | J | `Material_Source_or_Desitination Type` | 2 | Junk values `322`, `323`. |
| 11 | K | `Material_Source_Cut_Sec_[Sta. From-Sta. To]` | 2 | Two date-typed cells (error). |
| 12 | L | `Material_Source_Designation` | **0** | Empty. |
| 13 | M | `Material_Destination/Disposal_Designation` | **0** | Empty. |
| 14 | N | `Requested_From` | 2,420 | 2,268 numeric (metres, `00+000.00` format) and 152 text (`000-0`, `VA1-1,`, ranges). |
| 15 | O | `Requested_To` | 1,724 | Same as N. |
| 16 | P | `RFI_No.` | 2,469 | **2,465 distinct.** Mostly plain sequence numbers 1…~2470. Variants: trailing spaces (`"6 "`), `999A`, `999B`, `999 b`, 4 float-like values. **No prefix series** (unlike DOC_01's `Fill-401/2026`). |
| 17 | Q | `Inspection_Date` | 2,452 | 2,296 true Excel dates; **156 text dates**, of which 153 are DD/MM/YYYY and **3 are MM/DD/YYYY** (`04/27/2024`, `04/28/2024`, `04/30/2024`). 0 ambiguous. Range 05 Jan 2024 – 31 Mar 2025. |
| 18 | R | `Inspection_Time` | 2,131 | Free text with ~45 spellings: `9:00am`, `9.00am`, `9 :00am`, `13:00pm`, `10/00am`, `9:00am and 2:00pm`, one `1900-01-11` artefact. |
| 19 | S | `Work_Status` | 133 | Done 71, On_Progress 34, Not Done 25, "Note ready" 3. |
| 20 | T | `RFI_Status` | 2,310 | **16 spellings** (see §3). 159 blank. |
| 21 | U | `Approved_From ` | 1,550 | **Header has a trailing space.** Numeric chainage. |
| 22 | V | `Approved_To ` | 1,133 | **Header has a trailing space.** |
| 23 | W | `Application Rate` | 0 | Empty (CSV export header was `" Application Rate "`). |
| 24 | X | `Quantity G-40` | 0 | Empty. `X9` holds a `SUBTOTAL` formula. |
| 25 | Y | `All Quantity [& G-60]` | 0 | Empty. `Y9` holds a `SUBTOTAL`. |
| 26 | Z | `Remark` | 6 | Free text. |
| 27 | AA | *(unnamed)* | 318 | Formula: legacy network folder path `i:\<PROJECT_X>_Project\Main\Change\RFI\<n>`. |
| 28 | AB | `File_Path` | 320 | `HYPERLINK(AA, P)`. The **cached value is just the RFI number**; the link target is in AA. |
| 29 | AC | *(unnamed)* | 0 | Empty spacer. |
| 30 | AD | `RFI Included under IPC` | 0 | Empty on `RFI`. On `RFIxx` it holds `24` for 242 rows, i.e. **IPC No. 24**. |
| 31 | AE | *(unnamed)* | 318 | Formula: `i:\<PROJECT_Y>_Project\Main\Current\IPC\IPC_24\Suppport_Document\…\RFI\<n>` |
| 32 | AF | `File_Path[IPC]` | 318 | `HYPERLINK(AE, P)`. Cached value is the RFI number. |

**The unnamed columns are explained.** AA and AE are the hidden "helper" path columns behind the two HYPERLINK columns. AC is a spacer. They are legacy document-folder pointers on a network drive (`i:\`) that the application cannot reach. Preserve them as read-only provenance text; they are not live attachments. There is **no IPC workflow** in this data beyond "RFI was bundled in IPC 24". Per the brief, no IPC approval workflow will be built.

## 3. `RFI_Status` value inventory (historical outcomes)

| Raw value | Count | Closest DOC_03 disposition (proposed, **needs client confirmation**) |
|---|---|---|
| Accepted | 1,144 | Approved (legacy term, detailed disposition not recorded) |
| accepted | 2 | same |
| Approved | 6 | same |
| Accepted as Noted | 391 | Approved — Compliance to Comments required |
| Approved: For further works | 30 | Approved — For further works |
| Approved for further works | 3 | Approved — For further works |
| Approved: Compliance to Comments required | 1 | Approved — Compliance to Comments required |
| Approved: For the executed section and RFI to be resubmitted for remaining section | 1 | Approved — executed section; resubmit remaining |
| Not Ready | 429 | **Unclear**: "Activity on progress" or "Not approved — resubmit"? |
| Not ready | 9 | same |
| Note ready (typo) | 23 | same |
| Information | 181 | Information only |
| Information Only / Information only | 18 | Information only |
| Rejected | 57 | Not Approved — RFI to be resubmitted |
| Not Approved: RFI to be resubmitted | 15 | Not Approved — RFI to be resubmitted |
| *(blank)* | 159 | No decision recorded (legacy, unknown) |

## 4. Provenance concern — which project do these 2,469 RFIs belong to? (needs client confirmation)

`Info!C1` names the **[client project A]** project (contractor and consultant named; redacted), and its reporting period is Dec 2019 – Jan 2020. Several things in the data itself point elsewhere:
- Inspection dates run Jan 2024 – Mar 2025, four years after the Info period.
- The legacy folder paths are `i:\<PROJECT_X>_Project\…` and `i:\<PROJECT_Y>_Project\…`.
- Location names that refer to a different region (redacted), and road types `BC-01…BC-15`, `VA-01/02`.
- The external link points to a different summary file ("RFI_Summary_DG (4).xlsx", April 2025).

The workbook looks like a **template whose Info sheet was carried over from an older project, while the RFI rows belong to a later project**. The current system files all 2,465 imported RFIs under project `<PROJECT_CODE>` purely because of `Info!C1`.
**This needs client confirmation before any re-labelling.** Until then the records stay where they are, and the question is recorded in the decision register (DR-15).

This is separate from the [client project B] project shown on the DOC_01/DOC_03 samples. That third project must also not be merged with this data.

## 5. Duplicates

| RFI_No. | Excel rows | Content | Previous importer kept |
|---|---|---|---|
| 34 | 44, 45, 46 | Three **different** activities (as-built measurement, Finished FDT, Roadbed prep), dates 19/15/25 Jul 2024, statuses Approved: For further works / Accepted / blank | row 44 only |
| 79 | 91, 92 | Two different activities, same date 24/07/2024 | row 91 only |
| 154 | 169, 208 | Same activity text; second row has no date or status | row 169 only |

**7 rows across 3 numbers.** The importer kept the first occurrence and skipped **4 rows**: 2,469 − 4 = **2,465**. This matches the "2,465 imported / 4 conflicting" figure reported earlier.
Rows 45, 46 and 92 are **genuinely different inspections that are currently missing from the database.** Restoring them needs a decision (DR-16): import them as revisions (`34` Rev 1/2), or with a suffix such as `34-dup-row45`, each flagged `legacy_duplicate`.

## 6. Defects found in the existing historical importer (`backend/scripts/import_client_bundle.py`)

These were confirmed by replaying the importer's logic against the bundled CSV. The CSV is a formatted export of the `RFI` sheet: chainages appear as `00+035.00` and dates as `29/November/2024`, so those two came through correctly.

| # | Defect | Rows affected | Severity |
|---|---|---|---|
| I-1 | Headers `Approved_From ` / `Approved_To ` have trailing spaces. `row.get('Approved_From')` returns nothing, so **approved chainages were never imported.** | 1,549 RFIs have Approved_From in the source | **High** (real register data missing) |
| I-2 | `Inspection_Time` has no model column and is not imported. | 2,127 RFIs | High (DOC_02 column missing) |
| I-3 | `requested_date` is set to the **inspection date**. That is invented data: the workbook has no request date. | all with a date | Medium (provenance) |
| I-4 | Status mapping misses `Note ready` (23), `Approved for further works` (3), and `Approved: For the executed section…` (1). 159 are blank. Those **183** got `workflow_status='ARCHIVED'`, a value the workflow code does not recognise, while `record_state` stays `ACTIVE`. | 183 | Medium |
| I-5 | The status mapping collapses `Accepted as Noted` and `Approved: Compliance to comments` into `APPROVED`, and `Not Ready` into `ON_PROGRESS`. The raw value survives only as text appended to `remarks` (`… | Legacy status: X`). | 2,282 | Medium (recoverable from remarks) |
| I-6 | An empty `Description` is replaced with `"Legacy imported record"`; an empty `Item` is replaced with `"Legacy"`. | 1,128 / 6 | Low (placeholder, but indistinguishable from real text) |
| I-7 | `legacy_file_path` stores the HYPERLINK *display value* (the RFI number) instead of the target path in column AA/AE. | 318 | Low |
| I-8 | Duplicate RFI numbers: the 2nd/3rd occurrences are skipped, not preserved. | 4 | Medium (see §5) |
| I-9 | Text dates are parsed with `dayfirst=False` first. All 156 happen to be unambiguous, so no date was mis-parsed **in this file**. The approach would mis-parse future files. | 0 here | Low |

**Remediation approach (in the implementation plan):** a new **non-destructive back-fill script**. It matches existing DB rows by `(project, rfi_number, revision 0)` and fills *only empty* new columns (`approved_from/to`, `inspection_time_text`, `legacy_rfi_status`, `legacy_source_row`, the legacy path fields). It never overwrites a non-empty value and writes a reconciliation CSV. It runs on a DB copy first. The original importer stays unchanged and must not be rerun.

## 7. What the workbook does **not** contain (gaps against the SRS / DOC_01 / DOC_03)
- No submission/request date, no requested time, no submitter, no batch reference (DOC_01 has all of these).
- No BOQ item per RFI (DOC_03 has one; BOQ exists only in `Work_List!A:D`).
- No inspection order (First/Second/Third), no work-category checkboxes.
- No inspector identities, comments, or sequence. No RE/DRE name or decision date.
- No material source location/offset per RFI (columns J–M are effectively empty).
- No enclosures checklist and no distribution record.

Historical records therefore have **no DOC_01 batch and no DOC_03 reviews**. Per the brief they will be marked `provenance = LEGACY_IMPORT`; no submissions, reviews or approvals will be invented for them.
