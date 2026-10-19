import {FormIntro} from './StudentUI.jsx';
import React, { useEffect, useRef, useState } from 'react';
import { ApiError } from './api.js';
import { useAuth } from './Auth.jsx';
import { profileChangeError } from './profileValidation.js';

const editable = ['name', 'phone', 'telegram_username', 'external_contact_url'];
function formValues(profile) { return Object.fromEntries(editable.map(key => [key, profile[key] ?? ''])); }
function confirmedProfile(data, user) {
  if (data?.id !== user.id || data.email !== user.email || data.verified !== true || editable.some(key => data[key] !== null && typeof data[key] !== 'string')) throw new ApiError('response');
  return data;
}

export function ProfileForm() {
  const auth = useAuth();
  const [baseline, setBaseline] = useState(null);
  const [values, setValues] = useState({});
  const [loading, setLoading] = useState(true);
  const [retry, setRetry] = useState(0);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const [feedback, setFeedback] = useState('');
  const busy = useRef(false);
  useEffect(() => {
    let active = true;
    setLoading(true); setError('');
    auth.get('/users/me').then(result => {
      const profile = confirmedProfile(result.data, auth.user);
      if (active) { setBaseline(profile); setValues(formValues(profile)); }
    }).catch(() => { if (active) setError('Your profile could not be loaded. Please retry.'); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [auth.get, auth.user, retry]);

  const changes = {};
  if (baseline) {
    for (const key of editable) {
      const value = key === 'name' ? values[key].trim() : values[key];
      if (value !== (baseline[key] ?? '')) changes[key] = key !== 'name' && value === '' ? null : value;
    }
  }
  const hasChanges = Object.keys(changes).length > 0;
  function update(key, value) { setValues(previous => ({ ...previous, [key]: value })); setFeedback(''); }
  async function save(event) {
    event.preventDefault();
    if (busy.current || !hasChanges) return;
    const validation = profileChangeError(changes);
    if (validation) { setError(validation); return; }
    busy.current = true; setPending(true); setError(''); setFeedback('');
    try {
      const result = await auth.patch('/users/me', changes);
      const profile = confirmedProfile(result.data, auth.user);
      if (result.status !== 200) throw new ApiError('response');
      setBaseline(profile); setValues(formValues(profile)); setFeedback('Your profile was saved.');
    } catch { setError('Your profile save could not be confirmed. Check your details and try again.'); }
    finally { busy.current = false; setPending(false); }
  }
  if (loading) return <p role="status">Loading your profile…</p>;
  if (!baseline) return <section><p role="alert" className="form-feedback error">{error}</p><button className="button secondary" onClick={() => setRetry(previous => previous + 1)}>Retry loading profile</button></section>;
  return <form className="account-form" aria-label="Own profile" aria-busy={pending} onSubmit={save} noValidate><FormIntro title="Profile and contacts">Your email is verified and fixed. Share only the external contact details you want buyers to use.</FormIntro>
    <label htmlFor="profile-email">Verified university email</label>
    <input id="profile-email" type="email" value={baseline.email} readOnly aria-describedby="profile-email-help" />
    <p id="profile-email-help" className="field-help">Verified. University email cannot be changed.</p>
    <label htmlFor="profile-name">Name</label>
    <input id="profile-name" value={values.name} onChange={event => update('name', event.target.value)} autoComplete="name" aria-describedby="profile-name-help" disabled={pending} />
    <p id="profile-name-help" className="field-help">1–100 characters when provided; surrounding spaces are removed.</p>
    <label htmlFor="profile-phone">Phone</label>
    <input id="profile-phone" type="tel" value={values.phone} onChange={event => update('phone', event.target.value)} autoComplete="tel" aria-describedby="profile-phone-help" disabled={pending} />
    <p id="profile-phone-help" className="field-help">Optional: + followed by 7–15 digits. Leave empty to clear.</p>
    <label htmlFor="profile-telegram">Telegram username</label>
    <input id="profile-telegram" value={values.telegram_username} onChange={event => update('telegram_username', event.target.value)} autoComplete="off" aria-describedby="profile-telegram-help" disabled={pending} />
    <p id="profile-telegram-help" className="field-help">Optional: 5–32 letters, digits, or underscores; omit @.</p>
    <label htmlFor="profile-contact-url">External contact URL</label>
    <input id="profile-contact-url" type="url" value={values.external_contact_url} onChange={event => update('external_contact_url', event.target.value)} autoComplete="off" aria-describedby="profile-url-help" disabled={pending} />
    <p id="profile-url-help" className="field-help">Optional HTTPS link, up to 2048 characters; no login details or spaces. Contacts can all be empty.</p>
    {error && <p role="alert" className="form-feedback error">{error}</p>}
    {feedback && <p role="status" className="form-feedback">{feedback}</p>}
    {pending && <p role="status">Saving your profile…</p>}
    <button className="button primary" disabled={pending || !hasChanges}>{pending ? 'Saving profile…' : 'Save profile'}</button>
    {!hasChanges && !feedback && <p className="field-help">No changes to save.</p>}
  </form>;
}
