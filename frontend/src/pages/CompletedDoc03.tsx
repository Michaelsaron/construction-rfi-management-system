import React, { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api, download, fmtDate, fmtDay } from '../lib/api';
import type { CompletedRecord } from '../lib/contracts';
import { PageHeader, Loading, ErrorNote } from '../components/ui';
import { FileRow, previewFile } from '../components/EvidencePanel';
import { RemarkList } from '../components/RemarkEvidence';
import { fileSize } from '../lib/upload';

const tone = (code?: string) => (code?.startsWith('APPROVED') ? 'green' : code?.startsWith('NOT_APPROVED') ? 'red' : code ? 'blue' : '');

/** Completed DOC_03 · record and evidence (UI design s.11). Read-only for every role. */
export default function CompletedDoc03() {
  const { id } = useParams();
  const [d, setD] = useState<CompletedRecord | null>(null); const [err, setErr] = useState(''); const [open, setOpen] = useState<string>(''); const [busy, setBusy] = useState('');
  useEffect(() => { api(`/rfis/${id}/completed-record`).then(setD).catch(e => setErr(e.message)); }, [id]);
  if (err) return <><PageHeader title="Completed DOC_03" back={{ to: '/completed', label: 'Completed DOC_03' }} /><ErrorNote error={err} /><Link className="link" to={`/rfis/${id}`}>Open the RFI record</Link></>;
  if (!d) return <Loading />;
  const r = d.rfi;
  const get = async (kind: 'pdf' | 'zip') => {
    setBusy(kind);
    await download(kind === 'pdf' ? `/reports/doc03/${id}.pdf` : `/rfis/${id}/evidence-bundle.zip`, kind === 'pdf' ? `DOC03_${r.rfi_number}_rev${r.revision_no}.pdf` : `evidence_${r.rfi_number}_rev${r.revision_no}.zip`);
    setBusy('');
  };
  return <>
    <PageHeader title="Completed DOC_03 · record and evidence" back={{ to: '/completed', label: 'Completed DOC_03' }} actions={<Link className="btn secondary" to={`/rfis/${id}/workflow`}>Workflow</Link>} />
    <div className="card">
      <div className="section-title">
        <h2 style={{ fontSize: 17 }}><span className="mono">{r.rfi_number}</span>{r.revision_no ? ` Rev ${r.revision_no}` : ''} · Finalised {d.finalised_at ? fmtDay(String(d.finalised_at).slice(0, 10)) : '—'}</h2>
        {d.disposition && <span className={`pill ${tone(d.disposition.code)}`}>{d.disposition.label}</span>}
      </div>
      {d.legacy_document && <div className="notice">{d.legacy_document.label}. The historical document has not been migrated into the system.</div>}
      <h3>DOC_03 record sections</h3>
      <div className="table-wrap inset"><table>
        <thead><tr><th>Section</th><th>Recorded content</th><th>Attachments</th><th>Access</th></tr></thead>
        <tbody>{d.sections.map(s => <React.Fragment key={s.key}><tr>
          <td><b>{s.section}</b>{s.by && <div className="muted" style={{ fontSize: 12 }}>{s.by}{s.designation ? ` · ${s.designation}` : ''}{s.at ? ` · ${fmtDate(s.at)}` : ''}</div>}</td>
          <td style={{ whiteSpace: 'pre-wrap', minWidth: 220 }}>{s.content || '—'}{s.remark && <div className="muted">{s.remark}</div>}</td>
          <td className="nowrap">{s.files.length ? `${s.files.length} file${s.files.length > 1 ? 's' : ''}` : '—'}</td>
          <td>{s.files.length ? <button className="linkButton" aria-expanded={open === s.key} onClick={() => setOpen(open === s.key ? '' : s.key)}>{open === s.key ? 'Close' : 'Open'}</button> : <span className="muted">View</span>}</td>
        </tr>{open === s.key && <tr><td colSpan={4}><ul className="ev-list" style={{ margin: 0 }}>{s.files.map(f => <FileRow key={f.id} f={f} />)}</ul></td></tr>}</React.Fragment>)}</tbody>
      </table></div>
      <div className="actions">
        <button className="btn" disabled={!!busy} onClick={() => get('pdf')}>{busy === 'pdf' ? 'Opening…' : 'Open completed DOC_03 PDF'}</button>
        {d.can_download_bundle && <button className="btn success" disabled={!!busy} onClick={() => get('zip')}>{busy === 'zip' ? 'Preparing…' : 'Download evidence bundle'}</button>}
        <span className="muted" style={{ fontSize: 12.5 }}>Every attachment is linked to its author, remark, workflow stage and upload time.</span>
      </div>
      {d.issued_document ? <p className="muted" style={{ fontSize: 12.5 }}>DOC_03 issued {fmtDate(d.issued_document.issued_at)} by {d.issued_document.issued_by_name}. SHA-256 <span className="mono">{d.issued_document.sha256}</span>. The issued PDF is served exactly as issued and is never regenerated.</p>
        : <p className="muted" style={{ fontSize: 12.5 }}>No issued snapshot exists for this revision; the PDF is generated from the record.</p>}
    </div>
    {d.management_remarks.length > 0 && <div className="card"><h3>Management remarks</h3><RemarkList remarks={d.management_remarks} /></div>}
    <div className="card"><h3>Attachment index</h3>{d.attachment_index.length ? <div className="table-wrap"><table>
      <thead><tr><th>#</th><th>Stage</th><th>File</th><th>Added by</th><th>Uploaded</th><th>SHA-256</th><th></th></tr></thead>
      <tbody>{d.attachment_index.map((f, i) => <tr key={f.id}><td>{i + 1}</td><td>{f.stage_label}</td><td>{f.original_name}<div className="muted" style={{ fontSize: 12 }}>{fileSize(f.size_bytes)}{f.version_no > 1 ? ` · version ${f.version_no}` : ''}</div></td>
        <td>{f.uploaded_by_name}<div className="muted" style={{ fontSize: 12 }}>{f.author_role_label}</div></td><td className="nowrap">{fmtDate(f.uploaded_at)}</td>
        <td className="mono" style={{ fontSize: 11.5 }} title={f.sha256 || ''}>{f.sha256 ? f.sha256.slice(0, 16) + '…' : 'not recorded'}</td>
        <td className="nowrap">{f.previewable && <button className="btn secondary sm" onClick={() => previewFile(f)}>Preview</button>} <button className="btn secondary sm" onClick={() => download(`/evidence/files/${f.id}/download`, f.original_name)}>Open</button></td></tr>)}</tbody>
    </table></div> : <div className="empty">No attachments are recorded for this RFI.</div>}</div>
  </>;
}
