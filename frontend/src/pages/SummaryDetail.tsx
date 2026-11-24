import React, { useEffect, useMemo, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { api, apiOrQueue, download, post, put, fmtDate, fmtDay, roleLabel } from '../lib/api';
import { PageHeader, ConfirmDialog, ErrorNote, Loading } from '../components/ui';
import { Doc01ReviewRemark, RemarkList, useRemarkDraft, RemarkEvidence } from '../components/RemarkEvidence';
import Status, { pretty } from '../components/Status';
import Attachments from '../components/Attachments';

const BLANK = { rfi_number: '', contractor_request: '', work_item: '', description: '', structure_type: '', boq_item: '', road_type: '', direction: '', side: '', fill_layer: '',
  chainage_from: '', chainage_to: '', location_text: '', material_source_type: '', material_source: '', material_source_offset: '', requested_date: '', requested_time: '',
  inspection_date: '', inspection_time: '', inspection_order: '', enclosure_sheets: '', work_categories: [] as string[], remarks: '' };
const hoursUntil = (r: any) => { if (!r.inspection_date) return null; return (new Date(`${r.inspection_date}T${r.inspection_time || '00:00'}`).getTime() - Date.now()) / 36e5; };

/** DOC_01 — contractor batch editor (UI design s.4) and RE/DRE review with management remarks (s.5). */
export default function SummaryDetail() {
  const { id } = useParams();
  const [data, setData] = useState<any>(null); const [master, setMaster] = useState<any[]>([]); const [cats, setCats] = useState<any[]>([]); const [remarks, setRemarks] = useState<any[]>([]);
  const [f, setF] = useState<any>(BLANK); const [editing, setEditing] = useState<any>(null); const [formOpen, setFormOpen] = useState(false);
  const [msg, setMsg] = useState(''); const [err, setErr] = useState(''); const [busy, setBusy] = useState(false);
  const [submitDlg, setSubmitDlg] = useState(false); const [reason, setReason] = useState(''); const [returnDlg, setReturnDlg] = useState(false); const [returnReason, setReturnReason] = useState('');
  const load = () => api(`/rfi-summaries/${id}`).then((d: any) => {
    setData(d);
    api(`/evidence/remarks?summary_id=${id}`).then(setRemarks).catch(() => {});
    return api(`/master-data?project_id=${d.summary.project_id}`).then(setMaster);
  }).catch(e => setErr(e.message));
  useEffect(() => { load(); api('/projects/meta/work-categories').then(setCats).catch(() => {}); }, [id]);
  const vals = (cat: string, parent?: string) => [...new Set(master.filter(x => x.category === cat && (!parent || x.parent_value === parent)).map(x => x.value))] as string[];
  const descriptions = useMemo(() => vals('WORK_DESCRIPTION', f.work_item), [master, f.work_item]);
  const sources = useMemo(() => vals('MATERIAL_SOURCE', f.material_source_type), [master, f.material_source_type]);
  const returnDraft = useRemarkDraft(data?.summary.project_id, 'REASSIGNMENT_RETURN', null, data?.permissions.return ? +id! : null);
  if (err && !data) return <ErrorNote error={err} />;
  if (!data) return <Loading />;
  const s = data.summary, perm = data.permissions, rows: any[] = data.rfis;

  function body() {
    const b: any = {};
    for (const [k, v] of Object.entries(f)) b[k] = v === '' ? null : v;
    b.inspection_order = f.inspection_order ? +f.inspection_order : null; b.enclosure_sheets = f.enclosure_sheets === '' ? null : +f.enclosure_sheets;
    return b;
  }
  async function save(e?: any) {
    e?.preventDefault(); setBusy(true); setErr('');
    try {
      if (editing) { await put(`/rfis/${editing.id}`, { ...body(), version: editing.version }); setMsg(`RFI ${f.rfi_number} saved as draft.`); }
      else { const r: any = await apiOrQueue('/rfis', 'POST', { ...body(), project_id: s.project_id, summary_id: +id! }); setMsg(r?.queued ? 'Saved on this device; it will sync automatically.' : `RFI ${f.rfi_number} added as a draft row.`); }
      setF({ ...BLANK, inspection_date: f.inspection_date, inspection_time: f.inspection_time, work_item: f.work_item }); setEditing(null); setFormOpen(false); load();
    } catch (x: any) { setErr(x.message); } finally { setBusy(false); }
  }
  function edit(r: any) { setEditing(r); setFormOpen(true); setF({ ...BLANK, ...Object.fromEntries(Object.keys(BLANK).map(k => [k, r[k] ?? (k === 'work_categories' ? [] : '')])) }); window.scrollTo({ top: 0, behavior: 'smooth' }); }
  async function removeLine(r: any) { if (!confirm(`Remove RFI ${r.rfi_number} from this draft batch?`)) return; try { await api(`/rfis/${r.id}`, { method: 'DELETE' }); load(); } catch (x: any) { setErr(x.message); } }
  const short = rows.filter(r => { const h = hoursUntil(r); return h !== null && h < data.notice_hours; });
  const missing = rows.filter(r => r.missing?.length);
  async function submit() {
    setBusy(true);
    try { const r: any = await post(`/rfi-summaries/${id}/submit`, { short_notice_reason: reason || null }); setSubmitDlg(false); setMsg(`DOC_01 submitted to the RE/DRE.${r.short_notice_count ? ` ${r.short_notice_count} RFI(s) flagged short notice.` : ''}`); load(); }
    catch (x: any) { setSubmitDlg(false); setErr(x.message); } finally { setBusy(false); }
  }
  async function doReturn() {
    setBusy(true);
    try { await post(`/rfi-summaries/${id}/return`, { reason: returnReason, management_remark_id: returnDraft.remark?.id || null }); setReturnDlg(false); setMsg('DOC_01 returned to the contractor.'); load(); }
    catch (x: any) { alert(x.message); } finally { setBusy(false); }
  }
  async function receive() { try { await post(`/rfi-summaries/${id}/receive`); load(); } catch (x: any) { setErr(x.message); } }
  const field = (k: string, label: string, props: any = {}) => <div><label htmlFor={`f-${k}`} className={props.req ? 'req' : ''}>{label}</label><input id={`f-${k}`} value={f[k] ?? ''} onChange={e => setF({ ...f, [k]: e.target.value })} {...props} req={undefined} /></div>;
  const pick = (k: string, label: string, options: string[], req = false) => <div><label htmlFor={`f-${k}`} className={req ? 'req' : ''}>{label}</label><select id={`f-${k}`} value={f[k] ?? ''} onChange={e => setF({ ...f, [k]: e.target.value })}><option value="">Select…</option>{options.map(x => <option key={x} value={x}>{pretty(x)}</option>)}</select></div>;
  const toggleCat = (c: string) => setF({ ...f, work_categories: f.work_categories.includes(c) ? f.work_categories.filter((x: string) => x !== c) : [...f.work_categories, c] });
  const mgmt = data.my_category === '2.1';

  return <>
    <PageHeader title={mgmt ? 'DOC_01 review · assignment and management remarks' : 'DOC_01 · Daily Request for Inspection Summary Sheet'} back={{ to: mgmt ? '/summaries' : perm.edit ? '/doc01/drafts' : '/summaries', label: 'DOC_01 batches' }}
      actions={<>
        <button className="btn secondary" onClick={() => download(`/reports/doc01/${id}.pdf`, `DOC01_${s.summary_reference}.pdf`)}>DOC_01 PDF</button>
        {perm.receive && <button className="btn secondary" onClick={receive}>Acknowledge receipt</button>}
        {perm.return && <button className="btn danger" onClick={() => setReturnDlg(true)}>Return to contractor</button>}
      </>} />
    {msg && <div className="notice ok" role="status">{msg}</div>}
    <ErrorNote error={err} />
    <div className="card">
      <div className="section-title"><h3>{mgmt ? `Batch ${s.summary_reference} · ${rows.length} RFI${rows.length === 1 ? '' : 's'}` : 'Contractor submission'}</h3><Status value={s.workflow_status} /></div>
      <div className="grid">
        <div><label>Project</label><div className="ro-field">{data.project.name}</div></div>
        <div><label>Contract</label><div className="ro-field">{data.project_detail?.contract_number || '—'}</div></div>
        <div><label>Batch reference</label><div className="ro-field">{s.summary_reference}</div></div>
        <div><label>Submission date/time</label><div className="ro-field">{s.submitted_at ? fmtDate(s.submitted_at) : `${fmtDay(s.submission_date)} · not yet submitted`}</div></div>
      </div>
      {s.returned_reason && <div className="notice err" style={{ marginTop: 12 }}><b>Returned for correction:</b> {s.returned_reason}</div>}

      <h3 style={{ marginTop: 18 }}>Inspection items — one row per RFI</h3>
      {rows.length ? <div className="table-wrap inset"><table>
        <thead><tr><th>RFI No.</th><th>Description</th><th>Station From / To</th><th>Side</th><th>Material</th><th>Requested</th><th>Inspection</th><th>Remark</th>{mgmt ? <><th>Assigned sequence</th><th>Workflow</th></> : <th>Status</th>}{perm.edit && <th></th>}</tr></thead>
        <tbody>{rows.map(r => <tr key={r.id}>
          <td className="nowrap"><Link className="link mono" to={mgmt ? `/rfis/${r.id}/assign` : `/rfis/${r.id}`}>{r.rfi_number}</Link></td>
          <td style={{ minWidth: 180 }}>{r.contractor_request || r.description}{r.missing?.length > 0 && perm.edit && <div className="field-err">Missing: {r.missing.join(', ')}</div>}</td>
          <td className="mono nowrap">{r.chainage_from || '—'} / {r.chainage_to || '—'}</td><td>{r.side || '—'}</td>
          <td>{r.material_source || '—'}{r.material_source_offset ? ` · ${r.material_source_offset}` : ''}</td>
          <td className="nowrap">{r.requested_date ? `${fmtDay(r.requested_date)} ${r.requested_time || ''}` : <span className="muted">on submit</span>}</td>
          <td className="nowrap">{fmtDay(r.inspection_date)} {r.inspection_time || ''}{(r.short_notice || (perm.edit && (hoursUntil(r) ?? 99) < data.notice_hours)) && <div><Status value="SHORT_NOTICE" label={`Short notice${r.notice_hours != null ? ` · ${r.notice_hours} h` : ''}`} /></div>}</td>
          <td>{r.remarks || '—'}</td>
          {mgmt ? <><td style={{ fontSize: 12.5 }}>{r.workflow_status === 'SUBMITTED' ? <Link className="btn sm success" to={`/rfis/${r.id}/assign`}>Assign</Link> : <Link className="link" to={`/rfis/${r.id}/workflow`}>View sequence</Link>}</td>
            <td><Status value={r.workflow_status} label={r.workflow_status === 'SUBMITTED' ? 'Ready to assign' : r.status_label} /></td></> : <td><Status value={r.workflow_status} label={r.status_label} /></td>}
          {perm.edit && <td className="nowrap"><button className="btn secondary sm" onClick={() => edit(r)}>Edit</button> <button className="btn secondary sm" onClick={() => removeLine(r)}>Remove</button></td>}
        </tr>)}</tbody></table></div> : <div className="empty">No RFI rows yet.</div>}

      {perm.edit && <div className="actions">
        <button className="btn success" onClick={() => { setEditing(null); setF({ ...BLANK, inspection_date: f.inspection_date, inspection_time: f.inspection_time }); setFormOpen(true); }}>+ Add RFI row</button>
        <button className="btn neutral" disabled={busy} onClick={() => formOpen ? save() : setMsg('Draft saved. Every RFI row is stored as you add it; nothing is sent until you submit.')}>Save draft</button>
        <button className="btn" disabled={!perm.submit || busy} onClick={() => { setReason(''); setSubmitDlg(true); }}>Submit DOC_01</button>
      </div>}

      {perm.edit && formOpen && <form className="card tinted" style={{ marginTop: 16, marginBottom: 0 }} onSubmit={save}>
        <div className="section-title"><h3>{editing ? `Edit RFI ${editing.rfi_number}` : 'New RFI row'}</h3><button type="button" className="btn secondary sm" onClick={() => { setEditing(null); setFormOpen(false); }}>Close</button></div>
        <div className="grid">
          {field('rfi_number', 'RFI No.', { required: true, req: true, placeholder: 'e.g. AS-014/2026' })}
          {pick('work_item', 'Work item', vals('WORK_ITEM'), true)}
          {descriptions.length ? pick('description', 'Standard activity', descriptions) : field('description', 'Standard activity')}
          {pick('structure_type', 'Structure type', vals('STRUCTURE_TYPE'))}
          {field('boq_item', 'BOQ item no.', { placeholder: '64.02(a)' })}
          {pick('road_type', 'Road type', vals('ROAD_TYPE'))}
          {field('chainage_from', 'Station from', { req: true, placeholder: '187+325' })}
          {field('chainage_to', 'Station to', { placeholder: '187+405' })}
          {pick('side', 'Side', vals('SIDE'))}
          {field('fill_layer', 'Layer / check dam / Pww')}
          {pick('material_source_type', 'Material source type', vals('MATERIAL_SOURCE_TYPE'))}
          {sources.length ? pick('material_source', 'Material source – location', sources) : field('material_source', 'Material source – location')}
          {field('material_source_offset', 'Material source – offset', { placeholder: '20 m' })}
          {field('inspection_date', 'Inspection date', { type: 'date', req: true })}
          {field('inspection_time', 'Inspection time', { type: 'time', req: true })}
          <div><label htmlFor="f-order">Order of inspection</label><select id="f-order" value={f.inspection_order} onChange={e => setF({ ...f, inspection_order: e.target.value })}><option value="">—</option><option value="1">First</option><option value="2">Second</option><option value="3">Third</option></select></div>
          {field('enclosure_sheets', 'Enclosure sheets', { type: 'number', min: 0 })}
          {field('location_text', 'Other location text')}
        </div>
        <div style={{ marginTop: 12 }}><label htmlFor="f-desc" className="req">Description (as on DOC_01)</label><textarea id="f-desc" value={f.contractor_request} onChange={e => setF({ ...f, contractor_request: e.target.value })} placeholder="Inspection for 50 mm asphalt surfacing" /></div>
        <div style={{ marginTop: 12 }}><label>DOC_03 work category</label><div className="grid">{cats.map(g => <fieldset key={g.group}><legend>{g.label}</legend>
          {g.items.map((it: any) => <label key={it.code} className="check" style={{ margin: '4px 0' }}><input type="checkbox" checked={f.work_categories.includes(it.code)} onChange={() => toggleCat(it.code)} />{it.label}</label>)}</fieldset>)}</div></div>
        <div style={{ marginTop: 12 }}><label htmlFor="f-rem">Remark</label><textarea id="f-rem" value={f.remarks} onChange={e => setF({ ...f, remarks: e.target.value })} placeholder="e.g. Prior FDT attached" /></div>
        <p className="muted" style={{ fontSize: 13 }}>Fields marked * are required before the DOC_01 can be submitted. Requested date/time is recorded when you submit.</p>
        <div className="actions"><button className="btn success" disabled={busy}>{editing ? 'Save row' : 'Add row'}</button></div>
      </form>}

      <div className="card tinted" style={{ marginTop: 16, marginBottom: 0 }}>
        <h3>Representative details</h3>
        <div className="grid">
          <div><div className="muted" style={{ fontSize: 12.5 }}>Contractor representative: name / signature / date</div><div><b>{s.contractor_rep_name || s.submitted_by_name}</b> · {s.submitted_at ? <>electronically submitted {fmtDate(s.submitted_at)}</> : 'not yet submitted'}</div></div>
          <div><div className="muted" style={{ fontSize: 12.5 }}>Consultant representative: name / signature / date</div><div>{s.received_at ? <><b>{s.received_by_name}</b> · electronically acknowledged {fmtDate(s.received_at)}</> : 'Not yet acknowledged'}</div></div>
        </div>
        <p className="muted" style={{ fontSize: 12, margin: '8px 0 0' }}>Acknowledgements record the authenticated account and server time; no signature image is generated.</p>
      </div>
    </div>

    {(perm.management_remark || remarks.some(r => r.status === 'SUBMITTED')) && <div className="cols-2">
      <div className="card" style={{ marginBottom: 0 }}><h3>Recorded management remarks</h3><RemarkList remarks={remarks} /></div>
      {perm.management_remark && <div className="card" style={{ marginBottom: 0 }}><h3>Management remark / supporting evidence</h3><Doc01ReviewRemark projectId={s.project_id} summaryId={+id!} onRecorded={load} /></div>}
    </div>}
    <div style={{ height: 16 }} />
    <Attachments entityType="summary" entityId={+id!} canUpload={perm.edit} title="DOC_01 enclosures" note={perm.edit ? 'Enclosures are locked when the DOC_01 is submitted.' : undefined} />

    <ConfirmDialog open={submitDlg} title="Submit this DOC_01 to the RE/DRE?" confirmLabel="Submit DOC_01" tone="primary" busy={busy} onCancel={() => setSubmitDlg(false)} onConfirm={submit}
      intro="The RFI rows will be locked. Later corrections need an approved amendment."
      rows={[['Project', data.project.name], ['Batch reference', s.summary_reference], ['RFI rows', String(rows.length)],
        ['Requested inspections', rows.map(r => `${r.rfi_number}: ${fmtDay(r.inspection_date)} ${r.inspection_time || ''}`).join('\n')]]}
      warnings={[missing.length ? `${missing.length} row(s) are missing required fields: ${missing.map(r => r.rfi_number).join(', ')}. The submission will be refused until they are completed.` : '',
        short.length ? `${short.length} RFI(s) are less than ${data.notice_hours} hours before inspection (short notice): ${short.map(r => r.rfi_number).join(', ')}. ${data.notice_policy === 'REQUIRE_OVERRIDE' ? 'This project requires a reason.' : 'They will be flagged to the RE/DRE.'}` : '']}>
      {short.length > 0 && data.notice_policy === 'REQUIRE_OVERRIDE' && <div><label className="req" htmlFor="sn">Short-notice reason</label><input id="sn" value={reason} onChange={e => setReason(e.target.value)} /></div>}
    </ConfirmDialog>

    {returnDlg && <div className="modal-bg"><div className="modal" role="dialog" aria-modal="true" aria-labelledby="ret-t">
      <h2 id="ret-t">Return {s.summary_reference} to the contractor</h2>
      <p className="muted">The batch goes back to draft for correction. Your reason and any attached files are recorded as your management remark.</p>
      <div className="stack"><div><label className="req" htmlFor="rr">Reason</label><textarea id="rr" value={returnReason} onChange={e => setReturnReason(e.target.value)} placeholder="e.g. Station range missing for EW-021/2026" /></div>
        <RemarkEvidence draft={returnDraft} canEdit /></div>
      <div className="actions end"><button className="btn secondary" onClick={() => setReturnDlg(false)} disabled={busy}>Go back</button>
        <button className="btn danger" disabled={!returnReason.trim() || busy || returnDraft.busy} onClick={doReturn}>{returnDraft.busy ? 'Waiting for uploads…' : busy ? 'Returning…' : 'Return DOC_01'}</button></div>
    </div></div>}
    {data.my_role && <p className="muted" style={{ fontSize: 12 }}>Your role: {roleLabel(data.my_role)}</p>}
  </>;
}
