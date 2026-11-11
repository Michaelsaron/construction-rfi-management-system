import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, fmtDate } from '../lib/api';
import Status, { pretty } from '../components/Status';

export default function Summaries() {
  const [rows, setRows] = useState<any[]>([]); const [projects, setProjects] = useState<any[]>([]); const [msg, setMsg] = useState(''); const [q, setQ] = useState('');
  const [f, setF] = useState<any>({ project_id: 0, summary_reference: '', submission_date: new Date().toLocaleDateString('en-CA'), entry_source: 'CONTRACTOR_PORTAL', remarks: '' });
  const load = () => api('/rfi-summaries').then(setRows).catch(e => setMsg(e.message));
  useEffect(() => { load(); api('/projects').then((p: any[]) => { setProjects(p); if (p[0]) setF((x: any) => ({ ...x, project_id: p[0].id })); }); }, []);
  async function create(e: any) {
    e.preventDefault();
    try { const s: any = await api('/rfi-summaries', { method: 'POST', body: JSON.stringify(f) }); location.href = `/summaries/${s.id}`; }
    catch (e: any) { alert(e.message); }
  }
  const pname = (id: number) => projects.find(p => p.id === id)?.code || `#${id}`;
  const shown = rows.filter(s => !q || `${s.summary_reference} ${s.workflow_status}`.toLowerCase().includes(q.toLowerCase()));
  return <>
    <h1>RFI Summaries</h1>
    <p className="subtitle">Create a draft summary, add individual RFIs to it, then submit it to the Resident Engineer.</p>
    {msg && <div className="notice err">{msg}</div>}
    <form className="card" onSubmit={create}>
      <h3>New summary</h3>
      <div className="grid">
        <div><label>Project</label><select value={f.project_id} onChange={e => setF({ ...f, project_id: +e.target.value })}>{projects.map(p => <option key={p.id} value={p.id}>{p.code} — {p.name}</option>)}</select></div>
        <div><label>Summary reference</label><input required placeholder="e.g. SUM-2026-11-11" value={f.summary_reference} onChange={e => setF({ ...f, summary_reference: e.target.value })} /></div>
        <div><label>Date</label><input type="date" required value={f.submission_date} onChange={e => setF({ ...f, submission_date: e.target.value })} /></div>
        <div><label>Entry source</label><select value={f.entry_source} onChange={e => setF({ ...f, entry_source: e.target.value })}>{['CONTRACTOR_PORTAL', 'STAFF_ENTRY', 'MIGRATION'].map(x => <option key={x} value={x}>{pretty(x)}</option>)}</select></div>
      </div>
      <div style={{ marginTop: 14 }}><button className="btn">Create draft & add RFIs</button></div>
    </form>
    <div className="card">
      <div className="section-title"><h3>All summaries</h3><input style={{ maxWidth: 280 }} placeholder="Search reference…" value={q} onChange={e => setQ(e.target.value)} /></div>
      {shown.length ? <div className="table-wrap"><table>
        <thead><tr><th>Reference</th><th>Project</th><th>Date</th><th>Status</th><th>Submitted</th><th></th></tr></thead>
        <tbody>{shown.map(s => <tr key={s.id}>
          <td><Link className="link" to={`/summaries/${s.id}`}>{s.summary_reference}</Link>{s.returned_reason && <div className="muted" style={{ fontSize: 12.5 }}>Returned: {s.returned_reason}</div>}</td>
          <td>{pname(s.project_id)}</td><td>{s.submission_date}</td><td><Status value={s.workflow_status} /></td><td>{s.submitted_at ? fmtDate(s.submitted_at) : '—'}</td>
          <td><Link className="btn secondary sm" to={`/summaries/${s.id}`}>Open</Link></td>
        </tr>)}</tbody>
      </table></div> : <div className="empty">No summaries yet.</div>}
    </div>
  </>;
}
