import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import { App } from './App.jsx';

let fetchMock;
const password = 'TEST_FORM_PASSWORD_MARKER_123';
function response(status, data = {}, headers = {}) {
  return new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json', ...headers } });
}
function open(path) {
  window.history.replaceState(null, '', path);
  render(<App />);
}
function enterEmail(value = 'student@sdu.edu.kz') {
  fireEvent.change(screen.getByLabelText('University email'), { target: { value } });
}
function enterRegistration(email = 'student@sdu.edu.kz', value = password) {
  enterEmail(email);
  fireEvent.change(screen.getByLabelText('Password'), { target: { value } });
}
function submitRegistration() {
  fireEvent.submit(screen.getByRole('form', { name: 'Registration' }));
}

beforeEach(() => {
  fetchMock = vi.fn();
  vi.stubGlobal('fetch', fetchMock);
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

test('registration sends exact untrimmed credentials and hands off email only in memory', async () => {
  const storage = vi.spyOn(Storage.prototype, 'setItem');
  fetchMock.mockResolvedValue(response(201, { id: 1, email: 'student@sdu.edu.kz', verified: false }));
  open('/register');
  const spaced = ' 1234567890 ';
  enterRegistration(' Student@SDU.EDU.KZ ', spaced);
  submitRegistration();
  await screen.findByRole('heading', { name: 'Verify your university email' });
  const [url, options] = fetchMock.mock.calls[0];
  expect(url.endsWith('/auth/register')).toBe(true);
  expect(JSON.parse(options.body)).toEqual({ email: 'student@sdu.edu.kz', password: spaced });
  expect(options.credentials).toBe('include');
  expect(screen.getByLabelText('University email').value).toBe('student@sdu.edu.kz');
  expect(screen.getByRole('button', { name: 'Request new code' }).disabled).toBe(true);
  expect(window.location.pathname).toBe('/verify');
  expect(window.location.search).toBe('');
  expect(storage).not.toHaveBeenCalled();
});

test('client rejects wrong domain and password boundaries before any request', () => {
  open('/register');
  for (const email of ['student@sub.sdu.edu.kz', 'student@sdu.edu.kz.evil', 'student@sdu.edu.Kz']) {
    enterRegistration(email);
    submitRegistration();
    expect(screen.getByRole('alert').textContent).toContain('sdu.edu.kz');
  }
  for (const value of ['a'.repeat(11), 'a'.repeat(129)]) {
    enterRegistration('student@sdu.edu.kz', value);
    submitRegistration();
    expect(screen.getByRole('alert').textContent).toContain('12–128');
  }
  expect(fetchMock).not.toHaveBeenCalled();
});

test('pending registration blocks double submission and announces progress', async () => {
  let finish;
  fetchMock.mockReturnValue(new Promise(resolve => { finish = resolve; }));
  open('/register');
  enterRegistration();
  submitRegistration();
  submitRegistration();
  expect(fetchMock).toHaveBeenCalledTimes(1);
  expect(screen.getByRole('button', { name: 'Creating account…' }).disabled).toBe(true);
  expect(screen.getByRole('status').textContent).toContain('Creating your account');
  await act(async () => finish(response(201, { email: 'student@sdu.edu.kz', verified: false })));
  expect(screen.getByRole('heading', { name: 'Verify your university email' })).toBeTruthy();
});

test('duplicate, SMTP, and network errors remain safe and retryable', async () => {
  open('/register');
  enterRegistration();
  for (const failure of [response(409, { detail: password }), response(503, { detail: password }), new Error(password)]) {
    if (failure instanceof Error) fetchMock.mockRejectedValueOnce(failure);
    else fetchMock.mockResolvedValueOnce(failure);
    submitRegistration();
    await waitFor(() => expect(screen.getByRole('button', { name: 'Create account' }).disabled).toBe(false));
    expect(screen.getByRole('alert').textContent).not.toContain(password);
  }
  expect(fetchMock).toHaveBeenCalledTimes(3);
});

test('direct verification is editable, rejects non-ASCII codes, and verifies without login', async () => {
  open('/verify');
  expect(screen.getByLabelText('University email').value).toBe('');
  enterEmail(' Student@SDU.EDU.KZ ');
  fireEvent.change(screen.getByLabelText('Verification code'), { target: { value: '١٢٣٤٥٦' } });
  fireEvent.submit(screen.getByRole('form', { name: 'Email verification' }));
  expect(fetchMock).not.toHaveBeenCalled();
  expect(screen.getByRole('alert').textContent).toContain('six digits');
  fetchMock.mockResolvedValue(response(200, { verified: true }));
  fireEvent.change(screen.getByLabelText('Verification code'), { target: { value: '123456' } });
  fireEvent.submit(screen.getByRole('form', { name: 'Email verification' }));
  await screen.findByText('Your university email is verified.');
  expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ email: 'student@sdu.edu.kz', code: '123456' });
  expect(screen.getByRole('link', { name: 'Continue to sign in' }).getAttribute('href')).toBe('/login');
  expect(window.location.pathname).toBe('/verify');
  expect(fetchMock).toHaveBeenCalledTimes(1);
});

test('generic verification failure gives truthful recovery without invented attempt counts', async () => {
  fetchMock.mockResolvedValue(response(400, { detail: 'SENSITIVE_INPUT_MARKER' }));
  open('/verify');
  enterEmail();
  fireEvent.change(screen.getByLabelText('Verification code'), { target: { value: '123456' } });
  fireEvent.submit(screen.getByRole('form', { name: 'Email verification' }));
  const alert = await screen.findByRole('alert');
  expect(alert.textContent).toContain('could not be accepted');
  expect(alert.textContent).toContain('five incorrect attempts');
  expect(alert.textContent).not.toMatch(/remaining|SENSITIVE_/);
});

test('accepted resend stays generic and follows its sixty-second cooldown', async () => {
  vi.useFakeTimers();
  fetchMock.mockResolvedValue(response(202, { detail: 'generic' }, { 'Retry-After': '60' }));
  open('/verify');
  enterEmail();
  await act(async () => fireEvent.click(screen.getByRole('button', { name: 'Request new code' })));
  expect(screen.getByRole('status').textContent).toContain('If this address is eligible');
  expect(screen.getByText(/another code in 60 seconds/)).toBeTruthy();
  expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ email: 'student@sdu.edu.kz' });
  fireEvent.click(screen.getByRole('button', { name: 'Request new code' }));
  expect(fetchMock).toHaveBeenCalledTimes(1);
  act(() => vi.advanceTimersByTime(59_000));
  expect(screen.getByText(/another code in 1 second/)).toBeTruthy();
  expect(screen.getByRole('button', { name: 'Request new code' }).disabled).toBe(true);
  act(() => vi.advanceTimersByTime(1000));
  expect(screen.getByRole('button', { name: 'Request new code' }).disabled).toBe(false);
});

test('failed resend has no new cooldown and can retry after network or SMTP error', async () => {
  open('/verify');
  enterEmail();
  for (const failure of [response(503), new Error('SENSITIVE_TRANSPORT_MARKER')]) {
    if (failure instanceof Error) fetchMock.mockRejectedValueOnce(failure);
    else fetchMock.mockResolvedValueOnce(failure);
    fireEvent.click(screen.getByRole('button', { name: 'Request new code' }));
    await screen.findByRole('alert');
    await waitFor(() => expect(screen.getByRole('button', { name: 'Request new code' }).disabled).toBe(false));
    expect(screen.queryByText(/another code in/)).toBeNull();
    expect(screen.getByRole('alert').textContent).not.toContain('SENSITIVE_');
  }
});

test('pending verification prevents verification and resend from overlapping', async () => {
  let finish;
  fetchMock.mockReturnValue(new Promise(resolve => { finish = resolve; }));
  open('/verify');
  enterEmail();
  fireEvent.change(screen.getByLabelText('Verification code'), { target: { value: '123456' } });
  const form = screen.getByRole('form', { name: 'Email verification' });
  fireEvent.submit(form);
  fireEvent.submit(form);
  fireEvent.click(screen.getByRole('button', { name: 'Request new code' }));
  expect(fetchMock).toHaveBeenCalledTimes(1);
  expect(screen.getByRole('button', { name: 'Request new code' }).disabled).toBe(true);
  await act(async () => finish(response(400)));
  expect(screen.getByRole('alert')).toBeTruthy();
});
