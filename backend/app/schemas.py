from datetime import date
from pydantic import BaseModel, EmailStr, Field, field_validator
import re

TIME_RE = re.compile(r'^([01]\d|2[0-3]):[0-5]\d$')


def _time(v):
    if v in (None, ''):
        return None
    v = str(v).strip()
    if not TIME_RE.match(v):
        raise ValueError('Time must be HH:MM (24-hour)')
    return v


class LoginIn(BaseModel): email: EmailStr; password: str
class Token(BaseModel): access_token: str | None = None; token_type: str = 'bearer'


class MembershipIn(BaseModel):
    project_id: int
    role: str


class UserCreate(BaseModel):
    full_name: str
    email: EmailStr
    password: str
    role: str = 'VIEWER'                  # global/legacy role; ADMIN for administrators
    project_ids: list[int] = []           # legacy: membership with role = `role`
    memberships: list[MembershipIn] = []  # SRS: project-specific roles


class ProjectCreate(BaseModel):
    code: str; name: str; project_type: str = 'ROAD'; contract_number: str | None = None
    employer: str | None = None; consultant: str | None = None; contractor: str | None = None; project_length: str | None = None


class ProjectUpdate(BaseModel):
    name: str | None = None; project_type: str | None = None; contract_number: str | None = None
    employer: str | None = None; consultant: str | None = None; contractor: str | None = None; project_length: str | None = None


class MasterCreate(BaseModel): project_id: int | None = None; category: str; code: str | None = None; value: str; parent_value: str | None = None
class ReviewerRuleCreate(BaseModel): project_id: int; work_item: str; reviewer_role: str; required: bool = True


class SummaryCreate(BaseModel):
    project_id: int
    summary_reference: str
    submission_date: date
    original_submitter: str | None = None
    contractor_rep_name: str | None = None
    entry_source: str = 'CONTRACTOR_PORTAL'
    remarks: str | None = None
    client_request_id: str | None = Field(None, max_length=64)


class SummarySubmit(BaseModel):
    short_notice_reason: str | None = None


# DOC_01 row fields a contractor may enter (one individual RFI)
DOC01_FIELDS = ['rfi_number', 'contractor_request', 'work_item', 'description', 'structure_type', 'test_name', 'boq_item', 'road_type', 'direction',
                'side', 'fill_layer', 'chainage_from', 'chainage_to', 'location_text', 'material_source_type', 'material_source',
                'material_source_offset', 'material_source_cut_section', 'material_source_designation', 'material_destination_designation',
                'requested_date', 'requested_time', 'inspection_date', 'inspection_time', 'inspection_order', 'enclosure_sheets', 'work_categories', 'remarks']


class RfiFields(BaseModel):
    contractor_request: str | None = None
    work_item: str | None = None
    description: str | None = None
    structure_type: str | None = None
    test_name: str | None = None
    boq_item: str | None = None
    road_type: str | None = None
    direction: str | None = None
    side: str | None = None
    fill_layer: str | None = None
    chainage_from: str | None = None
    chainage_to: str | None = None
    location_text: str | None = None
    material_source_type: str | None = None
    material_source: str | None = None
    material_source_offset: str | None = None
    material_source_cut_section: str | None = None
    material_source_designation: str | None = None
    material_destination_designation: str | None = None
    requested_date: date | None = None
    requested_time: str | None = None
    inspection_date: date | None = None
    inspection_time: str | None = None
    inspection_order: int | None = Field(None, ge=1, le=3)
    enclosure_sheets: int | None = Field(None, ge=0, le=9999)
    work_categories: list[str] | None = None
    remarks: str | None = None

    @field_validator('requested_time', 'inspection_time')
    @classmethod
    def _times(cls, v):
        return _time(v)


class RfiCreate(RfiFields):
    project_id: int
    summary_id: int
    rfi_number: str
    client_request_id: str | None = Field(None, max_length=64)


class RfiUpdate(RfiFields):
    version: int
    rfi_number: str | None = None


class AmendmentCreate(BaseModel):
    changes: dict
    reason: str


class AmendmentResolve(BaseModel):
    comment: str | None = None


class AssignmentItem(BaseModel):
    user_id: int
    reviewer_role: str | None = None


class AssignmentPlan(BaseModel):
    """The ordered list of inspectors still to review (index 0 reviews first)."""
    assignments: list[AssignmentItem]
    reason: str | None = None
    management_remark_id: int | None = None   # optional draft remark (with its evidence) locked by this action
    remark: str | None = None                 # text of that remark (defaults to the reason)


class ReviewCreate(BaseModel):
    assignment_id: int
    comment: str
    recommendation: str | None = None
    attachment_count: int | None = None   # evidence count the inspector confirmed; a mismatch is refused (409)


class DecisionCreate(BaseModel):
    disposition_code: str
    comment: str | None = None
    conditions: str | None = None
    approved_from: str | None = None
    approved_to: str | None = None
    work_status: str | None = None
    management_remark_id: int | None = None
    evidence_count: int | None = None


class RevisionCreate(BaseModel):
    reason: str
    inspection_date: date | None = None
    inspection_time: str | None = None
    chainage_from: str | None = None
    chainage_to: str | None = None
    @field_validator('inspection_time')
    @classmethod
    def _itime(cls, v):
        return _time(v)


class StateChange(BaseModel): reason: str
class ReturnBatch(BaseModel):
    reason: str
    management_remark_id: int | None = None


class DailyProgressCreate(BaseModel):
    project_id: int
    progress_date: date
    work_item: str
    description: str
    chainage_from: str | None = None
    chainage_to: str | None = None
    side: str | None = None
    quantity: float | None = None
    unit: str | None = None
    remarks: str | None = None
    rfi_ids: list[int] = []


class DailyProgressComment(BaseModel):
    comment: str


class ForgotPasswordIn(BaseModel): email: EmailStr
class ResetPasswordIn(BaseModel): token: str; new_password: str
class AdminResetPasswordIn(BaseModel): new_password: str
class MasterUpdate(BaseModel): value: str; parent_value: str | None = None; code: str | None = None
class ChangePasswordIn(BaseModel): current_password: str; new_password: str
class UserProjectsIn(BaseModel): project_ids: list[int] = []


# ---------------------------------------------------------------- UI design v1: evidence
class RemarkCreate(BaseModel):
    project_id: int
    stage: str
    rfi_id: int | None = None
    summary_id: int | None = None
    body: str | None = None
    client_request_id: str | None = None


class RemarkUpdate(BaseModel):
    body: str | None = None
    version: int | None = None


class DraftComment(BaseModel):
    comment: str | None = None


class EvidenceAmendmentCreate(BaseModel):
    """Correction of a locked inspector review (target_kind REVIEW, target_id = assignment id) or management remark (REMARK)."""
    target_kind: str
    target_id: int
    reason: str
    new_comment: str | None = None


class RegisterViewIn(BaseModel):
    name: str
    project_id: int | None = None
    config: dict
