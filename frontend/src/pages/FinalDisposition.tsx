import React, { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { api, post, getUser, fmtDate, roleLabel } from '../lib/api';
import { PageHeader, ConfirmDialog, Loading, ErrorNote } from '../components/ui';
import { useRemarkDraft, RemarkEvidence } from '../components/RemarkEvidence';
import Status from '../components/Status';

/** Category 2.1 — final disposition with the exact DOC_03 values and the RE/DRE's own evidence (UI design s.7). */
export default function FinalDisposition() {
  const { id } = useParams(); const nav = useNavigate(); const me = getUser();
  const [d, setD] = useState<any>(null); const [err, setErr] = useState('');
  const [f, setF] = useState({ disposition_code: '', comment: '', conditions: '', approved_from: '', approved_to: '', work_status: '' });
  const [confirm, setConfirm] = useState(false); const [busy, setBusy] = useState(false);
  useEffect(() => { api(`/rfis/${id}`).then(setD).catch(e => setErr(e.message)); }, [id]);
  const draft = useRemarkDraft(d?.rfi.project_id, 'FINAL_DISPOSITION', d?.permissions.decide ? +id! : null);
  if (err) return <ErrorNote error={err} />;
  if (!d) return <Loading />;
  const r = d.rfi, perm = d.permissions, deputy = d.project.deputy_label;
  const live = d.assignments.filter((a: any) => a.status !== 'REPLACED');
  const disp = d.dispositions.find((x: any) => x.code === f.disposition_code);
  const needSection = disp?.requires_section;
  const missing = needSection && !(f.approved_from.trim() && f.approved_to.trim());
  async function record() {
    setBusy(true);
    try {
      await post(`/rfis/${id}/decision`, { ...f, work_status: f.work_status || null, management_remark_id: draft.remark?.id || null, evidence_count: draft.remark ? draft.files.length : null });
      setConfirm(false); nav(`/completed/${id}`);
    } catch (e: any) { setConfirm(false); alert(e.message); draft.reload(); } finally { setBusy(false); }
  }
  return <>
    <PageHeader title="Final disposition · DOC_03" back={{ to: '/decisions', label: 'Final decisions' }}
      actions={<><Link className="btn secondary" to={`/rfis/${id}/workflow`}>Workflow</Link><Link className="btn secondary" to={`/rfis/${id}`}>RFI record</Link></>} />
    <div className="card">
      <div className="section-title">
        <h2 style={{ fontSize: 17 }}><span className="mono">{r.rfi_number}</span>{r.revision_no ? ` Rev ${r.revision_no}` : ''} · {perm.decide ? 'All assigned inspector reviews completed' : r.status_label}</h2>
        {perm.decide ? <span className="pill amber">Awaiting final decision</span> : <Status value={r.workflow_status} label={r.status_label} />}
      </div>
      {!perm.decide && <div className="notice">{r.workflow_status === 'COMPLETED' ? <>The final decision has been recorded. <Link className="link" to={`/completed/${id}`}>Open the completed DOC_03</Link>.</> : 'The final decision is locked until every assigned inspector has submitted, and only the RE/DRE of this project can record it.'}</div>}
      <h3 style={{ marginTop: 6 }}>Inspector comments and evidence</h3>
      <div className="table-wrap inset"><table>
        <thead><tr><th>#</th><th>Reviewer</th><th>Latest comment</th><th>Evidence</th><th>Status</th></tr></thead>
        <tbody>{live.map((a: any) => <tr key={a.id}><td>{a.sequence_no}</td><td><b>{roleLabel(a.reviewer_role)}</b><div className="muted" style={{ fontSize: 12 }}>{a.user_name}</div></td>
          <td style={{ whiteSpace: 'pre-wrap', minWidth: 220 }}>{a.review?.comment || '—'}</td>
          <td className="nowrap">{a.evidence_count ?? 0} file{a.evidence_count === 1 ? '' : 's'}</td>
          <td><Status value={a.status === 'COMPLETED' ? 'SUBMITTED' : a.status} label={a.status === 'COMPLETED' ? 'Submitted' : undefined} /></td></tr>)}</tbody>
      </table></div>
      {live.some((a: any) => a.evidence_count) && <p className="muted" style={{ fontSize: 12.5 }}>Open the evidence from the <Link className="link" to={`/rfis/${id}/workflow`}>workflow timeline</Link>.</p>}
    </div>

    {perm.decide && <div className="card">
      <fieldset style={{ border: 0, padding: 0 }}><legend style={{ fontSize: 16, fontWeight: 700, padding: 0, marginBottom: 10 }}>Select the exact DOC_03 disposition</legend>
        <div className="disp-grid" role="radiogroup">{d.dispositions.map((x: any) => <label key={x.code} className={`disp-opt${f.disposition_code === x.code ? ' on' : ''}`}>
          <input type="radio" name="disp" value={x.code} checked={f.disposition_code === x.code} onChange={() => setF({ ...f, disposition_code: x.code })} />{x.label}</label>)}</div>
      </fieldset>
      {(needSection || disp?.decision === 'APPROVED') && <div className="grid" style={{ marginTop: 14 }}>
        <div><label className={needSection ? 'req' : ''} htmlFor="af">Approved (executed) from</label><input id="af" value={f.approved_from} placeholder={r.chainage_from || ''} onChange={e => setF({ ...f, approved_from: e.target.value })} aria-invalid={!!missing} /></div>
        <div><label className={needSection ? 'req' : ''} htmlFor="at">Approved (executed) to</label><input id="at" value={f.approved_to} placeholder={r.chainage_to || ''} onChange={e => setF({ ...f, approved_to: e.target.value })} aria-invalid={!!missing} /></div>
        <div><label>Requested section</label><div className="ro-field mono">{r.chainage_from || '—'} – {r.chainage_to || '—'}</div></div>
      </div>}
      {needSection && <p className="muted" style={{ fontSize: 13 }}>The remaining part of the requested section must be resubmitted by the contractor as the next revision.</p>}
      <div className="cols-2" style={{ marginTop: 14 }}>
        <div className="stack">
          <div><label htmlFor="fr">RE/{deputy} final remarks</label><textarea id="fr" value={f.comment} onChange={e => setF({ ...f, comment: e.target.value })} placeholder="e.g. Proceed subject to recorded comments and conditions." /></div>
          <div><label htmlFor="fc">Conditions (if any)</label><input id="fc" value={f.conditions} onChange={e => setF({ ...f, conditions: e.target.value })} /></div>
        </div>
        <RemarkEvidence draft={draft} canEdit title="Attach file / photograph to remark" />
      </div>
      <div className="actions end">
        <button className="btn success" disabled={!disp || !!missing || draft.busy || busy} onClick={() => setConfirm(true)}>{draft.busy ? 'Waiting for uploads…' : 'Record disposition'}</button>
      </div>
    </div>}

    <ConfirmDialog open={confirm} title="Record the final disposition?" tone="success" confirmLabel="Record disposition" busy={busy}
      intro={`This completes ${r.rfi_number} Rev ${r.revision_no}, locks the record and issues the DOC_03. It cannot be changed afterwards.`}
      onCancel={() => setConfirm(false)} onConfirm={record}
      rows={[['RFI No.', `${r.rfi_number}${r.revision_no ? ` Rev ${r.revision_no}` : ''}`], ['Disposition', disp?.label || ''], ['Final remarks', f.comment.trim()],
        ['Conditions', f.conditions.trim()], ['Evidence', `${draft.files.length} file(s) attached to your remark`],
        ['Decision-maker', `${me.name} · ${roleLabel(d.my_role)}`], ...(disp && (needSection || f.approved_from || f.approved_to) ? [['Approved section', `${f.approved_from || r.chainage_from || '—'} – ${f.approved_to || r.chainage_to || '—'}`] as [string, string]] : []),
        ...(needSection ? [['Remaining section', 'To be resubmitted by the contractor (next revision)'] as [string, string]] : []), ['Recorded at', 'Server time on confirmation']]} />
    {d.decisions.length > 0 && <div className="card"><h3>Recorded decision</h3>{d.decisions.map((x: any) => <p key={x.id} style={{ margin: 0 }}><b>{x.disposition_label || x.decision}</b> · {x.decided_by_name} ({x.designation_snapshot || 'RE/DRE'}) · {fmtDate(x.decided_at)}</p>)}</div>}
  </>;
}
