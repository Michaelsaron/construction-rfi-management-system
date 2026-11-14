import React, { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api, apiOrQueue, currentProjectId, fmtDate, isContractor, getUser } from '../lib/api';
import Status from '../components/Status';

export default function Summaries() {
  const pid = currentProjectId(); const nav = useNavigate();
  const [rows, setRows] = useState<any[] | null>(null); const [err, setErr] = useState('');
  const today = new Date().toISOString().slice(0, 10);
  const [f, setF] = useState({ summary_reference: `DRS-${today.replaceAll('-', '')}-01`, submission_date: today, contractor_rep_name: getUser().name || '', remarks: '' });
  const load = () => pid && api(`/rfi-summaries?project_id=${pid}`).then(setRows).catch(e => { setErr(e.message); setRows([]); });
  useEffect(() => { load(); }, [pid]);
  async function create(e: any) {
    e.preventDefault();
    try { const s: any = await apiOrQueue('/rfi-summaries', 'POST', { ...f, project_id: pid }); if (s?.queued) { alert('Saved offline; it will sync when you reconnect.'); return; } nav(`/summaries/${s.id}`); }
    catch (e: any) { alert(e.message); }
  }
  return <>
    <div className="top"><div><h1>DOC_01 – Daily Request For Inspection</h1><p className="subtitle">Each DOC_01 batch lists one or more RFIs offered for inspection. Submit at least 24 hours before inspection.</p></div></div>
    {err && <div className="notice err">{err}</div>}
    {isContractor() && <form className="card" onSubmit={create}><h3>New DOC_01 batch</h3><div className="grid">
      <div><label>Batch reference</label><input required value={f.summary_reference} onChange={e => setF({ ...f, summary_reference: e.target.value })} /></div>
      <div><label>Date</label><input type="date" required value={f.submission_date} onChange={e => setF({ ...f, submission_date: e.target.value })} /></div>
      <div><label>Contractor representative</label><input value={f.contractor_rep_name} onChange={e => setF({ ...f, contractor_rep_name: e.target.value })} /></div>
    </div><div style={{ marginTop: 12 }}><label>Remarks</label><textarea value={f.remarks} onChange={e => setF({ ...f, remarks: e.target.value })} /></div>
      <div style={{ marginTop: 12 }}><button className="btn">Create draft batch</button></div></form>}
    <div className="card"><h3>Batches</h3>{rows === null ? <div className="empty">Loading…</div> : rows.length ? <div className="table-wrap"><table>
      <thead><tr><th>Reference</th><th>Status</th><th>RFIs</th><th>Short notice</th><th>Submitted</th><th>By</th><th>Received</th></tr></thead>
      <tbody>{rows.map(s => <tr key={s.id}><td><Link className="link" to={`/summaries/${s.id}`}>{s.summary_reference}</Link></td><td><Status value={s.workflow_status} /></td>
        <td>{s.rfi_count}</td><td>{s.short_notice_count || '—'}</td><td>{fmtDate(s.submitted_at)}</td><td>{s.submitted_by_name}</td><td>{s.received_at ? fmtDate(s.received_at) : '—'}</td></tr>)}</tbody>
    </table></div> : <div className="empty">No DOC_01 batches yet.</div>}</div>
  </>;
}
