import React from 'react';

/** Decorative placeholder shapes. They are aria-hidden: wrap them in <Loading> to announce one "Loading" status. */
export function Skeleton({ shape = 'line', lines = 1, height }) {
  if (shape === 'card') {
    return (
      <div className="skeleton-card" aria-hidden="true">
        <span className="skeleton skeleton--block" style={{ '--skeleton-height': '120px' }} />
        <Skeleton shape="line" lines={3} />
      </div>
    );
  }
  if (shape === 'block') {
    return <span className="skeleton skeleton--block" aria-hidden="true" style={height ? { '--skeleton-height': typeof height === 'number' ? `${height}px` : height } : undefined} />;
  }
  return (
    <span aria-hidden="true" style={{ display: 'block' }}>
      {Array.from({ length: lines }, (_, index) => <span key={index} className="skeleton skeleton--line" />)}
    </span>
  );
}

/** One accessible status for a group of skeletons. Reserve the same space as the real content to avoid layout jump. */
export function Loading({ label = 'Loading', children }) {
  return (
    <div role="status">
      <span className="sr-only">{label}</span>
      {children}
    </div>
  );
}
