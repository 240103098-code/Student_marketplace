import React from 'react';
import { fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import { SiteHeader } from './SiteHeader.jsx';

let matches;
function show(auth, props = {}) {
  return render(<SiteHeader auth={auth} path="/marketplace" navigate={(e) => e.preventDefault()} signOut={vi.fn()} logoutPending={false} {...props} />);
}
const names = () => within(screen.getByRole('navigation', { name: 'Main navigation' })).getAllByRole('link').map((l) => l.textContent);
beforeEach(() => { matches = false; vi.stubGlobal('matchMedia', () => ({ matches, addEventListener: vi.fn(), removeEventListener: vi.fn() })); });
afterEach(() => vi.unstubAllGlobals());

test('wide viewport shows inline navigation without a menu button for each role', () => {
  const { unmount } = show({ status: 'anonymous', user: null });
  expect(screen.queryByRole('button', { name: 'Open menu' })).toBeNull();
  expect(names()).toEqual(['Home', 'Marketplace', 'Sign in', 'Register', 'Verify email']);
  unmount();
  const student = show({ status: 'authenticated', user: { is_admin: false } });
  expect(names()).toEqual(['Marketplace', 'Create listing', 'My Listings', 'Profile', 'Change password']);
  expect(screen.getByRole('button', { name: 'Sign out' })).toBeTruthy();
  student.unmount();
  show({ status: 'authenticated', user: { is_admin: true } });
  expect(names()).toContain('Admin');
});

test('the active route link has aria-current page', () => {
  show({ status: 'anonymous', user: null }, { path: '/login' });
  expect(screen.getByRole('link', { name: 'Sign in' }).getAttribute('aria-current')).toBe('page');
  expect(screen.getByRole('link', { name: 'Register' }).getAttribute('aria-current')).toBeNull();
});

test('pending sign-out shows the Signing out label disabled, and a desktop error is an alert while links stay usable', () => {
  const auth = { status: 'authenticated', user: { is_admin: false } };
  const view = show(auth, { logoutPending: true });
  const pending = screen.getByRole('button', { name: 'Signing out...' });
  expect(pending.disabled).toBe(true);
  expect(pending.getAttribute('aria-busy')).toBe('true');
  view.unmount();
  show(auth, { logoutError: 'Sign-out could not be confirmed. Your session may still be active. Please retry.' });
  expect(screen.getByRole('alert').textContent).toContain('could not be confirmed');
  fireEvent.click(screen.getByRole('link', { name: 'Profile' }));
  expect(screen.getByRole('link', { name: 'Profile' })).toBeTruthy();
});

test('wordmark link goes to the marketplace when signed in and home when anonymous', () => {
  const view = show({ status: 'anonymous', user: null });
  expect(screen.getByRole('link', { name: 'Student Marketplace home' }).getAttribute('href')).toBe('/');
  view.unmount();
  show({ status: 'authenticated', user: { is_admin: false } });
  expect(screen.getByRole('link', { name: 'Student Marketplace home' }).getAttribute('href')).toBe('/marketplace');
});
