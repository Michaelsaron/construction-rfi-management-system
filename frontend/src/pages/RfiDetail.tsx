import React, { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { api, post, download, fmtDate, fmtDay, loc, roleLabel } from '../lib/api';
import { PageHeader, ConfirmDialog, Loading, ErrorNote } from '../components/ui';
import { FileRow } from '../components/EvidencePanel';
import Attachments from '../components/Attachments';
import Status from '../components/Status';
import Icon from '../components/Icon';

const AMEND_FIELDS: [string, string, string?][] = [['contractor_request', 'Works description'], ['chainage_from', 'Station from'], ['chainage_to', 'Station to'], ['side', 'Side'],
  ['material_source', 'Material source'], ['material_source_offset', 'Material offset'], ['boq_item', 'BOQ item'], ['inspection_date', 'Inspection date', 'date'],
  ['inspection_time', 'Inspection time', 'time'], ['remarks', 'Remark']];

/** RFI record overview: DOC_01 data, links to the focused workflow screens, amendments, enclosures and status history. */
export default function RfiDetail() {
  const { id } = useParams(); const nav = useNavigate();
  const [d, setD] = useState<any>(null); const [err, setErr] = useState(''); const [msg, setMsg] = useState(''); const [busy, setBusy] = useState(false);
  const [amend, setAmend] = useState<any>(null); const [evAm, setEvAm] = useState<any[]>([]);
  const [resub, setResub] = useState<any>(null); const [cancelDlg, setCancelDlg] = useState(''); const [cancelOpen, setCancelOpen] = useState(false);
  const load = () => api(`/rfis/${id}`).then((x: any) => { setD(x); api(`/evidence/amendments?rfi_id=${id}`).then(setEvAm).catch(() => setEvAm([])); return x; }).catch(e => setErr(e.message));
  useEffect(() => { setD(null); setErr(''); setMsg(''); load(); }, [id]);
  async function run(fn: () => Promise<any>, ok: string) { setBusy(true); setMsg(''); try { await fn(); setMsg(ok); await load(); } catch (e: any) { alert(e.message); } finally { setBusy(false); } }
  if (err) return <><ErrorNote error={err} /><Link className="link" to="/rfis">Back to the register</Link></>;
  if (!d) return <Loading text="Loading RFI…" />;
  const r = d.rfi, perm = d.permissions;
  const isMineInspector = d.my_category === '2.2' && d.assignments.some((a: any) => a.status !== 'REPLACED');
  const sendAmend = (e: any) => {
    e.preventDefault();
    const changes: any = {}; for (const [k] of AMEND_FIELDS) if ((amend[k] ?? '') !== (r[k] ?? '')) changes[k] = amend[k] === '' ? null : amend[k];
    if (!Object.keys(changes).length) { alert('Nothing changed.'); return; }
    if (!amend.reason?.trim()) { alert('Enter the reason for the amendment.'); return; }
    run(() => post(`/rfis/${id}/amendments`, { changes, reason: amend.reason }), 'Amendment requested. The RE/DRE will review it.').then(() => setAmend(null));
  };
  const resolve = (aid: number, ok: boolean) => { const c = prompt(ok ? 'Approval comment (optional)' : 'Reason for rejecting') ?? ''; if (!ok && !c.trim()) return; run(() => post(`/rfis/amendments/${aid}/${ok ? 'approve' : 'reject'}`, { comment: c }), ok ? 'Amendment applied.' : 'Amendment rejected.'); };
  const fieldAmends = d.amendments.filter((a: any) => !a.amendment_type || a.amendment_type === 'FIELDS');
  return <>
    <PageHeader title={<><span className="mono">{r.rfi_number}</span>{r.revision_no ? ` · Rev ${r.revision_no}` : ''}</>} back={{ to: '/rfis', label: 'DOC_02 register' }}
      actions={<>
        <button className="btn secondary" onClick={() => download(`/reports/doc03/${id}.pdf`, `DOC03_${r.rfi_number}_rev${r.revision_no}.pdf`)}><Icon name="download" size={16} />DOC_03 PDF</button>
        {perm.request_amendment && <button className="btn secondary" onClick={() => setAmend({ ...Object.fromEntries(AMEND_FIELDS.map(([k]) => [k, r[k] ?? ''])), reason: '' })}>Request amendment</button>}
        {perm.resubmit && <button className="btn warn" onClick={() => setResub({ reason: '', inspection_date: '', inspection_time: '', chainage_from: '', chainage_to: '' })}>Resubmit (next revision)</button>}
        {perm.cancel && <button className="btn danger" onClick={() => { setCancelDlg(''); setCancelOpen(true); }}>Cancel RFI</button>}
      </>}>
      <div className="chips" style={{ marginTop: 8 }}>
        <Status value={r.workflow_status} label={r.status_label} />{r.current_decision && <Status value={r.current_decision} />}
        {r.is_legacy && <Status value="LEGACY" label="Historical record (read-only)" />}{r.short_notice && <Status value="SHORT_NOTICE" label={`Short notice: ${r.notice_hours} h`} />}
        {d.summary && <Link to={`/summaries/${d.summary.id}`} className="badge">DOC_01 {d.summary.summary_reference}</Link>}
        {d.revisions.length > 1 && d.revisions.map((v: any) => v.id !== r.id && <Link key={v.id} to={`/rfis/${v.id}`} className="badge">Rev {v.revision_no}</Link>)}
      </div>
    </PageHeader>
    {msg && <div className="notice ok" role="status">{msg}</div>}
    {r.is_legacy && <div className="notice">Imported from the historical DOC_02 workbook. No DOC_01 batch or DOC_03 review exists in the system for it; the original status text is preserved: <b>{r.legacy_rfi_status || '(blank)'}</b>.</div>}
    {r.legacy_document && <div className="notice info"><b>{r.legacy_document.label}.</b> The historical register referred to a document on the former shared drive{r.legacy_document.has_ipc_reference ? ' (and an IPC document)' : ''}. It has not been migrated, so no link is shown.</div>}

    <div className="card"><div className="section-title"><h3>Next steps</h3></div><div className="actions" style={{ marginTop: 0 }}>
      {perm.assign && <Link className="btn success" to={`/rfis/${id}/assign`}>{d.assignments.some((a: any) => a.status !== 'REPLACED') ? 'Change inspector sequence' : 'Assign inspectors'}</Link>}
      {perm.review_assignment_id && <Link className="btn success" to={`/rfis/${id}/review`}>Open my DOC_03 review</Link>}
      {!perm.review_assignment_id && isMineInspector && <Link className="btn secondary" to={`/rfis/${id}/review`}>My review</Link>}
      {perm.decide && <Link className="btn success" to={`/rfis/${id}/decision`}>Record final disposition</Link>}
      {!r.is_legacy && <Link className="btn secondary" to={`/rfis/${id}/workflow`}>Workflow timeline</Link>}
      {r.workflow_status === 'COMPLETED' && <Link className="btn" to={`/completed/${id}`}>Completed DOC_03</Link>}
    </div></div>

    <div className="card"><h3>Request for work inspection / approval</h3>
      <div className="kv">
        <div><div className="k">Project</div><div className="v">{d.project.code}</div></div>
        <div><div className="k">Work item</div><div className="v">{r.work_item || '—'}</div></div>
        <div><div className="k">Location / chainage</div><div className="v mono">{loc(r)}</div></div>
        <div><div className="k">Inspection</div><div className="v">{fmtDay(r.inspection_date)} {r.inspection_time || r.inspection_time_text || ''}</div></div>
        <div><div className="k">Requested</div><div className="v">{r.requested_date_note ? <span className="muted">{r.requested_date_note}</span> : <>{fmtDay(r.requested_date_display ?? r.requested_date)} {r.requested_time || ''}</>}</div></div>
        <div><div className="k">BOQ item</div><div className="v">{r.boq_item || '—'}</div></div>
        <div><div className="k">Material source</div><div className="v">{r.material_source || r.material_source_designation || '—'}{r.material_source_offset ? ` / ${r.material_source_offset}` : ''}</div></div>
        <div><div className="k">Order of inspection</div><div className="v">{['—', 'First', 'Second', 'Third'][r.inspection_order || 0]}</div></div>
        {r.origin_label ? <div><div className="k">Origin</div><div className="v">{r.origin_label}<div className="muted" style={{ fontSize: 12 }}>The original submitter is not recorded.</div></div></div>
          : <div><div className="k">Submitted by</div><div className="v">{d.summary?.submitted_by_name || d.created_by_name || '—'}{d.summary?.submitted_at && <> · {fmtDate(d.summary.submitted_at)}</>}</div></div>}
        <div><div className="k">Received by</div><div className="v">{d.received_by_name || '—'}{r.received_at && <> · {fmtDate(r.received_at)}</>}</div></div>
        {(r.approved_from || r.approved_to) && <div><div className="k">Approved section</div><div className="v mono">{r.approved_from} – {r.approved_to}</div></div>}
        <div><div className="k">Enclosure sheets</div><div className="v">{r.enclosure_sheets ?? '—'}</div></div>
      </div>
      <p><b>Works description:</b> {r.contractor_request || r.description}</p>
      {r.contractor_request && r.description && <p><b>Activity:</b> {r.description}</p>}
      {r.remarks && <p style={{ marginBottom: 0 }}><b>Remarks:</b> {r.remarks}</p>}
    </div>

    <div className="card"><h3>Action by the Engineer — inspector reviews</h3>
      {d.assignments.length ? <div className="table-wrap"><table>
        <thead><tr><th>#</th><th>Inspector</th><th>DOC_03 field</th><th>Status</th><th>Comments</th><th>Evidence</th><th>Submitted</th></tr></thead>
        <tbody>{d.assignments.map((a: any) => <tr key={a.id} style={a.status === 'REPLACED' ? { opacity: .6 } : undefined}>
          <td>{a.sequence_no ?? '—'}</td><td>{a.user_name}</td><td>{roleLabel(a.reviewer_role)}</td>
          <td><Status value={a.status} />{a.change_reason && a.status === 'REPLACED' && <div className="muted" style={{ fontSize: 12 }}>{a.change_reason}</div>}</td>
          <td style={{ whiteSpace: 'pre-wrap' }}>{a.review?.comment || ''}</td><td>{a.evidence_count ?? '—'}</td><td className="nowrap">{a.review ? fmtDate(a.review.reviewed_at) : ''}</td></tr>)}</tbody>
      </table></div> : <div className="empty">{r.is_legacy ? 'No inspector reviews were recorded for this historical RFI.' : 'No inspectors assigned yet.'}</div>}
    </div>

    {d.decisions.length > 0 && <div className="card"><h3>Final decision</h3><div className="table-wrap"><table>
      <thead><tr><th>Date</th><th>Rev</th><th>Disposition</th><th>By</th><th>Approved section</th><th>Remark</th></tr></thead>
      <tbody>{d.decisions.map((x: any) => <tr key={x.id}><td className="nowrap">{fmtDate(x.decided_at)}</td><td>{x.revision_no}</td><td>{x.disposition_label || <Status value={x.decision} />}</td><td>{x.decided_by_name}{x.designation_snapshot && <div className="muted" style={{ fontSize: 12 }}>{x.designation_snapshot}</div>}</td>
        <td className="mono">{x.approved_from || x.approved_to ? `${x.approved_from || ''} – ${x.approved_to || ''}` : '—'}</td><td>{x.comment}{x.conditions && <div className="muted">Conditions: {x.conditions}</div>}</td></tr>)}</tbody></table></div>
      {d.issued_documents[0] && <p className="muted" style={{ fontSize: 12 }}>DOC_03 issued {fmtDate(d.issued_documents[0].issued_at)} · SHA-256 {d.issued_documents[0].sha256.slice(0, 16)}…</p>}</div>}

    {evAm.length > 0 && <div className="card"><h3>Evidence corrections</h3><div className="stack">{evAm.map(a => <div key={a.id} className="evidence">
      <div className="section-title" style={{ marginBottom: 6 }}><b>{a.amendment_type === 'REVIEW' ? 'Inspector review correction' : 'Management remark correction'}</b><Status value={a.status} /></div>
      <div className="muted" style={{ fontSize: 12.5 }}>{a.requested_by_name} · {fmtDate(a.requested_at)} · Reason: {a.reason}</div>
      {a.changes.comment && <div style={{ marginTop: 6 }}><div className="muted" style={{ fontSize: 12 }}>Original</div><div style={{ whiteSpace: 'pre-wrap' }}>{a.changes.comment.old}</div><div className="muted" style={{ fontSize: 12, marginTop: 4 }}>Corrected</div><div style={{ whiteSpace: 'pre-wrap' }}>{a.changes.comment.new}</div></div>}
      {a.files.length > 0 && <ul className="ev-list">{a.files.map((f: any) => <FileRow key={f.id} f={f} />)}</ul>}
      {a.status === 'PENDING' && perm.resolve_amendment && <div className="actions"><button className="btn sm success" disabled={busy} onClick={() => resolve(a.id, true)}>Approve</button><button className="btn sm danger" disabled={busy} onClick={() => resolve(a.id, false)}>Reject</button></div>}
    </div>)}</div></div>}

    {fieldAmends.length > 0 && <div className="card"><h3>DOC_01 amendments</h3><div className="table-wrap"><table>
      <thead><tr><th>Requested</th><th>By</th><th>Changes (original → amended)</th><th>Reason</th><th>Status</th><th></th></tr></thead>
      <tbody>{fieldAmends.map((a: any) => <tr key={a.id}><td className="nowrap">{fmtDate(a.requested_at)}</td><td>{a.requested_by_name}</td>
        <td>{Object.entries(a.changes).map(([k, v]: any) => <div key={k}><b>{k}</b>: {String(v.old ?? '—')} → {String(v.new ?? '—')}</div>)}</td><td>{a.reason}</td>
        <td><Status value={a.status} />{a.resolved_by_name && <div className="muted" style={{ fontSize: 12 }}>{a.resolved_by_name} · {a.resolution_comment}</div>}</td>
        <td className="nowrap">{a.status === 'PENDING' && perm.resolve_amendment && <><button className="btn sm success" onClick={() => resolve(a.id, true)}>Approve</button> <button className="btn sm danger" onClick={() => resolve(a.id, false)}>Reject</button></>}</td></tr>)}</tbody></table></div></div>}

    <Attachments entityType="rfi" entityId={+id!} canUpload={!r.is_legacy && r.record_state === 'ACTIVE' && !!perm.edit_draft} title="DOC_01 enclosures"
      note={!r.is_legacy ? 'Inspection evidence is attached to the inspector review or the RE/DRE remark it supports; see the workflow timeline.' : undefined} />

    <div className="card"><h3>Status history</h3>{d.history?.length ? <div className="table-wrap"><table>
      <thead><tr><th>Date</th><th>Status</th><th>By</th><th>Reason</th></tr></thead>
      <tbody>{d.history.map((h: any) => <tr key={h.id}><td className="nowrap">{fmtDate(h.created_at)}</td><td><Status value={h.workflow_status} /></td><td>{h.changed_by_name}</td><td>{h.reason || ''}</td></tr>)}</tbody>
    </table></div> : <div className="empty">No history recorded.</div>}</div>

    {amend && <div className="modal-bg"><form className="modal" onSubmit={sendAmend} role="dialog" aria-modal="true" aria-labelledby="am-t">
      <h2 id="am-t">Request amendment – {r.rfi_number}</h2>
      <p className="muted">Submitted data is locked. The RE/DRE must approve the change; the original values are kept in the record.</p>
      <div className="grid">{AMEND_FIELDS.map(([k, l, t]) => <div key={k}><label htmlFor={`am-${k}`}>{l}</label><input id={`am-${k}`} type={t || 'text'} value={amend[k] ?? ''} onChange={e => setAmend({ ...amend, [k]: e.target.value })} /></div>)}</div>
      <div style={{ marginTop: 12 }}><label className="req" htmlFor="am-r">Reason</label><input id="am-r" required value={amend.reason} onChange={e => setAmend({ ...amend, reason: e.target.value })} /></div>
      <div className="actions end"><button type="button" className="btn secondary" onClick={() => setAmend(null)}>Cancel</button><button className="btn">Send for approval</button></div>
    </form></div>}
    {resub && <div className="modal-bg"><div className="modal" role="dialog" aria-modal="true" aria-labelledby="rs-t">
      <h2 id="rs-t">Resubmit {r.rfi_number} as Rev {r.revision_no + 1}</h2>
      <div className="grid"><div style={{ gridColumn: '1/-1' }}><label className="req" htmlFor="rs-r">What was corrected?</label><input id="rs-r" value={resub.reason} onChange={e => setResub({ ...resub, reason: e.target.value })} /></div>
        <div><label className="req" htmlFor="rs-d">Proposed inspection date</label><input id="rs-d" type="date" value={resub.inspection_date} onChange={e => setResub({ ...resub, inspection_date: e.target.value })} /></div>
        <div><label className="req" htmlFor="rs-t2">Proposed inspection time</label><input id="rs-t2" type="time" value={resub.inspection_time} onChange={e => setResub({ ...resub, inspection_time: e.target.value })} /></div>
        <div><label htmlFor="rs-f">Station from (remaining section)</label><input id="rs-f" value={resub.chainage_from} placeholder={r.approved_to || r.chainage_from || ''} onChange={e => setResub({ ...resub, chainage_from: e.target.value })} /></div>
        <div><label htmlFor="rs-to">Station to</label><input id="rs-to" value={resub.chainage_to} placeholder={r.chainage_to || ''} onChange={e => setResub({ ...resub, chainage_to: e.target.value })} /></div></div>
      <div className="actions end"><button className="btn secondary" onClick={() => setResub(null)}>Cancel</button>
        <button className="btn warn" disabled={!resub.reason.trim() || !resub.inspection_date || !resub.inspection_time} onClick={async () => { try { const n: any = await post(`/rfis/${id}/resubmit`, resub); nav(`/rfis/${n.id}`); } catch (e: any) { alert(e.message); } }}>Resubmit</button></div>
    </div></div>}
    <ConfirmDialog open={cancelOpen} title={`Cancel RFI ${r.rfi_number}?`} tone="danger" confirmLabel="Cancel RFI" busy={busy} onCancel={() => setCancelOpen(false)}
      onConfirm={() => { if (!cancelDlg.trim()) { alert('Give the reason.'); return; } setCancelOpen(false); run(() => post(`/rfis/${id}/cancel`, { reason: cancelDlg }), 'RFI cancelled.'); }}
      rows={[['RFI No.', r.rfi_number], ['Current status', r.status_label]]} warnings={['Open inspector turns end. The record is kept read-only.']}>
      <div><label className="req" htmlFor="cx">Reason</label><input id="cx" value={cancelDlg} onChange={e => setCancelDlg(e.target.value)} /></div>
    </ConfirmDialog>
  </>;
}
