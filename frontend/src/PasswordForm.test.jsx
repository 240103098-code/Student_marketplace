import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import { App } from './App.jsx';

const current = 'TEST_CURRENT_PASSWORD_MARKER_123';
const next = ' 1234567890 ';
const csrf = 'a'.repeat(64);
let fetchMock;
function response(status, data = {}) { return new Response(status === 204 ? null : JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } }); }
function setup(change) {
  fetchMock.mockImplementation((url, options) => {
    const path = new URL(url).pathname;
    if (path === '/auth/csrf') return Promise.resolve(response(200, { csrf_token: csrf }));
    if (path === '/auth/refresh') return Promise.resolve(response(200, { access_token: 'secret-access', token_type: 'bearer', expires_in: 900 }));
    if (path === '/auth/me') return Promise.resolve(response(200, { id: 1, email: 'student@sdu.edu.kz', verified: true, is_admin: false }));
    if (path === '/auth/change-password') return change(options);
    throw new Error('Unexpected test route');
  });
}
async function open() { window.history.replaceState(null, '', '/account/password'); render(<App />); await screen.findByRole('form', { name: 'Change password' }); }
function fill(old = current, value = next, confirmation = value) {
  fireEvent.change(screen.getByLabelText('Current password'), { target: { value: old } });
  fireEvent.change(screen.getByLabelText('New password'), { target: { value } });
  fireEvent.change(screen.getByLabelText('Confirm new password'), { target: { value: confirmation } });
}
function submit() { fireEvent.submit(screen.getByRole('form', { name: 'Change password' })); }
function changes() { return fetchMock.mock.calls.filter(([url]) => url.endsWith('/auth/change-password')); }
beforeEach(() => { fetchMock = vi.fn(); vi.stubGlobal('fetch', fetchMock); });
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

test('password screen validates boundaries and client-only confirmation without mutation', async () => {
  setup(() => Promise.resolve(response(204))); await open();
  for (const value of ['x'.repeat(11), 'x'.repeat(129)]) { fill(current, value); submit(); expect(screen.getByRole('alert').textContent).toContain('12–128'); }
  fill('x'.repeat(11)); submit(); expect(screen.getByRole('alert').textContent).toContain('12–128');
  fill(current, next, 'different confirmation'); submit(); expect(screen.getByRole('alert').textContent).toContain('must match');
  expect(changes()).toHaveLength(0);
  expect(screen.getByRole('button', { name: 'Sign out' })).toBeTruthy();
});

test('pending change blocks duplicate submissions and confirmed success clears auth/inputs', async () => {
  let finish;
  const pending = new Promise(resolve => { finish = resolve; });
  const storage = vi.spyOn(Storage.prototype, 'setItem');
  setup(() => pending); await open(); fill(); submit(); submit();
  expect(changes()).toHaveLength(1);
  const [, options] = changes()[0];
  expect(JSON.parse(options.body)).toEqual({ current_password: current, new_password: next });
  expect(options.headers.Authorization).toBe('Bearer secret-access');
  expect(options.credentials).toBe('include');
  expect(screen.getByRole('button', { name: 'Changing password…' }).disabled).toBe(true);
  expect(screen.getByLabelText('Current password').disabled).toBe(true);
  expect(screen.queryByText(/all sessions were revoked/)).toBeNull();
  await act(async () => finish(response(204)));
  await screen.findByRole('heading', { name: 'Sign in' });
  expect(screen.getByText(/Your password changed and all sessions were revoked/)).toBeTruthy();
  expect(screen.queryByLabelText('Current password')).toBeNull();
  expect(screen.getByLabelText('Password').value).toBe('');
  expect(screen.queryByRole('button', { name: 'Sign out' })).toBeNull();
  expect(document.body.textContent).not.toContain('secret-access');
  expect(storage).not.toHaveBeenCalled();
});

test('wrong-current/server/network failures preserve authentication and do not replay or claim success', async () => {
  let failure = 400;
  setup(() => failure === 0 ? Promise.reject(new Error('SENSITIVE_NETWORK')) : Promise.resolve(response(failure, { detail: current })));
  await open(); fill();
  for (const status of [400, 500, 0]) {
    failure = status; submit();
    await waitFor(() => expect(screen.getByRole('button', { name: 'Change password' }).disabled).toBe(false));
    expect(screen.getByRole('alert').textContent).not.toContain(current);
    expect(screen.getByRole('button', { name: 'Sign out' })).toBeTruthy();
    expect(screen.getByLabelText('Current password').value).toBe(current);
    expect(screen.queryByText(/all sessions were revoked/)).toBeNull();
  }
  expect(changes()).toHaveLength(3);
  expect(fetchMock.mock.calls.filter(([url]) => url.endsWith('/auth/refresh'))).toHaveLength(1);
});

test('expired access on password mutation stops without auto-replay and hides protected form', async () => {
  setup(() => Promise.resolve(response(401))); await open(); fill(); submit();
  await screen.findByRole('heading', { name: 'Sign in' });
  expect(screen.queryByRole('form', { name: 'Change password' })).toBeNull();
  expect(screen.getByText(/session expired or is unavailable/)).toBeTruthy();
  expect(changes()).toHaveLength(1);
  expect(fetchMock.mock.calls.filter(([url]) => url.endsWith('/auth/refresh'))).toHaveLength(1);
});
