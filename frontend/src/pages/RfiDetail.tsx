import React, { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { api, download, fmtDate, getUser, isManager } from '../lib/api';
import Attachments from '../components/Attachments';
import Status, { pretty } from '../components/Status';
import Icon from '../components/Icon';

const REVIEWER_ROLES = ['WORK_INSPECTOR', 'STRUCTURE_INSPECTOR', 'SURVEYOR', 'SENIOR_SURVEYOR', 'MATERIAL_INSPECTOR', 'LAB_TECHNICIAN', 'MATERIAL_ENGINEER'];
const REVIEWABLE = ['ACTIVATED', 'UNDER_REVIEW', 'AWAITING_DECISION'];
const EDIT_FIELDS: [string, string, string?][] = [
  ['contractor_request', 'Contractor request'], ['description', 'Description', 'textarea'], ['structure_type', 'Structure type'], ['test_name', 'Test'],
  ['road_type', 'Road type'], ['direction', 'Direction'], ['side', 'Side'], ['chainage_from', 'Chainage from'], ['chainage_to', 'Chainage to'],
  ['material_source_type', 'Material source type'], ['material_source', 'Material source'], ['requested_date', 'Requested date', 'date'],
  ['inspection_date', 'Inspection date', 'date'], ['work_status', 'Work status'], ['remarks', 'Remarks', 'textarea'],
];

export default function RfiDetail() {
  const { id } = useParams(); const nav = useNavigate();
  const [d, setD] = useState<any>(null); const [err, setErr] = useState('');
  const [users, setUsers] = useState<any[]>([]); const [suggested, setSuggested] = useState<any[]>([]);
  const [ass, setAss] = useState<any>({ user_id: 0, reviewer_role: 'WORK_INSPECTOR', required: true });
  const [dec, setDec] = useState<any>({ decision: 'APPROVED', comment: '', override_used: false, override_reason: '' });
  const [edit, setEdit] = useState<any>(null); const [busy, setBusy] = useState(false); const [msg, setMsg] = useState('');
  const manager = isManager(); const me = getUser();

  const load = () => api(`/rfis/${id}`).then(setD).catch(e => setErr(e.message));
  useEffect(() => {
    setD(null); setErr(''); setMsg(''); load();
    api('/users').then((u: any[]) => { setUsers(u); const ru = u.filter(x => REVIEWER_ROLES.includes(x.role) && x.is_active); if (ru[0]) setAss((x: any) => ({ ...x, user_id: ru[0].id, reviewer_role: ru[0].role })); }).catch(() => {});
    api(`/rfis/${id}/suggested-reviewers`).then(setSuggested).catch(() => {});
  }, [id]);

  async function run(fn: () => Promise<any>, ok: string) {
    setBusy(true); setMsg('');
    try { await fn(); setMsg(ok); await load(); } catch (e: any) { alert(e.message); } finally { setBusy(false); }
  }
  const post = (path: string, body?: any) => api(`/rfis/${id}/${path}`, { method: 'POST', body: body ? JSON.stringify(body) : undefined });
  const activate = () => run(() => post('activate'), 'RFI accepted and activated.');
  const assign = () => { if (!ass.user_id) { alert('Select a reviewer.'); return; } run(() => post('assign-reviewer', ass), 'Reviewer assigned and notified.'); };
  const decide = () => {
    if (dec.override_used && !dec.override_reason.trim()) { alert('Enter the override reason.'); return; }
    if (!confirm(`Record final decision: ${pretty(dec.decision)}? This completes the RFI.`)) return;
    run(() => post('decision', dec), 'Final decision recorded.');
  };
  async function resubmit() {
    const reason = prompt('Reason for resubmission (what was corrected)?'); if (!reason?.trim()) return;
    try { const n: any = await post('resubmit', { reason }); nav(`/rfis/${n.id}`); } catch (e: any) { alert(e.message); }
  }
  async function stateChange(action: 'archive' | 'cancel') {
    const reason = prompt(`Reason to ${action} this RFI?`); if (!reason?.trim()) return;
    run(() => post(action, { reason }), action === 'archive' ? 'RFI archived.' : 'RFI cancelled.');
  }
  async function saveEdit(e: any) {
    e.preventDefault();
    const body: any = { version: d.rfi.version };
    for (const [k] of EDIT_FIELDS) body[k] = edit[k] === '' ? null : edit[k];
    if (d.rfi.workflow_status === 'COMPLETED') { body.edit_reason = edit.edit_reason; if (!body.edit_reason?.trim()) { alert('Enter the reason for editing a completed RFI.'); return; } }
    try { await api(`/rfis/${id}`, { method: 'PUT', body: JSON.stringify(body) }); setEdit(null); setMsg('RFI updated.'); load(); } catch (e: any) { alert(e.message); }
  }

  if (err) return <div className="notice err">{err} <Link className="link" to="/rfis">Back to register</Link></div>;
  if (!d) return <div className="empty">Loading RFI…</div>;
  const r = d.rfi; const name = (uid: number) => users.find(u => u.id === uid)?.full_name || `User #${uid}`;
  const active = r.record_state === 'ACTIVE';
  const reviewers = users.filter(x => REVIEWER_ROLES.includes(x.role) && x.is_active);
  const pending = d.assignments.filter((a: any) => a.required && a.status !== 'COMPLETED').length;
  const reviewOf = (aid: number) => d.reviews.find((x: any) => x.assignment_id === aid);
  const canEdit = active && (r.workflow_status !== 'COMPLETED' || manager);

  return <>
    <div className="top">
      <div>
        <Link to="/rfis" className="link" style={{ fontSize: 14 }}>← RFI Register</Link>
        <h1 style={{ marginTop: 6 }}><span className="mono" style={{ fontSize: '.85em' }}>{r.rfi_number}</span> · Rev {r.revision_no}</h1>
        <div className="chips" style={{ marginBottom: 18 }}>
          <Status value={r.workflow_status} />{r.current_decision && <Status value={r.current_decision} />}
          {r.record_state !== 'ACTIVE' && <Status value={r.record_state} />}
          <span className="badge">Version {r.version}</span>
          {r.summary_id && <Link to={`/summaries/${r.summary_id}`} className="badge" style={{ textDecoration: 'none', color: 'inherit' }}>Summary #{r.summary_id}</Link>}
        </div>
      </div>
      <div className="toolbar">
        <button className="btn secondary" onClick={() => download(`/reports/rfi/${id}.pdf`, `rfi_${r.rfi_number}_rev${r.revision_no}.pdf`)}><Icon name="download" size={16} />Official PDF</button>
        {canEdit && <button className="btn secondary" onClick={() => setEdit({ ...Object.fromEntries(EDIT_FIELDS.map(([k]) => [k, r[k] ?? ''])), edit_reason: '' })}>Edit details</button>}
        {manager && active && <><button className="btn secondary" disabled={busy} onClick={() => stateChange('archive')}>Archive</button><button className="btn danger" disabled={busy} onClick={() => stateChange('cancel')}>Cancel RFI</button></>}
      </div>
    </div>
    {msg && <div className="notice ok">{msg}</div>}
    {!active && <div className="notice">This RFI is {r.record_state.toLowerCase()} and can no longer be changed.</div>}

    <div className="card">
      <div className="kv">
        <div><div className="k">Work item</div><div className="v">{pretty(r.work_item)}</div></div>
        <div><div className="k">Location</div><div className="v mono">{r.chainage_from || '—'}{r.chainage_to ? ` → ${r.chainage_to}` : ''} {r.side || ''}</div></div>
        <div><div className="k">Requested / Inspection</div><div className="v">{r.requested_date || '—'} / {r.inspection_date || '—'}</div></div>
        <div><div className="k">Work status</div><div className="v">{r.work_status || '—'}</div></div>
        {r.structure_type && <div><div className="k">Structure type</div><div className="v">{r.structure_type}</div></div>}
        {r.test_name && <div><div className="k">Test</div><div className="v">{r.test_name}</div></div>}
        <div><div className="k">Material source</div><div className="v">{r.material_source_designation || r.material_source || '—'}</div></div>
        <div><div className="k">Created by</div><div className="v">{name(r.created_by)}</div></div>
      </div>
      <p><b>Description:</b> {r.description}</p>
      {r.contractor_request && <p><b>Contractor request:</b> {r.contractor_request}</p>}
      {r.remarks && <p><b>Remarks:</b> {r.remarks}</p>}
      <div className="toolbar">
        {manager && active && ['DRAFT', 'SUBMITTED'].includes(r.workflow_status) && <button className="btn" disabled={busy} onClick={activate}><Icon name="check" size={16} />Accept / Activate</button>}
        {active && r.current_decision === 'REJECTED' && <button className="btn warn" onClick={resubmit}>Create next revision</button>}
      </div>
      {manager && active && r.workflow_status === 'DRAFT' && r.summary_id && <p className="muted" style={{ fontSize: 13, margin: '10px 0 0' }}>This RFI belongs to a summary that has not been submitted yet. It can be activated after the summary is submitted.</p>}
    </div>

    {manager && active && REVIEWABLE.includes(r.workflow_status) && <div className="card">
      <h3>Assign reviewer</h3>
      {suggested.length > 0 && <div className="notice">Suggested by reviewer rules: {suggested.map((x: any) => `${pretty(x.reviewer_role)}${x.required ? ' (required)' : ''}`).join(', ')}</div>}
      {reviewers.length === 0 ? <div className="notice">No active inspector / reviewer accounts exist yet. Create them on the Users page.</div> :
        <div className="grid">
          <div><label>Reviewer</label><select value={ass.user_id} onChange={e => { const uid = +e.target.value; const x = users.find(z => z.id === uid); setAss({ ...ass, user_id: uid, reviewer_role: REVIEWER_ROLES.includes(x?.role) ? x.role : ass.reviewer_role }); }}>{reviewers.map(u => <option key={u.id} value={u.id}>{u.full_name} — {pretty(u.role)}</option>)}</select></div>
          <div><label>Review role</label><select value={ass.reviewer_role} onChange={e => setAss({ ...ass, reviewer_role: e.target.value })}>{REVIEWER_ROLES.map(x => <option key={x} value={x}>{pretty(x)}</option>)}</select></div>
          <div><label>Required?</label><select value={String(ass.required)} onChange={e => setAss({ ...ass, required: e.target.value === 'true' })}><option value="true">Yes</option><option value="false">No (advisory)</option></select></div>
        </div>}
      <div style={{ marginTop: 14 }}><button className="btn" disabled={busy || !reviewers.length} onClick={assign}>Assign reviewer</button></div>
    </div>}

    <div className="card">
      <h3>Reviews</h3>
      {d.assignments.length ? <div className="table-wrap"><table>
        <thead><tr><th>Reviewer</th><th>Role</th><th>Required</th><th>Status</th><th>Recommendation</th><th>Comment</th></tr></thead>
        <tbody>{d.assignments.map((a: any) => { const rv = reviewOf(a.id); return <tr key={a.id}>
          <td>{name(a.user_id)}</td><td>{pretty(a.reviewer_role)}</td><td>{a.required ? 'Yes' : 'No'}</td><td><Status value={a.status} /></td>
          <td>{rv ? pretty(rv.recommendation) : '—'}</td><td>{rv?.comment || ''}{a.user_id === me.id && a.status !== 'COMPLETED' && <Link className="link" to="/my-inspections"> Submit my review →</Link>}</td>
        </tr>; })}</tbody>
      </table></div> : <div className="empty">No reviewers assigned yet.</div>}
    </div>

    {manager && active && REVIEWABLE.includes(r.workflow_status) && <div className="card">
      <h3>RE / ARE final decision</h3>
      {pending > 0 && <div className="notice">{pending} required review(s) still pending. Recording a decision now requires an override with a reason.</div>}
      <div className="grid">
        <div><label>Decision</label><select value={dec.decision} onChange={e => setDec({ ...dec, decision: e.target.value })}>{['APPROVED', 'REJECTED', 'ON_PROGRESS', 'INFORMATION_ONLY'].map(x => <option key={x} value={x}>{pretty(x)}</option>)}</select></div>
        {pending > 0 && <div><label>Override pending reviews?</label><select value={String(dec.override_used)} onChange={e => setDec({ ...dec, override_used: e.target.value === 'true' })}><option value="false">No</option><option value="true">Yes</option></select></div>}
      </div>
      <div style={{ marginTop: 12 }}><label>Comment</label><textarea value={dec.comment} onChange={e => setDec({ ...dec, comment: e.target.value })} /></div>
      {dec.override_used && pending > 0 && <div style={{ marginTop: 12 }}><label>Override reason</label><textarea required value={dec.override_reason} onChange={e => setDec({ ...dec, override_reason: e.target.value })} /></div>}
      <div style={{ marginTop: 14 }}><button className="btn success" disabled={busy || (pending > 0 && !dec.override_used)} onClick={decide}>Save final decision</button></div>
    </div>}

    {d.decisions.length > 0 && <div className="card"><h3>Decisions</h3><div className="table-wrap"><table>
      <thead><tr><th>Date</th><th>Rev</th><th>Decision</th><th>By</th><th>Comment</th><th>Override</th></tr></thead>
      <tbody>{d.decisions.map((x: any) => <tr key={x.id}><td>{fmtDate(x.decided_at)}</td><td>{x.revision_no}</td><td><Status value={x.decision} /></td><td>{name(x.decided_by)}</td><td>{x.comment || ''}</td><td>{x.override_used ? `Yes — ${x.override_reason}` : 'No'}</td></tr>)}</tbody>
    </table></div></div>}

    <Attachments entityType="rfi" entityId={+id!} canUpload={active} />

    <div className="card"><h3>Status history</h3>{d.history?.length ? <div className="table-wrap"><table>
      <thead><tr><th>Date</th><th>Workflow</th><th>Decision</th><th>Changed by</th><th>Reason</th></tr></thead>
      <tbody>{d.history.map((h: any) => <tr key={h.id}><td>{fmtDate(h.created_at)}</td><td><Status value={h.workflow_status} /></td><td><Status value={h.decision} /></td><td>{name(h.changed_by)}</td><td>{h.reason || ''}</td></tr>)}</tbody>
    </table></div> : <div className="empty">No history yet.</div>}</div>

    {edit && <div className="modal-bg" onClick={e => { if (e.target === e.currentTarget) setEdit(null); }}>
      <form className="modal" onSubmit={saveEdit}>
        <div className="section-title"><h3>Edit RFI {r.rfi_number}</h3><button type="button" className="icon-btn" onClick={() => setEdit(null)} aria-label="Close"><Icon name="x" /></button></div>
        <div className="grid">{EDIT_FIELDS.filter(([, , t]) => t !== 'textarea').map(([k, l, t]) => <div key={k}><label>{l}</label><input type={t || 'text'} value={edit[k] ?? ''} onChange={e => setEdit({ ...edit, [k]: e.target.value })} /></div>)}</div>
        {EDIT_FIELDS.filter(([, , t]) => t === 'textarea').map(([k, l]) => <div key={k} style={{ marginTop: 12 }}><label>{l}</label><textarea required={k === 'description'} value={edit[k] ?? ''} onChange={e => setEdit({ ...edit, [k]: e.target.value })} /></div>)}
        {r.workflow_status === 'COMPLETED' && <div style={{ marginTop: 12 }}><label>Reason for editing a completed RFI</label><input required value={edit.edit_reason} onChange={e => setEdit({ ...edit, edit_reason: e.target.value })} /></div>}
        <div className="toolbar" style={{ marginTop: 16 }}><button className="btn">Save changes</button><button type="button" className="btn secondary" onClick={() => setEdit(null)}>Cancel</button></div>
      </form>
    </div>}
  </>;
}
