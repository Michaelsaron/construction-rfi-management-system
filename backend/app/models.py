from datetime import datetime,date
from sqlalchemy import String,Integer,DateTime,Date,Text,Boolean,ForeignKey,UniqueConstraint,Float,CheckConstraint,ForeignKeyConstraint
from sqlalchemy.orm import Mapped,mapped_column
from app.database import Base

class User(Base):
    __tablename__='users'
    id:Mapped[int]=mapped_column(primary_key=True)
    full_name:Mapped[str]=mapped_column(String(150))
    email:Mapped[str]=mapped_column(String(190),unique=True,index=True)
    password_hash:Mapped[str]=mapped_column(String(255))
    role:Mapped[str]=mapped_column(String(60),default='VIEWER',index=True)
    is_active:Mapped[bool]=mapped_column(Boolean,default=True)
    reset_token:Mapped[str|None]=mapped_column(String(255),nullable=True)
    reset_expires_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    must_change_password:Mapped[bool]=mapped_column(Boolean,default=True)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
    last_login_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)

class Project(Base):
    __tablename__='projects'
    id:Mapped[int]=mapped_column(primary_key=True)
    code:Mapped[str]=mapped_column(String(50),unique=True)
    name:Mapped[str]=mapped_column(String(255))
    project_type:Mapped[str]=mapped_column(String(30),default='ROAD')
    contract_number:Mapped[str|None]=mapped_column(String(100),nullable=True)
    employer:Mapped[str|None]=mapped_column(String(255),nullable=True)
    consultant:Mapped[str|None]=mapped_column(String(255),nullable=True)
    contractor:Mapped[str|None]=mapped_column(String(255),nullable=True)
    is_active:Mapped[bool]=mapped_column(Boolean,default=True)
    # SRS v1.0 additions (nullable / defaulted, additive)
    project_length:Mapped[str|None]=mapped_column(String(60),nullable=True)
    archived_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    settings_json:Mapped[str|None]=mapped_column(Text,nullable=True)

class ProjectUser(Base):
    """Project membership. `role` is the project-specific role (SRS 3.1).
    NULL role = legacy row created before SRS v1.0; authz falls back to users.role."""
    __tablename__='project_users'
    id:Mapped[int]=mapped_column(primary_key=True)
    project_id:Mapped[int]=mapped_column(ForeignKey('projects.id'),index=True)
    user_id:Mapped[int]=mapped_column(ForeignKey('users.id'),index=True)
    role:Mapped[str|None]=mapped_column(String(60),nullable=True)
    status:Mapped[str]=mapped_column(String(20),default='ACTIVE')
    created_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True,default=datetime.utcnow)
    revoked_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    __table_args__=(UniqueConstraint('project_id','user_id',name='uq_project_user'),)

class MasterData(Base):
    __tablename__='master_data'
    id:Mapped[int]=mapped_column(primary_key=True)
    project_id:Mapped[int|None]=mapped_column(ForeignKey('projects.id'),nullable=True,index=True)
    category:Mapped[str]=mapped_column(String(60),index=True)
    code:Mapped[str|None]=mapped_column(String(100),nullable=True)
    value:Mapped[str]=mapped_column(String(255))
    parent_value:Mapped[str|None]=mapped_column(String(255),nullable=True)
    is_active:Mapped[bool]=mapped_column(Boolean,default=True)

class ReviewerRule(Base):
    __tablename__='reviewer_rules'
    id:Mapped[int]=mapped_column(primary_key=True)
    project_id:Mapped[int]=mapped_column(ForeignKey('projects.id'),index=True)
    work_item:Mapped[str]=mapped_column(String(150),index=True)
    reviewer_role:Mapped[str]=mapped_column(String(60))
    required:Mapped[bool]=mapped_column(Boolean,default=True)

class RfiSummary(Base):
    __tablename__='rfi_summaries'
    id:Mapped[int]=mapped_column(primary_key=True)
    project_id:Mapped[int]=mapped_column(ForeignKey('projects.id'),index=True)
    summary_reference:Mapped[str]=mapped_column(String(120))
    submission_date:Mapped[date]=mapped_column(Date)
    submitted_by:Mapped[int]=mapped_column(ForeignKey('users.id'))
    original_submitter:Mapped[str|None]=mapped_column(String(150),nullable=True)
    entry_source:Mapped[str]=mapped_column(String(30),default='CONTRACTOR_PORTAL')
    workflow_status:Mapped[str]=mapped_column(String(40),default='DRAFT',index=True)
    remarks:Mapped[str|None]=mapped_column(Text,nullable=True)
    returned_reason:Mapped[str|None]=mapped_column(Text,nullable=True)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
    submitted_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    client_request_id:Mapped[str|None]=mapped_column(String(64),nullable=True,unique=True)
    contractor_rep_name:Mapped[str|None]=mapped_column(String(150),nullable=True)
    received_by:Mapped[int|None]=mapped_column(ForeignKey('users.id'),nullable=True)
    received_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    __table_args__=(UniqueConstraint('project_id','summary_reference',name='uq_summary_project_ref'),)

class Rfi(Base):
    __tablename__='rfis'
    id:Mapped[int]=mapped_column(primary_key=True)
    project_id:Mapped[int]=mapped_column(ForeignKey('projects.id'),index=True)
    summary_id:Mapped[int|None]=mapped_column(ForeignKey('rfi_summaries.id'),nullable=True,index=True)
    rfi_number:Mapped[str]=mapped_column(String(120),index=True)
    revision_no:Mapped[int]=mapped_column(Integer,default=0)
    parent_rfi_id:Mapped[int|None]=mapped_column(ForeignKey('rfis.id'),nullable=True)
    contractor_request:Mapped[str|None]=mapped_column(Text,nullable=True)
    work_item:Mapped[str]=mapped_column(String(150),index=True)
    description:Mapped[str]=mapped_column(Text)
    structure_type:Mapped[str|None]=mapped_column(String(150),nullable=True)
    test_name:Mapped[str|None]=mapped_column(String(150),nullable=True)
    boq_item:Mapped[str|None]=mapped_column(String(100),nullable=True)
    road_type:Mapped[str|None]=mapped_column(String(100),nullable=True)
    direction:Mapped[str|None]=mapped_column(String(50),nullable=True)
    side:Mapped[str|None]=mapped_column(String(50),nullable=True)
    chainage_from:Mapped[str|None]=mapped_column(String(255),nullable=True)
    chainage_to:Mapped[str|None]=mapped_column(String(255),nullable=True)
    location_text:Mapped[str|None]=mapped_column(String(255),nullable=True)
    fill_layer:Mapped[str|None]=mapped_column(String(120),nullable=True)
    material_source_type:Mapped[str|None]=mapped_column(String(150),nullable=True)
    material_source:Mapped[str|None]=mapped_column(String(255),nullable=True)
    material_source_cut_section:Mapped[str|None]=mapped_column(String(255),nullable=True)
    material_source_designation:Mapped[str|None]=mapped_column(String(255),nullable=True)
    material_destination_designation:Mapped[str|None]=mapped_column(String(255),nullable=True)
    requested_date:Mapped[date|None]=mapped_column(Date,nullable=True)
    inspection_date:Mapped[date|None]=mapped_column(Date,nullable=True)
    work_status:Mapped[str|None]=mapped_column(String(80),nullable=True)
    approved_from:Mapped[str|None]=mapped_column(String(50),nullable=True)
    approved_to:Mapped[str|None]=mapped_column(String(50),nullable=True)
    application_rate:Mapped[str|None]=mapped_column(String(80),nullable=True)
    quantity_g40:Mapped[str|None]=mapped_column(String(80),nullable=True)
    all_quantity:Mapped[str|None]=mapped_column(String(80),nullable=True)
    legacy_file_path:Mapped[str|None]=mapped_column(String(500),nullable=True)
    legacy_ipc_included:Mapped[str|None]=mapped_column(String(100),nullable=True)
    legacy_ipc_file_path:Mapped[str|None]=mapped_column(String(500),nullable=True)
    workflow_status:Mapped[str]=mapped_column(String(40),default='DRAFT',index=True)
    current_decision:Mapped[str|None]=mapped_column(String(40),nullable=True,index=True)
    remarks:Mapped[str|None]=mapped_column(Text,nullable=True)
    record_state:Mapped[str]=mapped_column(String(20),default='ACTIVE')
    version:Mapped[int]=mapped_column(Integer,default=1)
    created_by:Mapped[int]=mapped_column(ForeignKey('users.id'))
    activated_by:Mapped[int|None]=mapped_column(ForeignKey('users.id'),nullable=True)
    activated_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
    updated_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow,onupdate=datetime.utcnow)
    # SRS v1.0 / DOC_01 / DOC_03 additions
    inspection_time:Mapped[str|None]=mapped_column(String(5),nullable=True)        # HH:MM (24h)
    inspection_time_text:Mapped[str|None]=mapped_column(String(60),nullable=True)  # raw legacy text
    requested_time:Mapped[str|None]=mapped_column(String(5),nullable=True)
    material_source_offset:Mapped[str|None]=mapped_column(String(120),nullable=True)
    inspection_order:Mapped[int|None]=mapped_column(Integer,nullable=True)          # 1 First / 2 Second / 3 Third
    enclosure_sheets:Mapped[int|None]=mapped_column(Integer,nullable=True)
    work_categories:Mapped[str|None]=mapped_column(Text,nullable=True)              # JSON list of DOC_03 category codes
    received_by:Mapped[int|None]=mapped_column(ForeignKey('users.id'),nullable=True)
    received_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    short_notice:Mapped[bool|None]=mapped_column(Boolean,nullable=True)
    notice_hours:Mapped[float|None]=mapped_column(Float,nullable=True)
    short_notice_reason:Mapped[str|None]=mapped_column(Text,nullable=True)
    current_disposition:Mapped[str|None]=mapped_column(String(60),nullable=True,index=True)
    provenance:Mapped[str|None]=mapped_column(String(20),nullable=True,index=True)  # PORTAL / LEGACY_IMPORT
    legacy_rfi_status:Mapped[str|None]=mapped_column(String(150),nullable=True)
    legacy_source_row:Mapped[int|None]=mapped_column(Integer,nullable=True)
    __table_args__=(UniqueConstraint('project_id','rfi_number','revision_no',name='uq_rfi_project_no_rev'),)

class ReviewerAssignment(Base):
    __tablename__='reviewer_assignments'
    id:Mapped[int]=mapped_column(primary_key=True)
    rfi_id:Mapped[int]=mapped_column(ForeignKey('rfis.id'),index=True)
    user_id:Mapped[int]=mapped_column(ForeignKey('users.id'),index=True)
    reviewer_role:Mapped[str]=mapped_column(String(60))
    required:Mapped[bool]=mapped_column(Boolean,default=True)
    status:Mapped[str]=mapped_column(String(30),default='PENDING',index=True)
    assigned_by:Mapped[int]=mapped_column(ForeignKey('users.id'))
    assigned_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
    completed_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    # SRS v1.0: strict sequence. status PENDING (waiting turn) / ACTIVE (its turn) / COMPLETED / REPLACED
    sequence_no:Mapped[int|None]=mapped_column(Integer,nullable=True)
    activated_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    change_reason:Mapped[str|None]=mapped_column(Text,nullable=True)
    sequence_backfilled:Mapped[bool|None]=mapped_column(Boolean,nullable=True)
    # UI design v1: the active inspector's unsent DOC_03 comment (preserved if an upload fails or the page closes)
    draft_comment:Mapped[str|None]=mapped_column(Text,nullable=True)
    draft_saved_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    # (id, rfi_id) is unique so attachments can carry a composite foreign key that pins evidence to the RFI of its review.
    __table_args__=(UniqueConstraint('id','rfi_id',name='uq_assignment_id_rfi'),)

class Review(Base):
    __tablename__='reviews'
    id:Mapped[int]=mapped_column(primary_key=True)
    assignment_id:Mapped[int]=mapped_column(ForeignKey('reviewer_assignments.id'),unique=True)
    rfi_id:Mapped[int]=mapped_column(ForeignKey('rfis.id'),index=True)
    reviewer_id:Mapped[int]=mapped_column(ForeignKey('users.id'),index=True)
    recommendation:Mapped[str]=mapped_column(String(50))
    comment:Mapped[str]=mapped_column(Text)
    reviewed_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
    # UI design v1 sign-off: identity of the authenticated user and the server time are recorded; no signature image is generated.
    reviewer_name_snapshot:Mapped[str|None]=mapped_column(String(150),nullable=True)
    reviewer_role_snapshot:Mapped[str|None]=mapped_column(String(60),nullable=True)
    attachment_count:Mapped[int|None]=mapped_column(Integer,nullable=True)

class Decision(Base):
    __tablename__='decisions'
    id:Mapped[int]=mapped_column(primary_key=True)
    rfi_id:Mapped[int]=mapped_column(ForeignKey('rfis.id'),index=True)
    revision_no:Mapped[int]=mapped_column(Integer)
    decision:Mapped[str]=mapped_column(String(40),index=True)
    comment:Mapped[str|None]=mapped_column(Text,nullable=True)
    override_used:Mapped[bool]=mapped_column(Boolean,default=False)
    override_reason:Mapped[str|None]=mapped_column(Text,nullable=True)
    decided_by:Mapped[int]=mapped_column(ForeignKey('users.id'))
    decided_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
    disposition_code:Mapped[str|None]=mapped_column(String(60),nullable=True)
    approved_from:Mapped[str|None]=mapped_column(String(255),nullable=True)
    approved_to:Mapped[str|None]=mapped_column(String(255),nullable=True)
    conditions:Mapped[str|None]=mapped_column(Text,nullable=True)
    decided_by_name_snapshot:Mapped[str|None]=mapped_column(String(150),nullable=True)
    designation_snapshot:Mapped[str|None]=mapped_column(String(100),nullable=True)


# Workflow stages at which RE/DRE (Category 2.1) may record a management remark with its own evidence.
REMARK_STAGES=('DOC01_REVIEW','ASSIGNMENT','SEQUENCE_CHANGE','REASSIGNMENT_RETURN','FINAL_DISPOSITION')


class ManagementRemark(Base):
    """A Category 2.1 management remark: a distinct record that owns its supporting attachments (UI design s.5, s.14).
    DRAFT remarks are visible only to their author. A remark is SUBMITTED (locked, with its files) by the workflow action it
    belongs to (assignment, sequence change, return, final disposition) or, at DOC_01 review, on its own."""
    __tablename__='management_remarks'
    id:Mapped[int]=mapped_column(primary_key=True)
    project_id:Mapped[int]=mapped_column(ForeignKey('projects.id'),index=True)
    rfi_id:Mapped[int|None]=mapped_column(ForeignKey('rfis.id'),nullable=True,index=True)
    summary_id:Mapped[int|None]=mapped_column(ForeignKey('rfi_summaries.id'),nullable=True,index=True)
    stage:Mapped[str]=mapped_column(String(30))
    author_id:Mapped[int]=mapped_column(ForeignKey('users.id'),index=True)
    author_role:Mapped[str]=mapped_column(String(60))
    author_name_snapshot:Mapped[str|None]=mapped_column(String(150),nullable=True)
    body:Mapped[str|None]=mapped_column(Text,nullable=True)
    status:Mapped[str]=mapped_column(String(20),default='DRAFT',index=True)
    decision_id:Mapped[int|None]=mapped_column(ForeignKey('decisions.id'),nullable=True)
    client_request_id:Mapped[str|None]=mapped_column(String(64),nullable=True,unique=True)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
    updated_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
    submitted_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    version:Mapped[int]=mapped_column(Integer,default=1)
    __table_args__=(UniqueConstraint('id','project_id',name='uq_mremark_id_project'),
                    CheckConstraint('rfi_id IS NOT NULL OR summary_id IS NOT NULL',name='ck_mremark_parent'),
                    CheckConstraint("stage IN ('DOC01_REVIEW','ASSIGNMENT','SEQUENCE_CHANGE','REASSIGNMENT_RETURN','FINAL_DISPOSITION')",name='ck_mremark_stage'),
                    CheckConstraint("status IN ('DRAFT','SUBMITTED','DISCARDED')",name='ck_mremark_status'))


class Attachment(Base):
    __tablename__='attachments'
    id:Mapped[int]=mapped_column(primary_key=True)
    entity_type:Mapped[str]=mapped_column(String(30),index=True)
    entity_id:Mapped[int]=mapped_column(Integer,index=True)
    original_name:Mapped[str]=mapped_column(String(255))
    stored_name:Mapped[str]=mapped_column(String(255))
    content_type:Mapped[str|None]=mapped_column(String(150),nullable=True)
    size_bytes:Mapped[int]=mapped_column(Integer)
    description:Mapped[str|None]=mapped_column(String(255),nullable=True)
    uploaded_by:Mapped[int]=mapped_column(ForeignKey('users.id'))
    uploaded_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
    is_active:Mapped[bool]=mapped_column(Boolean,default=True)
    # ---- UI design v1 evidence architecture (additive; see docs/ui-upgrade/ATTACHMENT_ARCHITECTURE.md)
    # attachment_kind: RECORD (contractor enclosure / batch / daily progress / pre-v1 files),
    #                  MANAGEMENT_REMARK (Category 2.1 path), INSPECTOR_REVIEW (Category 2.2 path).
    attachment_kind:Mapped[str|None]=mapped_column(String(30),nullable=True,default='RECORD',index=True)
    project_id:Mapped[int|None]=mapped_column(ForeignKey('projects.id'),nullable=True,index=True)
    rfi_id:Mapped[int|None]=mapped_column(ForeignKey('rfis.id'),nullable=True,index=True)
    summary_id:Mapped[int|None]=mapped_column(ForeignKey('rfi_summaries.id'),nullable=True,index=True)
    management_remark_id:Mapped[int|None]=mapped_column(Integer,nullable=True,index=True)
    assignment_id:Mapped[int|None]=mapped_column(Integer,nullable=True,index=True)
    review_id:Mapped[int|None]=mapped_column(ForeignKey('reviews.id'),nullable=True)
    amendment_id:Mapped[int|None]=mapped_column(ForeignKey('rfi_amendments.id'),nullable=True,index=True)
    workflow_stage:Mapped[str|None]=mapped_column(String(40),nullable=True)
    author_role:Mapped[str|None]=mapped_column(String(60),nullable=True)
    sha256:Mapped[str|None]=mapped_column(String(64),nullable=True)
    upload_status:Mapped[str|None]=mapped_column(String(20),nullable=True,default='COMPLETE')   # COMPLETE / PENDING_APPROVAL / REJECTED
    scan_status:Mapped[str|None]=mapped_column(String(20),nullable=True,default='NOT_SCANNED')  # NOT_SCANNED / CLEAN / ERROR
    scanned_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    version_no:Mapped[int|None]=mapped_column(Integer,nullable=True,default=1)
    supersedes_id:Mapped[int|None]=mapped_column(ForeignKey('attachments.id'),nullable=True)
    superseded_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    locked_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    upload_token:Mapped[str|None]=mapped_column(String(64),nullable=True)
    removed_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    removed_by:Mapped[int|None]=mapped_column(ForeignKey('users.id'),nullable=True)
    __table_args__=(
        UniqueConstraint('uploaded_by','upload_token',name='uq_attachment_upload_token'),
        # A remark's evidence must belong to the remark's project; a review's evidence to the review's RFI.
        ForeignKeyConstraint(['management_remark_id','project_id'],['management_remarks.id','management_remarks.project_id'],name='fk_attachment_remark_project'),
        ForeignKeyConstraint(['assignment_id','rfi_id'],['reviewer_assignments.id','reviewer_assignments.rfi_id'],name='fk_attachment_assignment_rfi'),
        CheckConstraint("(attachment_kind='MANAGEMENT_REMARK' AND management_remark_id IS NOT NULL AND assignment_id IS NULL AND project_id IS NOT NULL)"
                        " OR (attachment_kind='INSPECTOR_REVIEW' AND assignment_id IS NOT NULL AND rfi_id IS NOT NULL AND management_remark_id IS NULL AND project_id IS NOT NULL)"
                        " OR (attachment_kind='RECORD' AND management_remark_id IS NULL AND assignment_id IS NULL)",name='ck_attachment_path'),
    )

class DailyProgress(Base):
    __tablename__='daily_progress'
    id:Mapped[int]=mapped_column(primary_key=True)
    project_id:Mapped[int]=mapped_column(ForeignKey('projects.id'),index=True)
    progress_date:Mapped[date]=mapped_column(Date)
    work_item:Mapped[str]=mapped_column(String(150),index=True)
    description:Mapped[str]=mapped_column(Text)
    chainage_from:Mapped[str|None]=mapped_column(String(50),nullable=True)
    chainage_to:Mapped[str|None]=mapped_column(String(50),nullable=True)
    side:Mapped[str|None]=mapped_column(String(50),nullable=True)
    quantity:Mapped[float|None]=mapped_column(Float,nullable=True)
    unit:Mapped[str|None]=mapped_column(String(30),nullable=True)
    status:Mapped[str]=mapped_column(String(30),default='DRAFT',index=True)
    remarks:Mapped[str|None]=mapped_column(Text,nullable=True)
    review_comment:Mapped[str|None]=mapped_column(Text,nullable=True)
    confirmation_comment:Mapped[str|None]=mapped_column(Text,nullable=True)
    created_by:Mapped[int]=mapped_column(ForeignKey('users.id'))
    reviewed_by:Mapped[int|None]=mapped_column(ForeignKey('users.id'),nullable=True)
    reviewed_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    confirmed_by:Mapped[int|None]=mapped_column(ForeignKey('users.id'),nullable=True)
    confirmed_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)

class DailyProgressRfi(Base):
    __tablename__='daily_progress_rfis'
    id:Mapped[int]=mapped_column(primary_key=True)
    daily_progress_id:Mapped[int]=mapped_column(ForeignKey('daily_progress.id'),index=True)
    rfi_id:Mapped[int]=mapped_column(ForeignKey('rfis.id'),index=True)
    __table_args__=(UniqueConstraint('daily_progress_id','rfi_id',name='uq_dp_rfi'),)

class Notification(Base):
    __tablename__='notifications'
    id:Mapped[int]=mapped_column(primary_key=True)
    user_id:Mapped[int]=mapped_column(ForeignKey('users.id'),index=True)
    title:Mapped[str]=mapped_column(String(180))
    message:Mapped[str]=mapped_column(Text)
    entity_type:Mapped[str|None]=mapped_column(String(30),nullable=True)
    entity_id:Mapped[int|None]=mapped_column(Integer,nullable=True)
    project_id:Mapped[int|None]=mapped_column(Integer,nullable=True,index=True)
    is_read:Mapped[bool]=mapped_column(Boolean,default=False)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)

class AuditLog(Base):
    __tablename__='audit_logs'
    id:Mapped[int]=mapped_column(primary_key=True)
    user_id:Mapped[int]=mapped_column(ForeignKey('users.id'),index=True)
    entity_type:Mapped[str]=mapped_column(String(50),index=True)
    entity_id:Mapped[int]=mapped_column(Integer,index=True)
    action:Mapped[str]=mapped_column(String(60),index=True)
    details:Mapped[str|None]=mapped_column(Text,nullable=True)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow,index=True)
    project_id:Mapped[int|None]=mapped_column(Integer,nullable=True,index=True)
    before_json:Mapped[str|None]=mapped_column(Text,nullable=True)
    after_json:Mapped[str|None]=mapped_column(Text,nullable=True)


class RfiStatusHistory(Base):
    __tablename__='rfi_status_history'
    id:Mapped[int]=mapped_column(primary_key=True)
    rfi_id:Mapped[int]=mapped_column(ForeignKey('rfis.id'),index=True)
    workflow_status:Mapped[str]=mapped_column(String(40),index=True)
    decision:Mapped[str|None]=mapped_column(String(40),nullable=True)
    changed_by:Mapped[int]=mapped_column(ForeignKey('users.id'))
    reason:Mapped[str|None]=mapped_column(Text,nullable=True)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow,index=True)


class RfiAmendment(Base):
    """Controlled amendment of submitted DOC_01 data (SRS 5.4 / 11.2). Original values are kept."""
    __tablename__='rfi_amendments'
    id:Mapped[int]=mapped_column(primary_key=True)
    rfi_id:Mapped[int]=mapped_column(ForeignKey('rfis.id'),index=True)
    project_id:Mapped[int]=mapped_column(ForeignKey('projects.id'),index=True)
    changes_json:Mapped[str]=mapped_column(Text)       # {"field": {"old": .., "new": ..}}
    reason:Mapped[str]=mapped_column(Text)
    status:Mapped[str]=mapped_column(String(20),default='PENDING',index=True)  # PENDING / APPROVED / REJECTED
    requested_by:Mapped[int]=mapped_column(ForeignKey('users.id'))
    requested_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
    resolved_by:Mapped[int|None]=mapped_column(ForeignKey('users.id'),nullable=True)
    resolved_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    resolution_comment:Mapped[str|None]=mapped_column(Text,nullable=True)
    # UI design v1: NULL/'FIELDS' = DOC_01 field amendment (SRS v1.0); 'REVIEW' / 'REMARK' = correction of a locked inspector
    # review or management remark (new comment text and/or new evidence versions). Evidence amendments start as DRAFT.
    amendment_type:Mapped[str|None]=mapped_column(String(20),nullable=True)
    target_assignment_id:Mapped[int|None]=mapped_column(ForeignKey('reviewer_assignments.id'),nullable=True)
    target_remark_id:Mapped[int|None]=mapped_column(ForeignKey('management_remarks.id'),nullable=True)


class IssuedDocument(Base):
    """Immutable snapshot of a document as issued (e.g. completed DOC_03 PDF at decision time)."""
    __tablename__='issued_documents'
    id:Mapped[int]=mapped_column(primary_key=True)
    rfi_id:Mapped[int]=mapped_column(ForeignKey('rfis.id'),index=True)
    project_id:Mapped[int]=mapped_column(ForeignKey('projects.id'),index=True)
    revision_no:Mapped[int]=mapped_column(Integer)
    doc_type:Mapped[str]=mapped_column(String(20))
    stored_name:Mapped[str]=mapped_column(String(255))
    sha256:Mapped[str]=mapped_column(String(64))
    issued_by:Mapped[int]=mapped_column(ForeignKey('users.id'))
    issued_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)


class RegisterView(Base):
    """A user's saved DOC_02 register view (filters, sort, visible columns)."""
    __tablename__='register_views'
    id:Mapped[int]=mapped_column(primary_key=True)
    user_id:Mapped[int]=mapped_column(ForeignKey('users.id'),index=True)
    project_id:Mapped[int|None]=mapped_column(ForeignKey('projects.id'),nullable=True)
    name:Mapped[str]=mapped_column(String(80))
    config_json:Mapped[str]=mapped_column(Text)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
    updated_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
    __table_args__=(UniqueConstraint('user_id','project_id','name',name='uq_register_view_name'),)
