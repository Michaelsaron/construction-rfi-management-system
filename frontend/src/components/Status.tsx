import React from 'react';

const TONE: Record<string, string> = {
  APPROVED: 'success', COMPLETED: 'success', ACCEPTED: 'success', ACTIVE: 'info', CONFIRMED: 'success',
  REJECTED: 'danger', RETURNED: 'danger', CANCELLED: 'danger', OVERDUE: 'danger', REPLACED: 'neutral',
  AWAITING_DECISION: 'warn', PENDING: 'warn', PARTIALLY_APPROVED: 'warn', SHORT_NOTICE: 'warn',
  SUBMITTED: 'info', ACTIVATED: 'info', UNDER_REVIEW: 'info', ON_PROGRESS: 'info', REVIEWED: 'info',
  INFORMATION_ONLY: 'neutral', DRAFT: 'neutral', ARCHIVED: 'neutral', LEGACY: 'neutral',
};
const LABEL: Record<string, string> = {
  UNDER_REVIEW: 'Under Inspector Review', AWAITING_DECISION: 'Awaiting Final Decision', ACTIVATED: 'Received',
  ARCHIVED: 'Legacy – no decision', ACTIVE: 'Current turn', PENDING: 'Waiting turn', REPLACED: 'Replaced',
};

export const pretty = (v: any) => LABEL[String(v ?? '').toUpperCase()] ||
  String(v ?? '').replaceAll('_', ' ').toLowerCase().replace(/\b\w/g, c => c.toUpperCase());

/** Coloured status pill. Text label always present, so meaning never relies on colour alone. */
export default function Status({ value, label }: { value?: string | null; label?: string }) {
  if (!value) return <span className="muted">—</span>;
  const tone = TONE[String(value).toUpperCase()] || 'neutral';
  return <span className={`status s-${tone}`}>{label || pretty(value)}</span>;
}
