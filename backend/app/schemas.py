from datetime import date
from pydantic import BaseModel,EmailStr
class LoginIn(BaseModel): email:EmailStr; password:str
class Token(BaseModel): access_token:str; token_type:str='bearer'
class UserCreate(BaseModel): full_name:str; email:EmailStr; password:str; role:str; project_ids:list[int]=[]
class ProjectCreate(BaseModel): code:str; name:str; project_type:str='ROAD'; contract_number:str|None=None; employer:str|None=None; consultant:str|None=None; contractor:str|None=None
class MasterCreate(BaseModel): project_id:int|None=None; category:str; code:str|None=None; value:str; parent_value:str|None=None
class ReviewerRuleCreate(BaseModel): project_id:int; work_item:str; reviewer_role:str; required:bool=True
class SummaryCreate(BaseModel): project_id:int; summary_reference:str; submission_date:date; original_submitter:str|None=None; entry_source:str='CONTRACTOR_PORTAL'; remarks:str|None=None
class RfiCreate(BaseModel): project_id:int; summary_id:int|None=None; rfi_number:str; revision_no:int=0; contractor_request:str|None=None; work_item:str; description:str; structure_type:str|None=None; test_name:str|None=None; boq_item:str|None=None; road_type:str|None=None; direction:str|None=None; side:str|None=None; fill_layer:str|None=None; chainage_from:str|None=None; chainage_to:str|None=None; location_text:str|None=None; material_source_type:str|None=None; material_source:str|None=None; material_source_cut_section:str|None=None; material_source_designation:str|None=None; material_destination_designation:str|None=None; requested_date:date|None=None; inspection_date:date|None=None; work_status:str|None=None; approved_from:str|None=None; approved_to:str|None=None; application_rate:str|None=None; quantity_g40:str|None=None; all_quantity:str|None=None; legacy_file_path:str|None=None; legacy_ipc_included:str|None=None; legacy_ipc_file_path:str|None=None; remarks:str|None=None
class AssignmentCreate(BaseModel): user_id:int; reviewer_role:str; required:bool=True
class ReviewCreate(BaseModel): assignment_id:int; recommendation:str; comment:str
class DecisionCreate(BaseModel): decision:str; comment:str|None=None; override_used:bool=False; override_reason:str|None=None
class RevisionCreate(BaseModel): reason:str
class DailyProgressCreate(BaseModel):
    project_id:int
    progress_date:date
    work_item:str
    description:str
    chainage_from:str|None=None
    chainage_to:str|None=None
    side:str|None=None
    quantity:float|None=None
    unit:str|None=None
    remarks:str|None=None
    rfi_ids:list[int]=[]

class DailyProgressComment(BaseModel):
    comment:str

class ForgotPasswordIn(BaseModel): email:EmailStr
class ResetPasswordIn(BaseModel): token:str; new_password:str
class AdminResetPasswordIn(BaseModel): new_password:str

class RfiUpdate(BaseModel):
    version:int
    contractor_request:str|None=None
    work_item:str|None=None
    description:str|None=None
    structure_type:str|None=None
    test_name:str|None=None
    boq_item:str|None=None
    road_type:str|None=None
    direction:str|None=None
    side:str|None=None
    fill_layer:str|None=None
    chainage_from:str|None=None
    chainage_to:str|None=None
    location_text:str|None=None
    material_source_type:str|None=None
    material_source:str|None=None
    requested_date:date|None=None
    inspection_date:date|None=None
    work_status:str|None=None
    remarks:str|None=None
    edit_reason:str|None=None
class StateChange(BaseModel): reason:str

class MasterUpdate(BaseModel): value:str; parent_value:str|None=None; code:str|None=None

class ChangePasswordIn(BaseModel): current_password:str; new_password:str
class UserProjectsIn(BaseModel): project_ids:list[int]=[]
