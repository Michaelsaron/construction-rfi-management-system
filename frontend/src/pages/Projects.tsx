import React, { useEffect, useState } from 'react';
import { api, post, put, isAdmin, fmtDate } from '../lib/api';
import Status from '../components/Status';

const BLANK = { code: '', name: '', contract_number: '', employer: '', consultant: '', contractor: '', project_length: '' };

export default function Projects() {
  const [rows, setRows] = useState<any[]>([]); const [f, setF] = useState<any>(BLANK); const [sel, setSel] = useState<any>(null);
  const [members, setMembers] = useState<any[]>([]); const [users, setUsers] = useState<any[]>([]); const [roles, setRoles] = useState<any[]>([]);
  const [settings, setSettings] = useState<any>(null); const [add, setAdd] = useState({ user_id: '', role: '' }); const [msg, setMsg] = useState('');
  const load = () => api('/projects?include_archived=true').then(setRows);
  useEffect(() => { load(); api('/users').then(setUsers).catch(() => {}); api('/projects/meta/roles').then(setRoles).catch(() => {}); }, []);
  const open = (p: any) => { setSel(p); setF({ ...BLANK, ...p }); api(`/projects/${p.id}/members?include_revoked=true`).then(setMembers); api(`/projects/${p.id}/settings`).then(setSettings); };
  if (!isAdmin()) return <div className="notice err">Only the System Administrator can manage projects.</div>;
  async function save(e: any) {
    e.preventDefault();
    try { if (sel) { await put(`/projects/${sel.id}`, Object.fromEntries(Object.entries(f).filter(([k]) => k in BLANK && k !== 'code'))); setMsg('Project updated.'); } else { const p: any = await post('/projects', f); setMsg(`Project ${p.code} created.`); setF(BLANK); } load(); }
    catch (e: any) { alert(e.message); }
  }
  async function toggleArchive(p: any) { if (!confirm(p.status === 'ARCHIVED' ? 'Re-activate this project?' : 'Archive this project? It becomes read-only; nothing is deleted.')) return; try { await post(`/projects/${p.id}/${p.status === 'ARCHIVED' ? 'activate' : 'archive'}`); load(); } catch (e: any) { alert(e.message); } }
  async function addMember() { if (!add.user_id || !add.role) { alert('Choose a user and a project role.'); return; } try { await post(`/projects/${sel.id}/members`, { user_id: +add.user_id, role: add.role }); setAdd({ user_id: '', role: '' }); open(sel); } catch (e: any) { alert(e.message); } }
  async function revoke(m: any) { if (!confirm(`Revoke ${m.full_name}'s access to this project? Their past actions are kept.`)) return; try { await api(`/projects/${sel.id}/members/${m.user_id}`, { method: 'DELETE' }); open(sel); } catch (e: any) { alert(e.message); } }
  async function saveSettings() {
    try { const body = { notice_policy: settings.notice_policy, notice_hours: +settings.notice_hours, contractor_visibility: settings.contractor_visibility, inspector_register_access: !!settings.inspector_register_access, inspector_export: !!settings.inspector_export, overdue_hours: +settings.overdue_hours, dispositions: JSON.parse(settings._dispositions ?? JSON.stringify(settings.dispositions)) };
      setSettings(await put(`/projects/${sel.id}/settings`, body)); setMsg('Settings saved.'); } catch (e: any) { alert(e.message); }
  }
  const field = (k: string, l: string, req = false) => <div><label>{l}</label><input required={req} disabled={k === 'code' && !!sel} value={f[k] || ''} onChange={e => setF({ ...f, [k]: e.target.value })} /></div>;
  return <>
    <h1 className="page-title">Projects &amp; Members</h1><p className="subtitle">Each project keeps its own RFIs, DOC_01/02/03 records, members, notifications and audit trail.</p>
    {msg && <div className="notice ok">{msg}</div>}
    <form className="card" onSubmit={save}><div className="section-title"><h3>{sel ? `Edit ${sel.code}` : 'New project'}</h3>{sel && <button type="button" className="btn secondary sm" onClick={() => { setSel(null); setF(BLANK); setMembers([]); setSettings(null); }}>New project instead</button>}</div>
      <div className="grid">{field('code', 'Code', true)}{field('name', 'Project / contract title', true)}{field('contract_number', 'Contract number')}{field('project_length', 'Project length')}{field('employer', 'Employer')}{field('consultant', 'Consultant / Engineer')}{field('contractor', 'Contractor')}</div>
      <div style={{ marginTop: 12 }}><button className="btn">{sel ? 'Save project' : 'Create project'}</button></div></form>
    <div className="card"><h3>Projects</h3><div className="table-wrap"><table><thead><tr><th>Code</th><th>Name</th><th>Status</th><th></th></tr></thead>
      <tbody>{rows.map(p => <tr key={p.id}><td className="mono">{p.code}</td><td>{p.name}</td><td><Status value={p.status === 'ARCHIVED' ? 'ARCHIVED' : 'ACTIVE'} label={p.status} /></td>
        <td style={{ whiteSpace: 'nowrap' }}><button className="btn sm" onClick={() => open(p)}>Manage</button> <button className="btn secondary sm" onClick={() => toggleArchive(p)}>{p.status === 'ARCHIVED' ? 'Activate' : 'Archive'}</button></td></tr>)}</tbody></table></div></div>
    {sel && <div className="card"><h3>Members of {sel.code}</h3>
      <div className="toolbar"><select value={add.user_id} onChange={e => setAdd({ ...add, user_id: e.target.value })}><option value="">User…</option>{users.filter(u => u.role !== 'ADMIN').map(u => <option key={u.id} value={u.id}>{u.full_name} ({u.email})</option>)}</select>
        <select value={add.role} onChange={e => setAdd({ ...add, role: e.target.value })}><option value="">Project role…</option>{roles.map(g => <optgroup key={g.category} label={`${g.category} ${g.label}`}>{g.roles.map((r: any) => <option key={r.code} value={r.code}>{r.label}</option>)}</optgroup>)}</select>
        <button className="btn" onClick={addMember}>Add / change role</button></div>
      <p className="muted" style={{ fontSize: 13 }}>The deputy role is DRE (Deputy Resident Engineer, Category 2.1). Accounts created with the former ARE code are shown and treated as DRE.</p>
      <div className="table-wrap"><table><thead><tr><th>Name</th><th>E-mail</th><th>Role</th><th>Category</th><th>Status</th><th></th></tr></thead>
        <tbody>{members.map(m => <tr key={m.membership_id}><td>{m.full_name}</td><td>{m.email}</td><td>{m.role_label}{m.legacy_role && <span className="muted"> (from legacy global role)</span>}</td><td>{m.category}</td>
          <td><Status value={m.status === 'ACTIVE' ? 'ACTIVE' : 'CANCELLED'} label={m.status === 'ACTIVE' ? 'Active' : `Revoked ${fmtDate(m.revoked_at)}`} /></td>
          <td>{m.status === 'ACTIVE' && <button className="btn secondary sm" onClick={() => revoke(m)}>Revoke</button>}</td></tr>)}</tbody></table></div></div>}
    {sel && settings && <div className="card"><h3>Project settings (pending client decisions)</h3><div className="grid">
      <div><label>24-hour rule (OD-11)</label><select value={settings.notice_policy} onChange={e => setSettings({ ...settings, notice_policy: e.target.value })}><option value="FLAG">Flag short notice only</option><option value="REQUIRE_OVERRIDE">Require a reason</option></select></div>
      <div><label>Notice hours</label><input type="number" value={settings.notice_hours} onChange={e => setSettings({ ...settings, notice_hours: e.target.value })} /></div>
      <div><label>Contractor visibility (OD-03)</label><select value={settings.contractor_visibility} onChange={e => setSettings({ ...settings, contractor_visibility: e.target.value })}><option value="PROJECT">All project RFIs</option><option value="OWN">Own submissions only</option></select></div>
      <div><label>Inspectors may read register (OD-04)</label><select value={String(settings.inspector_register_access)} onChange={e => setSettings({ ...settings, inspector_register_access: e.target.value === 'true' })}><option value="true">Yes (read-only)</option><option value="false">No – assigned RFIs only</option></select></div>
      <div><label>Inspectors may export</label><select value={String(settings.inspector_export)} onChange={e => setSettings({ ...settings, inspector_export: e.target.value === 'true' })}><option value="false">No</option><option value="true">Yes</option></select></div>
      <div><label>Overdue after (hours)</label><input type="number" value={settings.overdue_hours} onChange={e => setSettings({ ...settings, overdue_hours: e.target.value })} /></div>
    </div>
      <div style={{ marginTop: 12 }}><label>DOC_03 disposition options (OD-06, JSON – subject to client approval)</label><textarea rows={8} className="mono" style={{ fontSize: 12 }} value={settings._dispositions ?? JSON.stringify(settings.dispositions, null, 2)} onChange={e => setSettings({ ...settings, _dispositions: e.target.value })} /></div>
      <div style={{ marginTop: 12 }}><button className="btn" onClick={saveSettings}>Save settings</button></div></div>}
  </>;
}
