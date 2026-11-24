# Role and permission matrix — release 6.0.0-ui

The server enforces every rule (`app/authz.py`, `services/evidence.py`, routers). Navigation only reflects these rules. Membership is per project; access to another project's records is refused (403) everywhere. Admins can export the live matrix, computed from each project's actual settings, from **Project memberships → Export access matrix** (`/admin/access-matrix.xlsx`).

Legend: ✔ allowed · ✖ refused · ◐ depends on a project setting (default shown in brackets).

| Capability | 1 Admin | 2.1 RE/DRE | 2.2 Inspectors | 2.3 Office | 3 Contractor |
|---|---|---|---|---|---|
| Projects, users, memberships, configuration | ✔ | ✖ | ✖ | ✖ | ✖ |
| Deactivate / activate accounts (history kept) | ✔ | ✖ | ✖ | ✖ | ✖ |
| Create / edit draft DOC_01, add enclosures, submit | ✖ | ✖ | ✖ | ✖ | ✔ |
| Acknowledge DOC_01 receipt | ✖ | ✔ | ✖ | Secretary only | ✖ |
| Return DOC_01 (with remark and evidence) | ✖ | ✔ | ✖ | ✖ | ✖ |
| Management remark + own evidence (DOC_01 review, assignment, sequence change, return, final disposition) | ✖ | ✔ (own remarks only) | ✖ | ✖ | ✖ |
| Assign / re-sequence inspectors (reason once started) | ✖ | ✔ | ✖ | ✖ | ✖ |
| DOC_03 review comment + evidence | ✖ | ✖ | ✔ own active turn only | ✖ | ✖ |
| Final disposition | ✖ (DR-01) | ✔ | ✖ | ✖ | ✖ |
| Request DOC_01 field amendment | ✖ | ✔ | ✖ | ✖ | ✔ |
| Request evidence correction (review / remark) | ✖ | ✔ | ✔ own submitted review | ✖ | ✖ |
| Approve / reject amendments | ✖ | ✔ | ✖ | ✖ | ✖ |
| View RFI record and timeline | ✔ | ✔ | assigned RFIs; ◐ all [all, read-only] | ✔ | ◐ project / own [project] |
| Open submitted inspection / management evidence | ✔ | ✔ | RFIs where they hold or held a turn | ✔ | ◐ [no] (UD-04) |
| Completed DOC_03 record and issued PDF | ✔ | ✔ | as RFI view | ✔ | as RFI view |
| Evidence bundle | ✔ | ✔ | files they may open | ✔ | ◐ [no] |
| DOC_02 register | ✔ | ✔ | ◐ [yes, read-only] | ✔ | ✔ |
| DOC_02 export | ✔ | ✔ | ◐ [no] | ✔ | ✔ |
| Hidden workbook fields I:M and S | ◐ [yes] | ◐ [yes] | ◐ [no] | ◐ [yes] | ◐ [no] (UD-06) |
| Saved register views | own | own | own | own | own |
| Audit log | ✔ | ✔ (project) | ✖ | ✖ | ✖ |

## Turn and state rules
- An inspector can comment, upload, save a draft or submit only while their assignment is **ACTIVE** and the RFI is **UNDER_REVIEW**. Later inspectors are read-only until activated. Replaced inspectors lose access to evidence.
- The final decision is accepted only in **AWAITING_DECISION** (all reviews submitted).
- Historical (imported) RFIs are read-only. Remarks, reviews and evidence cannot be added to them.
- Archived projects are read-only.
- A deactivated account is rejected on its next request, including existing sessions.
