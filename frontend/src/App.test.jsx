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
