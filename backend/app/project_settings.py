"""Per-project configuration with conservative defaults.

Everything the client has not yet confirmed (SRS section 14 / docs/srs/04_DECISION_REGISTER.md)
is a setting here, so a later decision changes configuration rather than code or historical data.
"""
import json
from copy import deepcopy

# DOC_03 disposition choices exactly as printed on the client's form.
# `decision` is the canonical reporting outcome; `requires_section` forces an approved chainage
# range; `allows_resubmit` lets the contractor create the next revision.
# PENDING CLIENT APPROVAL (OD-06) - kept configurable per project.
DEFAULT_DISPOSITIONS = [
    {'code': 'INFORMATION_ONLY', 'label': 'Information only', 'decision': 'INFORMATION_ONLY', 'requires_section': False, 'allows_resubmit': False},
    {'code': 'ACTIVITY_ON_PROGRESS', 'label': 'Activity On Progress', 'decision': 'ON_PROGRESS', 'requires_section': False, 'allows_resubmit': False},
    {'code': 'APPROVED_FURTHER_WORKS', 'label': 'Approved: For further works', 'decision': 'APPROVED', 'requires_section': False, 'allows_resubmit': False},
    {'code': 'APPROVED_COMPLY_COMMENTS', 'label': 'Approved: Compliance to Comments required', 'decision': 'APPROVED', 'requires_section': False, 'allows_resubmit': False},
    {'code': 'APPROVED_PARTIAL_RESUBMIT', 'label': 'Approved: For further works for the executed section and RFI to be resubmitted for the remaining section', 'decision': 'PARTIALLY_APPROVED', 'requires_section': True, 'allows_resubmit': True},
    {'code': 'NOT_APPROVED_RESUBMIT', 'label': 'Not Approved: RFI to be resubmitted', 'decision': 'REJECTED', 'requires_section': False, 'allows_resubmit': True},
]

# DOC_03 work-category checkboxes (client form).
DOC03_WORK_CATEGORIES = [
    ('GPS_BM', 'GPS/BM Checking', [('GPS_LEVEL_ROADBED', 'Level checking for road bed preparation'), ('GPS_DUMPING_SECTION', 'Section for Dumping and placing'), ('GPS_X_SECTION', 'X-Section'), ('GPS_OTHERS', 'Others')]),
    ('EARTHWORKS', 'Earthworks', [('EW_SURVEY', 'Survey'), ('EW_SITE_CLEARING', 'Site Clearing'), ('EW_EARTHWORKS', 'Earthworks'), ('EW_SUBGRADE', 'Sub-grade'), ('EW_OTHERS', 'Others')]),
    ('PAVEMENT', 'Pavement', [('PV_SUBBASE', 'Sub-base'), ('PV_BASE', 'Base'), ('PV_PRIMING', 'Priming'), ('PV_WEARING', 'Wearing Course'), ('PV_OTHERS', 'Others')]),
    ('STRUCTURES', 'Structures', [('ST_LAYOUT', 'Layout'), ('ST_ELEVATION', 'Elevation'), ('ST_FORMWORK', 'Formwork'), ('ST_REINFORCEMENT', 'Reinforcement'), ('ST_CONCRETING', 'Concreting'), ('ST_MASONRY', 'Masonry'), ('ST_BEDDING', 'Bedding'), ('ST_PIPE_LAYING', 'Pipe laying'), ('ST_BACKFILL', 'Backfill'), ('ST_OTHERS', 'Others')]),
    ('ANCILLARY', 'Ancillary works', [('ANCILLARY_WORKS', 'Ancillary works')]),
    ('OTHER', 'Other work', [('OTHER_WORK', 'Other work')]),
]
WORK_CATEGORY_CODES = {code for _, _, items in DOC03_WORK_CATEGORIES for code, _ in items}

DEFAULT_DOC03_NOTES = [
    'All the necessary prior details (like material quality tests, control tests of prior layers, etc.) shall be attached.',
    'Should significant damage or delay be caused, prior to or during construction, a new submission will be required.',
    'Rejection of any of the above items will result in rejection of this request - a new submission will then be required.',
    'RFI to be submitted to the Engineer a minimum of 24 hrs in advance from the date of inspection.',
    "RFI should be returned back to the Contractor within 24 hr's of Request.",
]

# Attachment policy (UI design s.14 / s.17.2). Every value is PENDING CLIENT DECISION (UD-07..UD-09) and is therefore a
# per-project setting. The defaults reproduce the behaviour of release 5.x so nothing changes until the client decides.
DEFAULT_ATTACHMENT_POLICY = {
    'allowed_extensions': ['.pdf', '.jpg', '.jpeg', '.png', '.xls', '.xlsx', '.doc', '.docx', '.dwg', '.dxf', '.dgn'],
    'max_file_mb': 50,              # never above the server limit MAX_UPLOAD_MB
    'max_files_per_record': 20,     # per management remark / inspector review / record
    'retention': 'KEEP_ALL',        # KEEP_ALL is the only value implemented: nothing is ever purged automatically
    'scanning': 'DISABLED',         # DISABLED / SCAN_IF_AVAILABLE / REQUIRED (needs CLAMD_HOST)
}
SCANNING_MODES = ('DISABLED', 'SCAN_IF_AVAILABLE', 'REQUIRED')
KNOWN_EXTENSIONS = {'.pdf', '.jpg', '.jpeg', '.png', '.xls', '.xlsx', '.doc', '.docx', '.dwg', '.dxf', '.dgn', '.heic', '.webp', '.csv', '.txt'}
# Categories that may see the workbook's hidden business columns I:M and S in the DOC_02 register (UD-06).
# Conservative default until the client confirms: Admin, RE/DRE and Office.
DEFAULT_HIDDEN_FIELD_CATEGORIES = ['1', '2.1', '2.3']

DEFAULTS = {
    # OD-11: FLAG = warn only; REQUIRE_OVERRIDE = contractor must give a reason for < notice_hours.
    'notice_policy': 'FLAG',
    'notice_hours': 24,
    # OD-03: PROJECT = contractor sees all RFIs of their projects; OWN = only batches they submitted.
    'contractor_visibility': 'PROJECT',
    # OD-04: inspectors may read the DOC_02 register (read-only) / export it.
    'inspector_register_access': True,
    'inspector_export': False,
    # DR-02 decided by the client (Nov 2026): the deputy is "DRE" everywhere. Fixed, not configurable.
    'deputy_label': 'DRE',
    'overdue_hours': 24,
    'dispositions': DEFAULT_DISPOSITIONS,
    'doc03_notes': DEFAULT_DOC03_NOTES,
    'attachment_policy': DEFAULT_ATTACHMENT_POLICY,
    # UD-04: contractors (Category 3) may open inspector / management evidence files. Default: no (they receive the DOC_03).
    'contractor_evidence_access': False,
    'hidden_field_categories': DEFAULT_HIDDEN_FIELD_CATEGORIES,
}
ALLOWED_KEYS = set(DEFAULTS)


def get_settings(project) -> dict:
    s = deepcopy(DEFAULTS)
    if project is not None and project.settings_json:
        try:
            stored = json.loads(project.settings_json)
            if isinstance(stored, dict):
                s.update({k: v for k, v in stored.items() if k in ALLOWED_KEYS})
                if isinstance(stored.get('attachment_policy'), dict):  # partial policies keep the remaining defaults
                    s['attachment_policy'] = {**deepcopy(DEFAULT_ATTACHMENT_POLICY), **stored['attachment_policy']}
        except ValueError:
            pass
    s['deputy_label'] = 'DRE'  # an older stored value ("ARE") is ignored
    return s


def validate_settings(data: dict) -> dict:
    out = {}
    for k, v in data.items():
        if k not in ALLOWED_KEYS:
            raise ValueError(f'Unknown setting: {k}')
        out[k] = v
    if 'deputy_label' in out and out['deputy_label'] != 'DRE':
        raise ValueError('deputy_label is fixed to DRE')
    if 'notice_policy' in out and out['notice_policy'] not in ('FLAG', 'REQUIRE_OVERRIDE'):
        raise ValueError('notice_policy must be FLAG or REQUIRE_OVERRIDE')
    if 'contractor_visibility' in out and out['contractor_visibility'] not in ('PROJECT', 'OWN'):
        raise ValueError('contractor_visibility must be PROJECT or OWN')
    if 'dispositions' in out:
        seen = set()
        for d in out['dispositions']:
            if not isinstance(d, dict) or not d.get('code') or not d.get('label') or d.get('decision') not in ('APPROVED', 'PARTIALLY_APPROVED', 'REJECTED', 'INFORMATION_ONLY', 'ON_PROGRESS'):
                raise ValueError('Each disposition needs code, label and a valid decision')
            if d['code'] in seen:
                raise ValueError(f"Duplicate disposition code {d['code']}")
            seen.add(d['code'])
    if 'attachment_policy' in out:
        ap = out['attachment_policy']
        if not isinstance(ap, dict): raise ValueError('attachment_policy must be an object')
        unknown = set(ap) - set(DEFAULT_ATTACHMENT_POLICY)
        if unknown: raise ValueError(f'Unknown attachment_policy keys: {", ".join(sorted(unknown))}')
        exts = ap.get('allowed_extensions', DEFAULT_ATTACHMENT_POLICY['allowed_extensions'])
        if not isinstance(exts, list) or not exts or any(not isinstance(e, str) or e.lower() not in KNOWN_EXTENSIONS for e in exts):
            raise ValueError('allowed_extensions must be a non-empty list of supported extensions: ' + ', '.join(sorted(KNOWN_EXTENSIONS)))
        ap['allowed_extensions'] = sorted({e.lower() for e in exts})
        for k in ('max_file_mb', 'max_files_per_record'):
            if k in ap and (not isinstance(ap[k], int) or ap[k] <= 0): raise ValueError(f'{k} must be a positive whole number')
        if ap.get('retention', 'KEEP_ALL') != 'KEEP_ALL': raise ValueError('Only KEEP_ALL retention is implemented (pending client decision UD-08)')
        if ap.get('scanning', 'DISABLED') not in SCANNING_MODES: raise ValueError('scanning must be one of ' + ', '.join(SCANNING_MODES))
    if 'contractor_evidence_access' in out and not isinstance(out['contractor_evidence_access'], bool):
        raise ValueError('contractor_evidence_access must be true or false')
    if 'hidden_field_categories' in out:
        hc = out['hidden_field_categories']
        if not isinstance(hc, list) or any(c not in ('1', '2.1', '2.2', '2.3', '3') for c in hc):
            raise ValueError('hidden_field_categories must be a list of categories: 1, 2.1, 2.2, 2.3, 3')
    for k in ('notice_hours', 'overdue_hours'):
        if k in out and (not isinstance(out[k], (int, float)) or out[k] <= 0):
            raise ValueError(f'{k} must be a positive number')
    return out


def disposition(settings: dict, code: str):
    for d in settings['dispositions']:
        if d['code'] == code:
            return d
    return None
