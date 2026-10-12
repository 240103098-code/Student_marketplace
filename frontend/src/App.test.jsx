import React from 'react';
import { expect, test } from 'vitest';
import { fireEvent, render, screen, within } from '@testing-library/react';
import { App } from './App.jsx';

test('students can navigate the shell through visible links', () => {
  render(<App />);
  expect(screen.getByRole('heading', { name: 'Your campus marketplace' })).toBeTruthy();
  const navigation = within(screen.getByRole('navigation', { name: 'Main navigation' }));
  fireEvent.click(navigation.getByRole('link', { name: 'Marketplace' }));
  expect(screen.getByRole('heading', { name: 'Marketplace' })).toBeTruthy();
  expect(window.location.pathname).toBe('/marketplace');
  fireEvent.click(navigation.getByRole('link', { name: 'Sign in' }));
  expect(screen.getByRole('heading', { name: 'Sign in' })).toBeTruthy();
  expect(screen.queryByRole('textbox')).toBeNull();
});

test('a direct unknown route offers a useful path home', () => {
  window.history.replaceState(null, '', '/missing');
  render(<App />);
  expect(screen.getByRole('heading', { name: 'Page not found' })).toBeTruthy();
  fireEvent.click(screen.getByRole('link', { name: 'Back to home' }));
  expect(screen.getByRole('heading', { name: 'Your campus marketplace' })).toBeTruthy();
});
