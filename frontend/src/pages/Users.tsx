import React, { useEffect, useState } from 'react';
import { api, fmtDate, getUser, isAdmin, roleLabel } from '../lib/api';
import Status, { pretty } from '../components/Status';

const blank = { full_name: '', email: '', password: '', role: 'VIEWER', memberships: [] as { project_id: number; role: string }[] };

export default function Users() {
  const [rows, setRows] = useState<any[]>([]); const [projects, setProjects] = useState<any[]>([]);
  const [f, setF] = useState<any>({ ...blank }); const [roles, setRoles] = useState<any[]>([]); const [m, setM] = useState({ project_id: '', role: '' }); const [msg, setMsg] = useState(''); const [q, setQ] = useState('');
  const admin = isAdmin(); const me = getUser();
  const load = () => api('/users').then(setRows).catch(e => setMsg(e.message));
  useEffect(() => { load(); api('/projects?include_archived=true').then(setProjects); api('/projects/meta/roles').then(setRoles).catch(() => {}); }, []);
  async function create(e: any) {
    e.preventDefault();
    try { await api('/users', { method: 'POST', body: JSON.stringify(f) }); setMsg(`User ${f.email} created. Share the temporary password with them; they must change it on first sign-in.`); setF({ ...blank }); load(); }
    catch (e: any) { alert(e.message); }
  }
  async function reset(u: any) {
    const p = prompt(`New temporary password for ${u.email} (min. 10 characters):`); if (!p) return;
    try { await api(`/users/${u.id}/reset-password`, { method: 'POST', body: JSON.stringify({ new_password: p }) }); setMsg(`Temporary password set for ${u.email}. They must change it at next sign-in.`); }
    catch (e: any) { alert(e.message); }
  }
  async function toggle(u: any) {
    if (!confirm(`${u.is_active ? 'Disable' : 'Enable'} ${u.email}?`)) return;
    try { await api(`/users/${u.id}/toggle-active`, { method: 'POST' }); load(); } catch (e: any) { alert(e.message); }
  }
  const code = (id: number) => projects.find(p => p.id === id)?.code || `#${id}`;
  const shown = rows.filter(u => !q || `${u.full_name} ${u.email} ${u.role}`.toLowerCase().includes(q.toLowerCase()));
  return <>
    <h1>Users &amp; Roles</h1>
    <p className="subtitle">Accounts are created by the administrator. There is no public signup. Roles are assigned per project on the Projects &amp; Members page; a user can hold different roles on different projects.</p>
    {msg && <div className="notice ok">{msg}</div>}
    {admin ? <form className="card" onSubmit={create}>
      <h3>Add user</h3>
      <div className="grid">
        <div><label>Full name</label><input required value={f.full_name} onChange={e => setF({ ...f, full_name: e.target.value })} /></div>
        <div><label>Email</label><input required type="email" value={f.email} onChange={e => setF({ ...f, email: e.target.value })} /></div>
        <div><label>Temporary password (min. 10)</label><input required minLength={10} value={f.password} onChange={e => setF({ ...f, password: e.target.value })} /></div>
        <div><label>Account type</label><select value={f.role} onChange={e => setF({ ...f, role: e.target.value, memberships: e.target.value === 'ADMIN' ? [] : f.memberships })}><option value="VIEWER">Project user (role set per project)</option><option value="ADMIN">System Administrator (Category 1)</option></select></div>
      </div>
      {f.role !== 'ADMIN' && <div style={{ marginTop: 12 }}><label>Project memberships and roles</label>
        <div className="toolbar"><select value={m.project_id} onChange={e => setM({ ...m, project_id: e.target.value })}><option value="">Project…</option>{projects.map(p => <option key={p.id} value={p.id}>{p.code}</option>)}</select>
          <select value={m.role} onChange={e => setM({ ...m, role: e.target.value })}><option value="">Role…</option>{roles.map(g => <optgroup key={g.category} label={`${g.category} ${g.label}`}>{g.roles.map((r: any) => <option key={r.code} value={r.code}>{r.label}</option>)}</optgroup>)}</select>
          <button type="button" className="btn secondary" onClick={() => { if (!m.project_id || !m.role) return; setF({ ...f, memberships: [...f.memberships.filter((x: any) => x.project_id !== +m.project_id), { project_id: +m.project_id, role: m.role }] }); setM({ project_id: '', role: '' }); }}>Add</button></div>
        <div className="chips">{f.memberships.map((x: any) => <span key={x.project_id} className="badge">{code(x.project_id)}: {roleLabel(x.role)} <button type="button" className="linkButton" onClick={() => setF({ ...f, memberships: f.memberships.filter((y: any) => y.project_id !== x.project_id) })}>×</button></span>)}</div>
      </div>}
      <button className="btn" style={{ marginTop: 14 }}>Add user</button>
    </form> : <div className="notice">Only the administrator can add or change users.</div>}
    <div className="card">
      <div className="section-title"><h3>{rows.length} users</h3><input style={{ maxWidth: 280 }} placeholder="Search name, email, role…" value={q} onChange={e => setQ(e.target.value)} /></div>
      <div className="table-wrap"><table>
        <thead><tr><th>Name</th><th>Email</th><th>Role</th><th>Projects</th><th>Status</th><th>Last sign-in</th>{admin && <th>Actions</th>}</tr></thead>
        <tbody>{shown.map(u => <tr key={u.id}>
          <td><b>{u.full_name}</b>{u.must_change_password && <div className="muted" style={{ fontSize: 12 }}>Temporary password</div>}</td>
          <td>{u.email}</td><td>{u.role === 'ADMIN' ? 'System Administrator' : <span className="muted">per project</span>}</td>
          <td>{u.role === 'ADMIN' ? <span className="muted">All (administration)</span> : (u.memberships || []).filter((x: any) => x.status === 'ACTIVE').length ? u.memberships.filter((x: any) => x.status === 'ACTIVE').map((x: any) => `${x.project_code}: ${roleLabel(x.role)}`).join(', ') : <span style={{ color: 'var(--danger)', fontWeight: 600 }}>None</span>}</td>
          <td><Status value={u.is_active ? 'ACTIVE' : 'CANCELLED'} /></td><td>{u.last_login_at ? fmtDate(u.last_login_at) : '—'}</td>
          {admin && <td><div className="toolbar" style={{ flexWrap: 'nowrap' }}>
            <button className="btn secondary sm" onClick={() => reset(u)}>Reset password</button>
            {u.id !== me.id && <button className={`btn sm ${u.is_active ? 'danger' : 'success'}`} onClick={() => toggle(u)}>{u.is_active ? 'Disable' : 'Enable'}</button>}
          </div></td>}
        </tr>)}</tbody>
      </table></div>
    </div>
  </>;
}
