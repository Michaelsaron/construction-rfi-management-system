import React, { useEffect, useState } from 'react';
import { api } from '../lib/api';
import { pretty } from '../components/Status';

const ROLES = ['WORK_INSPECTOR', 'STRUCTURE_INSPECTOR', 'SURVEYOR', 'SENIOR_SURVEYOR', 'MATERIAL_INSPECTOR', 'LAB_TECHNICIAN', 'MATERIAL_ENGINEER'];
export default function ReviewerRules() {
  const [rows, setRows] = useState<any[]>([]); const [projects, setProjects] = useState<any[]>([]); const [items, setItems] = useState<string[]>([]);
  const [f, setF] = useState<any>({ project_id: 0, work_item: '', reviewer_role: 'WORK_INSPECTOR', required: true }); const [msg, setMsg] = useState('');
  const load = (pid = f.project_id) => pid && api(`/reviewer-rules?project_id=${pid}`).then(setRows).catch(e => setMsg(e.message));
  useEffect(() => { api('/projects').then((p: any[]) => { setProjects(p); if (p[0]) setF((x: any) => ({ ...x, project_id: p[0].id })); }); }, []);
  useEffect(() => {
    if (!f.project_id) return; load(f.project_id);
    api(`/master-data?category=WORK_ITEM&project_id=${f.project_id}`).then((m: any[]) => setItems([...new Set(m.map(x => x.value))])).catch(() => setItems([]));
  }, [f.project_id]);
  async function create(e: any) {
    e.preventDefault();
    try { await api('/reviewer-rules', { method: 'POST', body: JSON.stringify(f) }); setMsg('Rule added.'); setF({ ...f, work_item: '' }); load(); } catch (e: any) { alert(e.message); }
  }
  async function del(r: any) {
    if (!confirm(`Delete rule "${r.work_item} → ${pretty(r.reviewer_role)}"?`)) return;
    try { await api(`/reviewer-rules/${r.id}`, { method: 'DELETE' }); load(); } catch (e: any) { alert(e.message); }
  }
  return <>
    <h1>Reviewer Rules</h1>
    <p className="subtitle">Choose which reviewer roles are suggested for each work item. RE/ARE see these suggestions when assigning reviewers to an RFI.</p>
    {msg && <div className="notice ok">{msg}</div>}
    <form className="card" onSubmit={create}>
      <div className="grid">
        <div><label>Project</label><select value={f.project_id} onChange={e => setF({ ...f, project_id: +e.target.value, work_item: '' })}>{projects.map(p => <option key={p.id} value={p.id}>{p.code} — {p.name}</option>)}</select></div>
        <div><label>Work item</label>{items.length ? <select required value={f.work_item} onChange={e => setF({ ...f, work_item: e.target.value })}><option value="">Select…</option>{items.map(x => <option key={x} value={x}>{pretty(x)}</option>)}</select> : <input required value={f.work_item} onChange={e => setF({ ...f, work_item: e.target.value })} />}</div>
        <div><label>Reviewer role</label><select value={f.reviewer_role} onChange={e => setF({ ...f, reviewer_role: e.target.value })}>{ROLES.map(x => <option key={x} value={x}>{pretty(x)}</option>)}</select></div>
        <div><label>Required?</label><select value={String(f.required)} onChange={e => setF({ ...f, required: e.target.value === 'true' })}><option value="true">Required</option><option value="false">Advisory</option></select></div>
      </div>
      <button className="btn" style={{ marginTop: 14 }}>Add rule</button>
    </form>
    <div className="card">{rows.length ? <div className="table-wrap"><table>
      <thead><tr><th>Work item</th><th>Reviewer role</th><th>Type</th><th></th></tr></thead>
      <tbody>{rows.map(r => <tr key={r.id}><td>{pretty(r.work_item)}</td><td>{pretty(r.reviewer_role)}</td><td>{r.required ? 'Required' : 'Advisory'}</td><td style={{ textAlign: 'right' }}><button className="btn secondary sm" onClick={() => del(r)}>Delete</button></td></tr>)}</tbody>
    </table></div> : <div className="empty">No rules configured for this project yet.</div>}</div>
  </>;
}
