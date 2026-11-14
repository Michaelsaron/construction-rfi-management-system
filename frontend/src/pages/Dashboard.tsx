import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, currentProjectId, fmtDate, fmtDay, loc, roleLabel, deputyLabel } from '../lib/api';
import Status from '../components/Status';

function RfiTable({ rows, empty, extra }: { rows: any[]; empty: string; extra?: (r: any) => React.ReactNode }) {
  if (!rows?.length) return <div className="empty">{empty}</div>;
  return <div className="table-wrap"><table>
    <thead><tr><th>RFI No.</th><th>Works description</th><th>Location</th><th>Inspection</th><th>Status</th>{extra && <th></th>}</tr></thead>
    <tbody>{rows.map(r => <tr key={r.id + '-' + (r.sequence_no || '')}>
      <td><Link className="link mono" to={`/rfis/${r.id}`}>{r.rfi_number}</Link>{r.revision_no ? <span className="muted"> R{r.revision_no}</span> : null}</td>
      <td>{r.contractor_request || r.work_item}</td><td className="mono">{loc(r)}</td>
      <td>{fmtDay(r.inspection_date)} {r.inspection_time || ''}{r.short_notice && <> <Status value="SHORT_NOTICE" label="Short notice" /></>}</td>
      <td><Status value={r.current_disposition ? r.current_decision : r.workflow_status} />{r.overdue && <> <Status value="OVERDUE" /></>}</td>
      {extra && <td>{extra(r)}</td>}
    </tr>)}</tbody></table></div>;
}

const Kpi = ({ label, value, to }: { label: string; value: any; to?: string }) => {
  const body = <div className="stat"><div className="muted" style={{ fontSize: 13 }}>{label}</div><div style={{ fontSize: 28, fontWeight: 700 }}>{value ?? 0}</div></div>;
  return to ? <Link to={to} style={{ textDecoration: 'none', color: 'inherit' }}>{body}</Link> : body;
};

export default function Dashboard() {
  const pid = currentProjectId();
  const [d, setD] = useState<any>(null); const [err, setErr] = useState('');
  useEffect(() => { if (pid) api(`/dashboard?project_id=${pid}`).then(setD).catch(e => setErr(e.message)); }, [pid]);
  if (!pid) return <div className="card"><h2>No project selected</h2><p className="muted">You are not a member of any project yet. Ask the System Administrator to add you to a project with the correct role.</p></div>;
  if (err) return <div className="notice err">{err}</div>;
  if (!d) return <div className="empty">Loading dashboard…</div>;
  const wf = d.counts.by_workflow || {};
  const role = d.role;
  return <>
    <div className="top"><div><h1>{d.project.code}</h1><p className="subtitle">{d.project.name} · You are signed in as <b>{roleLabel(role)}</b></p></div></div>
    <div className="stats">
      <Kpi label="RFIs in register" value={d.counts.total} to="/rfis" />
      <Kpi label="Submitted – awaiting assignment" value={(wf.SUBMITTED || 0) + (wf.ACTIVATED || 0)} to="/rfis?workflow_status=SUBMITTED" />
      <Kpi label="Under inspector review" value={wf.UNDER_REVIEW} to="/rfis?workflow_status=UNDER_REVIEW" />
      <Kpi label={`Awaiting RE/${deputyLabel()} decision`} value={wf.AWAITING_DECISION} to="/rfis?workflow_status=AWAITING_DECISION" />
    </div>

    {d.new_batches && <div className="card"><h3>New DOC_01 submissions</h3>{d.new_batches.length ? <div className="table-wrap"><table>
      <thead><tr><th>Batch</th><th>Submitted</th><th>RFIs</th><th>Short notice</th><th>Received</th></tr></thead>
      <tbody>{d.new_batches.map((b: any) => <tr key={b.id}><td><Link className="link" to={`/summaries/${b.id}`}>{b.summary_reference}</Link></td><td>{fmtDate(b.submitted_at)}</td><td>{b.rfi_count}</td>
        <td>{b.short_notice ? <Status value="SHORT_NOTICE" label={`${b.short_notice} short notice`} /> : '—'}</td><td>{b.received_at ? fmtDate(b.received_at) : <span className="muted">not yet</span>}</td></tr>)}</tbody>
    </table></div> : <div className="empty">No new submissions.</div>}</div>}
    {d.awaiting_assignment && <div className="card"><h3>RFIs awaiting inspector assignment</h3><RfiTable rows={d.awaiting_assignment} empty="Nothing waiting for assignment." extra={r => <Link className="btn sm" to={`/rfis/${r.id}`}>Assign</Link>} /></div>}
    {d.awaiting_decision && <div className="card"><h3>Awaiting your final decision</h3><RfiTable rows={d.awaiting_decision} empty="No RFIs awaiting a decision." extra={r => <Link className="btn sm success" to={`/rfis/${r.id}`}>Decide</Link>} /></div>}
    {d.overdue_reviews?.length > 0 && <div className="card"><h3>Overdue inspector reviews</h3><RfiTable rows={d.overdue_reviews} empty="" /></div>}
    {d.under_review && <div className="card"><h3>Active inspections</h3><RfiTable rows={d.under_review} empty="No active inspections." /></div>}
    {d.pending_amendments > 0 && <div className="notice">{d.pending_amendments} amendment request(s) await your approval. Open the RFI to review them.</div>}

    {d.my_active && <>
      <div className="card"><h3>Your turn now</h3><RfiTable rows={d.my_active} empty="Nothing is waiting for your inspection." extra={r => <Link className="btn sm" to={`/rfis/${r.id}`}>Inspect</Link>} /></div>
      <div className="card"><h3>Upcoming (waiting for earlier inspectors)</h3><RfiTable rows={d.my_upcoming} empty="No upcoming inspections." /></div>
      <div className="card"><h3>Recently submitted by you</h3><RfiTable rows={d.my_completed} empty="No completed reviews yet." /></div>
    </>}

    {d.drafts && <>
      <div className="card"><div className="section-title"><h3>Draft / returned DOC_01 batches</h3><Link className="btn sm" to="/summaries">New DOC_01</Link></div>
        {d.drafts.length ? <ul>{d.drafts.map((s: any) => <li key={s.id}><Link className="link" to={`/summaries/${s.id}`}>{s.summary_reference}</Link> <Status value={s.workflow_status} />{s.returned_reason && <span className="muted"> — returned: {s.returned_reason}</span>}</li>)}</ul> : <div className="empty">No drafts.</div>}</div>
      <div className="card"><h3>Requires your action (not approved / partially approved)</h3><RfiTable rows={d.action_required} empty="Nothing requires action." extra={r => <Link className="btn sm warn" to={`/rfis/${r.id}`}>Open</Link>} /></div>
    </>}
    {d.recent_decisions && <div className="card"><h3>Recent final decisions</h3><RfiTable rows={d.recent_decisions} empty="No decisions recorded yet." /></div>}
    {d.admin && <div className="card"><h3>Administration</h3><p>{d.admin.projects} projects · {d.admin.users} users · {d.admin.memberships} active members on this project.</p>
      <div className="table-wrap"><table><thead><tr><th>When</th><th>Action</th><th>Record</th></tr></thead><tbody>{d.admin.recent_audit.map((a: any, i: number) => <tr key={i}><td>{fmtDate(a.created_at)}</td><td>{a.action}</td><td>{a.entity_type} #{a.entity_id}</td></tr>)}</tbody></table></div></div>}
  </>;
}
