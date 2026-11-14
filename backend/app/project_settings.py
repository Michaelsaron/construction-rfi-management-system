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
}
ALLOWED_KEYS = set(DEFAULTS)


def get_settings(project) -> dict:
    s = deepcopy(DEFAULTS)
    if project is not None and project.settings_json:
        try:
            stored = json.loads(project.settings_json)
            if isinstance(stored, dict):
                s.update({k: v for k, v in stored.items() if k in ALLOWED_KEYS})
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
    for k in ('notice_hours', 'overdue_hours'):
        if k in out and (not isinstance(out[k], (int, float)) or out[k] <= 0):
            raise ValueError(f'{k} must be a positive number')
    return out


def disposition(settings: dict, code: str):
    for d in settings['dispositions']:
        if d['code'] == code:
            return d
    return None
