import React, { useEffect, useMemo, useState } from 'react';
import { NavLink, Navigate, Outlet, useLocation } from 'react-router-dom';
import { api, logout, syncPending, getUser, setUser, currentProjectId, setCurrentProject, projectRole, roleLabel } from '../lib/api';
import { pendingCount } from '../lib/offline';
import { ProjectContext, categoryOf, CATEGORY_NAME } from '../lib/project';
import Icon from './Icon';
import { installApp, isStandalone, onInstallChange } from '../lib/pwa';

type Item = { to: string; label: string; icon: string };
type Menu = { primary: Item[]; secondary?: { title: string; items: Item[] } };

/** Role-specific navigation (UI design s.12). The server enforces every permission regardless of what is shown here. */
export const MENUS: Record<string, Menu> = {
  '1': { primary: [
    { to: '/', label: 'Dashboard', icon: 'dashboard' }, { to: '/projects', label: 'Projects', icon: 'building' }, { to: '/users', label: 'Users', icon: 'users' },
    { to: '/memberships', label: 'Project Memberships', icon: 'layers' }, { to: '/roles', label: 'Roles', icon: 'shield' }, { to: '/audit', label: 'Audit Log', icon: 'history' },
    { to: '/configuration', label: 'Configuration', icon: 'database' }],
    secondary: { title: 'Records (oversight)', items: [{ to: '/summaries', label: 'DOC_01 Submissions', icon: 'layers' }, { to: '/rfis', label: 'DOC_02 Register', icon: 'clipboard' },
      { to: '/completed', label: 'Completed DOC_03', icon: 'file' }, { to: '/reports', label: 'Reports', icon: 'chart' }, { to: '/master-data', label: 'Reference Data', icon: 'database' },
      { to: '/reviewer-rules', label: 'Reviewer Rules', icon: 'shield' }] } },
  '2.1': { primary: [
    { to: '/', label: 'Dashboard', icon: 'dashboard' }, { to: '/summaries', label: 'DOC_01 Submissions', icon: 'layers' }, { to: '/assignment', label: 'Inspector Assignment', icon: 'users' },
    { to: '/workflow', label: 'Workflow Monitor', icon: 'progress' }, { to: '/decisions', label: 'Final Decisions', icon: 'check' }, { to: '/rfis', label: 'DOC_02', icon: 'clipboard' },
    { to: '/reports', label: 'Reports', icon: 'chart' }],
    secondary: { title: 'Project tools', items: [{ to: '/completed', label: 'Completed DOC_03', icon: 'file' }, { to: '/daily-progress', label: 'Daily Progress', icon: 'progress' },
      { to: '/master-data', label: 'Reference Data', icon: 'database' }, { to: '/reviewer-rules', label: 'Reviewer Rules', icon: 'shield' }, { to: '/audit', label: 'Audit Log', icon: 'history' }] } },
  '2.2': { primary: [
    { to: '/my-inspections', label: 'My Assigned RFIs', icon: 'hardhat' }, { to: '/active-review', label: 'Active DOC_03', icon: 'clipboard' },
    { to: '/review-history', label: 'Review History', icon: 'history' }, { to: '/my-attachments', label: 'Attachments', icon: 'clip' }],
    secondary: { title: 'Project', items: [{ to: '/rfis', label: 'DOC_02 Register', icon: 'clipboard' }, { to: '/daily-progress', label: 'Daily Progress', icon: 'progress' }] } },
  '2.3': { primary: [
    { to: '/rfis', label: 'DOC_02 Register', icon: 'clipboard' }, { to: '/completed', label: 'Completed DOC_03', icon: 'file' }, { to: '/search', label: 'Search', icon: 'search' },
    { to: '/reports', label: 'Reports', icon: 'chart' }, { to: '/exports', label: 'Exports', icon: 'download' }],
    secondary: { title: 'Project', items: [{ to: '/summaries', label: 'DOC_01 Submissions', icon: 'layers' }, { to: '/daily-progress', label: 'Daily Progress', icon: 'progress' }] } },
  '3': { primary: [
    { to: '/doc01/new', label: 'New DOC_01', icon: 'plus' }, { to: '/doc01/drafts', label: 'Draft Submissions', icon: 'layers' },
    { to: '/doc01/submitted', label: 'Submitted Batches', icon: 'check' }, { to: '/my-rfis', label: 'My RFI Records', icon: 'clipboard' }],
    secondary: { title: 'Project', items: [{ to: '/', label: 'Overview', icon: 'dashboard' }, { to: '/daily-progress', label: 'Daily Progress', icon: 'progress' }] } },
};

export default function Layout() {
  const [theme, setTheme] = useState(localStorage.getItem('theme') || 'light');
  const [pending, setPending] = useState(0);
  const [, force] = useState(0);
  const [open, setOpen] = useState(false);
  const [menu, setMenu] = useState(false);
  const [unread, setUnread] = useState(0);
  const loc = useLocation();
  const u = getUser();
  const [pid, setPid] = useState<number | null>(currentProjectId());
  const [projects, setProjects] = useState<any[]>([]);
  const role = projectRole(pid);
  const category = categoryOf(role);
  const project = projects.find(p => p.id === pid) || null;
  const nav = MENUS[category || ''] || { primary: [] };
  const initials = String(u.name || 'U').split(/\s+/).map((s: string) => s[0]).slice(0, 2).join('').toUpperCase();
  const ctx = useMemo(() => ({ project, role, category }), [project?.id, role, category]);

  useEffect(() => { document.documentElement.setAttribute('data-theme', theme); try { localStorage.setItem('theme', theme); } catch { /* */ } }, [theme]);
  useEffect(() => { setOpen(false); setMenu(false); window.scrollTo(0, 0); }, [loc.pathname]);
  useEffect(() => {
    const poll = () => api('/notifications/unread-count').then((r: any) => setUnread(r.count || 0)).catch(() => {});
    poll(); const t = setInterval(poll, 60000);
    window.addEventListener('notifications-changed', poll);
    return () => { clearInterval(t); window.removeEventListener('notifications-changed', poll); };
  }, [loc.pathname]);
  useEffect(() => { api('/me').then((m: any) => { setUser(m); force(x => x + 1); }).catch(() => {}); }, []);
  useEffect(() => { const on = () => setPid(currentProjectId()); window.addEventListener('project-changed', on); return () => window.removeEventListener('project-changed', on); }, []);
  useEffect(() => {
    const all = [...nav.primary, ...(nav.secondary?.items || [])];
    const hit = all.find(i => (i.to === '/' ? loc.pathname === '/' : loc.pathname.startsWith(i.to)));
    document.title = `${hit?.label || 'RFIMS'} · RFIMS`;
  }, [loc.pathname, category]);
  useEffect(() => {
    const refresh = () => pendingCount().then(setPending).catch(() => {});
    refresh();
    // Only projects the user is an authorised member of are returned (administrators see all).
    api('/projects').then((p: any[]) => { setProjects(p || []); if ((!currentProjectId() || !p.some(x => x.id === currentProjectId())) && p?.[0]) setCurrentProject(p[0].id); }).catch(() => {});
    const on = () => { syncPending().then(refresh); };
    window.addEventListener('online', on);
    const off = onInstallChange(() => force(x => x + 1));
    return () => { window.removeEventListener('online', on); off(); };
  }, []);

  if (u.must_change_password && loc.pathname !== '/change-password') return <Navigate to="/change-password" replace />;

  return <ProjectContext.Provider value={ctx}>
    <a href="#main" className="skip-link">Skip to content</a>
    <div className={`shell${open ? ' nav-open' : ''}`}>
      <header className="app-header">
        <button className="hdr-btn menu-btn" onClick={() => setOpen(!open)} aria-label={open ? 'Close menu' : 'Open menu'} aria-expanded={open}><Icon name={open ? 'x' : 'menu'} size={18} /></button>
        <NavLink to="/" className="brand-word"><b>RFIMS</b><span>Request for Inspection Management</span></NavLink>
        <div className="spacer" />
        {pending > 0 && <span className="chip-pending" title="Saved on this device; will sync when online"><Icon name="wifiOff" size={14} />{pending} pending</span>}
        {projects.length > 1 && <select className="project-select" aria-label="Active project" value={pid || ''} onChange={e => setCurrentProject(+e.target.value)}>
          {projects.map(p => <option key={p.id} value={p.id}>{p.code}</option>)}</select>}
        {projects.length === 1 && <span className="who-role mono">{projects[0].code}</span>}
        <span className="who-role">Category {category || '—'} · {role === 'ADMIN' ? 'System Admin' : roleLabel(role)}</span>
        <NavLink to="/notifications" className="hdr-btn" aria-label={`Notifications${unread ? `, ${unread} unread` : ''}`}><Icon name="bell" size={17} />{unread > 0 && <span className="count-dot">{unread > 99 ? '99+' : unread}</span>}</NavLink>
        <button className="avatar" onClick={() => setMenu(!menu)} aria-haspopup="menu" aria-expanded={menu} aria-label="Account menu">{initials}</button>
      </header>
      {menu && <div className="user-menu" role="menu" onKeyDown={e => { if (e.key === 'Escape') setMenu(false); }}>
        <div className="um-head"><b>{u.name}</b><div className="muted" style={{ fontSize: 12.5 }}>{CATEGORY_NAME[category || ''] || ''} · {role === 'ADMIN' ? 'System Administrator' : roleLabel(role)}</div></div>
        <NavLink role="menuitem" to="/change-password"><Icon name="lock" size={15} />Change password</NavLink>
        <button role="menuitem" onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')}><Icon name={theme === 'light' ? 'moon' : 'sun'} size={15} />{theme === 'light' ? 'Dark' : 'Light'} theme</button>
        {!isStandalone() && <button role="menuitem" onClick={installApp}><Icon name="phone" size={15} />Install app</button>}
        <button role="menuitem" onClick={logout}><Icon name="logout" size={15} />Sign out</button>
      </div>}
      <nav className="sidebar" aria-label="Main">
        {!category && <div className="sb-meta">{projects.length ? 'No role on this project.' : 'No project access. Ask the administrator to add you to a project.'}</div>}
        {nav.primary.map(i => <NavLink key={i.to} to={i.to} end={i.to === '/' || i.to === '/rfis'} className="nav"><Icon name={i.icon} size={17} />{i.label}</NavLink>)}
        {nav.secondary && <><div className="sb-group">{nav.secondary.title}</div>
          {nav.secondary.items.map(i => <NavLink key={i.to} to={i.to} end={i.to === '/' || i.to === '/rfis'} className="nav"><Icon name={i.icon} size={17} />{i.label}</NavLink>)}</>}
        {project && <div className="sb-meta"><div><b>{project.code}</b></div><div>{project.name}</div></div>}
      </nav>
      <div className="scrim" onClick={() => setOpen(false)} />
      <main className="main" id="main"><div className="content"><Outlet key={pid || 0} /></div></main>
    </div>
  </ProjectContext.Provider>;
}
