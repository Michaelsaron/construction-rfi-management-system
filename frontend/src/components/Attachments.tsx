import React, { useEffect, useState } from 'react';
import { api } from '../lib/api';
import type { Evidence } from '../lib/contracts';
import EvidencePanel from './EvidencePanel';

/** Record attachments (DOC_01 enclosures, batch files, Daily Progress). Inspection evidence uses EvidencePanel on the review / remark. */
export default function Attachments({ entityType, entityId, canUpload = true, title = 'Attachments', note }: { entityType: string; entityId: number; canUpload?: boolean; title?: string; note?: string }) {
  const [rows, setRows] = useState<Evidence[]>([]);
  useEffect(() => { api(`/attachments/${entityType}/${entityId}`).then(setRows).catch(() => {}); }, [entityType, entityId]);
  return <div className="card">
    <EvidencePanel title={title} files={rows} canEdit={canUpload} onFiles={setRows} target={async () => `/attachments/${entityType}/${entityId}`} emptyText="No attachments yet." />
    {note && <p className="muted" style={{ fontSize: 12.5, margin: '8px 0 0' }}>{note}</p>}
  </div>;
}
