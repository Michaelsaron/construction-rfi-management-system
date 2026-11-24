/**
 * API contracts shared by the React web app / PWA and the planned Expo (React Native) app.
 * Both clients use the same FastAPI backend, accounts, permissions and workflow. See docs/api/API_CONTRACTS.md.
 * The backend is the authority for every permission; these types only describe the payloads.
 */
export type Category = '1' | '2.1' | '2.2' | '2.3' | '3';
export type AttachmentKind = 'RECORD' | 'MANAGEMENT_REMARK' | 'INSPECTOR_REVIEW';
export type RemarkStage = 'DOC01_REVIEW' | 'ASSIGNMENT' | 'SEQUENCE_CHANGE' | 'REASSIGNMENT_RETURN' | 'FINAL_DISPOSITION';

export interface Membership { project_id: number; code: string; name: string; role: string; role_label: string; category: Category; deputy_label: string }
export interface Me { id: number; name: string; email: string; role: string; is_admin: boolean; must_change_password: boolean; memberships: Membership[] }

export interface Evidence {
  id: number; original_name: string; content_type: string | null; size_bytes: number; uploaded_by: number; uploaded_by_name?: string; uploaded_at: string;
  attachment_kind: AttachmentKind; kind_label: string; project_id: number | null; rfi_id: number | null; summary_id: number | null;
  management_remark_id: number | null; assignment_id: number | null; review_id: number | null; amendment_id: number | null;
  workflow_stage: string | null; author_role: string | null; author_role_label?: string | null; sha256: string | null;
  upload_status: 'COMPLETE' | 'PENDING_APPROVAL' | 'REJECTED'; scan_status: 'NOT_SCANNED' | 'CLEAN' | 'ERROR';
  version_no: number; supersedes_id: number | null; superseded_at: string | null; locked: boolean; locked_at: string | null; removed: boolean;
  previewable: boolean; duplicate?: boolean; stage_label?: string; rfi_number?: string;
}
export interface ManagementRemark {
  id: number; project_id: number; rfi_id: number | null; summary_id: number | null; stage: RemarkStage; stage_label: string;
  author_id: number; author_name: string; author_role: string; author_role_label: string; body: string | null;
  status: 'DRAFT' | 'SUBMITTED' | 'DISCARDED'; decision_id: number | null; submitted_at: string | null; version: number; editable: boolean; files: Evidence[];
}
export interface UploadPolicy { allowed_extensions: string[]; max_file_mb: number; max_files_per_record: number }
export interface ReviewWorkspace {
  assignment: { id: number; rfi_id: number; sequence_no: number; reviewer_role: string; reviewer_role_label: string; status: 'PENDING' | 'ACTIVE' | 'COMPLETED' | 'REPLACED';
                user_id: number; user_name: string; activated_at: string | null; completed_at: string | null };
  draft_comment: string | null; draft_saved_at: string | null;
  review: { comment: string; reviewed_at: string; reviewer_name: string; attachment_count: number | null } | null;
  files: Evidence[]; can_edit: boolean; policy: UploadPolicy;
}
export interface TimelineStage {
  key: string; title: string; status: 'done' | 'active' | 'pending' | 'replaced' | 'locked'; at?: string | null; actor?: string | null; actor_role?: string | null;
  detail?: string | null; comment?: string | null; sequence_no?: number; assignment_id?: number; due_at?: string | null; overdue?: boolean;
  remarks?: ManagementRemark[]; files?: Evidence[]; evidence_count?: number; change_reason?: string | null; approved_section?: { from: string; to: string } | null;
}
export interface Timeline { rfi: any; my_role: string; stages: TimelineStage[]; decision_locked: boolean; can_decide: boolean }
export interface CompletedRecord {
  rfi: any; project: { id: number; code: string; name: string; contract_number: string | null }; finalised_at: string | null;
  disposition: { code: string; label: string } | null;
  sections: { key: string; section: string; content: string; by?: string; at?: string; designation?: string; remark?: string; files: Evidence[]; sequence_no?: number }[];
  management_remarks: ManagementRemark[]; attachment_index: Evidence[];
  issued_document: { id: number; issued_at: string; sha256: string; issued_by_name: string } | null;
  legacy_document: { available: false; label: string } | null; read_only: true; can_download_bundle: boolean;
}
export interface RegisterPage { total: number; limit: number; offset: number; filters: Record<string, any>; hidden_fields_allowed: boolean | null; items: any[] }
