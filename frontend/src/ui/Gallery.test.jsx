import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { expect, test } from 'vitest';
import { Gallery } from './Gallery.jsx';

test('the component gallery shows every shared component with its variants and states', () => {
  render(<Gallery />);
  expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1);
  for (const name of ['Button', 'Field', 'StatusBadge', 'Skeleton', 'Notice and Toast', 'Dialog', 'EmptyState and ErrorState', 'NotFound']) expect(screen.getByRole('heading', { name })).toBeTruthy();
  for (const name of ['Primary', 'Secondary', 'Ghost', 'Danger', 'Disabled', 'Saving...']) expect(screen.getByRole('button', { name })).toBeTruthy();
  expect(screen.getByRole('link', { name: 'Link button' })).toBeTruthy();
  expect(screen.getByLabelText(/Title/).getAttribute('aria-invalid')).toBe('true');
  for (const status of ['Pending', 'Active', 'Sold', 'Rejected', 'Removed']) expect(screen.getByText(status)).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: 'Open dialog' }));
  expect(screen.getByRole('dialog', { name: 'Remove this listing?' })).toBeTruthy();
});
