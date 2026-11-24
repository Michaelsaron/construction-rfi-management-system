import React, { useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { api, post, put, download, fmtDate } from '../lib/api';
import { PageHeader, ConfirmDialog, Loading, ErrorNote } from '../components/ui';
import { Table } from './Queues';
import Status from '../components/Status';

/** Category 1 — Project memberships: user, project, category, role, account status and actions. */
export function Memberships() {
  const [sp] = useSearchParams();
  const [rows, setRows] = useState<any[] | null>(null); const [projects, setProjects] = useState<any[]>([]); const [users, setUsers] = useState<any[]>([]); const [roles, setRoles] = useState<any[]>([]);
  const [q, setQ] = useState(''); const [proj, setProj] = useState(''); const [showRevoked, setShowRevoked] = useState(false); const [err, setErr] = useState(''); const [msg, setMsg] = useState('');
  const [add, setAdd] = useState({ project_id: '', user_id: sp.get('user') || '', role: '' }); const [dlg, setDlg] = useState<any>(null); const [busy, setBusy] = useState(false);
  const load = () => api('/admin/memberships?include_revoked=true').then(setRows).catch(e => { setErr(e.message); setRows([]); });
  useEffect(() => { load(); api('/projects?include_archived=true').then(setProjects).catch(() => {}); api('/users').then(setUsers).catch(() => {}); api('/projects/meta/roles').then(setRoles).catch(() => {}); }, []);
  const userFilter = sp.get('user');
  const shown = useMemo(() => (rows || []).filter(m => (showRevoked || m.membership_status === 'ACTIVE') && (!proj || String(m.project_id) === proj) && (!userFilter || String(m.user_id) === userFilter)
    && (!q || `${m.full_name} ${m.email} ${m.role_label} ${m.project_code}`.toLowerCase().includes(q.toLowerCase()))), [rows, q, proj, showRevoked, userFilter]);
  async function addMember() {
    if (!add.project_id || !add.user_id || !add.role) { setErr('Choose a project, a user and a role.'); return; }
    try { await post(`/projects/${add.project_id}/members`, { user_id: +add.user_id, role: add.role }); setMsg('Membership saved.'); setErr(''); setAdd({ ...add, role: '' }); load(); } catch (e: any) { setErr(e.message); }
  }
  async function act() {
    setBusy(true);
    try {
      if (dlg.kind === 'revoke') await api(`/projects/${dlg.m.project_id}/members/${dlg.m.user_id}`, { method: 'DELETE' });
      else await post(`/users/${dlg.m.user_id}/toggle-active`);
      setMsg(dlg.kind === 'revoke' ? 'Project access revoked; past actions are kept.' : 'Account status changed.'); setDlg(null); load();
    } catch (e: any) { alert(e.message); } finally { setBusy(false); }
  }
  const roleSelect = <select aria-label="Role" value={add.role} onChange={e => setAdd({ ...add, role: e.target.value })}><option value="">Category / role…</option>
    {roles.map(g => <optgroup key={g.category} label={`${g.category} ${g.label}`}>{g.roles.map((r: any) => <option key={r.code} value={r.code}>{r.label}</option>)}</optgroup>)}</select>;
  return <>
    <PageHeader title="Project memberships" actions={<button className="btn neutral" onClick={() => download('/admin/access-matrix.xlsx', 'access_matrix.xlsx')}>Export access matrix</button>} />
    {msg && <div className="notice ok">{msg}</div>}<ErrorNote error={err} />
    <div className="card"><h3>Assign a project role</h3><div className="toolbar">
      <select aria-label="Project" value={add.project_id} onChange={e => setAdd({ ...add, project_id: e.target.value })}><option value="">Project…</option>{projects.filter(p => p.status !== 'ARCHIVED').map(p => <option key={p.id} value={p.id}>{p.code}</option>)}</select>
      <select aria-label="User" value={add.user_id} onChange={e => setAdd({ ...add, user_id: e.target.value })}><option value="">User…</option>{users.filter(u => u.role !== 'ADMIN' && u.is_active).map(u => <option key={u.id} value={u.id}>{u.full_name}</option>)}</select>
      {roleSelect}<button className="btn success" onClick={addMember}>Assign / change role</button></div>
      <p className="muted" style={{ fontSize: 12.5 }}>A user can hold one role per project. Changing a role replaces the previous one; history is kept in the audit log.</p></div>
    <div className="card">
      <div className="toolbar" style={{ marginBottom: 12 }}>
        <input aria-label="Search" placeholder="Search name, e-mail, role…" value={q} onChange={e => setQ(e.target.value)} style={{ flex: '1 1 220px' }} />
        <select aria-label="Filter by project" value={proj} onChange={e => setProj(e.target.value)}><option value="">All projects</option>{projects.map(p => <option key={p.id} value={p.id}>{p.code}</option>)}</select>
        <label className="check"><input type="checkbox" checked={showRevoked} onChange={e => setShowRevoked(e.target.checked)} />Show revoked</label>
        {userFilter && <Link className="link" to="/memberships">Show all users</Link>}
      </div>
      <Table rows={rows === null ? null : shown} empty="No memberships match."
        cards={m => <><div className="row1"><b>{m.full_name}</b><Status value={m.account_active ? 'ACTIVE' : 'CANCELLED'} label={m.account_active ? 'Active' : 'Deactivated'} /></div><dl><dt>Project</dt><dd>{m.project_code}</dd><dt>Role</dt><dd>{m.category} · {m.role_label}</dd></dl></>}
        cols={[{ h: 'User', c: m => <>{m.full_name}<div className="muted" style={{ fontSize: 12 }}>{m.email}</div></> }, { h: 'Project', c: m => m.project_code + (m.project_archived ? ' (archived)' : '') },
          { h: 'Category', c: m => `${m.category || '—'} · ${m.category_label}` }, { h: 'Role', c: m => <>{m.role_label}{m.legacy_role && <div className="muted" style={{ fontSize: 12 }}>from legacy global role</div>}</> },
          { h: 'Membership', c: m => <Status value={m.membership_status === 'ACTIVE' ? 'ACTIVE' : 'CANCELLED'} label={m.membership_status === 'ACTIVE' ? 'Active' : `Revoked ${fmtDate(m.revoked_at)}`} /> },
          { h: 'Account', c: m => <Status value={m.account_active ? 'ACTIVE' : 'CANCELLED'} label={m.account_active ? 'Active' : 'Deactivated'} /> },
          { h: 'Actions', c: m => <span className="nowrap">{m.membership_status === 'ACTIVE' && <button className="btn secondary sm" onClick={() => setDlg({ kind: 'revoke', m })}>Revoke</button>}{' '}
            <button className={`btn sm ${m.account_active ? 'danger' : 'success'}`} onClick={() => setDlg({ kind: 'toggle', m })}>{m.account_active ? 'Deactivate' : 'Activate'}</button></span> }]} />
    </div>
    {dlg && <ConfirmDialog open title={dlg.kind === 'revoke' ? `Revoke ${dlg.m.full_name}'s access to ${dlg.m.project_code}?` : `${dlg.m.account_active ? 'Deactivate' : 'Activate'} ${dlg.m.full_name}?`}
      tone={dlg.kind === 'revoke' || dlg.m.account_active ? 'danger' : 'success'} confirmLabel={dlg.kind === 'revoke' ? 'Revoke access' : dlg.m.account_active ? 'Deactivate account' : 'Activate account'} busy={busy}
      onCancel={() => setDlg(null)} onConfirm={act} rows={[['User', `${dlg.m.full_name} (${dlg.m.email})`], ['Project', dlg.m.project_code], ['Role', dlg.m.role_label]]}
      warnings={[dlg.kind === 'toggle' && dlg.m.account_active ? 'Deactivation applies to every project and takes effect immediately. Historical records, reviews and attachments are kept.' : '']} />}
  </>;
}

/** Category 1 — role catalogue with the capabilities each role has under the default project settings. */
export function Roles() {
  const [d, setD] = useState<any>(null); const [err, setErr] = useState('');
  useEffect(() => { api('/admin/roles').then(setD).catch(e => setErr(e.message)); }, []);
  if (err) return <ErrorNote error={err} />;
  if (!d) return <Loading />;
  return <>
    <PageHeader title="Roles" actions={<button className="btn neutral" onClick={() => download('/admin/access-matrix.xlsx', 'access_matrix.xlsx')}>Export access matrix</button>} />
    <p className="subtitle">{d.note}</p>
    {d.categories.map((g: any) => <div key={g.category} className="card"><h3>Category {g.category} — {g.label}</h3>
      <Table rows={g.roles.map((r: any) => ({ ...r, id: r.code }))} empty=""
        cols={[{ h: 'Role', c: r => <><b>{r.label}</b><div className="muted mono" style={{ fontSize: 12 }}>{r.code}</div></> }, { h: 'Capabilities', c: r => r.capabilities.join(' · ') || '—' },
          { h: 'Assignable', c: r => r.assignable ? 'Yes' : 'Legacy only' }]} /></div>)}
    <div className="card"><h3>Notes</h3><ul style={{ margin: 0 }}>{Object.entries(d.capability_notes).map(([k, v]: any) => <li key={k}><b>{k}:</b> {v}</li>)}</ul></div>
  </>;
}

const CATS: [string, string][] = [['1', 'System Admin'], ['2.1', 'RE / DRE'], ['2.2', 'Inspectors'], ['2.3', 'Office'], ['3', 'Contractor']];

/** Category 1 — per-project configuration. Every option that depends on a pending client decision is labelled with its register id. */
export function Configuration() {
  const [projects, setProjects] = useState<any[]>([]); const [pid, setPid] = useState(''); const [s, setS] = useState<any>(null); const [msg, setMsg] = useState(''); const [err, setErr] = useState('');
  useEffect(() => { api('/projects?include_archived=true').then((p: any[]) => { setProjects(p); if (p[0]) setPid(String(p[0].id)); }).catch(e => setErr(e.message)); }, []);
  useEffect(() => { if (pid) api(`/projects/${pid}/settings`).then((x: any) => setS({ ...x, _disp: JSON.stringify(x.dispositions, null, 2), _ext: x.attachment_policy.allowed_extensions.join(', ') })).catch(e => setErr(e.message)); }, [pid]);
  async function save() {
    setErr(''); setMsg('');
    try {
      const body = { notice_policy: s.notice_policy, notice_hours: +s.notice_hours, contractor_visibility: s.contractor_visibility, inspector_register_access: !!s.inspector_register_access,
        inspector_export: !!s.inspector_export, overdue_hours: +s.overdue_hours, dispositions: JSON.parse(s._disp), contractor_evidence_access: !!s.contractor_evidence_access,
        hidden_field_categories: s.hidden_field_categories,
        attachment_policy: { ...s.attachment_policy, allowed_extensions: s._ext.split(/[\s,]+/).filter(Boolean).map((e: string) => (e.startsWith('.') ? e : '.' + e).toLowerCase()),
          max_file_mb: +s.attachment_policy.max_file_mb, max_files_per_record: +s.attachment_policy.max_files_per_record } };
      const x: any = await put(`/projects/${pid}/settings`, body);
      setS({ ...x, _disp: JSON.stringify(x.dispositions, null, 2), _ext: x.attachment_policy.allowed_extensions.join(', ') }); setMsg('Configuration saved.');
    } catch (e: any) { setErr(e.message); }
  }
  const ap = s?.attachment_policy;
  const setAp = (k: string, v: any) => setS({ ...s, attachment_policy: { ...ap, [k]: v } });
  return <>
    <PageHeader title="Configuration" />
    <p className="subtitle">Project settings that depend on client decisions. Defaults are conservative; see the client decision register (docs/ui-upgrade/DECISION_REGISTER.md).</p>
    <div className="toolbar" style={{ marginBottom: 14 }}><div><label htmlFor="cfg-p">Project</label><select id="cfg-p" value={pid} onChange={e => setPid(e.target.value)}>{projects.map(p => <option key={p.id} value={p.id}>{p.code} — {p.name}</option>)}</select></div></div>
    {msg && <div className="notice ok">{msg}</div>}<ErrorNote error={err} />
    {!s ? <Loading /> : <>
      <div className="card"><h3>Workflow</h3><div className="grid">
        <div><label htmlFor="c1">24-hour rule (OD-11)</label><select id="c1" value={s.notice_policy} onChange={e => setS({ ...s, notice_policy: e.target.value })}><option value="FLAG">Flag short notice only</option><option value="REQUIRE_OVERRIDE">Require a reason</option></select></div>
        <div><label htmlFor="c2">Notice hours</label><input id="c2" type="number" value={s.notice_hours} onChange={e => setS({ ...s, notice_hours: e.target.value })} /></div>
        <div><label htmlFor="c3">Overdue inspector turn after (hours)</label><input id="c3" type="number" value={s.overdue_hours} onChange={e => setS({ ...s, overdue_hours: e.target.value })} /></div>
      </div>
        <div style={{ marginTop: 12 }}><label htmlFor="c4">DOC_03 disposition options (OD-06, JSON)</label><textarea id="c4" rows={8} className="mono" style={{ fontSize: 12 }} value={s._disp} onChange={e => setS({ ...s, _disp: e.target.value })} /></div></div>
      <div className="card"><h3>Visibility</h3><div className="grid">
        <div><label htmlFor="v1">Contractor visibility (UD-04 / OD-03)</label><select id="v1" value={s.contractor_visibility} onChange={e => setS({ ...s, contractor_visibility: e.target.value })}><option value="PROJECT">All project RFIs</option><option value="OWN">Own submissions only</option></select></div>
        <div><label htmlFor="v2">Contractors may open inspection evidence (UD-04)</label><select id="v2" value={String(s.contractor_evidence_access)} onChange={e => setS({ ...s, contractor_evidence_access: e.target.value === 'true' })}><option value="false">No (default)</option><option value="true">Yes</option></select></div>
        <div><label htmlFor="v3">Inspectors may read DOC_02 (UD-05)</label><select id="v3" value={String(s.inspector_register_access)} onChange={e => setS({ ...s, inspector_register_access: e.target.value === 'true' })}><option value="true">Yes (read-only)</option><option value="false">No — assigned RFIs only</option></select></div>
        <div><label htmlFor="v4">Inspectors may export DOC_02</label><select id="v4" value={String(s.inspector_export)} onChange={e => setS({ ...s, inspector_export: e.target.value === 'true' })}><option value="false">No</option><option value="true">Yes</option></select></div>
      </div>
        <fieldset style={{ marginTop: 12 }}><legend>Categories that may see hidden workbook fields I:M and S (UD-06)</legend><div className="actions" style={{ marginTop: 4 }}>
          {CATS.map(([c, l]) => <label key={c} className="check"><input type="checkbox" checked={s.hidden_field_categories.includes(c)} onChange={e => setS({ ...s, hidden_field_categories: e.target.checked ? [...s.hidden_field_categories, c] : s.hidden_field_categories.filter((x: string) => x !== c) })} />{c} {l}</label>)}</div></fieldset></div>
      <div className="card"><h3>Attachments (UD-07 to UD-09)</h3><div className="grid">
        <div style={{ gridColumn: '1/-1' }}><label htmlFor="a1">Allowed file types</label><input id="a1" value={s._ext} onChange={e => setS({ ...s, _ext: e.target.value })} /></div>
        <div><label htmlFor="a2">Maximum size per file (MB)</label><input id="a2" type="number" min={1} value={ap.max_file_mb} onChange={e => setAp('max_file_mb', e.target.value)} /></div>
        <div><label htmlFor="a3">Maximum files per remark / review</label><input id="a3" type="number" min={1} value={ap.max_files_per_record} onChange={e => setAp('max_files_per_record', e.target.value)} /></div>
        <div><label htmlFor="a4">Malware scanning</label><select id="a4" value={ap.scanning} onChange={e => setAp('scanning', e.target.value)}><option value="DISABLED">Disabled (pending decision)</option><option value="SCAN_IF_AVAILABLE">Scan when a scanner is available</option><option value="REQUIRED">Required (refuse if unavailable)</option></select></div>
        <div><label>Retention</label><div className="ro-field">Keep all files (no automatic deletion)</div></div>
      </div><p className="muted" style={{ fontSize: 12.5 }}>The server limit (MAX_UPLOAD_MB) always applies on top of these values. Scanning needs a ClamAV service (CLAMD_HOST).</p></div>
      <div className="actions"><button className="btn success" onClick={save}>Save configuration</button></div>
    </>}
    {projects.length === 0 && !err && <div className="empty">No projects yet. <Link className="link" to="/projects">Create a project</Link>.</div>}
  </>;
}
