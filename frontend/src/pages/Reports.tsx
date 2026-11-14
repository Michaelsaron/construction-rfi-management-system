import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, download, currentProjectId } from '../lib/api';
import { pretty } from '../components/Status';

export default function Reports() {
  const pid = currentProjectId();
  const [s, setS] = useState<any>(null); const [err, setErr] = useState('');
  useEffect(() => { if (pid) api(`/reports/summary?project_id=${pid}`).then(setS).catch(e => setErr(e.message)); }, [pid]);
  const table = (title: string, obj: Record<string, number>) => <div className="card"><h3>{title}</h3>{Object.keys(obj || {}).length ? <table><tbody>
    {Object.entries(obj).sort((a, b) => b[1] - a[1]).map(([k, v]) => <tr key={k}><td>{pretty(k)}</td><td style={{ textAlign: 'right' }}><b>{v.toLocaleString()}</b></td></tr>)}</tbody></table> : <div className="empty">None</div>}</div>;
  return <>
    <h1 className="page-title">Reports</h1><p className="subtitle">All exports respect your project role and are recorded in the audit log.</p>
    <div className="grid">
      <div className="card"><h3>DOC_02 register – Excel</h3><p className="muted">Workbook column order (Contractor_Request … File_Path[IPC]) plus system columns, frozen header, filters.</p><button className="btn" onClick={() => download(`/reports/register.xlsx?project_id=${pid}`, 'DOC02_register.xlsx')}>Download full register</button></div>
      <div className="card"><h3>DOC_02 register – PDF</h3><p className="muted">Landscape A3, repeated headings, page numbers. Use filters on the register page for a filtered PDF.</p><button className="btn secondary" onClick={() => download(`/reports/register.pdf?project_id=${pid}&provenance=PORTAL`, 'DOC02_register.pdf')}>Download (system RFIs)</button></div>
      <div className="card"><h3>Filtered exports</h3><p className="muted">Pending inspections, overdue, decisions in a date range, by inspector…</p><Link className="btn secondary" to="/rfis">Open register filters</Link></div>
      <div className="card"><h3>DOC_01 / DOC_03 PDFs</h3><p className="muted">Open a DOC_01 batch or an RFI and use its PDF button. Completed DOC_03 are served exactly as issued.</p><Link className="btn secondary" to="/summaries">DOC_01 batches</Link></div>
    </div>
    {err && <div className="notice err">{err}</div>}
    {s && <>
      <div className="grid">{table('By workflow status', s.by_workflow)}{table('By decision', s.by_decision)}{table('By DOC_03 disposition', s.by_disposition)}{table('Historical RFI_Status (preserved as imported)', s.legacy_status)}</div>
      <div className="card"><h3>Overdue inspector reviews</h3>{s.overdue_reviews.length ? <ul>{s.overdue_reviews.map((o: any) => <li key={o.rfi_id + '-' + o.sequence_no}><Link className="link" to={`/rfis/${o.rfi_id}`}>{o.rfi_number}</Link> — #{o.sequence_no} {pretty(o.role)}</li>)}</ul> : <div className="empty">No overdue reviews.</div>}
        <p className="muted">Short-notice RFIs in register: {s.short_notice}</p></div>
    </>}
  </>;
}
