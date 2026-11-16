import React from 'react';

const TONES = {
  pending: { label: 'Pending', mark: '…' },
  active: { label: 'Active', mark: '✓' },
  sold: { label: 'Sold', mark: '■' },
  rejected: { label: 'Rejected', mark: '✕' },
  removed: { label: 'Removed', mark: '–' },
};

export const STATUS_TONES = Object.keys(TONES);

/** Stamp-like status badge. The status is always visible text plus a glyph and border style, never colour alone. */
export function StatusBadge({ status, children, className = '' }) {
  const tone = TONES[status];
  const text = children ?? tone?.label ?? String(status ?? '');
  return (
    <span className={`status-badge ${className}`.trim()} data-tone={tone ? status : 'neutral'}>
      <span className="status-badge__mark" aria-hidden="true">{tone?.mark ?? '•'}</span>
      <span>{text}</span>
    </span>
  );
}
