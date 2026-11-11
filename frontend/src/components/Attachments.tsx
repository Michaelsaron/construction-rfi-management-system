import React, { useEffect, useRef, useState } from 'react';
import { api, apiOrQueue, download, fmtDate, isManager } from '../lib/api';
import Icon from './Icon';

const ACCEPT = '.pdf,.jpg,.jpeg,.png,.xls,.xlsx,.doc,.docx,.dwg,.dxf,.dgn';
const size = (b: number) => (b > 1048576 ? `${(b / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(b / 1024))} KB`);

/** Attachment list + upload for an RFI, summary or daily-progress record. */
export default function Attachments({ entityType, entityId, canUpload = true, title = 'Attachments' }: { entityType: string; entityId: number; canUpload?: boolean; title?: string }) {
  const [rows, setRows] = useState<any[]>([]); const [file, setFile] = useState<File | null>(null);
  const [msg, setMsg] = useState(''); const [busy, setBusy] = useState(false); const input = useRef<HTMLInputElement>(null);
  const load = () => api(`/attachments/${entityType}/${entityId}`).then(setRows).catch(() => {});
  useEffect(() => { load(); }, [entityType, entityId]);

  async function up() {
    if (!file) { alert('Choose a file first.'); return; }
    const fd = new FormData(); fd.append('file', file); setBusy(true);
    try {
      const r: any = await apiOrQueue(`/attachments/${entityType}/${entityId}`, 'POST', fd, true);
      setMsg(r?.queued ? 'Attachment saved offline. It will upload when you are back online.' : `Uploaded ${file.name}.`);
      setFile(null); if (input.current) input.current.value = '';
      if (!r?.queued) load();
    } catch (e: any) { alert(e.message); } finally { setBusy(false); }
  }
  async function remove(a: any) {
    if (!confirm(`Remove attachment "${a.original_name}"?`)) return;
    try { await api(`/attachments/${a.id}`, { method: 'DELETE' }); load(); } catch (e: any) { alert(e.message); }
  }

  return <div className="card">
    <h3>{title}</h3>
    {msg && <div className="notice ok">{msg}</div>}
    {canUpload && <div className="toolbar">
      <input ref={input} type="file" accept={ACCEPT} onChange={e => setFile(e.target.files?.[0] || null)} style={{ flex: '1 1 260px' }} />
      <button className="btn" disabled={busy || !file} onClick={up}><Icon name="clip" size={16} />{busy ? 'Uploading…' : 'Upload'}</button>
    </div>}
    {canUpload && <p className="muted" style={{ fontSize: 12.5, margin: '8px 0 0' }}>PDF, images, Office documents and CAD drawings (DWG/DXF/DGN). On a phone, you can take a photo directly.</p>}
    {rows.length ? <ul className="file-list">{rows.map(a => <li key={a.id}>
      <Icon name="file" size={18} />
      <button className="linkButton grow" style={{ textAlign: 'left' }} onClick={() => download(`/attachments/download/${a.id}`, a.original_name)} title={a.original_name}>{a.original_name}</button>
      <span className="muted hide-sm" style={{ fontSize: 12.5 }}>{size(a.size_bytes)} · {fmtDate(a.uploaded_at)}</span>
      {isManager() && <button className="btn secondary sm" onClick={() => remove(a)}>Remove</button>}
    </li>)}</ul> : <div className="empty" style={{ padding: '20px 0 4px' }}>No attachments yet.</div>}
  </div>;
}
