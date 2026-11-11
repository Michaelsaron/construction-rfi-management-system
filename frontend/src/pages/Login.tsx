import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { api, setToken, setUser } from '../lib/api';
import { BrandMark, SiteScene } from '../components/Brand';
import Icon from '../components/Icon';

export default function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [msg, setMsg] = useState('');
  const [busy, setBusy] = useState(false);

  async function go(e: any) {
    e.preventDefault(); setBusy(true); setMsg('');
    try {
      const r = await api('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) });
      setToken(r.access_token);
      const me = await api('/me');
      setUser(me);
      location.href = me.must_change_password ? '/change-password' : '/';
    } catch (e: any) { setMsg(e.message || 'Invalid email or password'); setBusy(false); }
  }
  async function forgot() {
    if (!email) { setMsg('Enter your email first.'); return; }
    try { const r = await api('/auth/forgot-password', { method: 'POST', body: JSON.stringify({ email }) }); setMsg(r.message); }
    catch (e: any) { setMsg(e.message); }
  }

  return (
    <div className="login">
      <section className="login-art">
        <Link to="/home" className="brand" style={{ color: '#fff' }}>
          <BrandMark /><span><span className="bt">Construction RFI</span><span className="bs">Site Control System</span></span>
        </Link>
        <div>
          <SiteScene className="scene" />
          <h2>Every inspection, signed off and on record.</h2>
          <p>Request for Inspection workflows, technical reviews, RE/ARE decisions and daily site progress in one place.</p>
        </div>
        <div style={{ fontSize: 13, color: '#8fa0b3' }}>© {new Date().getFullYear()} Construction RFI Management System</div>
      </section>
      <section className="login-side">
        <form className="login-card" onSubmit={go}>
          <BrandMark size={44} />
          <h1>Sign in</h1>
          <p className="muted">Welcome back. Use your project account to continue.</p>
          <div className="field"><label htmlFor="em">Email address</label><input id="em" type="email" autoComplete="username" required placeholder="you@company.com" value={email} onChange={e => setEmail(e.target.value)} /></div>
          <div className="field"><label htmlFor="pw">Password</label><input id="pw" type="password" autoComplete="current-password" required placeholder="••••••••" value={password} onChange={e => setPassword(e.target.value)} /></div>
          <div className="row-between">
            <Link to="/home" className="link">← Back to home</Link>
            <button type="button" className="linkButton" onClick={forgot}>Forgot password?</button>
          </div>
          {msg && <div className="notice">{msg}</div>}
          <button className="btn lg" disabled={busy}>{busy ? 'Signing in…' : <>Sign in <Icon name="arrow" size={17} /></>}</button>
          <div className="foot"><Icon name="lock" size={15} /><span>No public signup. Accounts are created by the project administrator.</span></div>
        </form>
      </section>
    </div>
  );
}
