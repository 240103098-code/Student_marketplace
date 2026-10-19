import {retryGuidance} from './api.js';
import React, { useEffect, useRef, useState } from 'react';
import { useAuth } from './Auth.jsx';

export function AvatarControl() {
  const auth = useAuth();
  const [preview, setPreview] = useState(null);
  const [loading, setLoading] = useState(true);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const [feedback, setFeedback] = useState('');
  const [retry, setRetry] = useState(0);
  const busy = useRef(false);
  const objectUrl = useRef(null);
  const input = useRef(null);
  function release() { if (objectUrl.current) URL.revokeObjectURL(objectUrl.current); objectUrl.current = null; }
  useEffect(() => {
    let active = true;
    setLoading(true);
    auth.get('/users/me/avatar', true).then(result => {
      if (!['image/jpeg', 'image/png', 'image/webp'].includes(result.data?.type)) throw new Error();
      if (active) { release(); objectUrl.current = URL.createObjectURL(result.data); setPreview(objectUrl.current); }
    }).catch(failure => {
      if (active) {
        if (failure.status === 404) { release(); setPreview(null); }
        else setError('Your profile photo could not be loaded. Please retry.');
      }
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; release(); };
  }, [auth.get, retry]);
  async function mutate(file) {
    if (busy.current) return;
    if (file && (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type) || file.size > 5*1024*1024)) { setError('Choose JPEG, PNG or WebP up to five MiB.'); return; }
    busy.current = true; setPending(true); setError(''); setFeedback('');
    try {
      const result = await auth.avatar(file);
      if (result.status !== 200) throw new Error();
      if (input.current) input.current.value = '';
      release(); setPreview(null);
      setFeedback(`${file ? 'Profile photo updated.' : 'Profile photo removed.'}${result.data?.cleanup_pending ? ' Old-file cleanup is pending.' : ''}`);
      setRetry(previous => previous+1);
    } catch (failure) { setError(failure.status===429?retryGuidance(failure):failure.status === 400 ? 'Choose a valid JPEG, PNG or WebP image within twenty million pixels.' : failure.status === 413 ? 'Choose an image up to five MiB.' : 'The photo change could not be confirmed. Please try again.'); }
    finally { if (input.current) input.current.value = ''; busy.current = false; setPending(false); }
  }
  return <section className="avatar-control" aria-label="Profile photo">
    <h2>Profile photo</h2>
    {loading ? <p role="status">Loading your photo…</p> : preview ? <img className="avatar-preview" src={preview} alt="Your profile photo" /> : <p>{error ? 'Photo preview is unavailable.' : 'No profile photo.'}</p>}
    <label htmlFor="avatar-file">Upload or replace profile photo</label>
    <input ref={input} id="avatar-file" type="file" accept="image/jpeg,image/png,image/webp" disabled={pending || loading} aria-describedby="avatar-help" onChange={event => { const file = event.target.files?.[0]; if (file) mutate(file); }} />
    <p id="avatar-help" className="field-help">Optional JPEG, PNG or WebP, up to five MiB and twenty million pixels. Uploaded images are validated and metadata removed.</p>
    <button className="button secondary" disabled={pending || loading || !preview} onClick={() => mutate(null)}>Remove photo</button>
    {pending && <p role="status">Updating your photo…</p>}
    {feedback && <p role="status" className="form-feedback">{feedback}</p>}
    {error && <><p role="alert" className="form-feedback error">{error}</p><button className="button secondary" disabled={pending || loading} onClick={() => { setError(''); setRetry(previous => previous+1); }}>Retry loading photo</button></>}
  </section>;
}
