import {FormIntro} from './StudentUI.jsx';
import {retryGuidance} from './api.js';
import React, { useEffect, useRef, useState } from 'react';
import { ApiError, postJson, universityEmail } from './api.js';
import { useAuth } from './Auth.jsx';

export function RecoveryRequestForm({ initialEmail, cooldowns, onRequested, navigate }) {
  const [email, setEmail] = useState(initialEmail || '');
  const [pending, setPending] = useState(false);
  const [feedback, setFeedback] = useState('');
  const [error, setError] = useState('');
  const [now, setNow] = useState(Date.now());
  const busy = useRef(false);
  const deadline = cooldowns[universityEmail(email)] || 0;
  const remaining = Math.max(0, Math.ceil((deadline - now) / 1000));
  useEffect(() => {
    setNow(Date.now());
    if (deadline <= Date.now()) return undefined;
    const timer = setInterval(() => {
      const current = Date.now(); setNow(current);
      if (current >= deadline) clearInterval(timer);
    }, 1000);
    return () => clearInterval(timer);
  }, [deadline]);
  async function submit(event) {
    event.preventDefault();
    if (busy.current || remaining > 0) return;
    const address = universityEmail(email);
    if (!address) { setError('Enter your sdu.edu.kz university email.'); return; }
    busy.current = true; setPending(true); setError(''); setFeedback('');
    try {
      const result = await postJson('/auth/forgot-password', { email: address });
      if (result.status !== 202) throw new ApiError('response');
      onRequested(address, Date.now() + result.retryAfter * 1000);
      setFeedback('If this address is eligible, a password-reset email may arrive. Check your inbox; this response does not guarantee delivery.');
    } catch (failure) { setError(failure.status===429?retryGuidance(failure):'The recovery request could not be confirmed. Please try again.'); }
    finally { busy.current = false; setPending(false); }
  }
  return <form className="account-form" aria-label="Password recovery" aria-busy={pending} onSubmit={submit} noValidate><FormIntro title="Request a reset code">Only an eligible verified account can receive an email.</FormIntro>
    <label htmlFor="recovery-email">University email</label>
    <input id="recovery-email" type="email" autoComplete="email" value={email} onChange={event => setEmail(event.target.value)} disabled={pending} required />
    {error && <p role="alert" className="form-feedback error">{error}</p>}
    {feedback && <p role="status" className="form-feedback">{feedback}</p>}
    {pending && <p role="status">Requesting recovery…</p>}
    <button className="button primary" disabled={pending || remaining > 0}>{pending ? 'Requesting code…' : 'Request reset code'}</button>
    {remaining > 0 && <p role="timer" aria-live="off" className="field-help">You can request another code in {remaining} {remaining === 1 ? 'second' : 'seconds'}.</p>}
    <a href="/reset-password" onClick={navigate}>Already have a code? Reset password</a>
    <a href="/login" onClick={navigate}>Back to sign in</a>
  </form>;
}

export function ResetPasswordForm({ initialEmail, navigate, onReset }) {
  const auth = useAuth();
  const [email, setEmail] = useState(initialEmail || '');
  const [code, setCode] = useState('');
  const [password, setPassword] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const busy = useRef(false);
  async function submit(event) {
    event.preventDefault();
    if (busy.current) return;
    const address = universityEmail(email);
    if (!address) { setError('Enter your sdu.edu.kz university email.'); return; }
    if (!/^[0-9]{6}$/.test(code)) { setError('Enter exactly six digits from 0 to 9.'); return; }
    if (Array.from(password).length < 12 || Array.from(password).length > 128) { setError('Use a password of 12–128 characters. Spaces are kept.'); return; }
    if (password !== confirmation) { setError('New password and confirmation must match.'); return; }
    busy.current = true; setPending(true); setError('');
    try {
      await auth.resetPassword(address, code, password);
      setCode(''); setPassword(''); setConfirmation(''); onReset();
    } catch (failure) {
      setError(failure.status === 400 ? 'The reset code could not be accepted. Check your details or request a replacement. Codes last ten minutes; after five incorrect attempts you need a new code.' : 'Password reset could not be confirmed. Please try again.');
    } finally { busy.current = false; setPending(false); }
  }
  return <form className="account-form" aria-label="Password reset" aria-busy={pending} onSubmit={submit} noValidate><FormIntro title="Choose a new password">Use the recovery code sent to your university inbox.</FormIntro>
    <label htmlFor="reset-email">University email</label>
    <input id="reset-email" type="email" autoComplete="email" value={email} onChange={event => setEmail(event.target.value)} disabled={pending} required />
    <label htmlFor="reset-code">Reset code</label>
    <input id="reset-code" inputMode="numeric" autoComplete="one-time-code" maxLength={6} value={code} onChange={event => setCode(event.target.value)} disabled={pending} required />
    <label htmlFor="reset-password">New password</label>
    <input id="reset-password" type="password" autoComplete="new-password" value={password} onChange={event => setPassword(event.target.value)} disabled={pending} required />
    <label htmlFor="reset-confirmation">Confirm new password</label>
    <input id="reset-confirmation" type="password" autoComplete="new-password" value={confirmation} onChange={event => setConfirmation(event.target.value)} disabled={pending} required />
    <p className="field-help">12–128 characters; spaces are kept. A successful reset signs out all account sessions.</p>
    {error && <p role="alert" className="form-feedback error">{error}</p>}
    {pending && <p role="status">Resetting your password…</p>}
    <button className="button primary" disabled={pending}>{pending ? 'Resetting password…' : 'Reset password'}</button>
    <a href="/forgot-password" onClick={navigate}>Request a replacement code</a>
    <a href="/login" onClick={navigate}>Back to sign in</a>
  </form>;
}
