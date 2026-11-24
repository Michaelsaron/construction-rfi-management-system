import React, { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api, apiOrQueue, currentProjectId, fmtDate, isContractor, getUser } from '../lib/api';
import { useProject } from '../lib/project';
import { PageHeader, ErrorNote } from '../components/ui';
import { Table } from './Queues';
import Status from '../components/Status';

type Mode = 'all' | 'new' | 'drafts' | 'submitted';
const TITLE: Record<Mode, string> = { all: 'DOC_01 submissions', new: 'New DOC_01', drafts: 'Draft submissions', submitted: 'Submitted batches' };

/** DOC_01 — Daily Request for Inspection Summary Sheet batches (contractor menus and the RE/DRE submissions list). */
export default function Summaries({ mode = 'all' }: { mode?: Mode }) {
  const pid = currentProjectId(); const nav = useNavigate(); const { project } = useProject();
  const [rows, setRows] = useState<any[] | null>(null); const [err, setErr] = useState('');
  const now = new Date(); const today = now.toISOString().slice(0, 10);
  const [f, setF] = useState({ summary_reference: `DOC01-${today.replaceAll('-', '')}-01`, submission_date: today, contractor_rep_name: getUser().name || '', remarks: '' });
  useEffect(() => { if (pid && mode !== 'new') api(`/rfi-summaries?project_id=${pid}`).then(setRows).catch(e => { setErr(e.message); setRows([]); }); }, [pid, mode]);
  async function create(e: any) {
    e.preventDefault();
    try { const s: any = await apiOrQueue('/rfi-summaries', 'POST', { ...f, project_id: pid }); if (s?.queued) { alert('Saved on this device; it will sync when you reconnect.'); return; } nav(`/summaries/${s.id}`); }
    catch (x: any) { setErr(x.message); }
  }
  const shown = rows === null ? null : rows.filter(s => mode === 'drafts' ? ['DRAFT', 'RETURNED'].includes(s.workflow_status) : mode === 'submitted' ? !['DRAFT', 'RETURNED'].includes(s.workflow_status) : true);
  return <>
    <PageHeader title={mode === 'new' ? 'DOC_01 · Daily Request for Inspection Summary Sheet' : TITLE[mode]} />
    <ErrorNote error={err} />
    {mode === 'new' && (isContractor() ? <form className="card" onSubmit={create}>
      <h3>Contractor submission</h3>
      <div className="grid">
        <div><label>Project</label><div className="ro-field">{project?.name || '—'}</div></div>
        <div><label>Contract</label><div className="ro-field">{project?.contract_number || '—'}</div></div>
        <div><label className="req" htmlFor="ref">Batch reference</label><input id="ref" required value={f.summary_reference} onChange={e => setF({ ...f, summary_reference: e.target.value })} /></div>
        <div><label className="req" htmlFor="sd">Submission date</label><input id="sd" type="date" required value={f.submission_date} onChange={e => setF({ ...f, submission_date: e.target.value })} /></div>
        <div><label htmlFor="rep">Contractor representative</label><input id="rep" value={f.contractor_rep_name} onChange={e => setF({ ...f, contractor_rep_name: e.target.value })} /></div>
      </div>
      <div style={{ marginTop: 12 }}><label htmlFor="rm">Remarks</label><textarea id="rm" value={f.remarks} onChange={e => setF({ ...f, remarks: e.target.value })} /></div>
      <p className="muted" style={{ fontSize: 13 }}>The submission time is recorded by the server when you submit. Next you add one row per RFI.</p>
      <div className="actions"><button className="btn success">Create DOC_01 and add RFI rows</button></div>
    </form> : <div className="notice">Only contractor users (Category 3) create DOC_01 submissions.</div>)}
    {mode !== 'new' && <div className="card">
      {mode !== 'all' && isContractor() && <div className="actions" style={{ marginTop: 0, marginBottom: 12 }}><Link className="btn success" to="/doc01/new">+ New DOC_01</Link></div>}
      <Table rows={shown} empty={mode === 'drafts' ? 'No draft or returned batches.' : 'No DOC_01 batches yet.'}
        cards={s => <><div className="row1"><Link className="link" to={`/summaries/${s.id}`}>{s.summary_reference}</Link><Status value={s.workflow_status} /></div>
          <dl><dt>RFIs</dt><dd>{s.rfi_count}{s.short_notice_count ? ` · ${s.short_notice_count} short notice` : ''}</dd><dt>Submitted</dt><dd>{fmtDate(s.submitted_at)}</dd>{s.returned_reason && <><dt>Returned</dt><dd>{s.returned_reason}</dd></>}</dl></>}
        cols={[{ h: 'Batch', c: s => <Link className="link" to={`/summaries/${s.id}`}>{s.summary_reference}</Link> }, { h: 'Requested by', c: s => s.contractor_rep_name || s.submitted_by_name },
          { h: 'RFI count', c: s => s.rfi_count, cls: 'num' }, { h: 'Short notice', c: s => s.short_notice_count ? <Status value="SHORT_NOTICE" label={`${s.short_notice_count} short notice`} /> : '—' },
          { h: 'Submitted', c: s => fmtDate(s.submitted_at), cls: 'nowrap' }, { h: 'Received', c: s => s.received_at ? fmtDate(s.received_at) : '—', cls: 'nowrap' },
          { h: 'Status', c: s => <><Status value={s.workflow_status} />{s.returned_reason && <div className="muted" style={{ fontSize: 12 }}>Returned: {s.returned_reason}</div>}</> }]} />
    </div>}
  </>;
}
