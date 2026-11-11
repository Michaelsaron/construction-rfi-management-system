import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../lib/api';
import Icon from '../components/Icon';
import Status, { pretty } from '../components/Status';

// Validated palette (light/dark) for the decision mix; every segment also carries a text label.
const MIX = [
  { key: 'approved', label: 'Approved', color: 'var(--success)' },
  { key: 'on_progress', label: 'On Progress', color: 'var(--info)' },
  { key: 'rejected', label: 'Rejected', color: 'var(--danger)' },
  { key: 'information_only', label: 'Information Only', color: 'var(--neutral)' },
];

const STEPS = [
  ['Summary created', 'Contractor drafts the RFI Summary and adds individual RFIs.'],
  ['Submitted & locked', 'Summary submitted to the Resident Engineer.'],
  ['Activated by RE/ARE', 'RFI accepted and technical reviewers assigned.'],
  ['Technical review', 'Reviewers inspect on site and submit recommendations.'],
  ['Final decision', 'RE/ARE approves, rejects or records for information.'],
];

function greeting() {
  const h = new Date().getHours();
  return h < 12 ? 'Good morning' : h < 17 ? 'Good afternoon' : 'Good evening';
}

export default function Dashboard() {
  const [d, setD] = useState<any>(null);
  const [err, setErr] = useState('');
  const u = JSON.parse(localStorage.getItem('user') || '{"name":"User"}');
  useEffect(() => { api('/dashboard').then(setD).catch(e => setErr(e.message)); }, []);

  if (err) return <div className="notice">Could not load dashboard: {err}</div>;
  if (!d) return <div className="empty">Loading site data…</div>;

  const total = Number(d.total) || 0;
  const pct = (n: number) => (total ? Math.round((n / total) * 100) : 0);
  const decided = MIX.reduce((s, m) => s + (Number(d[m.key]) || 0), 0);
  const today = new Date().toLocaleDateString(undefined, { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });

  const kpis = [
    { l: 'Total RFIs', n: total, icon: 'clipboard', k: 'total', sub: 'All records in register' },
    { l: 'Approved', n: d.approved, icon: 'checkCircle', k: 'success', sub: `${pct(d.approved)}% of total` },
    { l: 'Rejected', n: d.rejected, icon: 'xCircle', k: 'danger', sub: `${pct(d.rejected)}% of total` },
    { l: 'On Progress', n: d.on_progress, icon: 'clock', k: 'info', sub: `${pct(d.on_progress)}% of total` },
    { l: 'Information Only', n: d.information_only, icon: 'info', k: 'neutral', sub: `${pct(d.information_only)}% of total` },
  ];

  return (
    <>
      <section className="dash-hero">
        <div>
          <span className="eyebrow">{today}</span>
          <h1>{greeting()}, {String(u.name || '').split(' ')[0] || 'Engineer'}</h1>
          <p>Track inspection requests from submission to final decision. Technical reviews, approvals, attachments and daily site progress are all in one place.</p>
          <div className="toolbar">
            <Link className="btn lg" to="/summaries"><Icon name="plus" />New RFI Summary</Link>
            <Link className="btn secondary lg" to="/daily-progress"><Icon name="progress" />Daily Progress</Link>
          </div>
        </div>
        <div className="hero-kpis">
          <Link to="/rfis" className="hero-kpi"><div className="n">{d.under_review ?? 0}</div><div className="l">Under technical review</div></Link>
          <Link to="/rfis" className="hero-kpi amber"><div className="n">{d.awaiting_decision ?? 0}</div><div className="l">Awaiting RE/ARE decision</div></Link>
          <div className="hero-kpi wide"><span className="pulse" /><div><strong>System online</strong><div className="l" style={{ marginTop: 0 }}>API &amp; database connected · 24h overdue target</div></div></div>
        </div>
      </section>

      <div className="stats">
        {kpis.map(k => (
          <div className={`stat kpi k-${k.k}`} key={k.l}>
            <div className="row"><div className="ic"><Icon name={k.icon} size={20} /></div></div>
            <div><div className="n">{k.n ?? 0}</div><div className="l">{k.l}</div></div>
            <div className="pct">{k.sub}</div>
          </div>
        ))}
      </div>

      <div className="dash-cols">
        <div className="card" style={{ marginBottom: 0 }}>
          <div className="top" style={{ marginBottom: 14 }}>
            <div><h3 style={{ margin: 0 }}>Recent RFIs</h3><div className="muted" style={{ fontSize: 13 }}>Latest inspection requests across the project</div></div>
            <Link to="/rfis" className="btn secondary">Open register <Icon name="arrow" size={16} /></Link>
          </div>
          {d.recent?.length ? (
            <div className="table-wrap">
              <table>
                <thead><tr><th>RFI No.</th><th>Work item</th><th>Workflow</th><th>Decision</th></tr></thead>
                <tbody>
                  {d.recent.map((r: any) => (
                    <tr key={r.id}>
                      <td><Link className="link mono" to={`/rfis/${r.id}`}>{r.rfi_number}</Link></td>
                      <td>{pretty(r.work_item)}</td>
                      <td><Status value={r.workflow_status} /></td>
                      <td><Status value={r.decision} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : <div className="empty">No RFIs yet. Create your first Summary to get started.</div>}
        </div>

        <div>
          <div className="card">
            <h3 style={{ marginBottom: 2 }}>Decision mix</h3>
            <div className="muted" style={{ fontSize: 13 }}>{decided} decided RFIs by outcome</div>
            <div className="mix-bar" role="img" aria-label={MIX.map(m => `${m.label} ${d[m.key] ?? 0}`).join(', ')}>
              {decided > 0 && MIX.filter(m => Number(d[m.key]) > 0).map(m => (
                <span key={m.key} style={{ flex: Number(d[m.key]), background: m.color }} title={`${m.label}: ${d[m.key]} (${Math.round((d[m.key] / decided) * 100)}%)`} />
              ))}
            </div>
            <ul className="mix-legend">
              {MIX.map(m => (
                <li key={m.key}>
                  <span className="sw" style={{ background: m.color }} />{m.label}
                  <span className="v">{d[m.key] ?? 0}</span>
                  <span className="p">{decided ? Math.round(((d[m.key] || 0) / decided) * 100) : 0}%</span>
                </li>
              ))}
            </ul>
          </div>
          <div className="card" style={{ marginBottom: 0 }}>
            <h3>Approval workflow</h3>
            <ol className="flow">
              {STEPS.map(([t, s], i) => (
                <li key={t}><span className="no">{i + 1}</span><div><div className="t">{t}</div><div className="d">{s}</div></div></li>
              ))}
            </ol>
          </div>
        </div>
      </div>
    </>
  );
}
