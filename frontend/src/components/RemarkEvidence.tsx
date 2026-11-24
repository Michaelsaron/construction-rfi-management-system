import React, { useEffect, useRef, useState } from 'react';
import { api, post, put, fmtDate, requestId } from '../lib/api';
import type { Evidence, ManagementRemark, RemarkStage } from '../lib/contracts';
import EvidencePanel, { FileRow } from './EvidencePanel';

export type RemarkDraft = {
  remark: ManagementRemark | null; files: Evidence[]; busy: boolean; ensure: () => Promise<ManagementRemark>;
  setFiles: (f: Evidence[]) => void; setBusy: (b: boolean) => void; reload: () => Promise<void>; discard: () => Promise<void>;
};

/** The signed-in RE/DRE's own draft management remark for one stage of an RFI or DOC_01 batch. Created on first need. */
export function useRemarkDraft(projectId: number | null | undefined, stage: RemarkStage, rfiId?: number | null, summaryId?: number | null): RemarkDraft {
  const [remark, setRemark] = useState<ManagementRemark | null>(null);
  const [files, setFiles] = useState<Evidence[]>([]);
  const [busy, setBusy] = useState(false);
  const pending = useRef<Promise<ManagementRemark> | null>(null);
  const q = rfiId ? `rfi_id=${rfiId}` : `summary_id=${summaryId}`;
  const reload = async () => {
    if (!projectId || (!rfiId && !summaryId)) return;
    const rows: ManagementRemark[] = await api(`/evidence/remarks?${q}`).catch(() => []);
    const mine = rows.find(r => r.editable && r.stage === stage && (rfiId ? r.rfi_id === rfiId : r.rfi_id === null));
    setRemark(mine || null); setFiles(mine?.files || []);
  };
  useEffect(() => { reload(); }, [projectId, stage, rfiId, summaryId]);
  const ensure = () => {
    if (remark) return Promise.resolve(remark);
    if (!pending.current) {
      pending.current = post('/evidence/remarks', { project_id: projectId, stage, rfi_id: rfiId || null, summary_id: rfiId ? null : summaryId, client_request_id: requestId() })
        .then((r: ManagementRemark) => { setRemark(r); return r; })
        .finally(() => { pending.current = null; });
    }
    return pending.current;
  };
  const discard = async () => { if (remark) { await api(`/evidence/remarks/${remark.id}`, { method: 'DELETE' }); setRemark(null); setFiles([]); } };
  return { remark, files, busy, ensure, setFiles, setBusy, reload, discard };
}

/** Attachment control placed directly under a management remark field (Category 2.1 path). */
export function RemarkEvidence({ draft, canEdit, title = 'Supporting evidence for this remark' }: { draft: RemarkDraft; canEdit: boolean; title?: string }) {
  return <>
    <EvidencePanel title={title} files={draft.files} canEdit={canEdit} onFiles={draft.setFiles} onBusy={draft.setBusy}
      target={async () => `/evidence/remarks/${(await draft.ensure()).id}/files`} emptyText="No files attached to this remark." />
    <div className="ev-hint">The remark and its files are recorded as your own management record; author and time are captured automatically.</div>
  </>;
}

/** Standalone DOC_01 review remark: write, attach, record (locks text and files). */
export function Doc01ReviewRemark({ projectId, summaryId, rfiId, onRecorded }: { projectId: number; summaryId?: number; rfiId?: number; onRecorded?: () => void }) {
  const draft = useRemarkDraft(projectId, 'DOC01_REVIEW', rfiId, summaryId);
  const [body, setBody] = useState('');
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState('');
  useEffect(() => { if (draft.remark?.body) setBody(draft.remark.body); }, [draft.remark?.id]);
  async function record() {
    if (!body.trim() && !draft.files.length) { setMsg('Write the remark or attach a file first.'); return; }
    setSaving(true); setMsg('');
    try {
      const r = await draft.ensure();
      await put(`/evidence/remarks/${r.id}`, { body });
      await post(`/evidence/remarks/${r.id}/submit`);
      setBody(''); await draft.reload(); setMsg('Remark recorded.'); onRecorded?.();
    } catch (e: any) { setMsg(e.message); } finally { setSaving(false); }
  }
  return <div className="stack">
    <div><label htmlFor="mgmt-remark">Management remark</label>
      <textarea id="mgmt-remark" value={body} onChange={e => setBody(e.target.value)} placeholder="e.g. Reviewed submitted list. Ensure prior layer test results accompany the inspection." /></div>
    <RemarkEvidence draft={draft} canEdit />
    {msg && <div className={`notice ${msg === 'Remark recorded.' ? 'ok' : 'err'}`}>{msg}</div>}
    <div className="actions" style={{ marginTop: 0 }}>
      <button type="button" className="btn success" disabled={saving || draft.busy} onClick={record}>{draft.busy ? 'Waiting for uploads…' : saving ? 'Recording…' : 'Record remark'}</button>
      {draft.remark && <button type="button" className="btn secondary" disabled={saving} onClick={() => { if (confirm('Discard this draft remark and its files?')) draft.discard().then(() => setBody('')); }}>Discard draft</button>}
    </div>
  </div>;
}

/** Read-only list of submitted management remarks with their evidence. */
export function RemarkList({ remarks, empty = 'No management remarks recorded.' }: { remarks: ManagementRemark[]; empty?: string }) {
  const shown = remarks.filter(r => r.status === 'SUBMITTED');
  if (!shown.length) return <div className="muted" style={{ fontSize: 13 }}>{empty}</div>;
  return <div className="stack">{shown.map(r => <div key={r.id} className="evidence" style={{ background: 'var(--surface)' }}>
    <div className="section-title" style={{ marginBottom: 6 }}><b>{r.stage_label}</b><span className="muted" style={{ fontSize: 12.5 }}>{r.author_name} · {r.author_role_label} · {fmtDate(r.submitted_at)}</span></div>
    {r.body && <div style={{ whiteSpace: 'pre-wrap' }}>{r.body}</div>}
    {r.files.length > 0 && <ul className="ev-list">{r.files.map(f => <FileRow key={f.id} f={f} />)}</ul>}
  </div>)}</div>;
}
