import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, fmtDate, isManager } from '../lib/api';

const LINK: Record<string, string> = { RFI: '/rfis/', RFI_SUMMARY: '/summaries/', DAILY_PROGRESS: '/daily-progress' };
export default function Notifications() {
  const [rows, setRows] = useState<any[] | null>(null); const [msg, setMsg] = useState('');
  const load = () => api('/notifications').then(setRows).catch(e => { setRows([]); setMsg(e.message); });
  useEffect(() => { load(); }, []);
  const changed = () => window.dispatchEvent(new Event('notifications-changed'));
  async function mark(id: number) { try { await api(`/notifications/${id}/read`, { method: 'POST' }); load(); changed(); } catch (e: any) { alert(e.message); } }
  async function markAll() { try { await api('/notifications/read-all', { method: 'POST' }); load(); changed(); } catch (e: any) { alert(e.message); } }
  async function overdue() { try { const r: any = await api('/notifications/check-overdue', { method: 'POST' }); setMsg(`Overdue check complete: ${r.created} new reminder(s) sent to reviewers.`); } catch (e: any) { alert(e.message); } }
  const href = (n: any) => n.entity_type && LINK[n.entity_type] ? LINK[n.entity_type] + (n.entity_type === 'DAILY_PROGRESS' ? '' : n.entity_id) : null;
  const unread = (rows || []).filter(n => !n.is_read).length;
  return <>
    <div className="top">
      <div><h1>Notifications</h1><p className="subtitle">Assignments, submissions, decisions and overdue alerts.</p></div>
      <div className="toolbar">
        {isManager() && <button className="btn secondary" onClick={overdue}>Check overdue inspections</button>}
        {unread > 0 && <button className="btn" onClick={markAll}>Mark all as read ({unread})</button>}
      </div>
    </div>
    {msg && <div className="notice ok">{msg}</div>}
    <div className="card">{!rows ? <div className="empty">Loading…</div> : rows.length ? rows.map(n => <div className={`noti${n.is_read ? ' read' : ''}`} key={n.id}>
      <span className="dot" />
      <div style={{ flex: 1, minWidth: 0 }}>
        <strong>{n.title}</strong>
        <div>{String(n.message).replace(/\s*OVERDUE:\d+/, '')}</div>
        <small className="muted">{fmtDate(n.created_at)}{href(n) && <> · <Link className="link" to={href(n)!} onClick={() => !n.is_read && mark(n.id)}>Open</Link></>}</small>
      </div>
      {!n.is_read && <button className="btn secondary sm" onClick={() => mark(n.id)}>Mark read</button>}
    </div>) : <div className="empty">You're all caught up. No notifications.</div>}</div>
  </>;
}
