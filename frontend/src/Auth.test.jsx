import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import { App, safeReturnPath } from './App.jsx';
import { createSessionClient } from './Auth.jsx';

const user = { id: 7, email: 'student@sdu.edu.kz', verified: true };
const csrf = 'a'.repeat(64);
const access = token => ({ access_token: token, token_type: 'bearer', expires_in: 900 });
function response(status, data = {}) { return new Response(status === 204 ? null : JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } }); }
function deferred() { let resolve; const promise = new Promise(done => { resolve = done; }); return { promise, resolve }; }
let fetchMock;
function setup(routes = {}) {
  fetchMock.mockImplementation((url, options) => {
    const path = new URL(url).pathname;
    if (routes[path]) return routes[path](options);
    if(path==='/listings')return Promise.resolve(response(200,{items:[],total:0,count:0,limit:20,offset:0}));
    if(path==='/categories')return Promise.resolve(response(200,['Electronics','Clothing','Books','Furniture','Other'].map((label,index)=>({id:index+1,key:['electronics','clothing','books','furniture','other'][index],label}))));
    if (path === '/listings/mine') return Promise.resolve(response(200,{items:[],total:0,count:0,limit:20,offset:0,status:null}));
    if (path === '/auth/csrf') return Promise.resolve(response(401));
    throw new Error('Unexpected test route');
  });
}
function open(path) { window.history.replaceState(null, '', path); render(<App />); }
function loginFields(email = ' Student@SDU.EDU.KZ ', password = ' 1234567890 ') {
  fireEvent.change(screen.getByLabelText('University email'), { target: { value: email } });
  fireEvent.change(screen.getByLabelText('Password'), { target: { value: password } });
}
function submit() { fireEvent.submit(screen.getByRole('form', { name: 'Sign in' })); }
function activeRoutes(extra = {}) {
  return {
    '/auth/csrf': () => Promise.resolve(response(200, { csrf_token: csrf })),
    '/auth/refresh': () => Promise.resolve(response(200, access('restored-secret'))),
    '/auth/me': () => Promise.resolve(response(200, user)),
    '/users/me/avatar': () => Promise.resolve(response(404)),
    '/users/me': () => Promise.resolve(response(200, { ...user, name: null, phone: null, telegram_username: null, external_contact_url: null })), ...extra,
  };
}
beforeEach(() => { fetchMock = vi.fn(); vi.stubGlobal('fetch', fetchMock); });
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

test('login confirms me, keeps credentials private, and returns to the guarded internal route', async () => {
  let hasCookie = false;
  const storage = vi.spyOn(Storage.prototype, 'setItem');
  setup({
    '/auth/csrf': () => Promise.resolve(hasCookie ? response(200, { csrf_token: csrf }) : response(401)),
    '/auth/login': options => { expect(JSON.parse(options.body)).toEqual({ email: user.email, password: ' 1234567890 ' }); hasCookie = true; return Promise.resolve(response(200, access('login-secret'))); },
    '/auth/me': options => { expect(options.headers.Authorization).toBe('Bearer login-secret'); return Promise.resolve(response(200, user)); },
  });
  open('/my-listings');
  await screen.findByRole('heading', { name: 'Sign in' });
  loginFields(); submit();
  await screen.findByRole('heading', { name: 'My Listings' });
  expect(screen.getByRole('button', { name: 'Sign out' })).toBeTruthy();
  expect(screen.queryByRole('link', { name: 'Register' })).toBeNull();
  expect(window.location.pathname).toBe('/my-listings');
  expect(window.location.search).toBe('');
  expect(document.body.textContent).not.toContain('login-secret');
  expect(document.body.textContent).not.toContain(csrf);
  expect(storage).not.toHaveBeenCalled();
  expect(fetchMock.mock.calls.every(([, options]) => options.credentials === 'include')).toBe(true);
});

test('login rejects invalid inputs, prevents pending duplicates, and gives generic safe failures', async () => {
  const pending = deferred();
  setup({ '/auth/login': () => pending.promise });
  open('/login');
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
  loginFields('student@sub.sdu.edu.kz'); submit();
  expect(screen.getByRole('alert').textContent).toContain('sdu.edu.kz');
  for (const password of ['x'.repeat(11), 'x'.repeat(129)]) { loginFields(user.email, password); submit(); expect(screen.getByRole('alert').textContent).toContain('12–128'); }
  expect(fetchMock).toHaveBeenCalledTimes(1);
  loginFields(); submit(); submit();
  expect(screen.getByRole('button', { name: 'Signing in…' }).disabled).toBe(true);
  expect(fetchMock).toHaveBeenCalledTimes(2);
  await act(async () => pending.resolve(response(401, { detail: 'SENSITIVE suspended' })));
  expect(screen.getByRole('alert').textContent).toBe('Invalid credentials or account unavailable.');
  expect(screen.getByRole('link', { name: 'Need to verify your email?' }).getAttribute('href')).toBe('/verify');
  expect(screen.queryByRole('button', { name: 'Sign out' })).toBeNull();
  fetchMock.mockRejectedValueOnce(new Error('SENSITIVE network'));
  submit();
  await screen.findByText('Sign-in could not be confirmed. Please try again.');
});

test('reload shows no protected content until csrf, refresh, and eligibility are confirmed in order', async () => {
  const pending = deferred();
  setup(activeRoutes({ '/auth/csrf': () => pending.promise }));
  open('/profile');
  expect(screen.getByRole('heading', { name: 'Checking your session' })).toBeTruthy();
  expect(screen.queryByText('Your profile tools are being prepared.')).toBeNull();
  await act(async () => pending.resolve(response(200, { csrf_token: csrf })));
  await screen.findByRole('heading', { name: 'Profile' });
  expect(fetchMock.mock.calls.map(([url]) => new URL(url).pathname)).toEqual(['/auth/csrf', '/auth/refresh', '/auth/me', '/users/me/avatar', '/users/me']);
  expect(fetchMock.mock.calls[1][1].headers['X-CSRF-Token']).toBe(csrf);
});

test('ineligible restoration removes protected content with honest session feedback', async () => {
  setup(activeRoutes({ '/auth/me': () => Promise.resolve(response(401)) }));
  open('/marketplace');
  await screen.findByRole('heading', { name: 'Sign in' });
  expect(screen.getByText(/Your session expired or is unavailable/)).toBeTruthy();
  expect(screen.queryByRole('button', { name: 'Sign out' })).toBeNull();
});

test('only exact student return paths are accepted; admin and path tricks remain unavailable', async () => {
  for (const path of ['https://evil.test', '//evil.test', '/%2f%2fevil', '/admin', '/profile?next=evil', '/profile/../admin', '/my-listings/']) expect(safeReturnPath(path)).toBe('/marketplace');
  expect(safeReturnPath('/profile')).toBe('/profile');
  setup(activeRoutes()); open('/admin');
  expect(screen.getByRole('heading', { name: 'Page not found' })).toBeTruthy();
  await screen.findByRole('button', { name: 'Sign out' });
  expect(screen.getByRole('heading', { name: 'Page not found' })).toBeTruthy();
});

test('confirmed sign-out clears navigation only after server success and blocks duplicate clicks', async () => {
  const pending = deferred();
  setup(activeRoutes({ '/auth/logout': options => { expect(options.headers['X-CSRF-Token']).toBe(csrf); return pending.promise; } }));
  open('/marketplace'); await screen.findByRole('heading', { name: 'Marketplace' });
  fireEvent.click(screen.getByRole('button', { name: 'Sign out' }));
  fireEvent.click(screen.getByRole('button', { name: 'Signing out...' }));
  expect(screen.getByRole('heading', { name: 'Marketplace' })).toBeTruthy();
  expect(fetchMock.mock.calls.filter(([url]) => url.endsWith('/auth/logout'))).toHaveLength(1);
  await act(async () => pending.resolve(response(204)));
  await screen.findByRole('heading', { name: 'Sign in' });
  expect(screen.getByText('You have signed out.')).toBeTruthy();
});

test('failed sign-out retains protected access and offers truthful retry without claiming revocation', async () => {
  let attempts = 0;
  setup(activeRoutes({ '/auth/logout': () => { attempts += 1; return attempts === 1 ? Promise.reject(new Error('SECRET')) : Promise.resolve(response(204)); } }));
  open('/marketplace'); await screen.findByRole('heading', { name: 'Marketplace' });
  fireEvent.click(screen.getByRole('button', { name: 'Sign out' }));
  await screen.findByRole('alert');
  expect(screen.getByRole('alert').textContent).toContain('may still be active');
  expect(screen.getByRole('heading', { name: 'Marketplace' })).toBeTruthy();
  expect(screen.queryByText('You have signed out.')).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: 'Sign out' }));
  await screen.findByRole('heading', { name: 'Sign in' });
});

async function restoredClient(routes) {
  setup(activeRoutes(routes));
  const notify = vi.fn(); const client = createSessionClient(notify); await client.restore();
  fetchMock.mockClear(); return { client, notify };
}
test('simultaneous 401 GETs share one refresh and each retry once with the renewed bearer', async () => {
  let refreshes = 0; const pending = deferred();
  const { client } = await restoredClient({
    '/auth/refresh': () => ++refreshes === 1 ? Promise.resolve(response(200, access('restored-secret'))) : pending.promise,
    '/safe-read': options => Promise.resolve(options.headers.Authorization === 'Bearer restored-secret' ? response(401) : response(200, { ok: true })),
  });
  const first = client.get('/safe-read'); const second = client.get('/safe-read');
  await waitFor(() => expect(refreshes).toBe(2));
  pending.resolve(response(200, access('renewed-secret')));
  expect((await first).data).toEqual({ ok: true }); expect((await second).data).toEqual({ ok: true });
  expect(fetchMock.mock.calls.filter(([url]) => url.endsWith('/auth/refresh'))).toHaveLength(1);
  expect(fetchMock.mock.calls.filter(([url]) => url.endsWith('/safe-read'))).toHaveLength(4);
});

test.each([401, 403, 500])('refresh failure %s stops recovery and clears protected state without loops', async status => {
  let rotations = 0;
  const { client, notify } = await restoredClient({
    '/auth/refresh': () => Promise.resolve(++rotations === 1 ? response(200, access('restored-secret')) : response(status)),
    '/safe-read': () => Promise.resolve(response(401)),
  });
  await expect(client.get('/safe-read')).rejects.toHaveProperty('status', status);
  expect(fetchMock.mock.calls).toHaveLength(2);
  expect(notify.mock.lastCall[0].status).toBe('anonymous');
  await expect(client.get('/safe-read')).rejects.toHaveProperty('kind', 'session');
  expect(fetchMock.mock.calls).toHaveLength(2);
});

test('403 GET does not refresh; repeated 401 after refresh is retried once then stops', async () => {
  const { client, notify } = await restoredClient({ '/denied': () => Promise.resolve(response(403)) });
  await expect(client.get('/denied')).rejects.toHaveProperty('status', 403);
  expect(fetchMock.mock.calls).toHaveLength(1); expect(notify.mock.lastCall[0].status).toBe('anonymous');
  const second = await restoredClient({ '/denied': () => Promise.resolve(response(401)) });
  await expect(second.client.get('/denied')).rejects.toHaveProperty('status', 401);
  expect(fetchMock.mock.calls.map(([url]) => new URL(url).pathname)).toEqual(['/denied', '/auth/refresh', '/denied']);
  expect(second.notify.mock.lastCall[0].status).toBe('anonymous');
});
