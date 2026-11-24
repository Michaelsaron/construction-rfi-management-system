import React, { useEffect, useState } from 'react';
import { Link, Navigate } from 'react-router-dom';
import { api, currentProjectId, download, fmtDate, fmtDay, isAdmin, deputyLabel } from '../lib/api';
import { useProject } from '../lib/project';
import { PageHeader, KpiCard, Loading, ErrorNote } from '../components/ui';
import { Table } from './Queues';
import Status from '../components/Status';

export default function Dashboard() {
  const { category } = useProject();
  if (isAdmin()) return <AdminDashboard />;
  if (category === '2.2') return <Navigate to="/my-inspections" replace />;
  if (category === '2.3') return <Navigate to="/rfis" replace />;
  return <ProjectDashboard />;
}

/** Category 1 — System administration (UI design s.2). Every number comes from the database. */
function AdminDashboard() {
  const [o, setO] = useState<any>(null); const [ms, setMs] = useState<any[] | null>(null); const [err, setErr] = useState('');
  useEffect(() => { api('/admin/overview').then(setO).catch(e => setErr(e.message)); api('/admin/memberships?include_revoked=false').then(setMs).catch(e => { setErr(e.message); setMs([]); }); }, []);
  return <>
    <PageHeader title="System administration" />
    <ErrorNote error={err} />
    {!o ? <Loading /> : <div className="stats">
      <KpiCard label="Active projects" value={o.active_projects} caption={`Configured project workspaces${o.archived_projects ? ` · ${o.archived_projects} archived` : ''}`} tone="blue" to="/projects" />
      <KpiCard label="Active accounts" value={o.active_accounts} caption={`${o.active_memberships} active project memberships`} tone="green" to="/users" />
      <KpiCard label="Pending invitations" value={o.invitations.implemented ? o.invitations.pending : null} caption={o.invitations.implemented ? 'Awaiting activation' : 'Invitation workflow pending decision UD-12'} tone="amber" />
      <KpiCard label="Inactive accounts" value={o.inactive_accounts} caption="Historical actions retained" tone="grey" to="/users" />
    </div>}
    {o && (o.accounts_without_project > 0 || o.accounts_with_temporary_password > 0) && <div className="notice info">
      {o.accounts_without_project > 0 && <>{o.accounts_without_project} active account(s) have no project membership. </>}
      {o.accounts_with_temporary_password > 0 && <>{o.accounts_with_temporary_password} account(s) still use a temporary password.</>}</div>}
    <div className="card">
      <h3>Project membership and role administration</h3>
      <Table rows={ms && ms.slice(0, 12)} empty="No project memberships yet."
        cols={[{ h: 'User', c: m => m.full_name }, { h: 'Project', c: m => <span title={m.project_name}>{m.project_code}</span> },
          { h: 'Category / role', c: m => `${m.category || '—'} · ${m.role_label}` }, { h: 'Account', c: m => <Status value={m.account_active ? 'ACTIVE' : 'CANCELLED'} label={m.account_active ? 'Active' : 'Deactivated'} /> },
          { h: 'Actions', c: m => <Link className="link" to={`/memberships?user=${m.user_id}`}>View / Edit</Link> }]} />
      {ms && ms.length > 12 && <p className="muted" style={{ fontSize: 13 }}><Link className="link" to="/memberships">All {ms.length} memberships →</Link></p>}
      <div className="actions">
        <Link className="btn success" to="/projects">+ Create project</Link>
        <Link className="btn" to="/users">+ Add user</Link>
        <button className="btn neutral" onClick={() => download('/admin/access-matrix.xlsx', 'access_matrix.xlsx')}>Export access matrix</button>
      </div>
      <p className="muted" style={{ fontSize: 12.5 }}>Deactivating an account revokes access immediately; its historical records and attachments are kept.</p>
    </div>
  </>;
}

/** Category 2.1 management dashboard (UI design s.3) and the contractor overview. */
function ProjectDashboard() {
  const pid = currentProjectId();
  const [d, setD] = useState<any>(null); const [err, setErr] = useState('');
  useEffect(() => { if (pid) api(`/dashboard?project_id=${pid}`).then(setD).catch(e => setErr(e.message)); }, [pid]);
  if (!pid) return <div className="card"><h2>No project selected</h2><p className="muted">You are not a member of any project yet. Ask the System Administrator to add you to a project with the correct role.</p></div>;
  if (err) return <ErrorNote error={err} />;
  if (!d) return <Loading />;
  const wf = d.counts.by_workflow || {};
  if (d.new_batches) return <>
    <PageHeader title="Management dashboard" />
    <div className="stats">
      <KpiCard label="New DOC_01 batches" value={d.new_batches.filter((b: any) => b.next_action !== 'None').length} caption="Awaiting management review" tone="blue" to="/summaries" />
      <KpiCard label="RFIs under review" value={wf.UNDER_REVIEW || 0} caption="Across active sequences" tone="amber" to="/workflow" />
      <KpiCard label="Awaiting final decision" value={wf.AWAITING_DECISION || 0} caption="All inspector reviews complete" tone="red" to="/decisions" />
      <KpiCard label="Completed this week" value={d.completed_this_week ?? 0} caption="DOC_02 updated" tone="green" to="/completed" />
    </div>
    {d.pending_amendments > 0 && <div className="notice">{d.pending_amendments} amendment request(s) await RE/{deputyLabel()} approval. Open the RFI to review them.</div>}
    <div className="card">
      <h3>Daily Request for Inspection Summary Sheets</h3>
      <Table rows={d.new_batches} empty="No submitted DOC_01 batches."
        cards={b => <><div className="row1"><Link className="link" to={`/summaries/${b.id}`}>{b.summary_reference}</Link><Status value={b.status === 'In review' ? 'UNDER_REVIEW' : 'SUBMITTED'} label={b.status} /></div>
          <dl><dt>Requested by</dt><dd>{b.requested_by}</dd><dt>Inspection</dt><dd>{fmtDay(b.first_inspection_date)} {b.first_inspection_time}</dd><dt>RFIs</dt><dd>{b.rfi_count}</dd><dt>Next action</dt><dd>{b.next_action}</dd></dl></>}
        cols={[{ h: 'Batch / RFI', c: b => <Link className="link" to={`/summaries/${b.id}`}>{b.summary_reference}</Link> }, { h: 'Requested by', c: b => b.requested_by || '—' },
          { h: 'Inspection date / time', c: b => <>{fmtDay(b.first_inspection_date)} {b.first_inspection_time ? `· ${b.first_inspection_time}` : ''}{b.short_notice > 0 && <div><Status value="SHORT_NOTICE" label={`${b.short_notice} short notice`} /></div>}</>, cls: 'nowrap' },
          { h: 'RFI count', c: b => String(b.rfi_count).padStart(2, '0'), cls: 'num' }, { h: 'Next action', c: b => <Link className="link" to={`/summaries/${b.id}`}>{b.next_action}</Link> },
          { h: 'Status', c: b => <Status value={b.status === 'In review' ? 'UNDER_REVIEW' : 'SUBMITTED'} label={b.status} /> }]} />
      <div className="legend"><span className="pill amber">24-hour notice warning</span>Short-notice items are flagged for management attention; {d.notice_policy === 'REQUIRE_OVERRIDE' ? 'this project requires the contractor to give a reason.' : 'not blocked by default.'}</div>
    </div>
    {d.overdue_reviews?.length > 0 && <div className="card"><h3>Overdue inspector turns</h3><Table rows={d.overdue_reviews} empty=""
      cols={[{ h: 'RFI No.', c: r => <Link className="link mono" to={`/rfis/${r.id}/workflow`}>{r.rfi_number}</Link> }, { h: 'Work description', c: r => r.contractor_request || r.work_item }, { h: 'Inspection', c: r => `${fmtDay(r.inspection_date)} ${r.inspection_time || ''}` }]} /></div>}
  </>;
  return <>
    <PageHeader title="Overview" actions={<Link className="btn success" to="/doc01/new">+ New DOC_01</Link>} />
    <div className="stats">
      <KpiCard label="Draft / returned batches" value={(d.drafts || []).length} tone="grey" to="/doc01/drafts" />
      <KpiCard label="Submitted batches" value={(d.submitted_batches || []).length} tone="blue" to="/doc01/submitted" />
      <KpiCard label="Requires your action" value={(d.action_required || []).length} caption="Not approved / partially approved" tone="red" to="/my-rfis" />
    </div>
    {d.drafts?.some((s: any) => s.workflow_status === 'RETURNED') && <div className="notice err">One or more DOC_01 batches were returned for correction. See <Link className="link" to="/doc01/drafts">Draft submissions</Link>.</div>}
    <div className="card"><h3>Requires your action</h3><Table rows={d.action_required || []} empty="Nothing requires action."
      cols={[{ h: 'RFI No.', c: r => <Link className="link mono" to={`/rfis/${r.id}`}>{r.rfi_number}</Link> }, { h: 'Work description', c: r => r.contractor_request || r.work_item }, { h: 'Decision', c: r => <Status value={r.current_decision} /> }]} /></div>
    <div className="card"><h3>Recent final decisions</h3><Table rows={d.recent_decisions || []} empty="No decisions recorded yet."
      cols={[{ h: 'RFI No.', c: r => <Link className="link mono" to={`/completed/${r.id}`}>{r.rfi_number}</Link> }, { h: 'Work description', c: r => r.contractor_request || r.work_item }, { h: 'Decision', c: r => <Status value={r.current_decision} /> }]} /></div>
    <p className="muted" style={{ fontSize: 12 }}>Updated {fmtDate(new Date().toISOString().replace('Z', ''))}</p>
  </>;
}
