import React, { useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { api, download, currentProjectId, fmtDay, loc } from '../lib/api';
import Status, { pretty } from '../components/Status';

const EMPTY: Record<string, string> = { q: '', workflow_status: '', decision: '', disposition: '', legacy_status: '', work_item: '', side: '', road_type: '', date_from: '', date_to: '', provenance: '', short_notice: '', latest_only: '' };
const COLS: [string, string][] = [['rfi_number', 'RFI No.'], ['inspection_date', 'Inspection'], ['work_item', 'Item'], ['', 'Contractor request'], ['chainage_from', 'Location'], ['road_type', 'Road type'], ['', 'RFI status'], ['workflow_status', 'Workflow'], ['', 'Inspectors']];
const PAGE = 50;

export default function Rfis() {
  const pid = currentProjectId();
  const [sp, setSp] = useSearchParams();
  const initial = useMemo(() => ({ ...EMPTY, ...Object.fromEntries([...sp.entries()].filter(([k]) => k in EMPTY)) }), []);
  const [f, setF] = useState<Record<string, string>>(initial); const [applied, setApplied] = useState<Record<string, string>>(initial);
  const [sort, setSort] = useState({ sort: 'id', dir: 'desc' }); const [offset, setOffset] = useState(0);
  const [data, setData] = useState<any>(null); const [master, setMaster] = useState<any[]>([]); const [err, setErr] = useState(''); const [settings, setSettings] = useState<any>(null);
  const qs = (extra: Record<string, any> = {}) => { const p = new URLSearchParams(); if (pid) p.set('project_id', String(pid)); Object.entries({ ...applied, ...sort, ...extra }).forEach(([k, v]) => { if (v !== '' && v != null) p.set(k, String(v)); }); return p.toString(); };
  useEffect(() => { if (!pid) return; setData(null); api(`/rfis?${qs({ limit: PAGE, offset })}`).then(setData).catch(e => setErr(e.message)); }, [pid, applied, sort, offset]);
  useEffect(() => { if (pid) { api(`/master-data?project_id=${pid}`).then(setMaster).catch(() => {}); api(`/projects/${pid}/settings`).then(setSettings).catch(() => {}); } }, [pid]);
  const vals = (c: string) => [...new Set(master.filter(x => x.category === c).map(x => x.value))] as string[];
  const active = Object.entries(applied).filter(([, v]) => v);
  const apply = (e?: any) => { e?.preventDefault(); setOffset(0); setApplied(f); setSp(Object.fromEntries(Object.entries(f).filter(([, v]) => v))); };
  const clear = () => { setF(EMPTY); setApplied(EMPTY); setOffset(0); setSp({}); };
  const sortBy = (k: string) => { if (!k) return; setSort(s => ({ sort: k, dir: s.sort === k && s.dir === 'desc' ? 'asc' : 'desc' })); setOffset(0); };
  const sel = (k: string, label: string, opts: [string, string][]) => <div><label>{label}</label><select value={f[k]} onChange={e => setF({ ...f, [k]: e.target.value })}><option value="">All</option>{opts.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></div>;
  if (!pid) return <div className="empty">Select a project.</div>;
  return <>
    <div className="top"><div><h1>DOC_02 – Main RFI Record Sheet</h1><p className="subtitle">Central register: one row per RFI revision, populated from DOC_01 and completed by the DOC_03 final decision.</p></div>
      <div className="toolbar"><button className="btn alt" onClick={() => download(`/reports/register.xlsx?${qs()}`, 'DOC02_register.xlsx')}>Export Excel{active.length ? ' (filtered)' : ''}</button>
        <button className="btn secondary" onClick={() => download(`/reports/register.pdf?${qs()}`, 'DOC02_register.pdf')}>Export PDF{active.length ? ' (filtered)' : ''}</button></div></div>
    {err && <div className="notice err">{err}</div>}
    <form className="card" onSubmit={apply}><div className="grid">
      <div><label>Search</label><input placeholder="RFI No., description, chainage, remark…" value={f.q} onChange={e => setF({ ...f, q: e.target.value })} /></div>
      {sel('workflow_status', 'Workflow status', ['DRAFT', 'SUBMITTED', 'UNDER_REVIEW', 'AWAITING_DECISION', 'COMPLETED', 'CANCELLED', 'ARCHIVED'].map(x => [x, pretty(x)]))}
      {sel('decision', 'Decision', ['APPROVED', 'PARTIALLY_APPROVED', 'REJECTED', 'ON_PROGRESS', 'INFORMATION_ONLY'].map(x => [x, pretty(x)]))}
      {sel('disposition', 'DOC_03 disposition', (settings?.dispositions || []).map((d: any) => [d.code, d.label]))}
      {sel('legacy_status', 'Historical RFI_Status', ['Accepted', 'Accepted as Noted', 'Not Ready', 'Note ready', 'Information', 'Information Only', 'Rejected', 'Approved: For further works', 'Not Approved: RFI to be resubmitted'].map(x => [x, x]))}
      {sel('work_item', 'Item', vals('WORK_ITEM').map(x => [x, pretty(x)]))}
      {sel('side', 'Side', vals('SIDE').map(x => [x, x]))}
      {sel('road_type', 'Road type', vals('ROAD_TYPE').map(x => [x, x]))}
      <div><label>Inspection from</label><input type="date" value={f.date_from} onChange={e => setF({ ...f, date_from: e.target.value })} /></div>
      <div><label>Inspection to</label><input type="date" value={f.date_to} onChange={e => setF({ ...f, date_to: e.target.value })} /></div>
      {sel('provenance', 'Source', [['PORTAL', 'Submitted in system'], ['LEGACY_IMPORT', 'Historical import']])}
      {sel('short_notice', 'Short notice', [['true', 'Yes'], ['false', 'No']])}
      {sel('latest_only', 'Revisions', [['true', 'Latest revision only']])}
    </div><div className="toolbar" style={{ marginTop: 12 }}><button className="btn">Apply filters</button><button type="button" className="btn secondary" onClick={clear}>Clear filters</button></div></form>
    {active.length > 0 && <div className="notice">Filtered register: {active.map(([k, v]) => `${pretty(k)} = ${v}`).join(' · ')}. Exports contain only these records.</div>}
    <div className="card">
      {!data ? <div className="empty">Loading…</div> : data.items.length === 0 ? <div className="empty">No records match.</div> : <>
        <p className="muted" style={{ marginTop: 0 }}>{data.total.toLocaleString()} record(s){active.length ? ' (filtered)' : ''} · showing {offset + 1}–{offset + data.items.length}</p>
        <div className="table-wrap"><table><thead><tr>{COLS.map(([k, l]) => <th key={l} onClick={() => sortBy(k)} style={k ? { cursor: 'pointer' } : undefined} aria-sort={sort.sort === k ? (sort.dir === 'asc' ? 'ascending' : 'descending') : undefined}>{l}{sort.sort === k ? (sort.dir === 'asc' ? ' ▲' : ' ▼') : ''}</th>)}</tr></thead>
          <tbody>{data.items.map((r: any) => <tr key={r.id}>
            <td><Link className="link mono" to={`/rfis/${r.id}`}>{r.rfi_number}</Link>{r.revision_no ? <span className="muted"> R{r.revision_no}</span> : null}</td>
            <td>{fmtDay(r.inspection_date)} {r.inspection_time || r.inspection_time_text || ''}{r.short_notice && <div><Status value="SHORT_NOTICE" label="Short notice" /></div>}</td>
            <td>{pretty(r.work_item)}</td><td style={{ maxWidth: 340 }}>{r.contractor_request || r.description}</td><td className="mono">{loc(r)}</td><td>{r.road_type || '—'}</td>
            <td>{r.is_legacy ? (r.legacy_rfi_status || '—') : <Status value={r.current_decision} />}</td>
            <td><Status value={r.workflow_status} label={r.status_label} /></td>
            <td style={{ fontSize: 12 }}>{r.inspectors.map((i: any) => `${i.sequence_no}. ${i.name}`).join(', ') || '—'}</td></tr>)}</tbody></table></div>
        <div className="toolbar" style={{ marginTop: 12 }}><button className="btn secondary" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>← Previous</button>
          <button className="btn secondary" disabled={offset + PAGE >= data.total} onClick={() => setOffset(offset + PAGE)}>Next →</button>
          <span className="muted">Page {Math.floor(offset / PAGE) + 1} of {Math.max(1, Math.ceil(data.total / PAGE))}</span></div>
      </>}
    </div>
  </>;
}
