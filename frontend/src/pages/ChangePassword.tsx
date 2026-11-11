import React, { useState } from 'react';
import { api, getUser, setUser } from '../lib/api';

export default function ChangePassword() {
  const forced = !!getUser().must_change_password;
  const [f, setF] = useState({ current: '', next: '', confirm: '' });
  const [msg, setMsg] = useState(''); const [ok, setOk] = useState(false); const [busy, setBusy] = useState(false);
  async function go(e: any) {
    e.preventDefault(); setMsg(''); setOk(false);
    if (f.next !== f.confirm) { setMsg('The new passwords do not match.'); return; }
    setBusy(true);
    try {
      await api('/me/password', { method: 'POST', body: JSON.stringify({ current_password: f.current, new_password: f.next }) });
      setUser(await api('/me')); setOk(true); setF({ current: '', next: '', confirm: '' });
      if (forced) setTimeout(() => { location.href = '/'; }, 900);
    } catch (e: any) { setMsg(e.message); } finally { setBusy(false); }
  }
  return <>
    <h1>Change password</h1>
    <p className="subtitle">{forced ? 'Your account is using a temporary password. Set your own password to continue.' : 'Use at least 10 characters. You will stay signed in.'}</p>
    <form className="card" onSubmit={go} style={{ maxWidth: 520 }}>
      <div className="field"><label htmlFor="cur">Current password</label><input id="cur" type="password" autoComplete="current-password" required value={f.current} onChange={e => setF({ ...f, current: e.target.value })} /></div>
      <div className="field" style={{ marginTop: 12 }}><label htmlFor="nw">New password</label><input id="nw" type="password" autoComplete="new-password" minLength={10} required value={f.next} onChange={e => setF({ ...f, next: e.target.value })} /></div>
      <div className="field" style={{ marginTop: 12 }}><label htmlFor="cf">Confirm new password</label><input id="cf" type="password" autoComplete="new-password" minLength={10} required value={f.confirm} onChange={e => setF({ ...f, confirm: e.target.value })} /></div>
      {msg && <div className="notice">{msg}</div>}
      {ok && <div className="notice ok">Password changed successfully.</div>}
      <div style={{ marginTop: 16 }}><button className="btn" disabled={busy}>{busy ? 'Saving…' : 'Change password'}</button></div>
    </form>
  </>;
}
