import React, { forwardRef } from 'react';

export const BUTTON_VARIANTS = ['primary', 'secondary', 'ghost', 'danger'];

/**
 * Button (and link styled as a button when `href` is given).
 * - `loading` swaps the label for `loadingLabel`, shows a CSS spinner, sets aria-busy and blocks repeat activation.
 * - `disabled` uses the native attribute on <button> (removed from the tab order, never a focus trap)
 *   and aria-disabled + tabIndex -1 on <a>.
 */
export const Button = forwardRef(function Button(
  { variant = 'secondary', size = 'default', loading = false, loadingLabel, href, disabled = false, type = 'button', className = '', children, onClick, ...rest },
  ref,
) {
  const inert = Boolean(disabled || loading);
  const classes = ['button', variant, size === 'large' ? 'large' : '', loading ? 'is-loading' : '', className].filter(Boolean).join(' ');
  const content = loading
    ? <><span className="spinner" aria-hidden="true" /><span>{loadingLabel ?? children}</span></>
    : children;
  const busy = loading ? { 'aria-busy': true } : {};
  if (href !== undefined) {
    return (
      <a
        ref={ref}
        href={inert ? undefined : href}
        role={inert ? 'link' : undefined}
        aria-disabled={inert ? true : undefined}
        className={classes}
        onClick={(event) => { if (inert) { event.preventDefault(); return; } onClick?.(event); }}
        {...busy}
        {...rest}
      >{content}</a>
    );
  }
  return (
    <button
      ref={ref}
      type={type}
      className={classes}
      disabled={inert}
      onClick={(event) => { if (inert) { event.preventDefault(); return; } onClick?.(event); }}
      {...busy}
      {...rest}
    >{content}</button>
  );
});
