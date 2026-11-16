import React, { useRef, useState } from 'react';
import { act, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import { Button, Dialog, EmptyState, ErrorState, Field, Loading, NotFound, Notice, PriceTag, Skeleton, StatusBadge, STATUS_TONES, Toast } from './index.js';

afterEach(() => { vi.useRealTimers(); document.body.style.overflow = ''; });

test('Button renders every variant and size as a button with a class per variant', () => {
  render(<>{['primary', 'secondary', 'ghost', 'danger'].map((v) => <Button key={v} variant={v}>{v} action</Button>)}<Button size="large">Big</Button></>);
  for (const v of ['primary', 'secondary', 'ghost', 'danger']) expect(screen.getByRole('button', { name: `${v} action` }).className).toContain(v);
  expect(screen.getByRole('button', { name: 'Big' }).className).toContain('large');
});

test('Button loading swaps the label, sets aria-busy, shows a spinner and blocks repeat clicks', () => {
  const onClick = vi.fn();
  const { container } = render(<Button loading loadingLabel="Saving..." onClick={onClick}>Save</Button>);
  const button = screen.getByRole('button', { name: 'Saving...' });
  expect(button.getAttribute('aria-busy')).toBe('true');
  expect(button.disabled).toBe(true);
  expect(container.querySelector('.spinner').getAttribute('aria-hidden')).toBe('true');
  fireEvent.click(button);
  expect(onClick).not.toHaveBeenCalled();
});

test('Button disabled uses the native attribute and does not call onClick; enabled calls it once', () => {
  const onClick = vi.fn();
  const { rerender } = render(<Button disabled onClick={onClick}>Go</Button>);
  expect(screen.getByRole('button', { name: 'Go' }).disabled).toBe(true);
  fireEvent.click(screen.getByRole('button', { name: 'Go' }));
  expect(onClick).not.toHaveBeenCalled();
  rerender(<Button onClick={onClick}>Go</Button>);
  fireEvent.click(screen.getByRole('button', { name: 'Go' }));
  expect(onClick).toHaveBeenCalledTimes(1);
});

test('Button with href renders a link styled as a button and disabled links are inert', () => {
  const onClick = vi.fn();
  const { rerender } = render(<Button href="/marketplace" variant="primary" onClick={onClick}>Browse</Button>);
  const link = screen.getByRole('link', { name: 'Browse' });
  expect(link.getAttribute('href')).toBe('/marketplace');
  expect(link.className).toContain('button primary');
  fireEvent.click(link);
  expect(onClick).toHaveBeenCalledTimes(1);
  rerender(<Button href="/marketplace" disabled onClick={onClick}>Browse</Button>);
  const inert = screen.getByRole('link', { name: 'Browse' });
  expect(inert.getAttribute('aria-disabled')).toBe('true');
  expect(inert.getAttribute('href')).toBeNull();
  fireEvent.click(inert);
  expect(onClick).toHaveBeenCalledTimes(1);
});

test('Field associates label, hint and error and announces required and invalid state', () => {
  render(<Field label="Title" required hint="Up to 120 characters." error="Enter a title." />);
  const input = screen.getByLabelText(/Title/);
  expect(screen.getByText('(required)').className).toContain('sr-only');
  expect(input.getAttribute('aria-required')).toBe('true');
  expect(input.getAttribute('aria-invalid')).toBe('true');
  const described = input.getAttribute('aria-describedby').split(' ');
  expect(described.map((id) => document.getElementById(id).textContent)).toEqual(['Up to 120 characters.', 'Enter a title.']);
  fireEvent.click(screen.getByText('Title', { exact: false, selector: 'label' }));
  expect(document.activeElement).toBe(input);
});

test('Field without error has no aria-invalid and supports textarea and select', () => {
  render(<><Field label="Note" as="textarea" /><Field label="Category" as="select"><option>Books</option></Field></>);
  expect(screen.getByLabelText('Note').tagName).toBe('TEXTAREA');
  expect(screen.getByLabelText('Category').tagName).toBe('SELECT');
  expect(screen.getByLabelText('Note').getAttribute('aria-invalid')).toBeNull();
  expect(screen.getByLabelText('Note').getAttribute('aria-describedby')).toBeNull();
});

test('StatusBadge shows each status as visible text, not colour alone', () => {
  render(<>{STATUS_TONES.map((s) => <StatusBadge key={s} status={s} />)}</>);
  expect(STATUS_TONES).toEqual(['pending', 'active', 'sold', 'rejected', 'removed']);
  for (const label of ['Pending', 'Active', 'Sold', 'Rejected', 'Removed']) expect(screen.getByText(label)).toBeTruthy();
  expect(screen.getByText('Sold').parentElement.getAttribute('data-tone')).toBe('sold');
});

test('Skeleton is aria-hidden and Loading exposes a single Loading status', () => {
  const { container } = render(<Loading><Skeleton shape="line" lines={3} /><Skeleton shape="block" height={80} /><Skeleton shape="card" /></Loading>);
  expect(screen.getAllByRole('status')).toHaveLength(1);
  expect(within(screen.getByRole('status')).getByText('Loading')).toBeTruthy();
  expect(container.querySelectorAll('.skeleton').length).toBeGreaterThan(3);
  for (const node of container.querySelectorAll('.skeleton')) expect(node.closest('[aria-hidden="true"]')).toBeTruthy();
});

test('Notice uses role alert for errors, role status for other tones, and a named dismiss button', () => {
  const onDismiss = vi.fn();
  render(<><Notice tone="error" onDismiss={onDismiss}>Bad</Notice><Notice tone="info">Info</Notice><Notice tone="success" title="Saved">Done</Notice></>);
  expect(within(screen.getByRole('alert')).getByText('Bad')).toBeTruthy();
  expect(screen.getAllByRole('status')).toHaveLength(2);
  fireEvent.click(screen.getByRole('button', { name: 'Dismiss notice' }));
  expect(onDismiss).toHaveBeenCalledTimes(1);
});

test('Toast stays for at least six seconds before auto-dismissing', () => {
  vi.useFakeTimers();
  const onDismiss = vi.fn();
  render(<Toast tone="success" onDismiss={onDismiss} autoDismissMs={1000}>Copied</Toast>);
  act(() => { vi.advanceTimersByTime(5900); });
  expect(onDismiss).not.toHaveBeenCalled();
  act(() => { vi.advanceTimersByTime(200); });
  expect(onDismiss).toHaveBeenCalledTimes(1);
});

function DialogHost() {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  return <><Button ref={ref} onClick={() => setOpen(true)}>Open it</Button><Dialog open={open} onClose={() => setOpen(false)} title="Remove listing?" actions={<Button>Confirm</Button>}>Body text</Dialog></>;
}

test('Dialog is a named modal, traps Tab, locks scroll, closes with Escape and restores focus', () => {
  render(<DialogHost />);
  const opener = screen.getByRole('button', { name: 'Open it' });
  opener.focus();
  fireEvent.click(opener);
  const dialog = screen.getByRole('dialog', { name: 'Remove listing?' });
  expect(dialog.getAttribute('aria-modal')).toBe('true');
  const close = within(dialog).getByRole('button', { name: 'Close' });
  const confirm = within(dialog).getByRole('button', { name: 'Confirm' });
  expect(document.activeElement).toBe(close);
  expect(document.body.style.overflow).toBe('hidden');
  confirm.focus();
  fireEvent.keyDown(document, { key: 'Tab' });
  expect(document.activeElement).toBe(close);
  fireEvent.keyDown(document, { key: 'Tab', shiftKey: true });
  expect(document.activeElement).toBe(confirm);
  fireEvent.keyDown(document, { key: 'Escape' });
  expect(screen.queryByRole('dialog')).toBeNull();
  expect(document.body.style.overflow).toBe('');
  expect(document.activeElement).toBe(opener);
});

test('Dialog closes from its close button and from a backdrop press', () => {
  render(<DialogHost />);
  fireEvent.click(screen.getByRole('button', { name: 'Open it' }));
  fireEvent.click(screen.getByRole('button', { name: 'Close' }));
  expect(screen.queryByRole('dialog')).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: 'Open it' }));
  fireEvent.mouseDown(document.querySelector('.dialog-backdrop'));
  expect(screen.queryByRole('dialog')).toBeNull();
});

test('EmptyState has a heading, explanation, optional action and no image requests', () => {
  const { container } = render(<EmptyState title="No listings yet" action={<Button href="/listings/new" variant="primary">Create listing</Button>}>Nothing posted here yet.</EmptyState>);
  expect(screen.getByRole('heading', { name: 'No listings yet' })).toBeTruthy();
  expect(screen.getByText('Nothing posted here yet.')).toBeTruthy();
  expect(screen.getByRole('link', { name: 'Create listing' })).toBeTruthy();
  expect(container.querySelector('img')).toBeNull();
  expect(container.querySelector('svg').getAttribute('aria-hidden')).toBe('true');
  expect(container.textContent).toContain('KZT');
});

test('ErrorState is an alert, offers Try again only with a callback and shows no raw text', () => {
  const retry = vi.fn();
  const { rerender } = render(<ErrorState onRetry={retry} />);
  const alert = screen.getByRole('alert');
  expect(within(alert).getByRole('heading', { name: 'Something went wrong' })).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
  expect(retry).toHaveBeenCalledTimes(1);
  rerender(<ErrorState />);
  expect(screen.queryByRole('button', { name: 'Try again' })).toBeNull();
});

test('NotFound offers Go to home and Marketplace when anonymous', () => {
  const navigate = vi.fn((e) => e.preventDefault());
  render(<NotFound authed={false} navigate={navigate} />);
  expect(screen.getByRole('heading', { level: 1, name: 'Page not found' })).toBeTruthy();
  expect(screen.getByRole('link', { name: 'Go to home' }).getAttribute('href')).toBe('/');
  expect(screen.getByRole('link', { name: 'Browse Marketplace' }).getAttribute('href')).toBe('/marketplace');
  expect(screen.queryByRole('link', { name: 'Go to Marketplace' })).toBeNull();
  fireEvent.click(screen.getByRole('link', { name: 'Go to home' }));
  expect(navigate).toHaveBeenCalledTimes(1);
});

test('NotFound offers Go to Marketplace when signed in and attaches the heading ref', () => {
  const ref = React.createRef();
  render(<NotFound authed navigate={() => {}} headingRef={ref} />);
  expect(screen.getByRole('link', { name: 'Go to Marketplace' }).getAttribute('href')).toBe('/marketplace');
  expect(screen.queryByRole('link', { name: 'Go to home' })).toBeNull();
  expect(ref.current).toBe(screen.getByRole('heading', { name: 'Page not found' }));
});

test('PriceTag shows KZT and can be hidden from assistive tech when decorative', () => {
  const { container } = render(<><PriceTag amount="12 500" /><PriceTag amount="5" decorative /></>);
  const tags = container.querySelectorAll('.price-tag');
  expect(tags[0].textContent).toBe('12 500KZT');
  expect(tags[0].getAttribute('aria-hidden')).toBeNull();
  expect(tags[1].getAttribute('aria-hidden')).toBe('true');
});
