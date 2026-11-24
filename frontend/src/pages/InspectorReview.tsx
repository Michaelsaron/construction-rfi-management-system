import React, { useEffect, useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api, post, put, getUser, fmtDate, fmtDay, loc, roleLabel } from '../lib/api';
import type { ReviewWorkspace, Evidence } from '../lib/contracts';
import { PageHeader, ConfirmDialog, ReadOnly, Loading, ErrorNote } from '../components/ui';
import EvidencePanel, { FileRow } from '../components/EvidencePanel';

const ORDER = ['', 'First', 'Second', 'Third'];
const draftKey = (aid: number) => `rfims.review.draft.${aid}`;
const store = { get: (k: string) => { try { return localStorage.getItem(k); } catch { return null; } }, set: (k: string, v: string) => { try { localStorage.setItem(k, v); } catch { /* */ } },
  del: (k: string) => { try { localStorage.removeItem(k); } catch { /* */ } } };

/** Category 2.2 — the inspector's own DOC_03 review (desktop and mobile). Only the active assigned inspector can edit. */
export default function InspectorReview() {
  const { id } = useParams();
  const me = getUser();
  const [d, setD] = useState<any>(null); const [ws, setWs] = useState<ReviewWorkspace | null>(null);
  const [err, setErr] = useState(''); const [comment, setComment] = useState(''); const [files, setFiles] = useState<Evidence[]>([]);
  const [busyUp, setBusyUp] = useState(false); const [saving, setSaving] = useState(''); const [confirm, setConfirm] = useState(false); const [sending, setSending] = useState(false);
  const [done, setDone] = useState<any>(null); const [now, setNow] = useState(new Date()); const [fix, setFix] = useState(false);
  const timer = useRef<any>(null);

  const load = async () => {
    setErr('');
    try {
      const x = await api(`/rfis/${id}`); setD(x);
      const mine = x.assignments.filter((a: any) => a.user_id === me.id && a.status !== 'REPLACED');
      const a = mine.find((m: any) => m.status === 'ACTIVE') || mine.find((m: any) => m.status === 'PENDING') || mine[mine.length - 1];
      if (!a) { setWs(null); return; }
      const w: ReviewWorkspace = await api(`/evidence/assignments/${a.id}`);
      setWs(w); setFiles(w.files);
      const local = store.get(draftKey(a.id));
      setComment(w.review?.comment ?? (local !== null && local !== (w.draft_comment || '') ? local : w.draft_comment || ''));
    } catch (e: any) { setErr(e.message); }
  };
  useEffect(() => { load(); }, [id]);
  useEffect(() => { const t = setInterval(() => setNow(new Date()), 30000); return () => clearInterval(t); }, []);

  const aid = ws?.assignment.id;
  const editable = !!ws?.can_edit;
  function onComment(v: string) {
    setComment(v);
    if (!aid || !editable) return;
    store.set(draftKey(aid), v);          // kept on this device even if the network drops
    clearTimeout(timer.current);
    timer.current = setTimeout(() => saveDraft(v, true), 2500);
  }
  async function saveDraft(v = comment, auto = false) {
    if (!aid) return;
    setSaving(auto ? 'Saving draft…' : 'Saving…');
    try { const r: any = await put(`/evidence/assignments/${aid}/draft`, { comment: v }); setSaving(`Draft saved ${fmtDate(r.draft_saved_at)}`); }
    catch (e: any) { setSaving(`Draft kept on this device only: ${e.message}`); }
  }
  async function submit() {
    setSending(true);
    try {
      clearTimeout(timer.current);
      const r: any = await post(`/rfis/${id}/review`, { assignment_id: aid, comment, attachment_count: files.length });
      store.del(draftKey(aid!)); setConfirm(false); setDone(r); await load();
    } catch (e: any) { setConfirm(false); alert(e.message); await load(); } finally { setSending(false); }
  }

  if (err) return <ErrorNote error={err} />;
  if (!d) return <Loading />;
  const r = d.rfi;
  if (!ws) return <><PageHeader title={`${r.rfi_number} · DOC_03 review`} back={{ to: '/my-inspections', label: 'My assigned RFIs' }} />
    <div className="notice">You do not hold an inspection turn on this RFI.</div></>;
  const a = ws.assignment;
  const live = d.assignments.filter((x: any) => x.status !== 'REPLACED');
  const current = live.find((x: any) => x.status === 'ACTIVE');
  const state = a.status === 'ACTIVE' && editable ? 'active' : a.status;
  const canFix = d.permissions.amend_review_assignment_ids?.includes(a.id);
  return <>
    <PageHeader title="Assigned inspection · DOC_03 review" back={{ to: '/my-inspections', label: 'My assigned RFIs' }}
      actions={<Link className="btn secondary" to={`/rfis/${id}/workflow`}>Workflow</Link>} />
    {done && <div className="notice ok" role="status">Review submitted and locked at {fmtDate(done.reviewed_at)} with {done.attachment_count} evidence file(s). {done.next_sequence ? `Inspector #${done.next_sequence} has been notified.` : 'All reviews are complete; the RE/DRE has been notified.'}</div>}
    <div className="card">
      <div className="section-title">
        <h2 style={{ fontSize: 17 }}><span className="mono">{r.rfi_number}</span>{r.revision_no ? ` Rev ${r.revision_no}` : ''} · {ORDER[r.inspection_order || 0] ? `${ORDER[r.inspection_order]} inspection order` : `Inspection #${a.sequence_no}`}</h2>
        {state === 'active' && <span className="pill green">Your turn is active</span>}
        {state === 'PENDING' && <span className="pill">Awaiting your turn</span>}
        {state === 'COMPLETED' && <span className="pill blue">Submitted · locked</span>}
      </div>
      <div className="grid">
        <ReadOnly label="Work description" value={r.contractor_request || r.description} />
        <ReadOnly label="BOQ item no." value={r.boq_item} />
        <ReadOnly label="Source of material" value={[r.material_source || r.material_source_designation, r.material_source_offset].filter(Boolean).join(' / ')} />
        <ReadOnly label="Location / chainage" value={<span className="mono">{loc(r)}</span>} />
        <ReadOnly label="Inspection date / time" value={`${fmtDay(r.inspection_date)} ${r.inspection_time || ''}`} />
        <ReadOnly label="Your DOC_03 field · sequence" value={`${a.reviewer_role_label} · ${a.sequence_no} of ${live.length}`} />
      </div>
    </div>

    {state === 'PENDING' && <div className="card tinted" role="status"><h3>Awaiting previous reviewer</h3>
      <p style={{ margin: 0 }}>You are number {a.sequence_no} in the sequence. {current ? <>Inspector #{current.sequence_no} ({current.user_name}, {roleLabel(current.reviewer_role)}) is reviewing now.</> : 'The previous stage is not complete.'} You will be notified when it is your turn. Comments and evidence can be added then.</p></div>}

    {(state === 'active' || state === 'COMPLETED') && <div className="cols-2">
      <div className="card" style={{ marginBottom: 0 }}>
        <h3><label htmlFor="rv-comment" style={{ fontSize: 16, color: 'var(--text)', margin: 0 }}>Your assigned comment / remark</label></h3>
        {state === 'COMPLETED'
          ? <div style={{ whiteSpace: 'pre-wrap' }}>{ws.review?.comment}</div>
          : <><textarea id="rv-comment" rows={8} value={comment} onChange={e => onComment(e.target.value)} placeholder="Site findings: levels, crossfall, FDT results, corrections required…" aria-describedby="rv-save" />
            <div id="rv-save" className="muted" style={{ fontSize: 12.5, marginTop: 4 }} aria-live="polite">{saving || 'Draft saves automatically and stays on this device if the connection drops.'}</div></>}
      </div>
      {state === 'COMPLETED'
        ? <section className="evidence"><h4>Supporting evidence</h4>{files.length ? <ul className="ev-list">{files.map(f => <FileRow key={f.id} f={f} />)}</ul> : <div className="muted">No files were attached.</div>}</section>
        : <EvidencePanel files={files} canEdit={editable} policy={ws.policy} onFiles={setFiles} onBusy={setBusyUp} target={async () => `/evidence/assignments/${a.id}/files`} />}
    </div>}

    {(state === 'active' || state === 'COMPLETED') && <div className="card" style={{ marginTop: 16 }}>
      <h3>Inspector sign-off</h3>
      <div className="grid">
        <ReadOnly label="Name" value={ws.review?.reviewer_name || me.name} />
        <ReadOnly label="Date" value={state === 'COMPLETED' ? fmtDay(String(ws.review?.reviewed_at).slice(0, 10)) : now.toLocaleDateString(undefined, { day: '2-digit', month: 'short', year: 'numeric' })} />
        <ReadOnly label="Time" value={state === 'COMPLETED' ? new Date(ws.review!.reviewed_at + 'Z').toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' }) : `${now.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })} (server time recorded on submit)`} />
      </div>
      <p className="muted" style={{ fontSize: 12.5, margin: '8px 0 0' }}>Sign-off records your authenticated account and the server time. No signature image is generated.</p>
      {state === 'active' && <div className="sticky-actions" style={{ marginTop: 14 }}>
        <button type="button" className="btn neutral" onClick={() => saveDraft()} disabled={sending}>Save draft</button>
        <button type="button" className="btn success" disabled={!comment.trim() || busyUp || sending} onClick={() => setConfirm(true)}>{busyUp ? 'Waiting for uploads…' : 'Submit review'}</button>
      </div>}
      {state === 'COMPLETED' && canFix && <div className="actions"><button className="btn secondary" onClick={() => setFix(true)}>Request a correction</button><span className="muted" style={{ fontSize: 12.5 }}>Submitted reviews are locked; corrections need RE/DRE approval and keep the original.</span></div>}
    </div>}

    <ConfirmDialog open={confirm} title="Submit your DOC_03 review?" intro="Your comment and evidence will be locked. The next inspector (or the RE/DRE) will be notified." confirmLabel="Submit review" busy={sending}
      onCancel={() => setConfirm(false)} onConfirm={submit}
      rows={[['RFI No.', `${r.rfi_number}${r.revision_no ? ` Rev ${r.revision_no}` : ''}`], ['Assigned role', a.reviewer_role_label], ['Sequence position', `${a.sequence_no} of ${live.length}`],
        ['Review comments', comment.trim()], ['Attachments', `${files.length} file(s)`], ['Inspector', me.name], ['Sign-off', `${now.toLocaleString()} (server time is recorded)`]]}
      warnings={files.length === 0 ? ['No evidence is attached. Submit only if none is required.'] : []} />
    {fix && <ReviewCorrection assignmentId={a.id} current={ws.review?.comment || ''} files={files} onClose={() => { setFix(false); load(); }} />}
  </>;
}

/** Controlled amendment of a submitted review: corrected comment and/or replacement files; RE/DRE approves; originals are kept. */
export function ReviewCorrection({ assignmentId, current, files, onClose }: { assignmentId: number; current: string; files: Evidence[]; onClose: () => void }) {
  const [reason, setReason] = useState(''); const [text, setText] = useState(current); const [am, setAm] = useState<any>(null);
  const [newFiles, setNewFiles] = useState<Evidence[]>([]); const [replace, setReplace] = useState<string>(''); const [busy, setBusy] = useState(false); const [up, setUp] = useState(false);
  async function create() {
    if (!reason.trim()) { alert('Give the reason for the correction.'); return; }
    setBusy(true);
    try { setAm(await post('/evidence/amendments', { target_kind: 'REVIEW', target_id: assignmentId, reason, new_comment: text !== current ? text : null })); } catch (e: any) { alert(e.message); } finally { setBusy(false); }
  }
  async function send() { setBusy(true); try { await post(`/evidence/amendments/${am.id}/send`); onClose(); } catch (e: any) { alert(e.message); } finally { setBusy(false); } }
  async function withdraw() { if (am) await api(`/evidence/amendments/${am.id}`, { method: 'DELETE' }).catch(() => {}); onClose(); }
  return <div className="modal-bg"><div className="modal" role="dialog" aria-modal="true" aria-labelledby="fix-title">
    <h2 id="fix-title">Request a correction</h2>
    {!am ? <div className="stack">
      <div><label className="req" htmlFor="fx-r">Reason</label><input id="fx-r" value={reason} onChange={e => setReason(e.target.value)} placeholder="e.g. Wrong photograph attached" /></div>
      <div><label htmlFor="fx-c">Corrected comment (leave unchanged if only files are corrected)</label><textarea id="fx-c" value={text} onChange={e => setText(e.target.value)} /></div>
      <div className="actions end"><button className="btn secondary" onClick={onClose}>Cancel</button><button className="btn" disabled={busy} onClick={create}>Continue</button></div>
    </div> : <div className="stack">
      <div><label htmlFor="fx-s">New file replaces (optional)</label><select id="fx-s" value={replace} onChange={e => setReplace(e.target.value)}><option value="">— Add as an additional file —</option>{files.map(f => <option key={f.id} value={f.id}>{f.original_name}</option>)}</select></div>
      <EvidencePanel title="Correction files" files={newFiles} canEdit onFiles={setNewFiles} onBusy={setUp} extraFields={{ supersedes_id: replace || undefined }} target={async () => `/evidence/amendments/${am.id}/files`} />
      <div className="actions end"><button className="btn secondary" onClick={withdraw} disabled={busy}>Withdraw</button><button className="btn success" disabled={busy || up} onClick={send}>Send for RE/DRE approval</button></div>
    </div>}
  </div></div>;
}
