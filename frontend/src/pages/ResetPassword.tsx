import React, { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { api } from '../lib/api';
import { BrandMark } from '../components/Brand';

export default function ResetPassword() {
  const [sp] = useSearchParams();
  const [tok, setTok] = useState(sp.get('token') || '');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [msg, setMsg] = useState('');
  const [done, setDone] = useState(false);
  async function go(e: any) {
    e.preventDefault(); setMsg('');
    if (password !== confirm) { setMsg('The two passwords do not match.'); return; }
    try { await api('/auth/reset-password', { method: 'POST', body: JSON.stringify({ token: tok, new_password: password }) }); setDone(true); }
    catch (e: any) { setMsg(e.message); }
  }
  return (
    <div className="auth-center">
      <form className="login-card" onSubmit={go}>
        <BrandMark size={44} />
        <h1>Reset password</h1>
        {done ? <>
          <div className="notice">Your password has been changed.</div>
          <Link to="/login" className="btn lg" style={{ width: '100%' }}>Go to sign in</Link>
        </> : <>
          <p className="muted">Choose a new password with at least 10 characters.</p>
          {!sp.get('token') && <div className="field"><label htmlFor="tk">Reset token</label><input id="tk" required value={tok} onChange={e => setTok(e.target.value)} /></div>}
          <div className="field"><label htmlFor="np">New password</label><input id="np" type="password" autoComplete="new-password" minLength={10} required value={password} onChange={e => setPassword(e.target.value)} /></div>
          <div className="field"><label htmlFor="cp">Confirm new password</label><input id="cp" type="password" autoComplete="new-password" minLength={10} required value={confirm} onChange={e => setConfirm(e.target.value)} /></div>
          {msg && <div className="notice">{msg}</div>}
          <button className="btn lg">Set new password</button>
          <div className="row-between" style={{ marginTop: 16 }}><Link className="link" to="/login">← Back to sign in</Link></div>
        </>}
      </form>
    </div>
  );
}
