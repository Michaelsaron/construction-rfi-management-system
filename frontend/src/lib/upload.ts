import { API_BASE, authHeaders, requestId } from './api';

export type UploadHandle = { promise: Promise<any>; abort: () => void };

/** Multipart upload with progress and cancellation (XMLHttpRequest). The upload token makes a retry idempotent:
 *  the server returns the already stored file instead of creating a duplicate. */
export function uploadWithProgress(path: string, file: File, fields: Record<string, string | number | undefined>, onProgress: (pct: number) => void): UploadHandle {
  const xhr = new XMLHttpRequest();
  const promise = new Promise<any>((resolve, reject) => {
    xhr.open('POST', `${API_BASE}${path}`);
    xhr.withCredentials = true;
    const h: Record<string, string> = {};
    authHeaders('POST', h);
    Object.entries(h).forEach(([k, v]) => xhr.setRequestHeader(k, v));
    xhr.upload.onprogress = e => { if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100)); };
    xhr.onload = () => {
      let body: any = null;
      try { body = JSON.parse(xhr.responseText); } catch { /* not JSON */ }
      if (xhr.status >= 200 && xhr.status < 300) resolve(body);
      else {
        const d = body?.detail;
        reject(new Error(typeof d === 'string' ? d : xhr.status === 413 ? 'The file is larger than the allowed size' : `Upload failed (${xhr.status || 'network'})`));
      }
    };
    xhr.onerror = () => reject(new Error('Network interruption: the upload did not complete. Your text is kept; retry when the connection is back.'));
    xhr.onabort = () => reject(Object.assign(new Error('Upload cancelled'), { cancelled: true }));
    const fd = new FormData();
    fd.append('file', file);
    Object.entries(fields).forEach(([k, v]) => { if (v !== undefined && v !== null && v !== '') fd.append(k, String(v)); });
    xhr.send(fd);
  });
  return { promise, abort: () => xhr.abort() };
}

export const newToken = () => requestId().replace(/-/g, '');
export const fileSize = (b: number) => (b >= 1048576 ? `${(b / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(b / 1024))} KB`);
export const extOf = (n: string) => (n.includes('.') ? '.' + n.split('.').pop()!.toLowerCase() : '');
