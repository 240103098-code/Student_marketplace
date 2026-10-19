import {FormIntro} from './StudentUI.jsx';
import {retryGuidance} from './api.js';
import React, { useEffect, useRef, useState } from 'react';
import { ApiError, postJson, universityEmail } from './api.js';

function Feedback({ message, error = false }) {
  return message ? <p className={`form-feedback ${error ? 'error' : ''}`} role={error ? 'alert' : 'status'}>{message}</p> : null;
}

function requestError(error, mode) {
  if(error.status===429)return retryGuidance(error);
  if (error.status === 503) return 'Email delivery is unavailable right now. Please try again later.';
  if (mode === 'register' && error.status === 409) return 'This email is already registered. You can go to verification or sign in.';
  if (mode === 'verify' && error.status === 400) return 'The code could not be accepted. Check your details or request a new code when available. Codes last ten minutes; after five incorrect attempts you need a replacement.';
  if (error.status === 422) return 'Check the email and required fields, then try again.';
  if (error.kind === 'network') return 'The request could not be confirmed. Check your connection and try again.';
  return 'The request could not be confirmed. Please try again.';
}

export function RegistrationForm({ onRegistered, navigate }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const busy = useRef(false);

  async function submit(event) {
    event.preventDefault();
    if (busy.current) return;
    const normalized = universityEmail(email);
    if (!normalized) return setError('Enter your sdu.edu.kz university email.');
    const length = Array.from(password).length;
    if (length < 12 || length > 128) return setError('Use a password of 12–128 characters. Spaces are kept as entered.');
    busy.current = true;
    setPending(true);
    setError('');
    try {
      const result = await postJson('/auth/register', { email: normalized, password });
      if (result.status !== 201 || universityEmail(result.data?.email || '') !== normalized || result.data?.verified !== false) throw new ApiError('response');
      setPassword('');
      onRegistered(normalized, Date.now() + 60_000);
    } catch (failure) {
      setError(requestError(failure, 'register'));
    } finally {
      busy.current = false;
      setPending(false);
    }
  }

  return (
    <form className="account-form" onSubmit={submit} noValidate aria-label="Registration" aria-busy={pending}><FormIntro title="University account">Register with your own sdu.edu.kz address and verify it by email.</FormIntro>
      <label htmlFor="register-email">University email</label>
      <input id="register-email" type="email" autoComplete="email" value={email} onChange={event => setEmail(event.target.value)} disabled={pending} aria-describedby="register-email-help" required />
      <p id="register-email-help" className="field-help">Use your sdu.edu.kz address.</p>
      <label htmlFor="register-password">Password</label>
      <input id="register-password" type="password" autoComplete="new-password" value={password} onChange={event => setPassword(event.target.value)} disabled={pending} aria-describedby="password-help" required />
      <p id="password-help" className="field-help">12–128 characters. No special character rule; spaces are kept.</p>
      <Feedback message={error} error />
      <Feedback message={pending ? 'Creating your account…' : ''} />
      <button className="button primary" disabled={pending} type="submit">{pending ? 'Creating account…' : 'Create account'}</button>
      <p className="form-links"><a href="/verify" onClick={navigate}>Already have a code? Verify email</a></p>
    </form>
  );
}

export function VerificationForm({ initialEmail, cooldowns, onCooldown, navigate }) {
  const [email, setEmail] = useState(initialEmail || '');
  const [code, setCode] = useState('');
  const [pending, setPending] = useState('');
  const [feedback, setFeedback] = useState('');
  const [error, setError] = useState('');
  const [verified, setVerified] = useState(false);
  const [now, setNow] = useState(Date.now());
  const busy = useRef(false);
  const normalized = universityEmail(email);
  const deadline = cooldowns[normalized] || 0;
  const remaining = Math.max(0, Math.ceil((deadline - now) / 1000));

  useEffect(() => {
    setNow(Date.now());
    if (deadline <= Date.now()) return undefined;
    const timer = setInterval(() => {
      const current = Date.now();
      setNow(current);
      if (current >= deadline) clearInterval(timer);
    }, 1000);
    return () => clearInterval(timer);
  }, [deadline]);

  async function request(mode, event) {
    event?.preventDefault();
    if (busy.current || (mode === 'resend' && remaining > 0)) return;
    const address = universityEmail(email);
    if (!address) return setError('Enter your sdu.edu.kz university email.');
    if (mode === 'verify' && !/^[0-9]{6}$/.test(code)) return setError('Enter exactly six digits from 0 to 9.');
    busy.current = true;
    setPending(mode);
    setError('');
    setFeedback('');
    try {
      const result = await postJson(mode === 'verify' ? '/auth/verify-email' : '/auth/resend-verification', mode === 'verify' ? { email: address, code } : { email: address });
      if (mode === 'verify') {
        if (result.status !== 200 || result.data?.verified !== true) throw new ApiError('response');
        setVerified(true);
        setCode('');
      } else {
        if (result.status !== 202) throw new ApiError('response');
        onCooldown(address, Date.now() + result.retryAfter * 1000);
        setFeedback('If this address is eligible, a verification email may arrive. Check your inbox before requesting another.');
      }
    } catch (failure) {
      setError(requestError(failure, mode));
    } finally {
      busy.current = false;
      setPending('');
    }
  }

  if (verified) return <section className="verification-success"><Feedback message="Your university email is verified." /><a className="button primary" href="/login" onClick={navigate}>Continue to sign in</a></section>;

  return (
    <form className="account-form" onSubmit={event => request('verify', event)} noValidate aria-label="Email verification" aria-busy={!!pending}><FormIntro title="Email confirmation">Enter the code from your inbox. Requests never guarantee delivery.</FormIntro>
      <label htmlFor="verify-email">University email</label>
      <input id="verify-email" type="email" autoComplete="email" value={email} onChange={event => setEmail(event.target.value)} disabled={!!pending} required />
      <label htmlFor="verify-code">Verification code</label>
      <input id="verify-code" type="text" inputMode="numeric" autoComplete="one-time-code" maxLength={6} value={code} onChange={event => setCode(event.target.value)} disabled={!!pending} aria-describedby="code-help" required />
      <p id="code-help" className="field-help">Codes last ten minutes. After five incorrect attempts, request a new code.</p>
      <Feedback message={error} error />
      <Feedback message={feedback} />
      <Feedback message={pending ? pending === 'verify' ? 'Checking your code…' : 'Requesting a verification email…' : ''} />
      <div className="actions form-actions">
        <button className="button primary" type="submit" disabled={!!pending}>{pending === 'verify' ? 'Checking code…' : 'Verify email'}</button>
        <button className="button secondary" type="button" disabled={!!pending || remaining > 0} onClick={() => request('resend')}>{pending === 'resend' ? 'Requesting email…' : 'Request new code'}</button>
      </div>
      {remaining > 0 && <p className="field-help countdown" role="timer" aria-live="off">You can request another code in {remaining} {remaining === 1 ? 'second' : 'seconds'}.</p>}
      <p className="form-links"><a href="/login" onClick={navigate}>Already verified? Go to sign in</a></p>
    </form>
  );
}
