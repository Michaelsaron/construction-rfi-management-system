import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, fmtDate, fmtDay, loc, roleLabel, currentProjectId } from '../lib/api';
import Status from '../components/Status';

export default function MyInspections() {
  const [rows, setRows] = useState<any[] | null>(null); const [msg, setMsg] = useState(''); const [tab, setTab] = useState<'ACTIVE' | 'PENDING' | 'COMPLETED'>('ACTIVE');
  const pid = currentProjectId();
  useEffect(() => { api('/rfis/my-inspections').then(setRows).catch(e => { setRows([]); setMsg(e.message); }); }, []);
  if (!rows) return <div className="empty">Loading…</div>;
  const mine = rows.filter(x => !pid || x.rfi.project_id === pid);
  const list = mine.filter(x => x.assignment.status === tab);
  const count = (s: string) => mine.filter(x => x.assignment.status === s).length;
  return <>
    <h1>My Inspections</h1>
    <p className="subtitle">Reviews are strictly sequential. You can submit only when it is your turn; you are notified when the previous inspector submits.</p>
    {msg && <div className="notice err">{msg}</div>}
    <div className="toolbar" style={{ marginBottom: 14 }}>
      <button className={`btn ${tab === 'ACTIVE' ? 'dark' : 'secondary'}`} onClick={() => setTab('ACTIVE')}>Your turn ({count('ACTIVE')})</button>
      <button className={`btn ${tab === 'PENDING' ? 'dark' : 'secondary'}`} onClick={() => setTab('PENDING')}>Upcoming ({count('PENDING')})</button>
      <button className={`btn ${tab === 'COMPLETED' ? 'dark' : 'secondary'}`} onClick={() => setTab('COMPLETED')}>Submitted ({count('COMPLETED')})</button>
    </div>
    <div className="card">{list.length ? <div className="table-wrap"><table>
      <thead><tr><th>RFI</th><th>Works description</th><th>Location</th><th>Inspection</th><th>Your field / #</th><th>{tab === 'PENDING' ? 'Waiting for' : tab === 'ACTIVE' ? 'Active since' : 'Submitted'}</th><th></th></tr></thead>
      <tbody>{list.map(x => <tr key={x.assignment.id}>
        <td><Link className="link mono" to={`/rfis/${x.rfi.id}`}>{x.rfi.rfi_number}</Link> <span className="muted">R{x.rfi.revision_no}</span></td>
        <td>{x.rfi.contractor_request || x.rfi.work_item}</td><td className="mono">{loc(x.rfi)}</td><td>{fmtDay(x.rfi.inspection_date)} {x.rfi.inspection_time || ''}</td>
        <td>{roleLabel(x.assignment.reviewer_role)} · #{x.assignment.sequence_no}</td>
        <td>{tab === 'PENDING' ? (x.waiting_for ? `#${x.waiting_for.sequence_no} ${x.waiting_for.name || ''}` : '—') : fmtDate(tab === 'ACTIVE' ? x.assignment.activated_at : x.assignment.completed_at)}</td>
        <td>{tab === 'ACTIVE' ? <Link className="btn sm" to={`/rfis/${x.rfi.id}`}>Inspect</Link> : <Status value={x.rfi.workflow_status} />}</td>
      </tr>)}</tbody></table></div> : <div className="empty">{tab === 'ACTIVE' ? 'Nothing is waiting for your review.' : tab === 'PENDING' ? 'No upcoming inspections.' : 'No submitted reviews yet.'}</div>}</div>
  </>;
}
