import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, fmtDate } from '../lib/api';
import Status, { pretty } from '../components/Status';

const RECS = ['SATISFACTORY', 'CORRECTION_REQUIRED', 'REINSPECTION_REQUIRED', 'INFORMATION', 'NOT_APPLICABLE'];
export default function MyInspections() {
  const [rows, setRows] = useState<any[] | null>(null); const [sel, setSel] = useState<any>(null);
  const [f, setF] = useState({ recommendation: 'SATISFACTORY', comment: '' }); const [msg, setMsg] = useState(''); const [tab, setTab] = useState<'open' | 'done'>('open');
  const load = () => api('/rfis/my-inspections').then(setRows).catch(e => { setRows([]); setMsg(e.message); });
  useEffect(() => { load(); }, []);
  async function submit(e: any) {
    e.preventDefault();
    try {
      await api(`/rfis/${sel.rfi.id}/review`, { method: 'POST', body: JSON.stringify({ assignment_id: sel.assignment.id, ...f }) });
      setMsg(`Review submitted for RFI ${sel.rfi.rfi_number}.`); setSel(null); setF({ recommendation: 'SATISFACTORY', comment: '' }); load();
    } catch (e: any) { alert(e.message); }
  }
  if (!rows) return <div className="empty">Loading…</div>;
  const open = rows.filter(x => x.assignment.status !== 'COMPLETED'), done = rows.filter(x => x.assignment.status === 'COMPLETED');
  const list = tab === 'open' ? open : done;
  return <>
    <h1>My Inspections</h1>
    <p className="subtitle">RFIs assigned to you for technical review. Inspect on site, then submit your recommendation.</p>
    {msg && <div className="notice ok">{msg}</div>}
    {sel && <form className="card" onSubmit={submit} style={{ borderColor: 'var(--amber)' }}>
      <div className="section-title"><h3>Review RFI <span className="mono">{sel.rfi.rfi_number}</span> · Rev {sel.rfi.revision_no}</h3><Link className="link" to={`/rfis/${sel.rfi.id}`}>Open full RFI →</Link></div>
      <p className="muted" style={{ marginTop: 0 }}>{pretty(sel.rfi.work_item)} · {sel.rfi.description} · <span className="mono">{sel.rfi.chainage_from || ''}{sel.rfi.chainage_to ? ` → ${sel.rfi.chainage_to}` : ''} {sel.rfi.side || ''}</span></p>
      <div className="grid"><div><label>Recommendation</label><select value={f.recommendation} onChange={e => setF({ ...f, recommendation: e.target.value })}>{RECS.map(x => <option key={x} value={x}>{pretty(x)}</option>)}</select></div><div><label>Review role</label><input disabled value={pretty(sel.assignment.reviewer_role)} /></div></div>
      <div style={{ marginTop: 12 }}><label>Findings / comment (required)</label><textarea required value={f.comment} onChange={e => setF({ ...f, comment: e.target.value })} placeholder="Site findings, test results, corrections required…" /></div>
      <div className="toolbar" style={{ marginTop: 14 }}><button className="btn" disabled={!f.comment.trim()}>Submit review</button><button type="button" className="btn secondary" onClick={() => setSel(null)}>Cancel</button></div>
    </form>}
    <div className="toolbar" style={{ marginBottom: 14 }}>
      <button className={`btn ${tab === 'open' ? 'dark' : 'secondary'}`} onClick={() => setTab('open')}>To review ({open.length})</button>
      <button className={`btn ${tab === 'done' ? 'dark' : 'secondary'}`} onClick={() => setTab('done')}>Completed ({done.length})</button>
    </div>
    <div className="card">{list.length ? <div className="table-wrap"><table>
      <thead><tr><th>RFI</th><th>Work</th><th>Location</th><th>My role</th><th>Assigned</th><th>RFI status</th><th></th></tr></thead>
      <tbody>{list.map(x => <tr key={x.assignment.id}>
        <td><Link className="link mono" to={`/rfis/${x.rfi.id}`}>{x.rfi.rfi_number}</Link> <span className="muted">R{x.rfi.revision_no}</span></td>
        <td>{pretty(x.rfi.work_item)}</td><td className="mono">{x.rfi.chainage_from || ''}{x.rfi.chainage_to ? ` → ${x.rfi.chainage_to}` : ''} {x.rfi.side || ''}</td>
        <td>{pretty(x.assignment.reviewer_role)}{x.assignment.required ? '' : ' (advisory)'}</td><td>{fmtDate(x.assignment.assigned_at)}</td><td><Status value={x.rfi.workflow_status} /></td>
        <td>{x.assignment.status !== 'COMPLETED' && x.rfi.record_state === 'ACTIVE' && <button className="btn sm" onClick={() => { setSel(x); window.scrollTo({ top: 0, behavior: 'smooth' }); }}>Review</button>}</td>
      </tr>)}</tbody>
    </table></div> : <div className="empty">{tab === 'open' ? 'Nothing waiting for your review.' : 'No completed reviews yet.'}</div>}</div>
  </>;
}
