from datetime import datetime,date
from sqlalchemy import String,Integer,DateTime,Date,Text,Boolean,ForeignKey,UniqueConstraint,Float
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

class ProjectUser(Base):
    __tablename__='project_users'
    id:Mapped[int]=mapped_column(primary_key=True)
    project_id:Mapped[int]=mapped_column(ForeignKey('projects.id'),index=True)
    user_id:Mapped[int]=mapped_column(ForeignKey('users.id'),index=True)
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

class Review(Base):
    __tablename__='reviews'
    id:Mapped[int]=mapped_column(primary_key=True)
    assignment_id:Mapped[int]=mapped_column(ForeignKey('reviewer_assignments.id'),unique=True)
    rfi_id:Mapped[int]=mapped_column(ForeignKey('rfis.id'),index=True)
    reviewer_id:Mapped[int]=mapped_column(ForeignKey('users.id'),index=True)
    recommendation:Mapped[str]=mapped_column(String(50))
    comment:Mapped[str]=mapped_column(Text)
    reviewed_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)

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


class RfiStatusHistory(Base):
    __tablename__='rfi_status_history'
    id:Mapped[int]=mapped_column(primary_key=True)
    rfi_id:Mapped[int]=mapped_column(ForeignKey('rfis.id'),index=True)
    workflow_status:Mapped[str]=mapped_column(String(40),index=True)
    decision:Mapped[str|None]=mapped_column(String(40),nullable=True)
    changed_by:Mapped[int]=mapped_column(ForeignKey('users.id'))
    reason:Mapped[str|None]=mapped_column(Text,nullable=True)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow,index=True)
