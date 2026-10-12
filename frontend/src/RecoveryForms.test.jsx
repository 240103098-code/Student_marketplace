import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import { App } from './App.jsx';

const password = ' 1234567890 ';
let fetchMock;
function response(status, data = {}, headers = {}) { return new Response(status === 204 ? null : JSON.stringify(data), { status, headers }); }
function open(path) { window.history.replaceState(null, '', path); render(<App />); }
function email(value = ' Student@SDU.EDU.KZ ') { fireEvent.change(screen.getByLabelText('University email'), { target: { value } }); }
function resetFields(code = '123456', value = password, confirmation = value) {
  email();
  fireEvent.change(screen.getByLabelText('Reset code'), { target: { value: code } });
  fireEvent.change(screen.getByLabelText('New password'), { target: { value } });
  fireEvent.change(screen.getByLabelText('Confirm new password'), { target: { value: confirmation } });
}
function submitReset() { fireEvent.submit(screen.getByRole('form', { name: 'Password reset' })); }
beforeEach(() => {
  fetchMock = vi.fn();
  vi.stubGlobal('fetch', (url, options) => url.endsWith('/auth/csrf') ? Promise.resolve(response(401)) : fetchMock(url, options));
});
afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

test('generic recovery feedback, cooldown and memory-only email handoff do not guarantee delivery', async () => {
  vi.useFakeTimers();
  const storage = vi.spyOn(Storage.prototype, 'setItem');
  fetchMock.mockResolvedValue(response(202, {}, { 'Retry-After': '60' }));
  open('/forgot-password'); email();
  await act(async () => fireEvent.submit(screen.getByRole('form', { name: 'Password recovery' })));
  expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ email: 'student@sdu.edu.kz' });
  expect(fetchMock.mock.calls[0][1].credentials).toBe('include');
  expect(screen.getByRole('status').textContent).toContain('does not guarantee delivery');
  expect(screen.getByRole('timer').textContent).toContain('60 seconds');
  fireEvent.submit(screen.getByRole('form', { name: 'Password recovery' }));
  expect(fetchMock).toHaveBeenCalledTimes(1);
  act(() => vi.advanceTimersByTime(60_000));
  expect(screen.getByRole('button', { name: 'Request reset code' }).disabled).toBe(false);
  fireEvent.click(screen.getByRole('link', { name: 'Already have a code? Reset password' }));
  expect(screen.getByLabelText('University email').value).toBe('student@sdu.edu.kz');
  expect(window.location.search).toBe(''); expect(storage).not.toHaveBeenCalled();
});

test('request validates email, blocks pending duplicates and recovers honestly from network errors', async () => {
  let finish;
  fetchMock.mockReturnValue(new Promise(resolve => { finish = resolve; }));
  open('/forgot-password'); email('student@sub.sdu.edu.kz');
  const form = screen.getByRole('form', { name: 'Password recovery' });
  fireEvent.submit(form); expect(fetchMock).not.toHaveBeenCalled();
  email(); fireEvent.submit(form); fireEvent.submit(form);
  expect(fetchMock).toHaveBeenCalledTimes(1);
  expect(screen.getByRole('button', { name: 'Requesting code…' }).disabled).toBe(true);
  await act(async () => finish(response(500, { detail: 'SENSITIVE_DRIVER' })));
  expect(screen.getByRole('alert').textContent).toContain('could not be confirmed');
  expect(screen.queryByRole('timer')).toBeNull();
  fetchMock.mockRejectedValueOnce(new Error('SENSITIVE_NETWORK'));
  fireEvent.submit(form);
  await waitFor(() => expect(screen.getByRole('button', { name: 'Request reset code' }).disabled).toBe(false));
  expect(screen.getByRole('alert').textContent).not.toContain('SENSITIVE');
});

test('direct reset validates ASCII code/password/confirmation and safe generic errors', async () => {
  open('/reset-password'); expect(screen.getByLabelText('University email').value).toBe('');
  resetFields('١٢٣٤٥٦'); submitReset(); expect(screen.getByRole('alert').textContent).toContain('six digits');
  for (const value of ['x'.repeat(11), 'x'.repeat(129)]) { resetFields('123456', value); submitReset(); expect(screen.getByRole('alert').textContent).toContain('12–128'); }
  resetFields('123456', password, 'mismatch'); submitReset(); expect(screen.getByRole('alert').textContent).toContain('must match');
  expect(fetchMock).not.toHaveBeenCalled();
  resetFields();
  for (const status of [400, 422, 500]) {
    fetchMock.mockResolvedValueOnce(response(status, { detail: 'SENSITIVE_CODE' })); submitReset();
    await waitFor(() => expect(screen.getByRole('button', { name: 'Reset password' }).disabled).toBe(false));
    expect(screen.getByRole('alert').textContent).not.toContain('SENSITIVE');
    expect(screen.queryByText(/all sessions were revoked/)).toBeNull();
  }
  expect(fetchMock).toHaveBeenCalledTimes(3);
  expect(screen.getByRole('link', { name: 'Request a replacement code' }).getAttribute('href')).toBe('/forgot-password');
});

test('reset pending blocks duplicates; success sends only contract fields and clears secrets/auth', async () => {
  let finish;
  const storage = vi.spyOn(Storage.prototype, 'setItem');
  fetchMock.mockReturnValue(new Promise(resolve => { finish = resolve; }));
  vi.stubGlobal('fetch', (url, options) => {
    if (url.endsWith('/auth/csrf')) return Promise.resolve(response(200, { csrf_token: 'a'.repeat(64) }));
    if (url.endsWith('/auth/refresh')) return Promise.resolve(response(200, { access_token: 'secret-session', token_type: 'bearer', expires_in: 900 }));
    if (url.endsWith('/auth/me')) return Promise.resolve(response(200, { id: 1, email: 'student@sdu.edu.kz', verified: true }));
    return fetchMock(url, options);
  });
  open('/reset-password'); await screen.findByRole('button', { name: 'Sign out' });
  resetFields(); submitReset(); submitReset();
  expect(fetchMock).toHaveBeenCalledTimes(1);
  expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ email: 'student@sdu.edu.kz', code: '123456', new_password: password });
  expect(fetchMock.mock.calls[0][0].endsWith('/auth/reset-password')).toBe(true);
  expect(screen.getByRole('button', { name: 'Resetting password…' }).disabled).toBe(true);
  await act(async () => finish(response(204)));
  await screen.findByRole('heading', { name: 'Sign in' });
  expect(screen.getByText(/Your password was reset and all sessions were revoked/)).toBeTruthy();
  expect(screen.queryByLabelText('Reset code')).toBeNull();
  expect(screen.getByLabelText('Password').value).toBe('');
  expect(screen.queryByRole('button', { name: 'Sign out' })).toBeNull();
  expect(storage).not.toHaveBeenCalled(); expect(window.location.search).toBe('');
});
