import React, { useId } from 'react';

/**
 * Labelled form control. The label is always visible and bound with htmlFor/id, hint and error text are
 * linked through aria-describedby, aria-invalid is set when `error` is given and required is announced as text.
 * `as` may be "input" (default), "textarea" or "select" (options go in children).
 */
export function Field({ label, hint, error, required = false, as: Control = 'input', id, className = '', children, ...controlProps }) {
  const generated = useId();
  const controlId = id ?? `field-${generated}`;
  const hintId = hint ? `${controlId}-hint` : undefined;
  const errorId = error ? `${controlId}-error` : undefined;
  const describedBy = [controlProps['aria-describedby'], hintId, errorId].filter(Boolean).join(' ') || undefined;
  return (
    <div className={`field ${error ? 'has-error' : ''} ${className}`.trim()}>
      <label className="field__label" htmlFor={controlId}>
        {label}
        {required && <><span className="field__required" aria-hidden="true"> *</span><span className="sr-only"> (required)</span></>}
      </label>
      <Control {...controlProps} id={controlId} required={undefined} aria-required={required || undefined} aria-invalid={error ? true : undefined} aria-describedby={describedBy}>{children}</Control>
      {hint && <p className="field__hint" id={hintId}>{hint}</p>}
      {error && <p className="field__error" id={errorId}>{error}</p>}
    </div>
  );
}
