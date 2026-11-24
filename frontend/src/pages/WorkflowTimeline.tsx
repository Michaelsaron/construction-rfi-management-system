import React, { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api, fmtDate, loc } from '../lib/api';
import type { Timeline, TimelineStage } from '../lib/contracts';
import { PageHeader, Loading, ErrorNote } from '../components/ui';
import { FileRow } from '../components/EvidencePanel';
import { RemarkList } from '../components/RemarkEvidence';
import Status from '../components/Status';

const WORD: Record<string, string> = { done: 'Completed', active: 'Active', pending: 'Pending', replaced: 'Replaced', locked: 'Locked' };

function line(s: TimelineStage) {
  if (s.key.startsWith('INSPECTOR_')) {
    if (s.status === 'done') return `Submitted · ${fmtDate(s.at)}`;
    if (s.status === 'active') return `Active${s.due_at ? ` · due ${fmtDate(s.due_at)}` : ''}${s.overdue ? ' · OVERDUE' : ''}`;
    if (s.status === 'replaced') return `Replaced${s.change_reason ? ` · ${s.change_reason}` : ''}`;
    return 'Pending';
  }
  if (s.key === 'FINAL_DECISION' && s.status !== 'done') return s.status === 'active' ? 'Ready for final disposition' : 'Locked until reviews complete';
  return s.at ? fmtDate(s.at) : WORD[s.status];
}

/** Category 2.1 — sequential workflow monitoring (UI design s.6). Other roles see what they may see. */
export default function WorkflowTimeline() {
  const { id } = useParams();
  const [t, setT] = useState<Timeline | null>(null); const [err, setErr] = useState(''); const [sel, setSel] = useState<string>('');
  useEffect(() => { api(`/rfis/${id}/timeline`).then((x: Timeline) => {
    setT(x);
    const insp = x.stages.filter(s => s.key.startsWith('INSPECTOR_') && s.status === 'done');
    setSel((insp[insp.length - 1] || x.stages.find(s => s.status === 'active') || x.stages[0]).key);
  }).catch(e => setErr(e.message)); }, [id]);
  if (err) return <ErrorNote error={err} />;
  if (!t) return <Loading />;
  const r = t.rfi;
  const s = t.stages.find(x => x.key === sel) || t.stages[0];
  const title = s.key.startsWith('INSPECTOR_') ? (s.status === 'done' ? 'Inspector submission' : 'Inspector stage') : s.title;
  return <>
    <PageHeader title="Sequential workflow monitoring" back={{ to: '/workflow', label: 'Workflow monitor' }}
      actions={<>{t.can_decide && <Link className="btn success" to={`/rfis/${id}/decision`}>Final disposition</Link>}<Link className="btn secondary" to={`/rfis/${id}`}>RFI record</Link></>} />
    <div className="card">
      <h2 style={{ fontSize: 16 }}><span className="mono">{r.rfi_number}</span>{r.revision_no ? ` Rev ${r.revision_no}` : ''} · Ch.{loc(r)} · {r.contractor_request || r.description}</h2>
      <div className="cols-2" style={{ marginTop: 14 }}>
        <ol className="timeline" aria-label="Workflow stages">{t.stages.map(x => <li key={x.key} className={`${x.status}${x.key === sel ? ' sel' : ''}`}>
          <span className="dot" aria-hidden="true" />
          <div>
            <button type="button" className="t" onClick={() => setSel(x.key)} aria-current={x.key === sel ? 'step' : undefined}>
              {x.sequence_no ? `${x.sequence_no} · ` : ''}{x.title}<span className="sr-only"> ({WORD[x.status]})</span></button>
            <div className="d">{line(x)}{x.actor && ` · ${x.actor}`}</div>
            {x.overdue && <Status value="OVERDUE" label="Overdue" />}
          </div></li>)}</ol>
        <div className="evidence" aria-live="polite">
          <h4>{title}</h4>
          <div style={{ fontSize: 13, marginBottom: 8 }}><Status value={s.status === 'done' ? 'COMPLETED' : s.status === 'active' ? 'ACTIVE' : s.status === 'replaced' ? 'REPLACED' : 'PENDING'} label={`${s.title} · ${WORD[s.status]}`} /></div>
          <dl className="confirm-rows" style={{ margin: '8px 0', background: 'var(--surface)' }}>
            <dt>By</dt><dd>{s.actor || '—'}</dd><dt>Role</dt><dd>{s.actor_role || '—'}</dd><dt>Date / time</dt><dd>{s.at ? fmtDate(s.at) : '—'}</dd>
            {s.detail && <><dt>Detail</dt><dd>{s.detail}</dd></>}
            {s.approved_section && <><dt>Approved section</dt><dd className="mono">{s.approved_section.from} – {s.approved_section.to}</dd></>}
          </dl>
          {s.comment && <div style={{ whiteSpace: 'pre-wrap', margin: '10px 0' }}>{s.comment}</div>}
          {s.key.startsWith('INSPECTOR_') && s.status !== 'done' && <p className="muted" style={{ fontSize: 13 }}>Comments and evidence are visible after this inspector submits. Later inspectors stay read-only until their turn.</p>}
          {s.files && s.files.length > 0 && <><h4 style={{ marginTop: 12 }}>Evidence</h4><ul className="ev-list">{s.files.map(f => <FileRow key={f.id} f={f} />)}</ul></>}
          {s.key.startsWith('INSPECTOR_') && s.status === 'done' && !s.files?.length && <p className="muted" style={{ fontSize: 13 }}>{s.evidence_count ? `${s.evidence_count} file(s) recorded; your role cannot open them.` : 'No evidence files were attached.'}</p>}
          {s.remarks && s.remarks.length > 0 && <><h4 style={{ marginTop: 12 }}>Management remarks</h4><RemarkList remarks={s.remarks} /></>}
        </div>
      </div>
    </div>
  </>;
}
