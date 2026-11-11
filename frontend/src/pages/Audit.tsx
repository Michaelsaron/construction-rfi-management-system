import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, fmtDate, userNames } from '../lib/api';
import { pretty } from '../components/Status';

const LINK: Record<string, string> = { RFI: '/rfis/', RFI_SUMMARY: '/summaries/' };
export default function Audit() {
  const [rows, setRows] = useState<any[] | null>(null); const [names, setNames] = useState<Record<number, string>>({}); const [q, setQ] = useState(''); const [err, setErr] = useState('');
  useEffect(() => { api('/audit?limit=1000').then(setRows).catch(e => { setRows([]); setErr(e.message); }); userNames().then(setNames); }, []);
  const shown = (rows || []).filter(r => !q || `${names[r.user_id] || ''} ${r.entity_type} ${r.action} ${r.details || ''} ${r.entity_id}`.toLowerCase().includes(q.toLowerCase()));
  return <>
    <h1>Audit Log</h1>
    <p className="subtitle">Every create, submission, assignment, decision, export and admin action, with who did it and when.</p>
    {err && <div className="notice err">{err}</div>}
    <div className="card">
      <div className="section-title"><h3>Latest {rows?.length || 0} events</h3><input style={{ maxWidth: 300 }} placeholder="Filter by user, action, entity…" value={q} onChange={e => setQ(e.target.value)} /></div>
      {!rows ? <div className="empty">Loading…</div> : <div className="table-wrap"><table>
        <thead><tr><th>Time</th><th>User</th><th>Action</th><th>Entity</th><th>Details</th></tr></thead>
        <tbody>{shown.map(r => <tr key={r.id}>
          <td style={{ whiteSpace: 'nowrap' }}>{fmtDate(r.created_at)}</td><td>{names[r.user_id] || `#${r.user_id}`}</td><td><span className="badge">{pretty(r.action)}</span></td>
          <td>{LINK[r.entity_type] && r.entity_id ? <Link className="link" to={LINK[r.entity_type] + r.entity_id}>{pretty(r.entity_type)} #{r.entity_id}</Link> : `${pretty(r.entity_type)}${r.entity_id ? ` #${r.entity_id}` : ''}`}</td>
          <td>{r.details || ''}</td>
        </tr>)}</tbody>
      </table></div>}
    </div>
  </>;
}
