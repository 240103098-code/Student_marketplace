import React, { useRef, useState } from 'react';
import { universityEmail } from './api.js';
import { useAuth } from './Auth.jsx';

export function LoginForm({ navigate, onSignedIn }) {
  const auth = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const busy = useRef(false);
  async function submit(event) {
    event.preventDefault();
    if (busy.current) return;
    const normalized = universityEmail(email);
    if (!normalized) { setError('Use your sdu.edu.kz university email.'); return; }
    if (Array.from(password).length < 12 || Array.from(password).length > 128) { setError('Use a password of 12–128 characters. Spaces are kept.'); return; }
    busy.current = true; setPending(true); setError('');
    try { await auth.login(normalized, password); setPassword(''); onSignedIn(); }
    catch (failure) { setError(failure.status === 401 ? 'Invalid credentials or account unavailable.' : 'Sign-in could not be confirmed. Please try again.'); }
    finally { busy.current = false; setPending(false); }
  }
  return <form className="account-form" aria-label="Sign in" onSubmit={submit} noValidate>
    <label htmlFor="login-email">University email</label>
    <input id="login-email" type="email" autoComplete="username" value={email} onChange={event => setEmail(event.target.value)} disabled={pending} required />
    <label htmlFor="login-password">Password</label>
    <input id="login-password" type="password" autoComplete="current-password" value={password} onChange={event => setPassword(event.target.value)} disabled={pending} required />
    <p className="field-help">Use 12–128 characters. Spaces are kept.</p>
    {error && <p className="form-feedback error" role="alert">{error}</p>}
    {pending && <p className="form-feedback" role="status">Confirming your sign-in…</p>}
    <button className="button primary" disabled={pending}>{pending ? 'Signing in…' : 'Sign in'}</button>
    <a href="/verify" onClick={navigate}>Need to verify your email?</a>
  </form>;
}
