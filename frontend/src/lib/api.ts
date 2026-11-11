import {enqueueRequest,syncQueue} from './offline';
const API=import.meta.env.VITE_API_URL||'http://localhost:8000';
export const token=()=>localStorage.getItem('token');
export const setToken=(v:string)=>localStorage.setItem('token',v);
export const setUser=(u:any)=>localStorage.setItem('user',JSON.stringify(u));
export const getUser=()=>{try{return JSON.parse(localStorage.getItem('user')||'{}')}catch{return {}}};
export const MANAGER_ROLES=['ADMIN','RE','ARE','RE_ARE'];
export const isManager=()=>MANAGER_ROLES.includes(getUser().role);
export const isAdmin=()=>getUser().role==='ADMIN';
export const logout=()=>{const theme=localStorage.getItem('theme');localStorage.removeItem('token');localStorage.removeItem('user');if(theme)localStorage.setItem('theme',theme);location.href='/login'};
function message(text:string){try{const j=JSON.parse(text);const d=j.detail??j.message??text;return Array.isArray(d)?d.map((x:any)=>`${(x.loc||[]).slice(-1)[0]||''}: ${x.msg}`).join('; '):String(d)}catch{return text}}
export async function api(path:string,options:RequestInit={}){
  const h=new Headers(options.headers||{});
  if(!(options.body instanceof FormData))h.set('Content-Type','application/json');
  if(token())h.set('Authorization',`Bearer ${token()}`);
  let r:Response;
  try{r=await fetch(`${API}${path}`,{...options,headers:h})}catch{throw new Error('Cannot reach the server. Check your connection and try again.')}
  // A 401 on an authenticated call means the session expired. Login/reset calls report their own error instead.
  if(r.status===401&&token()&&!path.startsWith('/auth/')){logout();throw new Error('Session expired. Please sign in again.')}
  if(!r.ok)throw new Error(message(await r.text())||`Request failed (${r.status})`);
  const ct=r.headers.get('content-type')||'';
  return ct.includes('application/json')?r.json():r.blob();
}
export async function apiOrQueue(path:string,method:string,payload:any,isForm=false){if(!navigator.onLine){const body=isForm?Object.fromEntries((payload as FormData).entries()):payload;await enqueueRequest(path,method,body,isForm);return {queued:true}}return api(path,{method,body:isForm?payload:JSON.stringify(payload)})}
export async function syncPending(){return syncQueue(API,token())}
export async function download(path:string,filename?:string){try{const r=await fetch(`${API}${path}`,{headers:{Authorization:`Bearer ${token()||''}`}});if(!r.ok)throw new Error(message(await r.text()));const b=await r.blob(),u=URL.createObjectURL(b),a=document.createElement('a');a.href=u;a.download=filename||'download';document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(u),10000)}catch(e:any){alert(e.message||'Download failed')}}
window.addEventListener('online',()=>{syncPending().catch(()=>{})});
export const API_BASE=API;
/** Map of user id -> display name, loaded once per page. */
export async function userNames(){try{const us:any[]=await api('/users');return Object.fromEntries(us.map(u=>[u.id,u.full_name]))}catch{return {}}}
export const fmtDate=(v:any)=>v?new Date(String(v).endsWith('Z')||String(v).includes('+')?v:v+'Z').toLocaleString(undefined,{dateStyle:'medium',timeStyle:'short'}):'—';
