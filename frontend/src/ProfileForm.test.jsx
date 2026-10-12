import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import { App } from './App.jsx';

const emptyProfile = { id: 1, email: 'student@sdu.edu.kz', verified: true, name: null, phone: null, telegram_username: null, external_contact_url: null };
let fetchMock;
function response(status, data = {}) { return new Response(JSON.stringify(data), { status }); }
function setup({ profile = emptyProfile, load, save } = {}) {
  fetchMock.mockImplementation((url, options) => {
    const path = new URL(url).pathname;
    if (path === '/auth/csrf') return Promise.resolve(response(200, { csrf_token: 'a'.repeat(64) }));
    if (path === '/auth/refresh') return Promise.resolve(response(200, { access_token: 'secret-access', token_type: 'bearer', expires_in: 900 }));
    if (path === '/auth/me') return Promise.resolve(response(200, { id: 1, email: profile.email, verified: true }));
    if (path === '/users/me/avatar') return Promise.resolve(response(404));
    if (path === '/users/me' && options.method === 'GET') return load ? load(options) : Promise.resolve(response(200, profile));
    if (path === '/users/me' && options.method === 'PATCH') return save ? save(options) : Promise.resolve(response(200, { ...profile, ...JSON.parse(options.body) }));
    throw new Error('Unexpected test route');
  });
}
async function open() { window.history.replaceState(null, '', '/profile'); render(<App />); await screen.findByRole('form', { name: 'Own profile' }); }
function change(label, value) { fireEvent.change(screen.getByLabelText(label), { target: { value } }); }
function submit() { fireEvent.submit(screen.getByRole('form', { name: 'Own profile' })); }
function patches() { return fetchMock.mock.calls.filter(([, options]) => options.method === 'PATCH'); }
beforeEach(() => { fetchMock = vi.fn(); vi.stubGlobal('fetch', fetchMock); });
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

test('profile load has a clear loading state, safe retry, null fields and read-only verified identity', async () => {
  let finish; let attempts = 0;
  setup({ load: () => ++attempts === 1 ? new Promise(resolve => { finish = resolve; }) : Promise.resolve(response(200, emptyProfile)) });
  window.history.replaceState(null, '', '/profile'); render(<App />);
  await screen.findByText('Loading your profile…');
  expect(screen.queryByLabelText('Name')).toBeNull();
  await act(async () => finish(response(500, { detail: 'SENSITIVE_DRIVER' })));
  expect(screen.getByRole('alert').textContent).toBe('Your profile could not be loaded. Please retry.');
  fireEvent.click(screen.getByRole('button', { name: 'Retry loading profile' }));
  await screen.findByRole('form', { name: 'Own profile' });
  expect(screen.getByLabelText('Verified university email').value).toBe(emptyProfile.email);
  expect(screen.getByLabelText('Verified university email').readOnly).toBe(true);
  for (const label of ['Name', 'Phone', 'Telegram username', 'External contact URL']) expect(screen.getByLabelText(label).value).toBe('');
  expect(screen.getByText('Verified. University email cannot be changed.')).toBeTruthy();
  expect(screen.getByRole('button', { name: 'Save profile' }).disabled).toBe(true);
});

test('partial save omits untouched null name and takes returned authoritative values as baseline', async () => {
  const storage = vi.spyOn(Storage.prototype, 'setItem');
  setup({ save: options => { expect(JSON.parse(options.body)).toEqual({ phone: '+77001234567' }); return Promise.resolve(response(200, { ...emptyProfile, phone: '+77009999999' })); } });
  await open(); change('Phone', '+77001234567'); submit();
  await screen.findByText('Your profile was saved.');
  expect(screen.getByLabelText('Phone').value).toBe('+77009999999');
  expect(screen.getByRole('button', { name: 'Save profile' }).disabled).toBe(true);
  expect(patches()[0][1].headers.Authorization).toBe('Bearer secret-access');
  expect(patches()[0][1].credentials).toBe('include');
  expect(storage).not.toHaveBeenCalled(); expect(window.location.search).toBe('');
});

test('contact clearing submits explicit null and only changed allowed fields with trimmed name', async () => {
  const profile = { ...emptyProfile, name: 'Original', phone: '+77001234567', telegram_username: 'student_1', external_contact_url: 'https://example.test/contact' };
  setup({ profile }); await open();
  change('Name', '  Updated  ');
  for (const label of ['Phone', 'Telegram username', 'External contact URL']) change(label, '');
  submit(); await screen.findByText('Your profile was saved.');
  expect(JSON.parse(patches()[0][1].body)).toEqual({ name: 'Updated', phone: null, telegram_username: null, external_contact_url: null });
  expect(screen.getByLabelText('Name').value).toBe('Updated');
});

test('invalid changed name/contact formats stop before PATCH without losing edits', async () => {
  setup({ profile: { ...emptyProfile, name: 'Original' } }); await open();
  for (const value of ['', ' ', 'x'.repeat(101)]) { change('Name', value); submit(); expect(screen.getByRole('alert').textContent).toContain('1–100'); }
  change('Name', 'Original');
  const invalid = {
    Phone: ['1234567', '+123456', '+'+'1'.repeat(16), '+١٢٣٤٥٦٧', ' '],
    'Telegram username': ['abcd', 'x'.repeat(33), '@student', 'студент', ' '],
    'External contact URL': ['http://example.test', 'javascript:alert(1)', 'https://user:pass@example.test', 'https://@example.test', 'https://example.test/has space', 'https://-bad.test', 'https://bad..test', 'https://example.test:99999', 'https://example.test:0', 'https:///missing', 'https://example.test/'+'x'.repeat(2048)],
  };
  for (const [label, values] of Object.entries(invalid)) {
    for (const value of values) { change(label, value); submit(); expect(screen.getByRole('alert')).toBeTruthy(); expect(screen.getByLabelText(label).value).toBe(value); }
    change(label, '');
  }
  expect(patches()).toHaveLength(0);
});

test('empty and pending saves cannot submit duplicate requests', async () => {
  let finish; setup({ save: () => new Promise(resolve => { finish = resolve; }) }); await open();
  submit(); expect(patches()).toHaveLength(0);
  change('Name', 'Student'); submit(); submit();
  expect(patches()).toHaveLength(1);
  expect(screen.getByRole('button', { name: 'Saving profile…' }).disabled).toBe(true);
  expect(screen.getByLabelText('Name').disabled).toBe(true);
  expect(screen.queryByText('Your profile was saved.')).toBeNull();
  await act(async () => finish(response(200, { ...emptyProfile, name: 'Student' })));
  expect(screen.getByText('Your profile was saved.')).toBeTruthy();
});

test('network/server/validation save failures preserve edits and never automatically replay mutation', async () => {
  let status = 500;
  setup({ save: () => status ? Promise.resolve(response(status, { detail: 'SENSITIVE_INPUT' })) : Promise.reject(new Error('SENSITIVE_NETWORK')) }); await open();
  change('Name', 'Edited');
  for (const failure of [500, 422, 0]) {
    status = failure; submit();
    await waitFor(() => expect(screen.getByRole('button', { name: 'Save profile' }).disabled).toBe(false));
    expect(screen.getByRole('alert').textContent).toContain('could not be confirmed');
    expect(screen.getByLabelText('Name').value).toBe('Edited');
    expect(screen.queryByText('Your profile was saved.')).toBeNull();
  }
  expect(patches()).toHaveLength(3);
  expect(fetchMock.mock.calls.filter(([url]) => url.endsWith('/auth/refresh'))).toHaveLength(1);
});

test('revoked authorization on PATCH removes protected fields without replay or save claim', async () => {
  setup({ save: () => Promise.resolve(response(401)) }); await open(); change('Name', 'Edited'); submit();
  await screen.findByRole('heading', { name: 'Sign in' });
  expect(screen.queryByRole('form', { name: 'Own profile' })).toBeNull();
  expect(screen.getByText(/session expired or is unavailable/)).toBeTruthy();
  expect(patches()).toHaveLength(1);
  expect(fetchMock.mock.calls.filter(([url]) => url.endsWith('/auth/refresh'))).toHaveLength(1);
});
