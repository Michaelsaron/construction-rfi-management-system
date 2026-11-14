import React, { useEffect, useMemo, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { api, apiOrQueue, download, post, put, fmtDate, fmtDay, loc } from '../lib/api';
import Status, { pretty } from '../components/Status';
import Attachments from '../components/Attachments';

const BLANK = { rfi_number: '', contractor_request: '', work_item: '', description: '', structure_type: '', boq_item: '', road_type: '', direction: '', side: '', fill_layer: '',
  chainage_from: '', chainage_to: '', location_text: '', material_source_type: '', material_source: '', material_source_offset: '', requested_date: '', requested_time: '',
  inspection_date: '', inspection_time: '', inspection_order: '', enclosure_sheets: '', work_categories: [] as string[], remarks: '' };

export default function SummaryDetail() {
  const { id } = useParams();
  const [data, setData] = useState<any>(null); const [master, setMaster] = useState<any[]>([]); const [cats, setCats] = useState<any[]>([]);
  const [f, setF] = useState<any>(BLANK); const [editing, setEditing] = useState<any>(null); const [msg, setMsg] = useState(''); const [busy, setBusy] = useState(false);
  const load = () => api(`/rfi-summaries/${id}`).then((d: any) => { setData(d); return api(`/master-data?project_id=${d.summary.project_id}`).then(setMaster); }).catch(e => setMsg(e.message));
  useEffect(() => { load(); api('/projects/meta/work-categories').then(setCats).catch(() => {}); }, [id]);
  const vals = (cat: string, parent?: string) => [...new Set(master.filter(x => x.category === cat && (!parent || x.parent_value === parent)).map(x => x.value))] as string[];
  const descriptions = useMemo(() => vals('WORK_DESCRIPTION', f.work_item), [master, f.work_item]);
  const sources = useMemo(() => vals('MATERIAL_SOURCE', f.material_source_type), [master, f.material_source_type]);

  function body() {
    const b: any = {};
    for (const [k, v] of Object.entries(f)) b[k] = v === '' ? null : v;
    b.inspection_order = f.inspection_order ? +f.inspection_order : null; b.enclosure_sheets = f.enclosure_sheets === '' ? null : +f.enclosure_sheets;
    return b;
  }
  async function save(e: any) {
    e.preventDefault(); setBusy(true);
    try {
      if (editing) { await put(`/rfis/${editing.id}`, { ...body(), version: editing.version }); setMsg(`RFI ${f.rfi_number} updated.`); }
      else { const r: any = await apiOrQueue('/rfis', 'POST', { ...body(), project_id: data.summary.project_id, summary_id: +id! }); setMsg(r?.queued ? 'Saved offline; it will sync automatically.' : `RFI ${f.rfi_number} added.`); }
      setF({ ...BLANK, inspection_date: f.inspection_date, inspection_time: f.inspection_time, work_item: f.work_item }); setEditing(null); load();
    } catch (e: any) { alert(e.message); } finally { setBusy(false); }
  }
  function edit(r: any) { setEditing(r); setF({ ...BLANK, ...Object.fromEntries(Object.keys(BLANK).map(k => [k, r[k] ?? (k === 'work_categories' ? [] : '')])) }); window.scrollTo({ top: 0, behavior: 'smooth' }); }
  async function removeLine(r: any) { if (!confirm(`Remove RFI ${r.rfi_number} from this draft batch?`)) return; try { await api(`/rfis/${r.id}`, { method: 'DELETE' }); load(); } catch (e: any) { alert(e.message); } }
  async function submit() {
    const short = data.rfis.filter((r: any) => { if (!r.inspection_date) return false; const t = new Date(`${r.inspection_date}T${r.inspection_time || '00:00'}`); return (t.getTime() - Date.now()) / 36e5 < data.notice_hours; });
    let reason: string | null = null;
    if (short.length) {
      const text = `${short.length} RFI(s) are proposed less than ${data.notice_hours} hours before inspection (short notice).`;
      if (data.notice_policy === 'REQUIRE_OVERRIDE') { reason = prompt(text + '\nThis project requires a reason to submit:'); if (!reason?.trim()) return; }
      else if (!confirm(text + '\nThey will be flagged to the RE/DRE. Submit anyway?')) return;
    } else if (!confirm('Submit this DOC_01 to the RE/DRE? The RFIs will be locked; later corrections need an approved amendment.')) return;
    try { const r: any = await post(`/rfi-summaries/${id}/submit`, { short_notice_reason: reason }); setMsg(`Submitted. ${r.short_notice_count ? r.short_notice_count + ' RFI(s) flagged short notice.' : ''}`); load(); } catch (e: any) { alert(e.message); }
  }
  async function ret() { const reason = prompt('Reason for returning this DOC_01 to the contractor?'); if (!reason?.trim()) return; try { await post(`/rfi-summaries/${id}/return`, { reason }); load(); } catch (e: any) { alert(e.message); } }
  async function receive() { try { await post(`/rfi-summaries/${id}/receive`); load(); } catch (e: any) { alert(e.message); } }

  if (!data) return <p>{msg || 'Loading…'}</p>;
  const s = data.summary, perm = data.permissions;
  const field = (k: string, label: string, props: any = {}) => <div><label>{label}</label><input value={f[k] ?? ''} onChange={e => setF({ ...f, [k]: e.target.value })} {...props} /></div>;
  const pick = (k: string, label: string, options: string[], props: any = {}) => <div><label>{label}</label><select value={f[k] ?? ''} onChange={e => setF({ ...f, [k]: e.target.value })} {...props}><option value="">Select…</option>{options.map(x => <option key={x} value={x}>{pretty(x)}</option>)}</select></div>;
  const toggleCat = (c: string) => setF({ ...f, work_categories: f.work_categories.includes(c) ? f.work_categories.filter((x: string) => x !== c) : [...f.work_categories, c] });

  return <>
    <div className="top"><div><h1 className="page-title">{s.summary_reference}</h1>
      <p className="subtitle"><Link className="link" to="/summaries">← DOC_01 batches</Link> &nbsp; <Status value={s.workflow_status} /> &nbsp; {data.rfis.length} RFI(s)
        {s.submitted_at && <> · submitted {fmtDate(s.submitted_at)} by {s.submitted_by_name}</>}{s.received_at && <> · received {fmtDate(s.received_at)} by {s.received_by_name}</>}
        {s.returned_reason && <> · <b>Returned:</b> {s.returned_reason}</>}</p></div>
      <div className="toolbar">
        <button className="btn secondary" onClick={() => download(`/reports/doc01/${id}.pdf`, `DOC01_${s.summary_reference}.pdf`)}>DOC_01 PDF</button>
        {perm.submit && <button className="btn success" onClick={submit}>Submit DOC_01</button>}
        {perm.receive && <button className="btn secondary" onClick={receive}>Acknowledge receipt</button>}
        {perm.return && <button className="btn danger" onClick={ret}>Return to contractor</button>}
      </div></div>
    {msg && <div className="notice ok">{msg}</div>}

    {perm.edit && <form className="card" onSubmit={save}>
      <div className="section-title"><h3>{editing ? `Edit RFI ${editing.rfi_number}` : 'Add RFI to this DOC_01'}</h3>{editing && <button type="button" className="btn secondary sm" onClick={() => { setEditing(null); setF(BLANK); }}>Cancel edit</button>}</div>
      <div className="grid">
        {field('rfi_number', 'RFI No. *', { required: true, placeholder: 'e.g. Fill-401/2026' })}
        {pick('work_item', 'Work item *', vals('WORK_ITEM'))}
        {descriptions.length ? pick('description', 'Standard activity', descriptions) : field('description', 'Standard activity')}
        {pick('structure_type', 'Structure type', vals('STRUCTURE_TYPE'))}
        {field('boq_item', 'BOQ Item No.', { placeholder: '64.02(a)' })}
        {pick('road_type', 'Road type', vals('ROAD_TYPE'))}
        {field('chainage_from', 'Station from *', { placeholder: '188+650' })}
        {field('chainage_to', 'Station to', { placeholder: '188+870' })}
        {pick('side', 'Side', vals('SIDE'))}
        {field('fill_layer', 'Layer / Check dam / Pww')}
        {pick('material_source_type', 'Material source type', vals('MATERIAL_SOURCE_TYPE'))}
        {sources.length ? pick('material_source', 'Material source – location', sources) : field('material_source', 'Material source – location')}
        {field('material_source_offset', 'Material source – offset', { placeholder: '50m' })}
        {field('inspection_date', 'Inspection date *', { type: 'date' })}
        {field('inspection_time', 'Inspection time *', { type: 'time' })}
        <div><label>Order of inspection</label><select value={f.inspection_order} onChange={e => setF({ ...f, inspection_order: e.target.value })}><option value="">—</option><option value="1">First</option><option value="2">Second</option><option value="3">Third</option></select></div>
        {field('enclosure_sheets', 'Enclosure sheets', { type: 'number', min: 0 })}
        {field('location_text', 'Other location text')}
      </div>
      <div style={{ marginTop: 12 }}><label>Works description (as on DOC_01) *</label><textarea value={f.contractor_request} onChange={e => setF({ ...f, contractor_request: e.target.value })} placeholder="Inspection and FDT for embankment 1st layer" /></div>
      <div style={{ marginTop: 12 }}><label>DOC_03 work category</label><div className="grid">{cats.map(g => <fieldset key={g.group} style={{ border: '1px solid var(--line, #ccd)', borderRadius: 8, padding: 8 }}><legend style={{ fontSize: 13, fontWeight: 600 }}>{g.label}</legend>
        {g.items.map((it: any) => <label key={it.code} style={{ display: 'flex', gap: 6, fontWeight: 400, fontSize: 13 }}><input type="checkbox" checked={f.work_categories.includes(it.code)} onChange={() => toggleCat(it.code)} style={{ width: 'auto' }} />{it.label}</label>)}</fieldset>)}</div></div>
      <div style={{ marginTop: 12 }}><label>Remark</label><textarea value={f.remarks} onChange={e => setF({ ...f, remarks: e.target.value })} /></div>
      <p className="muted" style={{ fontSize: 13 }}>* required before the batch can be submitted. You can save incomplete rows as draft.</p>
      <button className="btn" disabled={busy}>{editing ? 'Save changes' : 'Add RFI'}</button>
    </form>}

    <div className="card"><h3>RFIs in this DOC_01</h3>{data.rfis.length ? <div className="table-wrap"><table>
      <thead><tr><th>RFI No.</th><th>Description</th><th>Station</th><th>Material source / offset</th><th>Inspection</th><th>Status</th>{perm.edit && <th></th>}</tr></thead>
      <tbody>{data.rfis.map((r: any) => <tr key={r.id}>
        <td><Link className="link mono" to={`/rfis/${r.id}`}>{r.rfi_number}</Link></td>
        <td>{r.contractor_request || r.description}{r.missing?.length > 0 && perm.edit && <div className="muted" style={{ color: 'var(--danger, #b42318)', fontSize: 12 }}>Missing: {r.missing.join(', ')}</div>}</td>
        <td className="mono">{loc(r)}</td><td>{r.material_source || '—'}{r.material_source_offset ? ` / ${r.material_source_offset}` : ''}</td>
        <td>{fmtDay(r.inspection_date)} {r.inspection_time || ''}{r.short_notice && <> <Status value="SHORT_NOTICE" label={`Short notice (${r.notice_hours} h)`} /></>}</td>
        <td><Status value={r.workflow_status} label={r.status_label} /></td>
        {perm.edit && <td style={{ whiteSpace: 'nowrap' }}><button className="btn secondary sm" onClick={() => edit(r)}>Edit</button> <button className="btn secondary sm" onClick={() => removeLine(r)}>Remove</button></td>}
      </tr>)}</tbody></table></div> : <div className="empty">No RFIs added yet.</div>}</div>
    <Attachments entityType="summary" entityId={+id!} canUpload={perm.edit} title="DOC_01 attachments" />
  </>;
}
