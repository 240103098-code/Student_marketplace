import React, { useEffect, useRef } from 'react';
import { Button } from './Button.jsx';

const MARKS = { info: 'i', success: '✓', error: '!' };
export const MIN_VISIBLE_MS = 6000;

/**
 * Inline notice or, with `floating`, a non-blocking toast.
 * Error uses role="alert", other tones role="status". It never dismisses itself earlier than 6 seconds.
 */
export function Notice({ tone = 'info', title, children, onDismiss, dismissLabel = 'Dismiss notice', floating = false, autoDismissMs, className = '' }) {
  const dismiss = useRef(onDismiss);
  dismiss.current = onDismiss;
  useEffect(() => {
    if (!autoDismissMs || !dismiss.current) return undefined;
    const timer = setTimeout(() => dismiss.current?.(), Math.max(autoDismissMs, MIN_VISIBLE_MS));
    return () => clearTimeout(timer);
  }, [autoDismissMs]);
  return (
    <div className={`notice notice--${tone} ${floating ? 'notice--floating' : ''} ${className}`.trim()} role={tone === 'error' ? 'alert' : 'status'}>
      <span className="notice__mark" aria-hidden="true"><span>{MARKS[tone] ?? MARKS.info}</span></span>
      <div className="notice__body">
        {title && <strong className="notice__title">{title}</strong>}
        {children}
      </div>
      {onDismiss && (
        <Button variant="ghost" className="notice__dismiss" aria-label={dismissLabel} onClick={onDismiss}>
          <svg className="menu-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18" /></svg>
        </Button>
      )}
    </div>
  );
}

export function Toast(props) { return <Notice {...props} floating />; }
