import React, { useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { useProject } from '../lib/project';

/** Page title with the project / contract context line used on every screen of the design. */
export function PageHeader({ title, back, actions, children }: { title: React.ReactNode; back?: { to: string; label: string }; actions?: React.ReactNode; children?: React.ReactNode }) {
  const { project } = useProject();
  return <div className="page-head">
    <div style={{ minWidth: 0 }}>
      {back && <Link className="back link" to={back.to}>← {back.label}</Link>}
      <h1>{title}</h1>
      {project && <div className="ctx">{project.name}{project.contract_number && <><span className="sep">|</span>{project.contract_number}</>}</div>}
      {children}
    </div>
    {actions && <div className="actions" style={{ marginTop: 0 }}>{actions}</div>}
  </div>;
}

export function KpiCard({ label, value, caption, tone = 'blue', to }: { label: string; value: React.ReactNode; caption?: string; tone?: 'blue' | 'green' | 'amber' | 'red' | 'grey'; to?: string }) {
  const na = value === null || value === undefined;
  const body = <><div className="l">{label}</div><div className={`n${na ? ' na' : ''}`}>{na ? 'Not enabled' : typeof value === 'number' ? String(value).padStart(2, '0') : value}</div>{caption && <div className="c">{caption}</div>}</>;
  return to ? <Link className={`kpi-card t-${tone}`} to={to}>{body}</Link> : <div className={`kpi-card t-${tone}`}>{body}</div>;
}

export type ConfirmRow = [string, React.ReactNode];

/** Confirmation before a final, locking action (UI design s.16.1). Not used for ordinary draft saving. */
export function ConfirmDialog({ open, title, intro, rows, warnings, confirmLabel, busy, tone = 'success', onConfirm, onCancel, children }: {
  open: boolean; title: string; intro?: React.ReactNode; rows: ConfirmRow[]; warnings?: React.ReactNode[]; confirmLabel: string; busy?: boolean;
  tone?: 'success' | 'danger' | 'primary'; onConfirm: () => void; onCancel: () => void; children?: React.ReactNode;
}) {
  const ok = useRef<HTMLButtonElement>(null);
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const prev = document.activeElement as HTMLElement | null;
    setTimeout(() => ok.current?.focus(), 0);
    const key = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !busy) onCancel();
      if (e.key === 'Tab' && box.current) {
        const f = Array.from(box.current.querySelectorAll<HTMLElement>('button,input,textarea,select,a[href]')).filter(x => !x.hasAttribute('disabled'));
        if (!f.length) return;
        if (e.shiftKey && document.activeElement === f[0]) { e.preventDefault(); f[f.length - 1].focus(); }
        else if (!e.shiftKey && document.activeElement === f[f.length - 1]) { e.preventDefault(); f[0].focus(); }
      }
    };
    document.addEventListener('keydown', key);
    return () => { document.removeEventListener('keydown', key); prev?.focus?.(); };
  }, [open, busy]);
  if (!open) return null;
  return <div className="modal-bg" onMouseDown={e => { if (e.target === e.currentTarget && !busy) onCancel(); }}>
    <div className="modal" role="dialog" aria-modal="true" aria-labelledby="confirm-title" ref={box}>
      <h2 id="confirm-title">{title}</h2>
      {intro && <p className="muted" style={{ margin: 0 }}>{intro}</p>}
      <dl className="confirm-rows">{rows.map(([k, v], i) => <React.Fragment key={i}><dt>{k}</dt><dd>{v === '' || v === null || v === undefined ? '—' : v}</dd></React.Fragment>)}</dl>
      {warnings?.filter(Boolean).map((w, i) => <div key={i} className="notice">{w}</div>)}
      {children}
      <div className="actions end">
        <button type="button" className="btn secondary" onClick={onCancel} disabled={busy}>Go back</button>
        <button type="button" ref={ok} className={`btn ${tone === 'danger' ? 'danger' : tone === 'primary' ? '' : 'success'}`} onClick={onConfirm} disabled={busy}>{busy ? 'Recording…' : confirmLabel}</button>
      </div>
    </div>
  </div>;
}

export const Field = ({ label, children, required, htmlFor }: { label: string; children: React.ReactNode; required?: boolean; htmlFor?: string }) =>
  <div><label htmlFor={htmlFor} className={required ? 'req' : undefined}>{label}</label>{children}</div>;

export const ReadOnly = ({ label, value }: { label: string; value: React.ReactNode }) =>
  <div><label>{label}</label><div className="ro-field">{value === '' || value === null || value === undefined ? '—' : value}</div></div>;

export function Loading({ text = 'Loading…' }: { text?: string }) { return <div className="empty" role="status">{text}</div>; }
export function ErrorNote({ error }: { error: string }) { return error ? <div className="notice err" role="alert">{error}</div> : null; }
