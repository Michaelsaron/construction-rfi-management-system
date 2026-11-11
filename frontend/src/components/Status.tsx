import React from 'react';

const TONE: Record<string, string> = {
  APPROVED: 'success', COMPLETED: 'success', ACCEPTED: 'success', ACTIVE: 'success',
  REJECTED: 'danger', RETURNED: 'danger', CANCELLED: 'danger', OVERDUE: 'danger',
  AWAITING_DECISION: 'warn', PENDING: 'warn', REVISION_REQUIRED: 'warn',
  SUBMITTED: 'info', ACTIVATED: 'info', UNDER_REVIEW: 'info', ON_PROGRESS: 'info', IN_PROGRESS: 'info',
  INFORMATION_ONLY: 'neutral', DRAFT: 'neutral',
};

export const pretty = (v: any) =>
  String(v ?? '').replaceAll('_', ' ').toLowerCase().replace(/\b\w/g, c => c.toUpperCase());

/** Colored status pill. Text label always present, so meaning never relies on color alone. */
export default function Status({ value }: { value?: string | null }) {
  if (!value) return <span className="muted">—</span>;
  const tone = TONE[String(value).toUpperCase()] || 'neutral';
  return <span className={`status s-${tone}`}>{pretty(value)}</span>;
}
