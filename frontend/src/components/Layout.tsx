import React, { useEffect, useState } from 'react';
import { NavLink, Navigate, Outlet, useLocation } from 'react-router-dom';
import { api, logout, syncPending, getUser, setUser, currentProjectId, setCurrentProject, projectRole, roleLabel, isMgmt, isInspector, isAdmin as adminUser } from '../lib/api';
import { pendingCount } from '../lib/offline';
import Icon from './Icon';
import { BrandMark } from './Brand';
import { installApp, isStandalone, onInstallChange } from '../lib/pwa';

type Item = { to: string; label: string; icon: string; show?: () => boolean };
const groups: { title: string; items: Item[] }[] = [
  { title: 'Operations', items: [
    { to: '/', label: 'Dashboard', icon: 'dashboard' },
    { to: '/summaries', label: 'DOC_01 Submissions', icon: 'layers' },
    { to: '/rfis', label: 'DOC_02 RFI Register', icon: 'clipboard' },
    { to: '/my-inspections', label: 'My Inspections', icon: 'hardhat', show: () => isInspector() },
    { to: '/daily-progress', label: 'Daily Progress', icon: 'progress' },
  ] },
  { title: 'Insights', items: [
    { to: '/reports', label: 'Reports', icon: 'chart' },
    { to: '/notifications', label: 'Notifications', icon: 'bell' },
  ] },
  { title: 'Administration', items: [
    { to: '/master-data', label: 'Reference Data', icon: 'database', show: () => adminUser() || isMgmt() },
    { to: '/reviewer-rules', label: 'Reviewer Rules', icon: 'shield', show: () => adminUser() || isMgmt() },
    { to: '/projects', label: 'Projects & Members', icon: 'building', show: () => adminUser() },
    { to: '/users', label: 'Users', icon: 'users', show: () => adminUser() },
    { to: '/audit', label: 'Audit Log', icon: 'history', show: () => adminUser() || isMgmt() },
  ] },
];

function current(path: string) {
  for (const g of groups) for (const i of g.items) {
    if (i.to === '/' ? path === '/' : path === i.to || path.startsWith(i.to + '/')) {
      const detail = i.to !== '/' && path !== i.to;
      return { group: g.title, label: detail ? ({ '/rfis': 'RFI Detail', '/summaries': 'Summary Detail' } as any)[i.to] || i.label : i.label };
    }
  }
  if (path === '/change-password') return { group: 'Account', label: 'Change Password' };
  return { group: '', label: 'RFI Control' };
}

export default function Layout() {
  const [theme, setTheme] = useState(localStorage.getItem('theme') || 'light');
  const [pending, setPending] = useState(0);
  const [, force] = useState(0);
  const [open, setOpen] = useState(false);
  const [unread, setUnread] = useState(0);
  const loc = useLocation();
  const u = getUser();
  const [pid, setPid] = useState<number | null>(currentProjectId());
  const [projects, setProjects] = useState<any[]>([]);
  const myRole = projectRole(pid);
  const initials = String(u.name || 'U').split(/\s+/).map((s: string) => s[0]).slice(0, 2).join('').toUpperCase();
  const here = current(loc.pathname);

  useEffect(() => { document.documentElement.setAttribute('data-theme', theme); localStorage.setItem('theme', theme); }, [theme]);
  useEffect(() => { setOpen(false); window.scrollTo(0, 0); }, [loc.pathname]);
  useEffect(() => {
    const poll = () => api('/notifications/unread-count').then((r: any) => setUnread(r.count || 0)).catch(() => {});
    poll(); const t = setInterval(poll, 60000);
    window.addEventListener('notifications-changed', poll);
    return () => { clearInterval(t); window.removeEventListener('notifications-changed', poll); };
  }, [loc.pathname]);
  useEffect(() => { api('/me').then((m: any) => { setUser(m); force(x => x + 1); }).catch(() => {}); }, []);
  useEffect(() => { const on = () => setPid(currentProjectId()); window.addEventListener('project-changed', on); return () => window.removeEventListener('project-changed', on); }, []);
  useEffect(() => { document.title = `${here.label} · Construction RFI`; }, [here.label]);
  useEffect(() => {
    const refresh = () => pendingCount().then(setPending).catch(() => {});
    refresh();
    api('/projects').then((p: any[]) => { setProjects(p || []); if (!currentProjectId() && p?.[0]) setCurrentProject(p[0].id); }).catch(() => {});
    const on = () => { syncPending().then(refresh); };
    window.addEventListener('online', on);
    const off = onInstallChange(() => force(x => x + 1));
    return () => { window.removeEventListener('online', on); off(); };
  }, []);

  if (u.must_change_password && loc.pathname !== '/change-password') return <Navigate to="/change-password" replace />;

  return (
    <div className={`shell${open ? ' nav-open' : ''}`}>
      <aside className="sidebar">
        <NavLink to="/home" className="sb-brand">
          <BrandMark />
          <div><div className="t1">Construction RFI</div><div className="t2">Site Control System</div></div>
        </NavLink>
        {projects.length > 0 && (
          <div className="sb-project" title={projects.find(p => p.id === pid)?.name}>
            <label className="k" htmlFor="project-select">Active project</label>
            <select id="project-select" value={pid || ''} onChange={e => setCurrentProject(+e.target.value)} style={{ width: '100%', marginTop: 4 }}>
              {projects.map(p => <option key={p.id} value={p.id}>{p.code}</option>)}
            </select>
            <div className="k" style={{ marginTop: 6 }}>{roleLabel(myRole)}</div>
          </div>
        )}
        {projects.length === 0 && !adminUser() && <div className="sb-project"><div className="k">No project access</div><div className="v" style={{ fontSize: 12 }}>Ask the administrator to add you to a project.</div></div>}
        <nav className="sb-nav">
          {groups.map(g => {
            const items = g.items.filter(i => !i.show || i.show());
            if (!items.length) return null;
            return (
              <div key={g.title}>
                <div className="sb-group">{g.title}</div>
                {items.map(i => (
                  <NavLink key={i.to} to={i.to} end={i.to === '/'} className="nav">
                    <Icon name={i.icon} />{i.label}
                  </NavLink>
                ))}
              </div>
            );
          })}
        </nav>
        <div className="sb-foot">
          <div className="avatar">{initials}</div>
          <NavLink to="/change-password" className="who" style={{ textDecoration: 'none' }} title="Change password"><div className="nm">{u.name}</div><div className="rl">{roleLabel(myRole || u.role)} · Password</div></NavLink>
          <button className="icon-btn" style={{ background: 'transparent', borderColor: 'var(--steel-line)', color: '#c5d0dc' }} onClick={logout} title="Sign out" aria-label="Sign out">
            <Icon name="logout" />
          </button>
        </div>
      </aside>
      <div className="scrim" onClick={() => setOpen(false)} />
      <main className="main">
        <header className="topbar">
          <div className="tb-left">
            <button className="icon-btn menu-btn" onClick={() => setOpen(true)} aria-label="Open menu"><Icon name="menu" /></button>
            <div style={{ minWidth: 0 }}>
              {here.group && <div className="crumbs hide-sm">{here.group}</div>}
              <div className="tb-title">{here.label}</div>
            </div>
          </div>
          <div className="tb-right">
            {pending > 0 && <span className="chip-pending" title="Changes saved offline, will sync when online"><Icon name="wifiOff" size={14} />{pending} pending</span>}
            {!isStandalone() && <button className="btn secondary hide-sm" onClick={installApp}><Icon name="phone" size={16} />Install App</button>}
            <button className="icon-btn" onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')} aria-label="Toggle theme" title="Toggle theme">
              <Icon name={theme === 'light' ? 'moon' : 'sun'} />
            </button>
            <NavLink to="/notifications" className="icon-btn" aria-label={`Notifications${unread ? `, ${unread} unread` : ''}`} title="Notifications"><Icon name="bell" />{unread > 0 && <span className="count-dot">{unread > 99 ? '99+' : unread}</span>}</NavLink>
          </div>
        </header>
        <div className="content"><Outlet key={pid || 0} /></div>
      </main>
    </div>
  );
}
