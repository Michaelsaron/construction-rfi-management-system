"""Workflow monitoring timeline (UI design s.6), Completed DOC_03 record (s.11) and the evidence bundle."""
import csv
import io
import json
import tempfile
import zipfile
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select, or_, and_
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import (Rfi, RfiSummary, ReviewerAssignment, Review, Decision, ManagementRemark, Attachment, IssuedDocument, Project, User, RfiStatusHistory)
from app.security import current_user
from app import authz
from app.project_settings import get_settings, disposition
from app.services import evidence as ev
from app.services.audit import log
from app.services.documents import stage_text
from app.services.workflow import STATUS_LABELS, rfi_dict
from app.routers.evidence import remark_out, legacy_document

router = APIRouter(prefix='/rfis', tags=['Records'])


def _remarks(db, u, r: Rfi, stages=None):
    conds = [ManagementRemark.rfi_id == r.id]
    if r.summary_id: conds.append(and_(ManagementRemark.rfi_id.is_(None), ManagementRemark.summary_id == r.summary_id))
    q = select(ManagementRemark).where(or_(*conds), ManagementRemark.status == 'SUBMITTED')
    if stages: q = q.where(ManagementRemark.stage.in_(stages))
    out = []
    for m in db.scalars(q.order_by(ManagementRemark.submitted_at)):
        files = ev.visible(db, u, list(db.scalars(select(Attachment).where(Attachment.management_remark_id == m.id, *ev.live_clause()).order_by(Attachment.id))))
        out.append(remark_out(db, m, u, files))
    return out


def _review_files(db, u, a):
    return ev.visible(db, u, list(db.scalars(select(Attachment).where(Attachment.assignment_id == a.id, *ev.live_clause()).order_by(Attachment.id))))


@router.get('/{rid}/timeline')
def timeline(rid: int, db: Session = Depends(get_db), u: User = Depends(current_user)):
    """Sequential workflow monitoring: every stage with actor, role, time, comments, evidence and status."""
    r, role = authz.load_rfi(db, u, rid)
    st = get_settings(db.get(Project, r.project_id))
    s = db.get(RfiSummary, r.summary_id) if r.summary_id else None
    assigns = list(db.scalars(select(ReviewerAssignment).where(ReviewerAssignment.rfi_id == rid).order_by(ReviewerAssignment.sequence_no, ReviewerAssignment.id)))
    reviews = {x.assignment_id: x for x in db.scalars(select(Review).where(Review.rfi_id == rid))}
    dec = db.scalar(select(Decision).where(Decision.rfi_id == rid, Decision.revision_no == r.revision_no).order_by(Decision.id.desc()))
    nm = ev.names_for(db, [a.user_id for a in assigns] + [a.assigned_by for a in assigns] + [s.submitted_by if s else None, s.received_by if s else None, r.received_by,
                                                                                              dec.decided_by if dec else None])
    now = datetime.utcnow()
    stages = []
    if r.provenance == 'LEGACY_IMPORT':
        stages.append({'key': 'LEGACY', 'title': 'Imported historical record', 'status': 'done', 'at': r.created_at,
                       'detail': f'Historical RFI_Status: {r.legacy_rfi_status or "(blank)"}. No DOC_01 batch or DOC_03 reviews were recorded in the system.'})
        return {'rfi': rfi_dict(r), 'stages': stages, 'decision_locked': True, 'legacy_document': legacy_document(r)}
    stages.append({'key': 'DOC01_RECEIVED', 'title': 'DOC_01 received', 'status': 'done' if s and s.submitted_at else 'pending',
                   'at': s.submitted_at if s else None, 'actor': nm.get(s.submitted_by) if s else None, 'actor_role': 'Contractor (Category 3)',
                   'detail': f'Batch {s.summary_reference}' if s else None})
    rem_review = _remarks(db, u, r, ['DOC01_REVIEW', 'REASSIGNMENT_RETURN'])
    rec_at = r.received_at or (s.received_at if s else None); rec_by = r.received_by or (s.received_by if s else None)
    first_assign = min((a.assigned_at for a in assigns), default=None)
    stages.append({'key': 'MANAGEMENT_REVIEW', 'title': 'Management review', 'status': 'done' if (rec_at or rem_review or first_assign) else ('active' if r.workflow_status in ('SUBMITTED', 'ACTIVATED') else 'pending'),
                   'at': rec_at or (rem_review[0]['submitted_at'] if rem_review else None), 'actor': nm.get(rec_by) if rec_by else (rem_review[0]['author_name'] if rem_review else None),
                   'actor_role': 'RE / DRE (Category 2.1)', 'remarks': rem_review})
    rem_assign = _remarks(db, u, r, ['ASSIGNMENT', 'SEQUENCE_CHANGE'])
    if first_assign:
        first = next(a for a in assigns if a.assigned_at == first_assign)
        changes = [{'at': a.assigned_at, 'reason': a.change_reason} for a in assigns if a.status == 'REPLACED' and a.change_reason]
        stages.append({'key': 'ASSIGNMENT', 'title': 'Assignment saved', 'status': 'done', 'at': first_assign, 'actor': nm.get(first.assigned_by),
                       'actor_role': 'RE / DRE (Category 2.1)', 'detail': ' → '.join(authz.ROLE_LABELS.get(a.reviewer_role, a.reviewer_role) for a in assigns if a.status != 'REPLACED'),
                       'remarks': rem_assign, 'sequence_changes': changes})
    else:
        stages.append({'key': 'ASSIGNMENT', 'title': 'Assignment', 'status': 'active' if r.workflow_status in ('SUBMITTED', 'ACTIVATED') else 'pending', 'remarks': rem_assign})
    overdue_h = st['overdue_hours']
    for a in assigns:
        rv = reviews.get(a.id)
        status = {'COMPLETED': 'done', 'ACTIVE': 'active', 'PENDING': 'pending', 'REPLACED': 'replaced'}.get(a.status, 'pending')
        files = _review_files(db, u, a) if (rv or a.user_id == u.id) else []
        due = a.activated_at + timedelta(hours=overdue_h) if a.status == 'ACTIVE' and a.activated_at else None
        stages.append({'key': f'INSPECTOR_{a.id}', 'assignment_id': a.id, 'title': authz.ROLE_LABELS.get(a.reviewer_role, a.reviewer_role), 'sequence_no': a.sequence_no,
                       'status': status, 'actor': rv.reviewer_name_snapshot if rv and rv.reviewer_name_snapshot else nm.get(a.user_id),
                       'actor_role': f'{authz.ROLE_LABELS.get(a.reviewer_role, a.reviewer_role)} (Category 2.2)',
                       'at': rv.reviewed_at if rv else (a.activated_at if a.status == 'ACTIVE' else None), 'due_at': due, 'overdue': bool(due and due < now),
                       'comment': rv.comment if rv else None, 'change_reason': a.change_reason if a.status == 'REPLACED' else None,
                       'files': [ev.out(f, ev.names_for(db, [f.uploaded_by])) for f in files],
                       'evidence_count': rv.attachment_count if rv and rv.attachment_count is not None else len(files)})
    rem_final = _remarks(db, u, r, ['FINAL_DISPOSITION'])
    disp = (disposition(st, dec.disposition_code) or {}) if dec and dec.disposition_code else {}
    open_reviews = [a for a in assigns if a.status in ('PENDING', 'ACTIVE')]
    stages.append({'key': 'FINAL_DECISION', 'title': 'RE / DRE decision',
                   'status': 'done' if dec else ('active' if r.workflow_status == 'AWAITING_DECISION' else 'locked'),
                   'at': dec.decided_at if dec else None, 'actor': (dec.decided_by_name_snapshot or nm.get(dec.decided_by)) if dec else None,
                   'actor_role': dec.designation_snapshot if dec and dec.designation_snapshot else 'RE / DRE (Category 2.1)',
                   'detail': disp.get('label') or (dec.decision if dec else ('Locked until all inspector reviews are submitted' if open_reviews or not assigns else 'Ready for final disposition')),
                   'comment': dec.comment if dec else None, 'remarks': rem_final,
                   'approved_section': {'from': dec.approved_from, 'to': dec.approved_to} if dec and (dec.approved_from or dec.approved_to) else None})
    return {'rfi': rfi_dict(r), 'my_role': role, 'stages': stages, 'decision_locked': r.workflow_status != 'AWAITING_DECISION',
            'can_decide': role in authz.MANAGEMENT and r.workflow_status == 'AWAITING_DECISION' and r.record_state == 'ACTIVE'}


def _issued(db, r: Rfi):
    return db.scalar(select(IssuedDocument).where(IssuedDocument.rfi_id == r.id, IssuedDocument.revision_no == r.revision_no, IssuedDocument.doc_type == 'DOC03')
                     .order_by(IssuedDocument.id.desc()))


@router.get('/{rid}/completed-record')
def completed_record(rid: int, db: Session = Depends(get_db), u: User = Depends(current_user)):
    """Completed DOC_03: sections, comments, final disposition and attachment index (read-only for every role)."""
    r, role = authz.load_rfi(db, u, rid)
    if r.workflow_status != 'COMPLETED':
        raise HTTPException(409, f'RFI {r.rfi_number} is not completed yet ({STATUS_LABELS.get(r.workflow_status, r.workflow_status)})')
    p = db.get(Project, r.project_id); st = get_settings(p)
    assigns = [a for a in db.scalars(select(ReviewerAssignment).where(ReviewerAssignment.rfi_id == rid, ReviewerAssignment.status == 'COMPLETED').order_by(ReviewerAssignment.sequence_no))]
    reviews = {x.assignment_id: x for x in db.scalars(select(Review).where(Review.rfi_id == rid))}
    dec = db.scalar(select(Decision).where(Decision.rfi_id == rid, Decision.revision_no == r.revision_no).order_by(Decision.id.desc()))
    issued = _issued(db, r)
    files = ev.rfi_evidence(db, u, rid)
    nm = ev.names_for(db, [a.user_id for a in assigns] + [f.uploaded_by for f in files] + [dec.decided_by if dec else None, issued.issued_by if issued else None])
    sections = [{'key': 'WORK', 'section': 'Work details', 'content': ' · '.join(x for x in [r.contractor_request or r.description, f'BOQ {r.boq_item}' if r.boq_item else None] if x),
                 'files': [ev.out(f, nm) for f in files if f.attachment_kind in ('RECORD', None)]}]
    for a in assigns:
        rv = reviews.get(a.id)
        fs = [f for f in files if f.assignment_id == a.id]
        sections.append({'key': f'REVIEW_{a.id}', 'section': authz.ROLE_LABELS.get(a.reviewer_role, a.reviewer_role), 'sequence_no': a.sequence_no,
                         'by': rv.reviewer_name_snapshot or nm.get(a.user_id) if rv else nm.get(a.user_id), 'at': rv.reviewed_at if rv else None,
                         'content': rv.comment if rv else '', 'files': [ev.out(f, nm) for f in fs]})
    remarks = _remarks(db, u, r)
    disp = (disposition(st, dec.disposition_code) or {}) if dec and dec.disposition_code else {}
    final_files = [f for m in remarks if m['stage'] == 'FINAL_DISPOSITION' for f in m['files']]
    if dec:
        sections.append({'key': 'DISPOSITION', 'section': f'RE/{st["deputy_label"]} disposition', 'by': dec.decided_by_name_snapshot or nm.get(dec.decided_by),
                         'designation': dec.designation_snapshot, 'at': dec.decided_at, 'content': disp.get('label') or dec.decision, 'remark': dec.comment,
                         'conditions': dec.conditions, 'approved_section': {'from': dec.approved_from, 'to': dec.approved_to} if (dec.approved_from or dec.approved_to) else None,
                         'files': final_files})
    return {'rfi': rfi_dict(r), 'my_role': role, 'project': {'id': p.id, 'code': p.code, 'name': p.name, 'contract_number': p.contract_number},
            'finalised_at': dec.decided_at if dec else None, 'disposition': {'code': dec.disposition_code, 'label': disp.get('label') or dec.decision} if dec else None,
            'sections': sections, 'management_remarks': remarks,
            'attachment_index': [ev.out(f, nm, {'stage_label': stage_text(f)}) for f in files],
            'issued_document': {'id': issued.id, 'issued_at': issued.issued_at, 'sha256': issued.sha256, 'issued_by_name': nm.get(issued.issued_by)} if issued else None,
            'legacy_document': legacy_document(r), 'read_only': True,
            'can_download_bundle': role in authz.MANAGEMENT | authz.OFFICE | {authz.ADMIN} or (role in authz.INSPECTORS and bool(files))
                                   or (role in authz.CONTRACTOR and bool(st.get('contractor_evidence_access')))}


def _safe(name: str) -> str:
    keep = ''.join(c if c.isalnum() or c in '-_. ' else '_' for c in (name or 'file'))
    return keep.strip()[:120] or 'file'


@router.get('/{rid}/evidence-bundle.zip')
def evidence_bundle(rid: int, db: Session = Depends(get_db), u: User = Depends(current_user)):
    """ZIP: the DOC_03 PDF exactly as issued, every original attachment the user may open, and a manifest (author, stage, time, SHA-256).
    Access is checked for every file; files that fail their integrity check are left out and listed as such."""
    r, role = authz.load_rfi(db, u, rid)
    if r.workflow_status != 'COMPLETED':
        raise HTTPException(409, 'The evidence bundle is available for completed RFIs')
    st = get_settings(db.get(Project, r.project_id))
    if role in authz.CONTRACTOR and not st.get('contractor_evidence_access'):
        raise HTTPException(403, 'Your project role does not give access to inspection evidence (pending client decision UD-04)')
    issued = _issued(db, r)
    files = ev.rfi_evidence(db, u, rid)          # visibility checked per file inside
    nm = ev.names_for(db, [f.uploaded_by for f in files])
    manifest = {'rfi_number': r.rfi_number, 'revision_no': r.revision_no, 'rfi_id': r.id, 'project_id': r.project_id,
                'generated_at': datetime.utcnow().isoformat() + 'Z', 'generated_by': u.full_name, 'generated_by_role': role, 'files': [], 'excluded': []}
    spool = tempfile.SpooledTemporaryFile(max_size=64 * 1024 * 1024)
    with zipfile.ZipFile(spool, 'w', zipfile.ZIP_DEFLATED) as z:
        if issued:
            path = ev.file_path(issued)
            import hashlib
            data = path.read_bytes() if path.exists() else None
            if data is not None and hashlib.sha256(data).hexdigest() == issued.sha256:
                name = f'DOC03_{_safe(r.rfi_number)}_rev{r.revision_no}_issued.pdf'
                z.writestr(name, data)
                manifest['issued_doc03'] = {'file': name, 'issued_at': issued.issued_at.isoformat(), 'sha256': issued.sha256}
            else:
                manifest['issued_doc03'] = {'error': 'Issued DOC_03 missing or failed its integrity check; not included', 'sha256': issued.sha256}
        else:
            manifest['issued_doc03'] = {'error': 'No issued DOC_03 snapshot exists for this revision (historical record or issuance failure). Nothing was regenerated.'}
        for i, a in enumerate(files, 1):
            ev.can_view_attachment(db, u, a)  # explicit per-file check (defence in depth)
            entry = {'n': i, 'attachment_id': a.id, 'original_name': a.original_name, 'kind': a.attachment_kind or 'RECORD', 'stage': stage_text(a),
                     'author': nm.get(a.uploaded_by), 'author_role': a.author_role, 'uploaded_at': a.uploaded_at.isoformat() if a.uploaded_at else None,
                     'size_bytes': a.size_bytes, 'sha256': a.sha256, 'version_no': a.version_no or 1, 'locked': a.locked_at is not None}
            path = ev.file_path(a)
            if not path.exists() or not ev.verify_integrity(a):
                manifest['excluded'].append({**entry, 'reason': 'stored file missing or checksum mismatch'})
                continue
            entry['file'] = f'evidence/{i:02d}_{_safe(stage_text(a))}_{_safe(a.original_name)}'
            z.write(path, entry['file'])
            manifest['files'].append(entry)
        if r.legacy_file_path or r.legacy_ipc_file_path:
            manifest['legacy_document'] = 'File unavailable — migration required (historical shared-drive document, not migrated)'
        z.writestr('manifest.json', json.dumps(manifest, indent=2, default=str))
        buf = io.StringIO(); w = csv.writer(buf)
        w.writerow(['n', 'file', 'original_name', 'kind', 'stage', 'author', 'author_role', 'uploaded_at_utc', 'size_bytes', 'sha256', 'version'])
        for e in manifest['files']:
            w.writerow([e['n'], e['file'], e['original_name'], e['kind'], e['stage'], e['author'], e['author_role'], e['uploaded_at'], e['size_bytes'], e['sha256'], e['version_no']])
        z.writestr('manifest.csv', buf.getvalue())
        z.writestr('README.txt', f'Evidence bundle for RFI {r.rfi_number} Rev {r.revision_no}\nGenerated {manifest["generated_at"]} by {u.full_name} ({role}).\n'
                                 'The DOC_03 PDF is the document as issued at the final decision (not regenerated).\n'
                                 'Each file is listed in manifest.csv / manifest.json with its author, workflow stage, upload time (UTC) and SHA-256.\n'
                                 'Only files the requesting user is authorised to open are included.\n')
    log(db, u.id, 'RFI', rid, 'EXPORT_EVIDENCE_BUNDLE', f'{len(manifest["files"])} file(s), {len(manifest["excluded"])} excluded', project_id=r.project_id, commit=True)
    spool.seek(0)
    fname = f'evidence_{_safe(r.rfi_number).replace(" ", "_")}_rev{r.revision_no}.zip'
    return StreamingResponse(spool, media_type='application/zip', headers={'Content-Disposition': f'attachment; filename="{fname}"'})
