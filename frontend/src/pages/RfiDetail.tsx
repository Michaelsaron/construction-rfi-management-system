import React, { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { api, post, download, fmtDate, fmtDay, loc, roleLabel, INSPECTORS } from '../lib/api';
import Attachments from '../components/Attachments';
import Status from '../components/Status';
import Icon from '../components/Icon';

const AMEND_FIELDS: [string, string, string?][] = [['contractor_request', 'Works description'], ['chainage_from', 'Station from'], ['chainage_to', 'Station to'], ['side', 'Side'],
  ['material_source', 'Material source'], ['material_source_offset', 'Material offset'], ['boq_item', 'BOQ item'], ['inspection_date', 'Inspection date', 'date'],
  ['inspection_time', 'Inspection time', 'time'], ['remarks', 'Remark']];

export default function RfiDetail() {
  const { id } = useParams(); const nav = useNavigate();
  const [d, setD] = useState<any>(null); const [err, setErr] = useState(''); const [msg, setMsg] = useState(''); const [busy, setBusy] = useState(false);
  const [members, setMembers] = useState<any[]>([]); const [plan, setPlan] = useState<number[]>([]); const [planReason, setPlanReason] = useState(''); const [suggested, setSuggested] = useState<any[]>([]);
  const [comment, setComment] = useState('');
  const [dec, setDec] = useState<any>({ disposition_code: '', comment: '', conditions: '', approved_from: '', approved_to: '' });
  const [amend, setAmend] = useState<any>(null);
  const load = () => api(`/rfis/${id}`).then((x: any) => { setD(x); return x; }).catch(e => setErr(e.message));
  useEffect(() => {
    setD(null); setErr(''); setMsg('');
    load().then((x: any) => {
      if (!x) return;
      if (x.permissions.assign) {
        api(`/projects/${x.rfi.project_id}/members`).then((ms: any[]) => setMembers(ms.filter(m => INSPECTORS.includes(m.role) && m.is_active))).catch(() => {});
        api(`/rfis/${id}/suggested-reviewers`).then(setSuggested).catch(() => {});
        setPlan(x.assignments.filter((a: any) => ['PENDING', 'ACTIVE'].includes(a.status)).map((a: any) => a.user_id));
      }
    });
  }, [id]);

  async function run(fn: () => Promise<any>, ok: string) {
    setBusy(true); setMsg('');
    try { await fn(); setMsg(ok); await load(); } catch (e: any) { alert(e.message); } finally { setBusy(false); }
  }
  if (err) return <div className="notice err">{err} <Link className="link" to="/rfis">Back to register</Link></div>;
  if (!d) return <div className="empty">Loading RFI…</div>;
  const r = d.rfi, perm = d.permissions, deputy = d.project.deputy_label;
  const started = d.assignments.some((a: any) => a.status === 'COMPLETED');
  const live = d.assignments.filter((a: any) => a.status !== 'REPLACED');
  const disp = d.dispositions.find((x: any) => x.code === dec.disposition_code);
  const savePlan = () => {
    if (!plan.length) { alert('Add at least one inspector.'); return; }
    if (started && !planReason.trim()) { alert('Inspection has started: enter the reason for changing the sequence.'); return; }
    run(() => post(`/rfis/${id}/assignments`, { assignments: plan.map(u => ({ user_id: u })), reason: planReason || null }), 'Inspection sequence saved and inspectors notified.');
  };
  const move = (i: number, delta: number) => { const p = [...plan]; const j = i + delta; if (j < 0 || j >= p.length) return; [p[i], p[j]] = [p[j], p[i]]; setPlan(p); };
  const submitReview = () => {
    if (!comment.trim()) { alert('Enter your inspection comments.'); return; }
    if (!confirm('Submit your review? It will be locked and the next inspector will be notified.')) return;
    run(() => post(`/rfis/${id}/review`, { assignment_id: perm.review_assignment_id, comment }), 'Review submitted.').then(() => setComment(''));
  };
  const decide = () => {
    if (!disp) { alert('Select a disposition.'); return; }
    if (disp.requires_section && !(dec.approved_from && dec.approved_to)) { alert('Enter the approved (executed) section.'); return; }
    if (!confirm(`Record final decision: "${disp.label}"? This completes Rev ${r.revision_no} and issues the DOC_03.`)) return;
    run(() => post(`/rfis/${id}/decision`, dec), 'Final decision recorded. Completed DOC_03 issued.');
  };
  const resubmit = async () => {
    const reason = prompt('What was corrected? (resubmission reason)'); if (!reason?.trim()) return;
    const date = prompt('Proposed inspection date (YYYY-MM-DD)'); if (!date) return;
    const time = prompt('Proposed inspection time (HH:MM, 24-hour)'); if (!time) return;
    try { const n: any = await post(`/rfis/${id}/resubmit`, { reason, inspection_date: date, inspection_time: time }); nav(`/rfis/${n.id}`); } catch (e: any) { alert(e.message); }
  };
  const sendAmend = (e: any) => {
    e.preventDefault();
    const changes: any = {}; for (const [k] of AMEND_FIELDS) if ((amend[k] ?? '') !== (r[k] ?? '')) changes[k] = amend[k] === '' ? null : amend[k];
    if (!Object.keys(changes).length) { alert('Nothing changed.'); return; }
    if (!amend.reason?.trim()) { alert('Enter the reason for the amendment.'); return; }
    run(() => post(`/rfis/${id}/amendments`, { changes, reason: amend.reason }), 'Amendment requested. RE/DRE will review it.').then(() => setAmend(null));
  };
  const resolve = (aid: number, ok: boolean) => { const c = prompt(ok ? 'Approval comment (optional)' : 'Reason for rejecting the amendment') ?? ''; run(() => post(`/rfis/amendments/${aid}/${ok ? 'approve' : 'reject'}`, { comment: c }), ok ? 'Amendment applied.' : 'Amendment rejected.'); };

  return <>
    <div className="top"><div>
      <Link to="/rfis" className="link" style={{ fontSize: 14 }}>← DOC_02 register</Link>
      <h1 style={{ marginTop: 6 }}><span className="mono" style={{ fontSize: '.85em' }}>{r.rfi_number}</span> · Rev {r.revision_no}</h1>
      <div className="chips" style={{ marginBottom: 18 }}>
        <Status value={r.workflow_status} label={r.status_label} />{r.current_decision && <Status value={r.current_decision} />}
        {r.is_legacy && <Status value="LEGACY" label="Historical record (read-only)" />}{r.short_notice && <Status value="SHORT_NOTICE" label={`Short notice: ${r.notice_hours} h`} />}
        {d.summary && <Link to={`/summaries/${d.summary.id}`} className="badge" style={{ textDecoration: 'none', color: 'inherit' }}>DOC_01 {d.summary.summary_reference}</Link>}
        {d.revisions.length > 1 && d.revisions.map((v: any) => v.id !== r.id && <Link key={v.id} to={`/rfis/${v.id}`} className="badge" style={{ textDecoration: 'none', color: 'inherit' }}>Rev {v.revision_no}</Link>)}
      </div></div>
      <div className="toolbar">
        <button className="btn secondary" onClick={() => download(`/reports/doc03/${id}.pdf`, `DOC03_${r.rfi_number}_rev${r.revision_no}.pdf`)}><Icon name="download" size={16} />DOC_03 PDF</button>
        {perm.request_amendment && <button className="btn secondary" onClick={() => setAmend({ ...Object.fromEntries(AMEND_FIELDS.map(([k]) => [k, r[k] ?? ''])), reason: '' })}>Request amendment</button>}
        {perm.resubmit && <button className="btn warn" onClick={resubmit}>Resubmit (next revision)</button>}
        {perm.cancel && <button className="btn danger" disabled={busy} onClick={() => { const reason = prompt('Reason to cancel this RFI?'); if (reason?.trim()) run(() => post(`/rfis/${id}/cancel`, { reason }), 'RFI cancelled.'); }}>Cancel RFI</button>}
      </div></div>
    {msg && <div className="notice ok">{msg}</div>}
    {r.is_legacy && <div className="notice">Imported from the historical DOC_02 workbook. There is no DOC_01 batch or DOC_03 review for it in the system; the original status text is preserved: <b>{r.legacy_rfi_status || '(blank)'}</b>.</div>}

    <div className="card"><h3>Request For Work Inspection / Approval</h3>
      <div className="kv">
        <div><div className="k">Project</div><div className="v">{d.project.code}</div></div>
        <div><div className="k">Work item</div><div className="v">{r.work_item || '—'}</div></div>
        <div><div className="k">Location / chainage</div><div className="v mono">{loc(r)}</div></div>
        <div><div className="k">Inspection</div><div className="v">{fmtDay(r.inspection_date)} {r.inspection_time || r.inspection_time_text || ''}</div></div>
        <div><div className="k">Requested</div><div className="v">{fmtDay(r.requested_date)} {r.requested_time || ''}</div></div>
        <div><div className="k">BOQ item</div><div className="v">{r.boq_item || '—'}</div></div>
        <div><div className="k">Material source</div><div className="v">{r.material_source || r.material_source_designation || '—'}{r.material_source_offset ? ` / ${r.material_source_offset}` : ''}</div></div>
        <div><div className="k">Order of inspection</div><div className="v">{['—', 'First', 'Second', 'Third'][r.inspection_order || 0]}</div></div>
        <div><div className="k">Submitted by</div><div className="v">{d.summary?.submitted_by_name || d.created_by_name || '—'}{d.summary?.submitted_at && <> · {fmtDate(d.summary.submitted_at)}</>}</div></div>
        <div><div className="k">Received by</div><div className="v">{d.received_by_name || '—'}{r.received_at && <> · {fmtDate(r.received_at)}</>}</div></div>
        {(r.approved_from || r.approved_to) && <div><div className="k">Approved section</div><div className="v mono">{r.approved_from} – {r.approved_to}</div></div>}
        <div><div className="k">Enclosure sheets</div><div className="v">{r.enclosure_sheets ?? '—'}</div></div>
      </div>
      <p><b>Works description:</b> {r.contractor_request || r.description}</p>
      {r.contractor_request && r.description && <p><b>Activity:</b> {r.description}</p>}
      {r.work_categories?.length > 0 && <p><b>Work category:</b> {r.work_categories.join(', ').replaceAll('_', ' ')}</p>}
      {r.remarks && <p><b>Remarks:</b> {r.remarks}</p>}
    </div>

    {perm.assign && <div className="card" style={{ borderColor: 'var(--amber)' }}>
      <h3>{live.length ? 'Inspection sequence' : 'Assign inspectors and review order'}</h3>
      <p className="muted" style={{ marginTop: 0 }}>Inspectors review strictly in this order. Only the first inspector can submit; each next inspector is activated when the previous one submits. {started && 'Completed reviews stay locked; you are changing the remaining sequence.'}</p>
      {suggested.length > 0 && <div className="notice">Reviewer rules suggest: {suggested.map((x: any) => roleLabel(x.reviewer_role)).join(' → ')}</div>}
      {members.length === 0 ? <div className="notice">No inspectors (Category 2.2) are members of this project. The administrator must add them.</div> : <>
        <ol>{plan.map((uid, i) => { const m = members.find(x => x.user_id === uid); return <li key={uid} style={{ marginBottom: 6 }}>{m ? `${m.full_name} — ${m.role_label}` : `User ${uid}`}{' '}
          <button className="btn secondary sm" onClick={() => move(i, -1)} disabled={i === 0} aria-label="Move up">↑</button> <button className="btn secondary sm" onClick={() => move(i, 1)} disabled={i === plan.length - 1} aria-label="Move down">↓</button> <button className="btn secondary sm" onClick={() => setPlan(plan.filter(x => x !== uid))}>Remove</button></li>; })}</ol>
        <div className="toolbar"><select defaultValue="" onChange={e => { const v = +e.target.value; if (v && !plan.includes(v)) setPlan([...plan, v]); e.target.value = ''; }}>
          <option value="">+ Add inspector…</option>{members.filter(m => !plan.includes(m.user_id)).map(m => <option key={m.user_id} value={m.user_id}>{m.full_name} — {m.role_label}</option>)}</select></div>
        {(started || live.length > 0) && <div style={{ marginTop: 10 }}><label>Reason for change {started ? '(required)' : '(optional)'}</label><input value={planReason} onChange={e => setPlanReason(e.target.value)} placeholder="e.g. Surveyor on leave" /></div>}
        <div style={{ marginTop: 12 }}><button className="btn" disabled={busy || !plan.length} onClick={savePlan}>Save sequence &amp; notify</button></div>
      </>}
    </div>}

    <div className="card"><h3>Action by the Engineer – inspector reviews</h3>
      {d.assignments.length ? <div className="table-wrap"><table>
        <thead><tr><th>#</th><th>Inspector</th><th>DOC_03 field</th><th>Status</th><th>Comments</th><th>Submitted</th></tr></thead>
        <tbody>{d.assignments.map((a: any) => <tr key={a.id} style={a.status === 'REPLACED' ? { opacity: .55 } : undefined}>
          <td>{a.sequence_no ?? '—'}</td><td>{a.user_name}</td><td>{roleLabel(a.reviewer_role)}</td><td><Status value={a.status} />{a.change_reason && a.status === 'REPLACED' && <div className="muted" style={{ fontSize: 12 }}>{a.change_reason}</div>}</td>
          <td style={{ whiteSpace: 'pre-wrap' }}>{a.review?.comment || ''}</td><td>{a.review ? fmtDate(a.review.reviewed_at) : ''}</td></tr>)}</tbody>
      </table></div> : <div className="empty">{r.is_legacy ? 'No inspector reviews were recorded for this historical RFI.' : 'No inspectors assigned yet.'}</div>}
      {perm.review_assignment_id && <div style={{ marginTop: 14 }}>
        <label>Your inspection comments (your designated DOC_03 field)</label>
        <textarea value={comment} onChange={e => setComment(e.target.value)} placeholder="Site findings, levels, FDT results, corrections required…" rows={4} />
        <div className="toolbar" style={{ marginTop: 10 }}><button className="btn" disabled={busy || !comment.trim()} onClick={submitReview}>Submit my review</button></div>
      </div>}
      {!perm.review_assignment_id && d.assignments.some((a: any) => a.status === 'PENDING' && INSPECTORS.includes(d.my_role) && a.user_name) && d.my_role && INSPECTORS.includes(d.my_role) &&
        <div className="notice" style={{ marginTop: 12 }}>You will be able to submit when the inspectors before you have submitted.</div>}
    </div>

    {perm.decide && <div className="card" style={{ borderColor: 'var(--green, #12805c)' }}>
      <h3>RE/{deputy} final disposition</h3>
      <div className="grid"><div><label>Disposition</label><select value={dec.disposition_code} onChange={e => setDec({ ...dec, disposition_code: e.target.value })}>
        <option value="">Select…</option>{d.dispositions.map((x: any) => <option key={x.code} value={x.code}>{x.label}</option>)}</select></div>
        {(disp?.requires_section || disp?.decision === 'APPROVED') && <><div><label>Approved from {disp?.requires_section && '*'}</label><input value={dec.approved_from} placeholder={r.chainage_from || ''} onChange={e => setDec({ ...dec, approved_from: e.target.value })} /></div>
          <div><label>Approved to {disp?.requires_section && '*'}</label><input value={dec.approved_to} placeholder={r.chainage_to || ''} onChange={e => setDec({ ...dec, approved_to: e.target.value })} /></div></>}
      </div>
      <div style={{ marginTop: 12 }}><label>Remark</label><textarea value={dec.comment} onChange={e => setDec({ ...dec, comment: e.target.value })} /></div>
      <div style={{ marginTop: 12 }}><label>Conditions (if any)</label><input value={dec.conditions} onChange={e => setDec({ ...dec, conditions: e.target.value })} /></div>
      <p className="muted" style={{ fontSize: 13 }}>Disposition options are configurable per project and remain subject to client approval.</p>
      <button className="btn success" disabled={busy || !dec.disposition_code} onClick={decide}>Record final decision</button>
    </div>}

    {d.decisions.length > 0 && <div className="card"><h3>Final decision</h3><div className="table-wrap"><table>
      <thead><tr><th>Date</th><th>Rev</th><th>Disposition</th><th>By</th><th>Approved section</th><th>Remark</th></tr></thead>
      <tbody>{d.decisions.map((x: any) => <tr key={x.id}><td>{fmtDate(x.decided_at)}</td><td>{x.revision_no}</td><td>{x.disposition_label || <Status value={x.decision} />}</td><td>{x.decided_by_name}</td>
        <td className="mono">{x.approved_from || x.approved_to ? `${x.approved_from || ''} – ${x.approved_to || ''}` : '—'}</td><td>{x.comment}{x.conditions && <div className="muted">Conditions: {x.conditions}</div>}</td></tr>)}</tbody></table></div>
      {d.issued_documents[0] && <p className="muted" style={{ fontSize: 12 }}>DOC_03 issued {fmtDate(d.issued_documents[0].issued_at)} · SHA-256 {d.issued_documents[0].sha256.slice(0, 16)}…</p>}</div>}

    {d.amendments.length > 0 && <div className="card"><h3>Amendments</h3><div className="table-wrap"><table>
      <thead><tr><th>Requested</th><th>By</th><th>Changes (original → amended)</th><th>Reason</th><th>Status</th><th></th></tr></thead>
      <tbody>{d.amendments.map((a: any) => <tr key={a.id}><td>{fmtDate(a.requested_at)}</td><td>{a.requested_by_name}</td>
        <td>{Object.entries(a.changes).map(([k, v]: any) => <div key={k}><b>{k}</b>: {String(v.old ?? '—')} → {String(v.new ?? '—')}</div>)}</td><td>{a.reason}</td>
        <td><Status value={a.status} />{a.resolved_by_name && <div className="muted" style={{ fontSize: 12 }}>{a.resolved_by_name} · {a.resolution_comment}</div>}</td>
        <td>{a.status === 'PENDING' && perm.resolve_amendment && <><button className="btn sm success" onClick={() => resolve(a.id, true)}>Approve</button> <button className="btn sm danger" onClick={() => resolve(a.id, false)}>Reject</button></>}</td></tr>)}</tbody></table></div></div>}

    <Attachments entityType="rfi" entityId={+id!} canUpload={!r.is_legacy && r.record_state === 'ACTIVE' && (perm.edit_draft || perm.assign || !!perm.review_assignment_id || perm.request_amendment)} />

    <div className="card"><h3>Status history</h3>{d.history?.length ? <div className="table-wrap"><table>
      <thead><tr><th>Date</th><th>Status</th><th>By</th><th>Reason</th></tr></thead>
      <tbody>{d.history.map((h: any) => <tr key={h.id}><td>{fmtDate(h.created_at)}</td><td><Status value={h.workflow_status} /></td><td>{h.changed_by_name}</td><td>{h.reason || ''}</td></tr>)}</tbody>
    </table></div> : <div className="empty">No history recorded.</div>}</div>

    {amend && <div className="modal-bg" onClick={e => { if (e.target === e.currentTarget) setAmend(null); }}>
      <form className="modal" onSubmit={sendAmend}>
        <div className="section-title"><h3>Request amendment – {r.rfi_number}</h3><button type="button" className="icon-btn" onClick={() => setAmend(null)} aria-label="Close"><Icon name="x" /></button></div>
        <p className="muted">Submitted data is locked. The RE/DRE must approve the change; the original values are kept in the record.</p>
        <div className="grid">{AMEND_FIELDS.map(([k, l, t]) => <div key={k}><label>{l}</label><input type={t || 'text'} value={amend[k] ?? ''} onChange={e => setAmend({ ...amend, [k]: e.target.value })} /></div>)}</div>
        <div style={{ marginTop: 12 }}><label>Reason *</label><input required value={amend.reason} onChange={e => setAmend({ ...amend, reason: e.target.value })} /></div>
        <div className="toolbar" style={{ marginTop: 16 }}><button className="btn">Send for approval</button><button type="button" className="btn secondary" onClick={() => setAmend(null)}>Cancel</button></div>
      </form></div>}
  </>;
}
