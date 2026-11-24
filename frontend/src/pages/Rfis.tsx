import React, { useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { api, post, download, currentProjectId, fmtDay } from '../lib/api';
import { PageHeader, ErrorNote, Loading } from '../components/ui';
import Status, { pretty } from '../components/Status';

const EMPTY: Record<string, string> = { rfi_no: '', q: '', road_type: '', decision: '', date_from: '', date_to: '', workflow_status: '', disposition: '', legacy_status: '',
  work_item: '', side: '', provenance: '', short_notice: '', latest_only: '' };
type Col = { key: string; label: string; sort?: string; pdf?: string[]; hidden?: 'IM' | 'S'; c: (r: any) => React.ReactNode };
const docLink = (r: any) => r.legacy_document ? <span className="muted" title="Historical shared-drive document, not migrated">{r.legacy_document.label}</span>
  : r.workflow_status === 'COMPLETED' && !r.is_legacy ? <Link className="link" to={`/completed/${r.id}`}>DOC_03</Link> : <span className="muted">—</span>;
// Workbook column order (DOC_02 A:AF) for the business columns; I:M and S are the workbook's hidden columns.
const COLS: Col[] = [
  { key: 'rfi_number', label: 'RFI No.', sort: 'rfi_number', pdf: ['rfi_number', 'revision_no'], c: r => <><Link className="link mono" to={`/rfis/${r.id}`}>{r.rfi_number}</Link>{r.revision_no ? <span className="muted"> R{r.revision_no}</span> : null}</> },
  { key: 'work_item', label: 'Item', sort: 'work_item', pdf: ['work_item'], c: r => pretty(r.work_item) },
  { key: 'road_type', label: 'Road type', sort: 'road_type', pdf: ['road_type'], c: r => r.road_type || '—' },
  { key: 'description', label: 'Description', pdf: ['contractor_request'], c: r => <span style={{ display: 'block', maxWidth: 320 }}>{r.contractor_request || r.description}</span> },
  { key: 'side', label: 'Side', sort: 'side', pdf: ['side'], c: r => r.side || '—' },
  { key: 'fill_layer', label: 'Fill layer', hidden: 'IM', pdf: ['fill_layer'], c: r => r.fill_layer || '—' },
  { key: 'material_source_type', label: 'Source/destination type', hidden: 'IM', pdf: ['material_source_type'], c: r => r.material_source_type || '—' },
  { key: 'material_source_cut_section', label: 'Source cut section', hidden: 'IM', pdf: ['material_source_cut_section'], c: r => r.material_source_cut_section || '—' },
  { key: 'material_source_designation', label: 'Source designation', hidden: 'IM', pdf: ['material_source_designation'], c: r => r.material_source_designation || r.material_source || '—' },
  { key: 'material_destination_designation', label: 'Destination designation', hidden: 'IM', pdf: ['material_destination_designation'], c: r => r.material_destination_designation || '—' },
  { key: 'requested', label: 'Requested From / To', sort: 'chainage_from', pdf: ['chainage_from', 'chainage_to'], c: r => <span className="mono nowrap">{r.chainage_from || '—'} / {r.chainage_to || '—'}</span> },
  { key: 'inspection', label: 'Inspection', sort: 'inspection_date', pdf: ['inspection_date', 'inspection_time'], c: r => <span className="nowrap">{fmtDay(r.inspection_date)} {r.inspection_time || r.inspection_time_text || ''}{r.short_notice && <div><Status value="SHORT_NOTICE" label="Short notice" /></div>}</span> },
  { key: 'work_status', label: 'Work status', hidden: 'S', pdf: ['work_status'], c: r => r.work_status || '—' },
  { key: 'rfi_status', label: 'RFI status', sort: 'current_decision', pdf: ['rfi_status'], c: r => r.is_legacy ? (r.legacy_rfi_status || '—') : r.current_decision ? <Status value={r.current_decision} /> : '—' },
  { key: 'approved', label: 'Approved From / To', pdf: ['approved_from', 'approved_to'], c: r => r.approved_from || r.approved_to ? <span className="mono">{r.approved_from} / {r.approved_to}</span> : '—' },
  { key: 'workflow', label: 'Workflow', sort: 'workflow_status', pdf: ['workflow_status'], c: r => <Status value={r.workflow_status} label={r.status_label} /> },
  { key: 'inspectors', label: 'Inspectors', pdf: ['inspectors'], c: r => <span style={{ fontSize: 12 }}>{(r.inspectors || []).map((i: any) => `${i.sequence_no}. ${i.name}`).join(', ') || '—'}</span> },
  { key: 'ipc', label: 'IPC', c: r => r.legacy_ipc_included || (r.legacy_document?.has_ipc_reference ? 'Yes' : 'No') },
  { key: 'batch', label: 'DOC_01', pdf: ['batch'], c: r => r.summary_reference || '—' },
  { key: 'remarks', label: 'Remark', pdf: ['remarks'], c: r => r.remarks || '—' },
  { key: 'doc', label: 'Document', c: docLink },
];
const DEFAULT = ['rfi_number', 'road_type', 'description', 'requested', 'inspection', 'rfi_status', 'workflow', 'ipc', 'doc'];
const PAGE_SIZES = [25, 50, 100];

/** DOC_02 · Main RFI Record Sheet — searchable master register (UI design s.10). */
export default function Rfis() {
  const pid = currentProjectId();
  const [sp, setSp] = useSearchParams();
  const initial = useMemo(() => ({ ...EMPTY, ...Object.fromEntries([...sp.entries()].filter(([k]) => k in EMPTY)) }), []);
  const [f, setF] = useState<Record<string, string>>(initial); const [applied, setApplied] = useState<Record<string, string>>(initial);
  const [sort, setSort] = useState({ sort: 'id', dir: 'desc' }); const [offset, setOffset] = useState(0); const [size, setSize] = useState(50);
  const [cols, setCols] = useState<string[]>(DEFAULT); const [adv, setAdv] = useState({ IM: false, S: false }); const [more, setMore] = useState(false);
  const [data, setData] = useState<any>(null); const [master, setMaster] = useState<any[]>([]); const [err, setErr] = useState(''); const [settings, setSettings] = useState<any>(null);
  const [views, setViews] = useState<any[]>([]); const [view, setView] = useState('');
  const qs = (extra: Record<string, any> = {}) => { const p = new URLSearchParams(); if (pid) p.set('project_id', String(pid)); Object.entries({ ...applied, ...sort, ...extra }).forEach(([k, v]) => { if (v !== '' && v != null) p.set(k, String(v)); }); return p.toString(); };
  useEffect(() => { if (!pid) return; setData(null); setErr(''); api(`/rfis?${qs({ limit: size, offset })}`).then(setData).catch(e => setErr(e.message)); }, [pid, applied, sort, offset, size]);
  useEffect(() => { if (pid) { api(`/master-data?project_id=${pid}`).then(setMaster).catch(() => {}); api(`/projects/${pid}/settings`).then(setSettings).catch(() => {}); loadViews(); } }, [pid]);
  const loadViews = () => api(`/register-views?project_id=${pid}`).then(setViews).catch(() => setViews([]));
  const vals = (c: string) => [...new Set(master.filter(x => x.category === c).map(x => x.value))] as string[];
  const allowed = data?.hidden_fields_allowed !== false;
  const visible = COLS.filter(c => (c.hidden ? allowed && adv[c.hidden] : cols.includes(c.key)));
  const active = Object.entries(applied).filter(([, v]) => v);
  const apply = (e?: any) => { e?.preventDefault(); setOffset(0); setApplied(f); setSp(Object.fromEntries(Object.entries(f).filter(([, v]) => v))); };
  const clear = () => { setF(EMPTY); setApplied(EMPTY); setOffset(0); setSp({}); setView(''); };
  const sortBy = (k?: string) => { if (!k) return; setSort(s => ({ sort: k, dir: s.sort === k && s.dir === 'desc' ? 'asc' : 'desc' })); setOffset(0); };
  function useView(idv: string) {
    setView(idv); const v = views.find(x => String(x.id) === idv); if (!v) return;
    const c = v.config; const fl = { ...EMPTY, ...(c.filters || {}) };
    setF(fl); setApplied(fl); setSort({ sort: c.sort || 'id', dir: c.dir || 'desc' }); setCols(c.columns || DEFAULT); setAdv({ IM: !!c.advanced?.IM, S: !!c.advanced?.S }); if (c.page_size) setSize(c.page_size); setOffset(0);
  }
  async function saveView() {
    const name = prompt('Name this view (filters, sort and visible columns are saved for you):', views.find(v => String(v.id) === view)?.name || ''); if (!name?.trim()) return;
    try { const v: any = await post('/register-views', { name, project_id: pid, config: { filters: Object.fromEntries(Object.entries(applied).filter(([, x]) => x)), sort: sort.sort, dir: sort.dir, columns: cols, advanced: adv, page_size: size } }); await loadViews(); setView(String(v.id)); }
    catch (e: any) { alert(e.message); }
  }
  async function deleteView() { if (!view || !confirm('Delete this saved view?')) return; await api(`/register-views/${view}`, { method: 'DELETE' }).catch(() => {}); setView(''); loadViews(); }
  const pdfCols = visible.flatMap(c => c.pdf || []).join(',');
  const sel = (k: string, label: string, opts: [string, string][]) => <div><label htmlFor={`r-${k}`}>{label}</label><select id={`r-${k}`} value={f[k]} onChange={e => setF({ ...f, [k]: e.target.value })}><option value="">All</option>{opts.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></div>;
  if (!pid) return <div className="empty">Select a project.</div>;
  return <>
    <PageHeader title="DOC_02 · Main RFI Record Sheet" />
    <ErrorNote error={err} />
    <form className="card" onSubmit={apply} role="search">
      <h3>Searchable master register</h3>
      <div className="grid">
        <div><label htmlFor="r-no">RFI No.</label><input id="r-no" value={f.rfi_no} placeholder="e.g. AS-014" onChange={e => setF({ ...f, rfi_no: e.target.value })} /></div>
        <div><label htmlFor="r-q">Description</label><input id="r-q" value={f.q} placeholder="e.g. asphalt surfacing" onChange={e => setF({ ...f, q: e.target.value })} /></div>
        {sel('road_type', 'Road type', vals('ROAD_TYPE').map(x => [x, x]))}
        {sel('decision', 'RFI status', ['APPROVED', 'PARTIALLY_APPROVED', 'REJECTED', 'ON_PROGRESS', 'INFORMATION_ONLY'].map(x => [x, pretty(x)]))}
        <div><label htmlFor="r-df">Inspection from</label><input id="r-df" type="date" value={f.date_from} onChange={e => setF({ ...f, date_from: e.target.value })} /></div>
        <div><label htmlFor="r-dt">Inspection to</label><input id="r-dt" type="date" value={f.date_to} onChange={e => setF({ ...f, date_to: e.target.value })} /></div>
      </div>
      {more && <div className="grid" style={{ marginTop: 12 }}>
        {sel('workflow_status', 'Workflow status', ['DRAFT', 'SUBMITTED', 'UNDER_REVIEW', 'AWAITING_DECISION', 'COMPLETED', 'CANCELLED', 'ARCHIVED'].map(x => [x, pretty(x)]))}
        {sel('disposition', 'DOC_03 disposition', (settings?.dispositions || []).map((d: any) => [d.code, d.label]))}
        {sel('legacy_status', 'Historical RFI_Status', ['Accepted', 'Accepted as Noted', 'Not Ready', 'Note ready', 'Information', 'Information Only', 'Rejected'].map(x => [x, x]))}
        {sel('work_item', 'Item', vals('WORK_ITEM').map(x => [x, pretty(x)]))}
        {sel('side', 'Side', vals('SIDE').map(x => [x, x]))}
        {sel('provenance', 'Source', [['PORTAL', 'Submitted in RFIMS'], ['LEGACY_IMPORT', 'Historical import']])}
        {sel('short_notice', 'Short notice', [['true', 'Yes'], ['false', 'No']])}
        {sel('latest_only', 'Revisions', [['true', 'Latest revision only']])}
      </div>}
      <div className="actions"><button className="btn">Apply filters</button><button type="button" className="btn secondary" onClick={clear}>Clear</button>
        <button type="button" className="linkButton" onClick={() => setMore(!more)} aria-expanded={more}>{more ? 'Fewer filters' : 'More filters'}</button></div>
    </form>
    {active.length > 0 && <div className="notice info">Filtered register: {active.map(([k, v]) => `${pretty(k)} = ${v}`).join(' · ')}. Exports contain only these records.</div>}

    <div className="card">
      {!data ? <Loading /> : <>
        <div className="section-title">
          <span className="muted">{data.total.toLocaleString()} record(s){active.length ? ' (filtered)' : ''}{data.items.length ? ` · showing ${offset + 1}–${offset + data.items.length}` : ''}</span>
          <div className="toolbar">
            <select aria-label="Saved views" value={view} onChange={e => useView(e.target.value)} style={{ minWidth: 160 }}><option value="">Saved views…</option>{views.map(v => <option key={v.id} value={v.id}>{v.name}</option>)}</select>
            <button type="button" className="btn secondary sm" onClick={saveView}>Save view</button>
            {view && <button type="button" className="btn secondary sm" onClick={deleteView}>Delete view</button>}
            <details style={{ position: 'relative' }}><summary className="btn secondary sm" style={{ listStyle: 'none' }}>Columns</summary>
              <div className="user-menu" style={{ top: 36, right: 0, width: 240, padding: 10 }}>{COLS.filter(c => !c.hidden).map(c => <label key={c.key} className="check" style={{ margin: '4px 0' }}>
                <input type="checkbox" checked={cols.includes(c.key)} disabled={c.key === 'rfi_number'} onChange={e => setCols(e.target.checked ? [...cols, c.key] : cols.filter(x => x !== c.key))} />{c.label}</label>)}
                <button type="button" className="linkButton" onClick={() => setCols(DEFAULT)}>Reset</button></div></details>
          </div>
        </div>
        {data.items.length === 0 ? <div className="empty">No records match.</div> : <>
          <ul className="rec-cards">{data.items.map((r: any) => <li key={r.id} className="rec-card">
            <div className="row1"><Link className="link mono" to={`/rfis/${r.id}`}>{r.rfi_number}{r.revision_no ? ` R${r.revision_no}` : ''}</Link><Status value={r.workflow_status} label={r.status_label} /></div>
            <dl>{visible.filter(c => !['rfi_number', 'workflow'].includes(c.key)).map(c => <React.Fragment key={c.key}><dt>{c.label}</dt><dd>{c.c(r)}</dd></React.Fragment>)}</dl></li>)}</ul>
          <div className="table-wrap"><table><thead><tr>{visible.map(c => <th key={c.key} className={c.sort ? 'sortable' : ''} onClick={() => sortBy(c.sort)} tabIndex={c.sort ? 0 : undefined}
            onKeyDown={e => { if (c.sort && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); sortBy(c.sort); } }}
            aria-sort={c.sort && sort.sort === c.sort ? (sort.dir === 'asc' ? 'ascending' : 'descending') : undefined}>{c.label}{c.sort && sort.sort === c.sort ? (sort.dir === 'asc' ? ' ▲' : ' ▼') : ''}</th>)}</tr></thead>
            <tbody>{data.items.map((r: any) => <tr key={r.id}>{visible.map(c => <td key={c.key}>{c.c(r)}</td>)}</tr>)}</tbody></table></div>
          <div className="actions">
            <button className="btn secondary" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - size))}>← Previous</button>
            <button className="btn secondary" disabled={offset + size >= data.total} onClick={() => setOffset(offset + size)}>Next →</button>
            <span className="muted">Page {Math.floor(offset / size) + 1} of {Math.max(1, Math.ceil(data.total / size))}</span>
            <select aria-label="Rows per page" value={size} onChange={e => { setSize(+e.target.value); setOffset(0); }} style={{ width: 'auto' }}>{PAGE_SIZES.map(n => <option key={n} value={n}>{n} per page</option>)}</select>
          </div>
        </>}
        <h3 style={{ marginTop: 18 }}>Advanced / hidden workbook fields</h3>
        {allowed ? <div className="actions" style={{ marginTop: 4 }}>
          <label className="check"><input type="checkbox" checked={adv.IM} onChange={e => setAdv({ ...adv, IM: e.target.checked })} />Show source, destination and fill-layer fields (I:M)</label>
          <label className="check"><input type="checkbox" checked={adv.S} onChange={e => setAdv({ ...adv, S: e.target.checked })} />Show Work_Status (S, hidden in workbook)</label>
        </div> : <p className="muted" style={{ fontSize: 13 }}>The workbook's hidden columns I:M and S are not available to your role on this project.</p>}
        <p className="muted" style={{ fontSize: 12.5 }}>File_Path fields are shown as secure document links; legacy local drive paths are never displayed.</p>
        <div className="actions end">
          <button className="btn success" onClick={() => download(`/reports/register.xlsx?${qs({ show_hidden: allowed && (adv.IM || adv.S) ? 'true' : '' })}`, 'DOC02_register.xlsx')}>Export Excel{active.length ? ' (filtered)' : ''}</button>
          <button className="btn" onClick={() => download(`/reports/register.pdf?${qs({ columns: pdfCols })}`, 'DOC02_register.pdf')}>Export PDF{active.length ? ' (filtered)' : ''}</button>
        </div>
      </>}
    </div>
  </>;
}
