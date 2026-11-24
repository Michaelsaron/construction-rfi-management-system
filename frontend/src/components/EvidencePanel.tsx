import React, { useEffect, useRef, useState } from 'react';
import { API_BASE, api, download, fmtDate } from '../lib/api';
import { uploadWithProgress, newToken, fileSize, extOf, UploadHandle } from '../lib/upload';
import type { Evidence, UploadPolicy } from '../lib/contracts';

const DEFAULT_POLICY: UploadPolicy = { allowed_extensions: ['.pdf', '.jpg', '.jpeg', '.png', '.xls', '.xlsx', '.doc', '.docx', '.dwg', '.dxf', '.dgn'], max_file_mb: 50, max_files_per_record: 20 };
type Q = { key: string; file: File; token: string; status: 'uploading' | 'failed'; pct: number; error?: string; handle?: UploadHandle };

/** Open a stored file in a new tab without exposing any storage path: the bytes are fetched with the session and shown from a local blob. */
export async function previewFile(f: Evidence) {
  const w = window.open('', '_blank');
  try {
    const r = await fetch(`${API_BASE}/evidence/files/${f.id}/download?inline=1`, { credentials: 'include' });
    if (!r.ok) { let m = `Could not open the file (${r.status})`; try { m = (await r.json()).detail || m; } catch { /* */ } throw new Error(m); }
    const url = URL.createObjectURL(await r.blob());
    if (w) w.location.href = url; else window.location.href = url;
    setTimeout(() => URL.revokeObjectURL(url), 60000);
  } catch (e: any) { w?.close(); alert(e.message); }
}

export function FileRow({ f, onRemove }: { f: Evidence; onRemove?: () => void }) {
  return <li className="ev-item">
    <span className="nm" title={f.original_name}>{f.original_name}</span>
    <span className="acts">
      {f.previewable && <button type="button" className="btn secondary sm" onClick={() => previewFile(f)} aria-label={`Preview ${f.original_name}`}>Preview</button>}
      <button type="button" className="btn secondary sm" onClick={() => download(`/evidence/files/${f.id}/download`, f.original_name)} aria-label={`Download ${f.original_name}`}>Open</button>
      {onRemove && !f.locked && <button type="button" className="btn secondary sm" onClick={onRemove} aria-label={`Remove ${f.original_name}`}>Remove</button>}
    </span>
    <span className={`meta ${f.upload_status === 'COMPLETE' ? 'ok' : ''}`}>
      {(extOf(f.original_name).slice(1) || 'file').toUpperCase()} · {fileSize(f.size_bytes)} · {f.locked ? 'Submitted (locked)' : f.upload_status === 'PENDING_APPROVAL' ? 'Awaiting RE/DRE approval' : 'Uploaded'}
      {f.version_no > 1 && ` · version ${f.version_no}`} · {f.uploaded_by_name || 'you'} · {fmtDate(f.uploaded_at)}
    </span>
  </li>;
}

/**
 * Evidence beside a remark/comment (UI design s.14): camera, gallery and file selection, progress, cancel, retry without duplicates,
 * preview/download, remove before submission. The typed remark lives in the parent and is never lost when an upload fails.
 */
export default function EvidencePanel({ title = 'Supporting evidence', files, target, canEdit, policy, onFiles, onBusy, extraFields, emptyText = 'No files attached.' }: {
  title?: string; files: Evidence[]; target: () => Promise<string>; canEdit: boolean; policy?: UploadPolicy | null;
  onFiles: (f: Evidence[]) => void; onBusy?: (busy: boolean) => void; extraFields?: Record<string, string | number | undefined>; emptyText?: string;
}) {
  const pol = policy || DEFAULT_POLICY;
  const [queue, setQueue] = useState<Q[]>([]);
  const [err, setErr] = useState('');
  const cam = useRef<HTMLInputElement>(null), gal = useRef<HTMLInputElement>(null), any = useRef<HTMLInputElement>(null);
  const live = useRef(files); live.current = files;
  useEffect(() => { onBusy?.(queue.some(q => q.status === 'uploading')); }, [queue]);
  const patch = (key: string, p: Partial<Q>) => setQueue(qs => qs.map(q => (q.key === key ? { ...q, ...p } : q)));

  async function start(q: Q) {
    let path: string;
    try { path = await target(); } catch (e: any) { patch(q.key, { status: 'failed', error: e.message }); return; }
    const h = uploadWithProgress(path, q.file, { upload_token: q.token, ...(extraFields || {}) }, pct => patch(q.key, { pct }));
    patch(q.key, { status: 'uploading', pct: 0, error: undefined, handle: h });
    try {
      const saved: Evidence = await h.promise;
      setQueue(qs => qs.filter(x => x.key !== q.key));
      if (!live.current.some(f => f.id === saved.id)) onFiles([...live.current, saved]);
    } catch (e: any) {
      if (e.cancelled) setQueue(qs => qs.filter(x => x.key !== q.key));
      else patch(q.key, { status: 'failed', error: e.message, handle: undefined });
    }
  }
  function pick(list: FileList | null) {
    setErr('');
    if (!list?.length) return;
    const room = pol.max_files_per_record - files.length - queue.length;
    const chosen = Array.from(list);
    if (chosen.length > room) setErr(`Only ${Math.max(0, room)} more file(s) can be added (limit ${pol.max_files_per_record}).`);
    for (const f of chosen.slice(0, Math.max(0, room))) {
      const ext = extOf(f.name);
      const q: Q = { key: newToken(), file: f, token: newToken(), status: 'uploading', pct: 0 };
      if (!pol.allowed_extensions.includes(ext)) { setQueue(qs => [...qs, { ...q, status: 'failed', error: `${ext || 'This file type'} is not allowed. Allowed: ${pol.allowed_extensions.join(', ')}` }]); continue; }
      if (f.size > pol.max_file_mb * 1048576) { setQueue(qs => [...qs, { ...q, status: 'failed', error: `Larger than the ${pol.max_file_mb} MB limit (${fileSize(f.size)})` }]); continue; }
      if (f.size === 0) { setQueue(qs => [...qs, { ...q, status: 'failed', error: 'The file is empty' }]); continue; }
      setQueue(qs => [...qs, q]); start(q);
    }
    [cam, gal, any].forEach(r => { if (r.current) r.current.value = ''; });
  }
  async function remove(f: Evidence) {
    if (!confirm(`Remove "${f.original_name}" before submission?`)) return;
    try { await api(`/evidence/files/${f.id}`, { method: 'DELETE' }); onFiles(live.current.filter(x => x.id !== f.id)); } catch (e: any) { alert(e.message); }
  }
  const images = pol.allowed_extensions.filter(e => ['.jpg', '.jpeg', '.png', '.webp', '.heic'].includes(e));
  const imgAccept = images.length ? images.join(',') + ',image/*' : '';
  return <section className="evidence" aria-label={title}>
    <h4>{title}</h4>
    {canEdit && <>
      <div className="ev-pickers">
        {imgAccept && <button type="button" className="ev-pick" onClick={() => cam.current?.click()}>Camera<small>Take photo</small></button>}
        {imgAccept && <button type="button" className="ev-pick" onClick={() => gal.current?.click()}>Gallery<small>Choose photo</small></button>}
        <button type="button" className="ev-pick" onClick={() => any.current?.click()}>Files<small>Browse device</small></button>
      </div>
      <input ref={cam} className="sr-only" type="file" accept={imgAccept} capture="environment" onChange={e => pick(e.target.files)} tabIndex={-1} aria-hidden="true" />
      <input ref={gal} className="sr-only" type="file" accept={imgAccept} multiple onChange={e => pick(e.target.files)} tabIndex={-1} aria-hidden="true" />
      <input ref={any} className="sr-only" type="file" accept={pol.allowed_extensions.join(',')} multiple onChange={e => pick(e.target.files)} tabIndex={-1} aria-hidden="true" />
      <div className="ev-hint">{pol.allowed_extensions.join(' ').toUpperCase().replaceAll('.', '')} · up to {pol.max_file_mb} MB each · max {pol.max_files_per_record} files. If the camera is unavailable or permission is denied, use Gallery or Files.</div>
    </>}
    {err && <div className="field-err" role="alert">{err}</div>}
    <ul className="ev-list" aria-live="polite">
      {files.map(f => <FileRow key={f.id} f={f} onRemove={canEdit ? () => remove(f) : undefined} />)}
      {queue.map(q => <li key={q.key} className={`ev-item${q.status === 'failed' ? ' failed' : ''}`}>
        <span className="nm" title={q.file.name}>{q.file.name}</span>
        <span className="acts">
          {q.status === 'uploading' && <button type="button" className="btn secondary sm" onClick={() => q.handle?.abort()}>Cancel</button>}
          {q.status === 'failed' && !q.error?.includes('not allowed') && !q.error?.includes('limit') && !q.error?.includes('empty') && <button type="button" className="btn sm" onClick={() => start(q)}>Retry</button>}
          {q.status === 'failed' && <button type="button" className="btn secondary sm" onClick={() => setQueue(qs => qs.filter(x => x.key !== q.key))}>Dismiss</button>}
        </span>
        {q.status === 'uploading' && <span className="progress" role="progressbar" aria-valuenow={q.pct} aria-valuemin={0} aria-valuemax={100} aria-label={`Uploading ${q.file.name}`}><span style={{ width: `${q.pct}%` }} /></span>}
        <span className={`meta ${q.status === 'failed' ? 'bad' : ''}`}>{fileSize(q.file.size)} · {q.status === 'uploading' ? `Uploading ${q.pct}%` : `Upload failed: ${q.error}`}</span>
      </li>)}
    </ul>
    {!files.length && !queue.length && <div className="muted" style={{ fontSize: 13, marginTop: 8 }}>{emptyText}</div>}
  </section>;
}
