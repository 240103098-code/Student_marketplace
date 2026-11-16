import React, { useEffect, useId, useRef } from 'react';
import { createPortal } from 'react-dom';
import { Button } from './Button.jsx';

const FOCUSABLE = 'a[href],button:not(:disabled),input:not(:disabled):not([type="hidden"]),select:not(:disabled),textarea:not(:disabled),[tabindex]:not([tabindex="-1"])';

/**
 * Reusable modal. role="dialog", aria-modal, labelled by its heading, focus moves in on open and is trapped,
 * Esc and backdrop click close it, body scroll is locked, and focus returns to the opener on close.
 * It renders nothing when `open` is false.
 */
export function Dialog({ open, onClose, title, children, actions, closeLabel = 'Close', initialFocusRef }) {
  const headingId = useId();
  const panel = useRef(null);
  const close = useRef(onClose);
  close.current = onClose;
  useEffect(() => {
    if (!open) return undefined;
    const opener = document.activeElement;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const focusable = () => [...(panel.current?.querySelectorAll(FOCUSABLE) ?? [])];
    (initialFocusRef?.current ?? focusable()[0] ?? panel.current)?.focus();
    function keys(event) {
      if (event.key === 'Escape') { event.preventDefault(); close.current?.(); return; }
      if (event.key !== 'Tab') return;
      const items = focusable();
      if (!items.length) { event.preventDefault(); panel.current?.focus(); return; }
      const first = items[0];
      const last = items[items.length - 1];
      const inside = panel.current?.contains(document.activeElement);
      if (event.shiftKey && (document.activeElement === first || !inside)) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && (document.activeElement === last || !inside)) { event.preventDefault(); first.focus(); }
    }
    document.addEventListener('keydown', keys);
    return () => {
      document.removeEventListener('keydown', keys);
      document.body.style.overflow = previousOverflow;
      if (opener && opener.isConnected && typeof opener.focus === 'function') opener.focus();
    };
  }, [open, initialFocusRef]);
  if (!open) return null;
  return createPortal(
    <div className="dialog-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) close.current?.(); }}>
      <div ref={panel} className="dialog" role="dialog" aria-modal="true" aria-labelledby={headingId} tabIndex={-1}>
        <div className="dialog__head">
          <h2 className="dialog__title" id={headingId}>{title}</h2>
          <Button variant="ghost" aria-label={closeLabel} onClick={() => close.current?.()}>
            <svg className="menu-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18" /></svg>
          </Button>
        </div>
        <div className="dialog__body">{children}</div>
        {actions && <div className="dialog__actions">{actions}</div>}
      </div>
    </div>,
    document.body,
  );
}
