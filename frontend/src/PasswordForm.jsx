import React, { useRef, useState } from 'react';
import { useAuth } from './Auth.jsx';

export function PasswordForm({ onChanged }) {
  const auth = useAuth();
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const busy = useRef(false);
  async function submit(event) {
    event.preventDefault();
    if (busy.current) return;
    if ([current, next].some(value => Array.from(value).length < 12 || Array.from(value).length > 128)) { setError('Passwords must contain 12–128 characters. Spaces are kept.'); return; }
    if (next !== confirmation) { setError('New password and confirmation must match.'); return; }
    busy.current = true; setPending(true); setError('');
    try {
      await auth.changePassword(current, next);
      setCurrent(''); setNext(''); setConfirmation('');
      onChanged();
    } catch (failure) {
      setError(failure.status === 400 ? 'Current password is incorrect. Please try again.' : 'Password change could not be confirmed. Please try again.');
    } finally { busy.current = false; setPending(false); }
  }
  return <form className="account-form" aria-label="Change password" onSubmit={submit} noValidate>
    <label htmlFor="current-password">Current password</label>
    <input id="current-password" type="password" autoComplete="current-password" value={current} onChange={event => setCurrent(event.target.value)} disabled={pending} required />
    <label htmlFor="new-password">New password</label>
    <input id="new-password" type="password" autoComplete="new-password" value={next} onChange={event => setNext(event.target.value)} disabled={pending} required />
    <label htmlFor="confirm-password">Confirm new password</label>
    <input id="confirm-password" type="password" autoComplete="new-password" value={confirmation} onChange={event => setConfirmation(event.target.value)} disabled={pending} required />
    <p className="field-help">Use 12–128 characters. Spaces are kept. All sessions will be signed out after success.</p>
    {error && <p role="alert" className="form-feedback error">{error}</p>}
    {pending && <p role="status">Changing your password…</p>}
    <button className="button primary" disabled={pending}>{pending ? 'Changing password…' : 'Change password'}</button>
  </form>;
}
