import React from 'react';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import { fireEvent, render, screen, within } from '@testing-library/react';
import { App } from './App.jsx';

beforeEach(() => vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{}', { status: 401 }))));
afterEach(() => vi.unstubAllGlobals());

test('students can navigate the shell through visible links', async () => {
  render(<App />);
  expect(screen.getByRole('heading', { name: 'Your campus marketplace' })).toBeTruthy();
  const navigation = within(screen.getByRole('navigation', { name: 'Main navigation' }));
  fireEvent.click(navigation.getByRole('link', { name: 'Marketplace' }));
  await screen.findByRole('heading', { name: 'Sign in' });
  expect(window.location.pathname).toBe('/login');
  fireEvent.click(navigation.getByRole('link', { name: 'Sign in' }));
  expect(screen.getByRole('heading', { name: 'Sign in' })).toBeTruthy();
  expect(screen.getByLabelText('University email')).toBeTruthy();
});

test('a direct unknown route offers a useful path home', () => {
  window.history.replaceState(null, '', '/missing');
  render(<App />);
  expect(screen.getByRole('heading', { name: 'Page not found' })).toBeTruthy();
  fireEvent.click(screen.getByRole('link', { name: 'Back to home' }));
  expect(screen.getByRole('heading', { name: 'Your campus marketplace' })).toBeTruthy();
});

test('guest home is compact: @sdu.edu.kz strip with sign-in links and no marketplace requests', async () => {
  window.history.replaceState(null, '', '/');
  render(<App />);
  const strip = within(screen.getByRole('group', { name: 'Sign in for university students' }));
  expect(strip.getByText('@sdu.edu.kz')).toBeTruthy();
  expect(strip.getByRole('link', { name: 'Sign in' }).getAttribute('href')).toBe('/login');
  expect(strip.getByRole('link', { name: 'Create an account' }).getAttribute('href')).toBe('/register');
  expect(screen.queryByRole('link', { name: 'Explore marketplace' })).toBeNull();
  await screen.findByRole('heading', { name: 'Your campus marketplace' });
  const urls = fetch.mock.calls.map(([url]) => String(url));
  expect(urls.some((url) => url.includes('/listings') || url.includes('/photos/'))).toBe(false);
});
