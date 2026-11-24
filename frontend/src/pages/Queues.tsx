import React, { useEffect, useState } from 'react';
import { Link, Navigate } from 'react-router-dom';
import { api, download, currentProjectId, getUser, fmtDate, fmtDay, loc, roleLabel } from '../lib/api';
import { PageHeader, Loading, ErrorNote } from '../components/ui';
import { previewFile } from '../components/EvidencePanel';
import { fileSize } from '../lib/upload';
import Status, { pretty } from '../components/Status';

type Col = { h: string; c: (r: any) => React.ReactNode; cls?: string };
const C = {
  rfi: (to: (r: any) => string): Col => ({ h: 'RFI No.', c: r => <Link className="link mono" to={to(r)}>{r.rfi_number}</Link>, cls: 'nowrap' }),
  desc: { h: 'Work description', c: (r: any) => r.contractor_request || r.description || r.work_item } as Col,
  loc: { h: 'Station', c: (r: any) => <span className="mono">{loc(r)}</span> } as Col,
  insp: { h: 'Inspection', c: (r: any) => <>{fmtDay(r.inspection_date)} {r.inspection_time || ''}{r.short_notice && <div><Status value="SHORT_NOTICE" label="Short notice" /></div>}</>, cls: 'nowrap' } as Col,
  status: { h: 'Status', c: (r: any) => <Status value={r.workflow_status} label={r.status_label} /> } as Col,
};

export function Table({ rows, cols, empty, cards }: { rows: any[] | null; cols: Col[]; empty: string; cards?: (r: any) => React.ReactNode }) {
  if (rows === null) return <Loading />;
  if (!rows.length) return <div className="empty">{empty}</div>;
  return <>
    {cards && <ul className="rec-cards">{rows.map((r, i) => <li key={r.id ?? i} className="rec-card">{cards(r)}</li>)}</ul>}
    <div className="table-wrap"><table><thead><tr>{cols.map(c => <th key={c.h}>{c.h}</th>)}</tr></thead>
      <tbody>{rows.map((r, i) => <tr key={r.id ?? i}>{cols.map(c => <td key={c.h} className={c.cls}>{c.c(r)}</td>)}</tr>)}</tbody></table></div>
  </>;
}

function rfiCard(to: string, r: any, action?: React.ReactNode) {
  return <><div className="row1"><Link className="link mono" to={to}>{r.rfi_number}</Link><Status value={r.workflow_status} label={r.status_label} /></div>
    <dl><dt>Work</dt><dd>{r.contractor_request || r.description || r.work_item}</dd><dt>Station</dt><dd className="mono">{loc(r)}</dd><dt>Inspection</dt><dd>{fmtDay(r.inspection_date)} {r.inspection_time || ''}</dd></dl>
    {action && <div className="actions" style={{ marginTop: 8 }}>{action}</div>}</>;
}

function useRegister(params: string) {
  const pid = currentProjectId();
  const [rows, setRows] = useState<any[] | null>(null); const [err, setErr] = useState('');
  useEffect(() => { if (pid) api(`/rfis?project_id=${pid}&${params}`).then((d: any) => setRows(d.items)).catch(e => { setErr(e.message); setRows([]); }); }, [pid, params]);
  return { rows, err };
}
const activeOf = (r: any) => (r.inspectors || []).find((i: any) => i.status === 'ACTIVE');

// ------------------------------------------------------------------------------------------ Category 2.1
export function AssignmentQueue() {
  const a = useRegister('workflow_status=SUBMITTED&limit=200&sort=inspection_date&dir=asc');
  const b = useRegister('workflow_status=UNDER_REVIEW&limit=200&sort=inspection_date&dir=asc');
  const act = (r: any, label: string) => <Link className="btn sm success" to={`/rfis/${r.id}/assign`}>{label}</Link>;
  return <>
    <PageHeader title="Inspector assignment" />
    <ErrorNote error={a.err || b.err} />
    <div className="card"><h3>Awaiting inspector assignment</h3>
      <Table rows={a.rows} empty="No submitted RFIs are waiting for assignment." cards={r => rfiCard(`/rfis/${r.id}/assign`, r, act(r, 'Assign'))}
        cols={[C.rfi(r => `/rfis/${r.id}/assign`), C.desc, C.loc, C.insp, { h: 'DOC_01', c: r => r.summary_reference || '—' }, { h: '', c: r => act(r, 'Assign') }]} /></div>
    <div className="card"><h3>Under review — sequence can be changed with a reason</h3>
      <Table rows={b.rows} empty="No RFIs under review." cards={r => rfiCard(`/rfis/${r.id}/assign`, r, act(r, 'Change sequence'))}
        cols={[C.rfi(r => `/rfis/${r.id}/workflow`), C.desc, { h: 'Assigned sequence', c: r => (r.inspectors || []).map((i: any) => roleLabel(i.role).split(' ').map((w: string) => w[0]).join('')).join(' → ') || '—' },
          { h: 'Active', c: r => activeOf(r) ? `#${activeOf(r).sequence_no} ${activeOf(r).name}` : '—' }, { h: '', c: r => <Link className="btn sm secondary" to={`/rfis/${r.id}/assign`}>Change sequence</Link> }]} /></div>
  </>;
}

export function WorkflowQueue() {
  const a = useRegister('workflow_status=UNDER_REVIEW&limit=200&sort=inspection_date&dir=asc');
  return <>
    <PageHeader title="Workflow monitor" />
    <ErrorNote error={a.err} />
    <div className="card"><h3>RFIs in sequential review</h3>
      <Table rows={a.rows} empty="No RFIs are under inspector review." cards={r => rfiCard(`/rfis/${r.id}/workflow`, r)}
        cols={[C.rfi(r => `/rfis/${r.id}/workflow`), C.desc, C.insp, { h: 'Sequence', c: r => (r.inspectors || []).map((i: any) => <div key={i.sequence_no} style={{ fontSize: 12.5 }}>{i.sequence_no}. {roleLabel(i.role)} — <Status value={i.status} /></div>) },
          { h: '', c: r => <Link className="btn sm" to={`/rfis/${r.id}/workflow`}>Monitor</Link> }]} /></div>
  </>;
}

export function DecisionQueue() {
  const a = useRegister('workflow_status=AWAITING_DECISION&limit=200&sort=updated_at&dir=asc');
  return <>
    <PageHeader title="Final decisions" />
    <ErrorNote error={a.err} />
    <div className="card"><h3>Awaiting final disposition</h3>
      <Table rows={a.rows} empty="No RFIs are awaiting a final decision." cards={r => rfiCard(`/rfis/${r.id}/decision`, r, <Link className="btn sm success" to={`/rfis/${r.id}/decision`}>Decide</Link>)}
        cols={[C.rfi(r => `/rfis/${r.id}/decision`), C.desc, C.loc, C.insp, { h: 'Reviews', c: r => `${(r.inspectors || []).length} submitted` }, { h: '', c: r => <Link className="btn sm success" to={`/rfis/${r.id}/decision`}>Decide</Link> }]} /></div>
  </>;
}

// ------------------------------------------------------------------------------------------ Category 2.2
function useMine() {
  const pid = currentProjectId();
  const [rows, setRows] = useState<any[] | null>(null); const [err, setErr] = useState('');
  useEffect(() => { api('/rfis/my-inspections').then((x: any[]) => setRows(x.filter(i => !pid || i.rfi.project_id === pid))).catch(e => { setErr(e.message); setRows([]); }); }, [pid]);
  return { rows, err };
}
const reviewLink = (x: any) => `/rfis/${x.rfi.id}/review`;
const inspCols = (last: Col): Col[] => [
  { h: 'RFI', c: x => <Link className="link mono" to={reviewLink(x)}>{x.rfi.rfi_number}</Link>, cls: 'nowrap' }, { h: 'Work description', c: x => x.rfi.contractor_request || x.rfi.work_item },
  { h: 'Station', c: x => <span className="mono">{loc(x.rfi)}</span> }, { h: 'Inspection', c: x => `${fmtDay(x.rfi.inspection_date)} ${x.rfi.inspection_time || ''}`, cls: 'nowrap' },
  { h: 'Your field · #', c: x => `${roleLabel(x.assignment.reviewer_role)} · ${x.assignment.sequence_no}` }, last];
const inspCard = (x: any, extra: React.ReactNode) => <><div className="row1"><Link className="link mono" to={reviewLink(x)}>{x.rfi.rfi_number}</Link><span className="badge">#{x.assignment.sequence_no} {roleLabel(x.assignment.reviewer_role)}</span></div>
  <dl><dt>Work</dt><dd>{x.rfi.contractor_request || x.rfi.work_item}</dd><dt>Station</dt><dd className="mono">{loc(x.rfi)}</dd><dt>Inspection</dt><dd>{fmtDay(x.rfi.inspection_date)} {x.rfi.inspection_time || ''}</dd></dl>
  <div className="actions" style={{ marginTop: 8 }}>{extra}</div></>;

export function MyAssigned() {
  const { rows, err } = useMine();
  const act = rows?.filter(x => x.assignment.status === 'ACTIVE') ?? null, up = rows?.filter(x => x.assignment.status === 'PENDING') ?? null;
  return <>
    <PageHeader title="My assigned RFIs" />
    <p className="subtitle">Reviews are strictly sequential. You can comment, attach evidence and submit only when it is your turn.</p>
    <ErrorNote error={err} />
    <div className="card"><h3>Your turn is active</h3><Table rows={act} empty="Nothing is waiting for your review." cards={x => inspCard(x, <Link className="btn success" to={reviewLink(x)}>Open DOC_03 review</Link>)}
      cols={inspCols({ h: '', c: x => <Link className="btn sm success" to={reviewLink(x)}>Inspect</Link> })} /></div>
    <div className="card"><h3>Awaiting your turn</h3><Table rows={up} empty="No upcoming inspections." cards={x => inspCard(x, <span className="muted">Waiting for #{x.waiting_for?.sequence_no ?? '—'} {x.waiting_for?.name || ''}</span>)}
      cols={inspCols({ h: 'Waiting for', c: x => x.waiting_for ? `#${x.waiting_for.sequence_no} ${x.waiting_for.name || ''} (${roleLabel(x.waiting_for.role)})` : '—' })} /></div>
  </>;
}

export function ActiveReviews() {
  const { rows, err } = useMine();
  const act = rows?.filter(x => x.assignment.status === 'ACTIVE') ?? null;
  if (act && act.length === 1) return <Navigate to={reviewLink(act[0])} replace />;
  return <>
    <PageHeader title="Active DOC_03" />
    <ErrorNote error={err} />
    <div className="card"><Table rows={act} empty="You have no active DOC_03 review. You will be notified when it is your turn." cards={x => inspCard(x, <Link className="btn success" to={reviewLink(x)}>Open</Link>)}
      cols={inspCols({ h: 'Active since', c: x => fmtDate(x.assignment.activated_at) })} /></div>
  </>;
}

export function ReviewHistory() {
  const { rows, err } = useMine();
  const done = rows?.filter(x => x.assignment.status === 'COMPLETED') ?? null;
  return <>
    <PageHeader title="Review history" />
    <ErrorNote error={err} />
    <div className="card"><Table rows={done} empty="No submitted reviews yet." cards={x => inspCard(x, <Link className="btn secondary" to={reviewLink(x)}>View review</Link>)}
      cols={inspCols({ h: 'Submitted', c: x => <>{fmtDate(x.assignment.completed_at)}<div><Status value={x.rfi.workflow_status} label={x.rfi.status_label} /></div></> })} /></div>
  </>;
}

export function MyAttachments() {
  const pid = currentProjectId();
  const [rows, setRows] = useState<any[] | null>(null); const [err, setErr] = useState('');
  useEffect(() => { api(`/evidence/mine${pid ? `?project_id=${pid}` : ''}`).then(setRows).catch(e => { setErr(e.message); setRows([]); }); }, [pid]);
  return <>
    <PageHeader title="My attachments" />
    <p className="subtitle">Evidence you added to your own DOC_03 reviews and remarks. Files of submitted reviews are locked.</p>
    <ErrorNote error={err} />
    <div className="card"><Table rows={rows} empty="You have not attached any evidence yet."
      cols={[{ h: 'File', c: f => <>{f.original_name}<div className="muted" style={{ fontSize: 12 }}>{fileSize(f.size_bytes)}</div></> },
        { h: 'RFI', c: f => f.rfi_id ? <Link className="link mono" to={`/rfis/${f.rfi_id}/review`}>{f.rfi_number}</Link> : '—' }, { h: 'Stage', c: f => f.kind_label },
        { h: 'Uploaded', c: f => fmtDate(f.uploaded_at), cls: 'nowrap' }, { h: 'State', c: f => <Status value={f.locked ? 'COMPLETED' : 'DRAFT'} label={f.locked ? 'Submitted · locked' : f.upload_status === 'PENDING_APPROVAL' ? 'Awaiting approval' : 'Draft'} /> },
        { h: '', c: f => <>{f.previewable && <button className="btn secondary sm" onClick={() => previewFile(f)}>Preview</button>} <button className="btn secondary sm" onClick={() => download(`/evidence/files/${f.id}/download`, f.original_name)}>Open</button></> }]} /></div>
  </>;
}

// ------------------------------------------------------------------------------------------ Category 2.3
export function CompletedList() {
  const [hist, setHist] = useState(false);
  const a = useRegister(`workflow_status=COMPLETED&limit=200&sort=updated_at&dir=desc${hist ? '' : '&provenance=PORTAL'}`);
  return <>
    <PageHeader title="Completed DOC_03" />
    <label className="check" style={{ marginBottom: 12 }}><input type="checkbox" checked={hist} onChange={e => setHist(e.target.checked)} />Include historical (imported) records</label>
    <ErrorNote error={a.err} />
    <div className="card"><Table rows={a.rows} empty="No completed RFIs." cards={r => rfiCard(`/completed/${r.id}`, r, <Link className="btn sm" to={`/completed/${r.id}`}>Open record</Link>)}
      cols={[C.rfi(r => `/completed/${r.id}`), C.desc, C.loc, C.insp, { h: 'Disposition', c: r => r.is_legacy ? (r.legacy_rfi_status || '—') : <Status value={r.current_decision} /> },
        { h: '', c: r => <Link className="btn sm secondary" to={`/completed/${r.id}`}>Open</Link> }]} /></div>
  </>;
}

export function SearchPage() {
  const pid = currentProjectId();
  const [q, setQ] = useState(''); const [rows, setRows] = useState<any[] | null>([]); const [total, setTotal] = useState(0); const [err, setErr] = useState(''); const [ran, setRan] = useState(false);
  async function go(e?: any) {
    e?.preventDefault(); if (!q.trim()) return; setRows(null); setRan(true);
    try { const d: any = await api(`/rfis?project_id=${pid}&q=${encodeURIComponent(q.trim())}&limit=100`); setRows(d.items); setTotal(d.total); } catch (x: any) { setErr(x.message); setRows([]); }
  }
  const to = (r: any) => (r.workflow_status === 'COMPLETED' && !r.is_legacy ? `/completed/${r.id}` : `/rfis/${r.id}`);
  return <>
    <PageHeader title="Search" />
    <form className="card" onSubmit={go} role="search"><label htmlFor="sq">RFI No., description, station, road type or remark</label>
      <div className="toolbar"><input id="sq" style={{ flex: '1 1 320px' }} value={q} onChange={e => setQ(e.target.value)} placeholder="e.g. AS-014/2026 or asphalt or 187+325" autoFocus /><button className="btn">Search</button></div></form>
    <ErrorNote error={err} />
    {ran && <div className="card">{rows && <p className="muted" style={{ marginTop: 0 }}>{total.toLocaleString()} match(es){total > 100 ? ' — showing the first 100; refine the search or use the DOC_02 register filters' : ''}</p>}
      <Table rows={rows} empty="No records match." cards={r => rfiCard(to(r), r)} cols={[C.rfi(to), C.desc, C.loc, C.insp, C.status]} /></div>}
  </>;
}

export function ExportsPage() {
  const pid = currentProjectId();
  const [f, setF] = useState({ workflow_status: '', decision: '', date_from: '', date_to: '', provenance: '', latest_only: '' });
  const qs = () => { const p = new URLSearchParams({ project_id: String(pid) }); Object.entries(f).forEach(([k, v]) => v && p.set(k, v)); return p.toString(); };
  const sel = (k: keyof typeof f, label: string, opts: [string, string][]) => <div><label htmlFor={`ex-${k}`}>{label}</label><select id={`ex-${k}`} value={f[k]} onChange={e => setF({ ...f, [k]: e.target.value })}><option value="">All</option>{opts.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></div>;
  return <>
    <PageHeader title="Exports" />
    <p className="subtitle">Exports contain only the records your role may see, in the DOC_02 workbook column order. Use the DOC_02 register for column choices and saved views.</p>
    <div className="card"><h3>DOC_02 register export</h3><div className="grid">
      {sel('workflow_status', 'Workflow status', ['SUBMITTED', 'UNDER_REVIEW', 'AWAITING_DECISION', 'COMPLETED', 'CANCELLED', 'ARCHIVED'].map(x => [x, pretty(x)]))}
      {sel('decision', 'Decision', ['APPROVED', 'PARTIALLY_APPROVED', 'REJECTED', 'ON_PROGRESS', 'INFORMATION_ONLY'].map(x => [x, pretty(x)]))}
      <div><label htmlFor="ex-df">Inspection from</label><input id="ex-df" type="date" value={f.date_from} onChange={e => setF({ ...f, date_from: e.target.value })} /></div>
      <div><label htmlFor="ex-dt">Inspection to</label><input id="ex-dt" type="date" value={f.date_to} onChange={e => setF({ ...f, date_to: e.target.value })} /></div>
      {sel('provenance', 'Source', [['PORTAL', 'Submitted in RFIMS'], ['LEGACY_IMPORT', 'Historical import']])}
      {sel('latest_only', 'Revisions', [['true', 'Latest revision only']])}
    </div>
      <div className="actions"><button className="btn success" onClick={() => download(`/reports/register.xlsx?${qs()}`, 'DOC02_register.xlsx')}>Export Excel</button>
        <button className="btn" onClick={() => download(`/reports/register.pdf?${qs()}`, 'DOC02_register.pdf')}>Export PDF</button></div></div>
    <div className="card"><h3>Other documents</h3><p style={{ margin: 0 }}>DOC_01 PDFs are on each <Link className="link" to="/summaries">DOC_01 batch</Link>; completed DOC_03 PDFs and evidence bundles are on each <Link className="link" to="/completed">completed record</Link>.</p></div>
  </>;
}

// ------------------------------------------------------------------------------------------ Category 3
export function MyRfis() {
  const me = getUser();
  const a = useRegister(`submitted_by=${me.id}&limit=200`);
  const to = (r: any) => (r.workflow_status === 'COMPLETED' ? `/completed/${r.id}` : `/rfis/${r.id}`);
  return <>
    <PageHeader title="My RFI records" />
    <ErrorNote error={a.err} />
    <div className="card"><Table rows={a.rows} empty="You have not submitted any RFIs in this project yet." cards={r => rfiCard(to(r), r)}
      cols={[C.rfi(to), C.desc, C.loc, C.insp, C.status, { h: 'Decision', c: r => r.current_decision ? <Status value={r.current_decision} /> : '—' }]} /></div>
  </>;
}
