import { enqueueRequest, syncQueue } from './offline';
const API = import.meta.env.VITE_API_URL || 'http://localhost:8000';
export const API_BASE = API;

export const token = () => localStorage.getItem('token');
export const setToken = (v: string) => localStorage.setItem('token', v);
export const setUser = (u: any) => localStorage.setItem('user', JSON.stringify(u));
export const getUser = (): any => { try { return JSON.parse(localStorage.getItem('user') || '{}'); } catch { return {}; } };

// ---- Role model (mirrors backend app/authz.py; the backend is the authority, this only shapes the UI)
export const MANAGEMENT = ['RE', 'DRE'];
export const INSPECTORS = ['WORK_INSPECTOR', 'STRUCTURE_INSPECTOR', 'SURVEYOR', 'SENIOR_SURVEYOR', 'MATERIAL_INSPECTOR', 'LAB_TECHNICIAN', 'MATERIAL_ENGINEER'];
export const OFFICE = ['QUANTITY_SURVEYOR', 'DRAFTSPERSON', 'SECRETARY', 'PROJECT_MANAGER', 'VIEWER'];
export const CONTRACTOR = ['DATA_ENCODER', 'OFFICE_ENGINEER', 'CONTRACTOR', 'SITE_ENGINEER'];
export const ROLE_LABEL: Record<string, string> = {
  ADMIN: 'System Administrator', RE: 'Resident Engineer', DRE: 'Deputy Resident Engineer',
  WORK_INSPECTOR: 'Works Inspector', STRUCTURE_INSPECTOR: 'Structure Inspector', SURVEYOR: 'Surveyor', SENIOR_SURVEYOR: 'Senior Surveyor',
  MATERIAL_INSPECTOR: 'Material Inspector', LAB_TECHNICIAN: 'Soil Lab Technician', MATERIAL_ENGINEER: 'Material Engineer', QUANTITY_SURVEYOR: 'Quantity Surveyor',
  DRAFTSPERSON: 'Draftsperson', SECRETARY: 'Secretary', PROJECT_MANAGER: 'Project Manager (read-only)', VIEWER: 'Viewer (read-only)', DATA_ENCODER: 'Data Encoder',
  OFFICE_ENGINEER: 'Office Engineer', CONTRACTOR: 'Contractor (legacy)', SITE_ENGINEER: 'Site Engineer (legacy)',
};
export const roleLabel = (r?: string | null) => (r ? ROLE_LABEL[r] || r : '—');

export const isAdmin = () => getUser().role === 'ADMIN';
export function currentProjectId(): number | null {
  const v = Number(localStorage.getItem('project_id') || 0);
  if (v) return v;
  const m = getUser().memberships || [];
  return m[0]?.project_id || null;
}
export function setCurrentProject(id: number) { localStorage.setItem('project_id', String(id)); window.dispatchEvent(new Event('project-changed')); }
/** Role of the signed-in user in the current project (ADMIN for administrators). */
export function projectRole(pid: number | null = currentProjectId()): string | null {
  const u = getUser();
  if (u.role === 'ADMIN') return 'ADMIN';
  return (u.memberships || []).find((m: any) => m.project_id === pid)?.role || null;
}
export const isMgmt = (r = projectRole()) => !!r && MANAGEMENT.includes(r);
export const isInspector = (r = projectRole()) => !!r && INSPECTORS.includes(r);
export const isContractor = (r = projectRole()) => !!r && CONTRACTOR.includes(r);
export const isOffice = (r = projectRole()) => !!r && OFFICE.includes(r);
/** Kept for older components: RE/DRE of the current project. */
export const isManager = () => isMgmt();
export const deputyLabel = () => (getUser().memberships || []).find((m: any) => m.project_id === currentProjectId())?.deputy_label || 'DRE';

export const logout = () => {
  const theme = localStorage.getItem('theme');
  ['token', 'user', 'project_id'].forEach(k => localStorage.removeItem(k));
  if (theme) localStorage.setItem('theme', theme);
  location.href = '/login';
};
export const requestId = () => (crypto as any).randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(16).slice(2)}`;

function message(text: string) {
  try {
    const j = JSON.parse(text); const d = j.detail ?? j.message ?? text;
    return Array.isArray(d) ? d.map((x: any) => `${(x.loc || []).slice(-1)[0] || ''}: ${x.msg}`).join('; ') : String(d);
  } catch { return text; }
}
export async function api(path: string, options: RequestInit = {}) {
  const h = new Headers(options.headers || {});
  if (!(options.body instanceof FormData)) h.set('Content-Type', 'application/json');
  if (token()) h.set('Authorization', `Bearer ${token()}`);
  let r: Response;
  try { r = await fetch(`${API}${path}`, { ...options, headers: h }); } catch { throw new Error('Cannot reach the server. Check your connection and try again.'); }
  if (r.status === 401 && token() && !path.startsWith('/auth/')) { logout(); throw new Error('Session expired. Please sign in again.'); }
  if (!r.ok) throw new Error(message(await r.text()) || `Request failed (${r.status})`);
  const ct = r.headers.get('content-type') || '';
  return ct.includes('application/json') ? r.json() : r.blob();
}
export const post = (path: string, body?: any) => api(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) });
export const put = (path: string, body: any) => api(path, { method: 'PUT', body: JSON.stringify(body) });

/** Writes that may be queued offline carry a client_request_id so a replay never creates a duplicate. */
export async function apiOrQueue(path: string, method: string, payload: any, isForm = false) {
  if (!isForm && payload && typeof payload === 'object' && !payload.client_request_id) payload = { ...payload, client_request_id: requestId() };
  if (!navigator.onLine) {
    const body = isForm ? Object.fromEntries((payload as FormData).entries()) : payload;
    await enqueueRequest(path, method, body, isForm); return { queued: true };
  }
  return api(path, { method, body: isForm ? payload : JSON.stringify(payload) });
}
export async function syncPending() { return syncQueue(API, token()); }
export async function download(path: string, filename?: string) {
  try {
    const r = await fetch(`${API}${path}`, { headers: { Authorization: `Bearer ${token() || ''}` } });
    if (!r.ok) throw new Error(message(await r.text()));
    const b = await r.blob(), u = URL.createObjectURL(b), a = document.createElement('a');
    a.href = u; a.download = filename || 'download'; document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(u), 10000);
  } catch (e: any) { alert(e.message || 'Download failed'); }
}
window.addEventListener('online', () => { syncPending().catch(() => {}); });

export const fmtDate = (v: any) => v ? new Date(String(v).endsWith('Z') || String(v).includes('+') ? v : v + 'Z').toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' }) : '—';
export const fmtDay = (v: any) => v ? new Date(String(v) + 'T00:00:00').toLocaleDateString(undefined, { day: '2-digit', month: 'short', year: 'numeric' }) : '—';
export const loc = (r: any) => [r.chainage_from, r.chainage_to].filter(Boolean).join(' – ') + (r.side ? ` ${r.side}` : '') || r.location_text || '—';
/** Member names of a project (no e-mails). Replaces the old global user directory. */
export async function memberNames(pid: number | null = currentProjectId()) {
  if (!pid) return {};
  try { const ms: any[] = await api(`/projects/${pid}/members`); return Object.fromEntries(ms.map(m => [m.user_id, m.full_name])); } catch { return {}; }
}
export const userNames = memberNames;
