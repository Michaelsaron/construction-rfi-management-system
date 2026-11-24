import React, { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api, post, fmtDay, loc, roleLabel, INSPECTORS } from '../lib/api';
import { PageHeader, ConfirmDialog, Loading, ErrorNote } from '../components/ui';
import { useRemarkDraft, RemarkEvidence } from '../components/RemarkEvidence';
import Status from '../components/Status';

/** Category 2.1 — inspector assignment and sequence, with the RE/DRE's own remark and evidence (UI design s.5). */
export default function AssignInspectors() {
  const { id } = useParams();
  const [d, setD] = useState<any>(null); const [err, setErr] = useState(''); const [members, setMembers] = useState<any[]>([]); const [suggested, setSuggested] = useState<any[]>([]);
  const [plan, setPlan] = useState<number[]>([]); const [reason, setReason] = useState(''); const [note, setNote] = useState(''); const [confirm, setConfirm] = useState(false); const [busy, setBusy] = useState(false); const [msg, setMsg] = useState('');
  const load = () => api(`/rfis/${id}`).then((x: any) => {
    setD(x); setPlan(x.assignments.filter((a: any) => ['PENDING', 'ACTIVE'].includes(a.status)).map((a: any) => a.user_id));
    if (x.permissions.assign) {
      api(`/projects/${x.rfi.project_id}/members`).then((ms: any[]) => setMembers(ms.filter(m => INSPECTORS.includes(m.role) && m.is_active))).catch(() => {});
      api(`/rfis/${id}/suggested-reviewers`).then(setSuggested).catch(() => {});
    }
  }).catch(e => setErr(e.message));
  useEffect(() => { load(); }, [id]);
  const started = !!d?.assignments.some((a: any) => a.status === 'COMPLETED');
  const hasPlan = !!d?.assignments.some((a: any) => ['PENDING', 'ACTIVE'].includes(a.status));
  const stage = started || hasPlan ? 'SEQUENCE_CHANGE' : 'ASSIGNMENT';
  const draft = useRemarkDraft(d?.rfi.project_id, stage as any, d?.permissions.assign ? +id! : null);
  if (err) return <ErrorNote error={err} />;
  if (!d) return <Loading />;
  const r = d.rfi;
  const completed = d.assignments.filter((a: any) => a.status === 'COMPLETED');
  const move = (i: number, k: number) => { const p = [...plan]; const j = i + k; if (j < 0 || j >= p.length) return; [p[i], p[j]] = [p[j], p[i]]; setPlan(p); };
  const name = (uid: number) => members.find(m => m.user_id === uid) || d.assignments.find((a: any) => a.user_id === uid);
  async function save() {
    setBusy(true);
    try {
      const rem = note.trim() && !draft.remark ? await draft.ensure() : draft.remark;
      await post(`/rfis/${id}/assignments`, { assignments: plan.map(u => ({ user_id: u })), reason: reason.trim() || null, remark: note.trim() || null, management_remark_id: rem?.id || null });
      setConfirm(false); setMsg('Assignment saved. The first inspector in the sequence has been notified.'); setReason(''); setNote(''); await load(); await draft.reload();
    } catch (e: any) { setConfirm(false); alert(e.message); } finally { setBusy(false); }
  }
  return <>
    <PageHeader title="DOC_01 review · assignment and management remarks" back={{ to: '/assignment', label: 'Inspector assignment' }}
      actions={<><Link className="btn secondary" to={`/rfis/${id}/workflow`}>Workflow</Link>{d.summary && <Link className="btn secondary" to={`/summaries/${d.summary.id}`}>DOC_01 {d.summary.summary_reference}</Link>}</>} />
    {msg && <div className="notice ok" role="status">{msg}</div>}
    <div className="card">
      <div className="section-title"><h2 style={{ fontSize: 17 }}><span className="mono">{r.rfi_number}</span>{r.revision_no ? ` Rev ${r.revision_no}` : ''} · {r.contractor_request || r.description}</h2><Status value={r.workflow_status} label={r.status_label} /></div>
      <div className="kv"><div><div className="k">Inspection</div><div className="v">{fmtDay(r.inspection_date)} {r.inspection_time || ''}</div></div>
        <div><div className="k">Location</div><div className="v mono">{loc(r)}</div></div><div><div className="k">Work item</div><div className="v">{r.work_item}</div></div>
        <div><div className="k">Notice</div><div className="v">{r.short_notice ? <Status value="SHORT_NOTICE" label={`Short notice · ${r.notice_hours} h`} /> : `${r.notice_hours ?? '—'} h`}</div></div></div>
    </div>
    {!d.permissions.assign ? <div className="notice">Assignment is not open for this RFI ({r.status_label}). Only the RE/DRE can assign while the RFI is submitted or under review.</div> :
    <div className="cols-2">
      <div className="card tinted" style={{ marginBottom: 0 }}>
        <h3>Inspector sequence</h3>
        <p className="muted" style={{ marginTop: 0, fontSize: 13 }}>Inspectors review strictly in this order. Each next inspector is activated when the previous one submits.</p>
        {suggested.length > 0 && <div className="notice info">Reviewer rules suggest: {suggested.map((x: any) => roleLabel(x.reviewer_role)).join(' → ')}</div>}
        {completed.map((a: any) => <div key={a.id} className="ev-item" style={{ marginBottom: 8, opacity: .8 }}><span className="nm">{a.sequence_no} · {roleLabel(a.reviewer_role)} — {a.user_name}</span><span className="acts"><Status value="COMPLETED" label="Submitted" /></span></div>)}
        {members.length === 0 ? <div className="notice">No inspectors (Category 2.2) are members of this project. The administrator must add them.</div> : <>
          <ol style={{ listStyle: 'none', padding: 0, margin: 0, display: 'grid', gap: 8 }}>{plan.map((uid, i) => { const m = name(uid); return <li key={uid} className="ev-item">
            <span className="nm">{completed.length + i + 1} · {roleLabel(m?.role || m?.reviewer_role)} — {m?.full_name || m?.user_name}</span>
            <span className="acts"><button type="button" className="btn secondary sm" onClick={() => move(i, -1)} disabled={i === 0} aria-label="Move up">↑</button>
              <button type="button" className="btn secondary sm" onClick={() => move(i, 1)} disabled={i === plan.length - 1} aria-label="Move down">↓</button>
              <button type="button" className="btn secondary sm" onClick={() => setPlan(plan.filter(x => x !== uid))}>Remove</button></span></li>; })}</ol>
          <div style={{ marginTop: 10 }}><label htmlFor="add-insp">Add inspector</label><select id="add-insp" value="" onChange={e => { const v = +e.target.value; if (v) setPlan(p => (p.includes(v) ? p : [...p, v])); }}>
            <option value="">Select assigned user…</option>{members.filter(m => !plan.includes(m.user_id)).map(m => <option key={m.user_id} value={m.user_id}>{m.role_label} — {m.full_name}</option>)}</select></div>
          {(started || hasPlan) && <div style={{ marginTop: 10 }}><label className={started ? 'req' : ''} htmlFor="why">Reason for the change {started ? '(required: inspection has started)' : '(optional)'}</label>
            <input id="why" value={reason} onChange={e => setReason(e.target.value)} placeholder="e.g. Works inspector on leave" /></div>}
          <div className="actions"><button className="btn success" disabled={busy || !plan.length || (started && !reason.trim()) || draft.busy} onClick={() => setConfirm(true)}>{draft.busy ? 'Waiting for uploads…' : 'Save assignment'}</button></div>
        </>}
      </div>
      <div className="card" style={{ marginBottom: 0 }}>
        <h3>Management remark / supporting evidence</h3>
        <div style={{ marginBottom: 10 }}><label htmlFor="mn">Remark</label><textarea id="mn" value={note} onChange={e => setNote(e.target.value)} placeholder="e.g. Ensure prior layer test results accompany the inspection." /></div>
        <RemarkEvidence draft={draft} canEdit />
      </div>
    </div>}
    <ConfirmDialog open={confirm} title={started || hasPlan ? 'Change the inspector sequence?' : 'Save the inspector assignment?'} confirmLabel="Save assignment" busy={busy}
      onCancel={() => setConfirm(false)} onConfirm={save}
      rows={[['RFI No.', r.rfi_number], ['Sequence', plan.map((u, i) => `${completed.length + i + 1}. ${roleLabel(name(u)?.role || name(u)?.reviewer_role)} — ${name(u)?.full_name || name(u)?.user_name}`).join('\n')],
        ...(reason.trim() ? [['Reason', reason.trim()] as [string, string]] : []), ...(note.trim() ? [['Remark', note.trim()] as [string, string]] : []), ['Remark evidence', `${draft.files.length} file(s)`]]}
      warnings={started ? ['Completed reviews stay locked. Inspectors removed from the sequence lose access to this RFI.'] : []} />
  </>;
}
