import React from 'react';
import { PriceTag } from './PriceTag.jsx';

/** Inline-SVG illustration (no image requests): a paper slip with a perforation and a price tag. */
export function EmptyArt() {
  return (
    <svg className="state-card__art" viewBox="0 0 96 72" aria-hidden="true" focusable="false">
      <rect className="art-paper" x="8" y="8" width="64" height="56" rx="6" />
      <path className="art-line" d="M24 8v56" />
      <rect className="art-accent" x="34" y="20" width="26" height="6" rx="2" />
      <rect className="art-accent" x="34" y="34" width="18" height="6" rx="2" />
      <circle className="art-accent" cx="76" cy="52" r="12" />
    </svg>
  );
}

export function EmptyState({ title, children, action, headingLevel = 2, showTag = true }) {
  const Heading = `h${headingLevel}`;
  return (
    <div className="state-card">
      <EmptyArt />
      {showTag && <PriceTag amount="0" decorative />}
      <Heading>{title}</Heading>
      {children && <p>{children}</p>}
      {action && <div className="state-card__actions">{action}</div>}
    </div>
  );
}
