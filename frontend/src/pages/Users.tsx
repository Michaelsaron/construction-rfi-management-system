import React, { useEffect, useState } from 'react';
import { api, fmtDate, getUser, isAdmin } from '../lib/api';
import Status, { pretty } from '../components/Status';

const ROLES = ['ADMIN', 'RE', 'ARE', 'RE_ARE', 'CONTRACTOR', 'SITE_ENGINEER', 'WORK_INSPECTOR', 'STRUCTURE_INSPECTOR', 'SURVEYOR', 'SENIOR_SURVEYOR', 'MATERIAL_INSPECTOR', 'LAB_TECHNICIAN', 'MATERIAL_ENGINEER', 'PROJECT_MANAGER', 'VIEWER'];
const blank = { full_name: '', email: '', password: '', role: 'CONTRACTOR', project_ids: [] as number[] };

function ProjectPicker({ projects, value, onChange }: { projects: any[]; value: number[]; onChange: (v: number[]) => void }) {
  return <div className="chips">{projects.map(p => <label key={p.id} className="badge" style={{ cursor: 'pointer', margin: 0, color: 'var(--text)', fontWeight: 600, background: value.includes(p.id) ? 'var(--amber-soft)' : undefined, borderColor: value.includes(p.id) ? 'var(--amber)' : undefined }}>
    <input type="checkbox" checked={value.includes(p.id)} onChange={e => onChange(e.target.checked ? [...value, p.id] : value.filter(x => x !== p.id))} /> {p.code}
  </label>)}</div>;
}

export default function Users() {
  const [rows, setRows] = useState<any[]>([]); const [projects, setProjects] = useState<any[]>([]);
  const [f, setF] = useState({ ...blank }); const [msg, setMsg] = useState(''); const [editing, setEditing] = useState<any>(null); const [q, setQ] = useState('');
  const admin = isAdmin(); const me = getUser();
  const load = () => api('/users').then(setRows).catch(e => setMsg(e.message));
  useEffect(() => { load(); api('/projects').then(setProjects); }, []);
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
  async function saveProjects() {
    try { await api(`/users/${editing.id}/projects`, { method: 'PUT', body: JSON.stringify({ project_ids: editing.project_ids }) }); setEditing(null); setMsg('Project access updated.'); load(); }
    catch (e: any) { alert(e.message); }
  }
  const code = (id: number) => projects.find(p => p.id === id)?.code || `#${id}`;
  const shown = rows.filter(u => !q || `${u.full_name} ${u.email} ${u.role}`.toLowerCase().includes(q.toLowerCase()));
  return <>
    <h1>Users &amp; Roles</h1>
    <p className="subtitle">Accounts are created by the administrator. There is no public signup. Users need project access to work with Daily Progress.</p>
    {msg && <div className="notice ok">{msg}</div>}
    {admin ? <form className="card" onSubmit={create}>
      <h3>Add user</h3>
      <div className="grid">
        <div><label>Full name</label><input required value={f.full_name} onChange={e => setF({ ...f, full_name: e.target.value })} /></div>
        <div><label>Email</label><input required type="email" value={f.email} onChange={e => setF({ ...f, email: e.target.value })} /></div>
        <div><label>Temporary password (min. 10)</label><input required minLength={10} value={f.password} onChange={e => setF({ ...f, password: e.target.value })} /></div>
        <div><label>Role</label><select value={f.role} onChange={e => setF({ ...f, role: e.target.value })}>{ROLES.map(x => <option key={x} value={x}>{pretty(x)}</option>)}</select></div>
      </div>
      <div style={{ marginTop: 12 }}><label>Project access</label><ProjectPicker projects={projects} value={f.project_ids} onChange={v => setF({ ...f, project_ids: v })} /></div>
      <button className="btn" style={{ marginTop: 14 }}>Add user</button>
    </form> : <div className="notice">Only the administrator can add or change users.</div>}
    <div className="card">
      <div className="section-title"><h3>{rows.length} users</h3><input style={{ maxWidth: 280 }} placeholder="Search name, email, role…" value={q} onChange={e => setQ(e.target.value)} /></div>
      <div className="table-wrap"><table>
        <thead><tr><th>Name</th><th>Email</th><th>Role</th><th>Projects</th><th>Status</th><th>Last sign-in</th>{admin && <th>Actions</th>}</tr></thead>
        <tbody>{shown.map(u => <tr key={u.id}>
          <td><b>{u.full_name}</b>{u.must_change_password && <div className="muted" style={{ fontSize: 12 }}>Temporary password</div>}</td>
          <td>{u.email}</td><td>{pretty(u.role)}</td>
          <td>{u.role === 'ADMIN' ? <span className="muted">All</span> : (u.project_ids || []).length ? u.project_ids.map(code).join(', ') : <span style={{ color: 'var(--danger)', fontWeight: 600 }}>None</span>}</td>
          <td><Status value={u.is_active ? 'ACTIVE' : 'CANCELLED'} /></td><td>{u.last_login_at ? fmtDate(u.last_login_at) : '—'}</td>
          {admin && <td><div className="toolbar" style={{ flexWrap: 'nowrap' }}>
            <button className="btn secondary sm" onClick={() => setEditing({ id: u.id, name: u.full_name, project_ids: [...(u.project_ids || [])] })}>Projects</button>
            <button className="btn secondary sm" onClick={() => reset(u)}>Reset password</button>
            {u.id !== me.id && <button className={`btn sm ${u.is_active ? 'danger' : 'success'}`} onClick={() => toggle(u)}>{u.is_active ? 'Disable' : 'Enable'}</button>}
          </div></td>}
        </tr>)}</tbody>
      </table></div>
    </div>
    {editing && <div className="modal-bg" onClick={e => { if (e.target === e.currentTarget) setEditing(null); }}>
      <div className="modal" style={{ width: 'min(520px,100%)' }}>
        <h3>Project access: {editing.name}</h3>
        <ProjectPicker projects={projects} value={editing.project_ids} onChange={v => setEditing({ ...editing, project_ids: v })} />
        <div className="toolbar" style={{ marginTop: 18 }}><button className="btn" onClick={saveProjects}>Save</button><button className="btn secondary" onClick={() => setEditing(null)}>Cancel</button></div>
      </div>
    </div>}
  </>;
}
