import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import { App } from './App.jsx';

const profile = { id:1, email:'student@sdu.edu.kz', verified:true, name:null, phone:null, telegram_username:null, external_contact_url:null };
let fetchMock, create, revoke;
function response(status, data = {}) { return new Response(JSON.stringify(data), { status }); }
function image() { return new Response(new Uint8Array([1,2,3]), { status:200, headers:{ 'Content-Type':'image/png' } }); }
function setup(avatar) {
  fetchMock.mockImplementation((url, options) => {
    const path = new URL(url).pathname;
    if (path === '/auth/csrf') return Promise.resolve(response(200,{csrf_token:'a'.repeat(64)}));
    if (path === '/auth/refresh') return Promise.resolve(response(200,{access_token:'secret-access',token_type:'bearer',expires_in:900}));
    if (path === '/auth/me') return Promise.resolve(response(200,{id:1,email:profile.email,verified:true}));
    if (path === '/users/me') return Promise.resolve(response(200,profile));
    if (path === '/users/me/avatar') return avatar(options);
    throw new Error('Unexpected test route');
  });
}
async function open() { window.history.replaceState(null,'','/profile'); const view=render(<App/>); await screen.findByRole('form',{name:'Own profile'}); await waitFor(()=>expect(screen.queryByText('Loading your photo…')).toBeNull()); return view; }
function choose(file = new File(['pixels'],'SENSITIVE_ORIGINAL.png',{type:'image/png'})) { fireEvent.change(screen.getByLabelText('Upload or replace profile photo'),{target:{files:[file]}}); }
beforeEach(()=>{
  fetchMock=vi.fn(); vi.stubGlobal('fetch',fetchMock);
  let number=0; create=vi.fn(()=>`blob:test-photo-${++number}`); revoke=vi.fn();
  vi.stubGlobal('URL', class extends URL {});
  URL.createObjectURL=create; URL.revokeObjectURL=revoke;
});
afterEach(()=>{vi.unstubAllGlobals();vi.restoreAllMocks();});

test('authenticated binary photo uses a blob URL without token/path and releases on unmount', async()=>{
  setup(()=>Promise.resolve(image())); const view=await open();
  const preview=screen.getByRole('img',{name:'Your profile photo'});
  expect(preview.getAttribute('src')).toBe('blob:test-photo-1');
  const call=fetchMock.mock.calls.find(([url])=>url.endsWith('/users/me/avatar'));
  expect(call[1].headers.Authorization).toBe('Bearer secret-access'); expect(call[1].credentials).toBe('include');
  expect(call[0]).not.toContain('secret-access'); expect(preview.src).not.toContain('secret-access');
  expect(create.mock.calls[0][0].type).toBe('image/png');
  view.unmount(); expect(revoke).toHaveBeenCalledWith('blob:test-photo-1');
});

test('empty photo becomes a multipart replacement with browser boundary and refreshed preview', async()=>{
  let present=false;
  setup(options=>{if(options.method==='POST'){present=true;return Promise.resolve(response(200,{detail:'Profile photo updated.',cleanup_pending:false}));}return Promise.resolve(present?image():response(404));});
  await open(); expect(screen.getByText('No profile photo.')).toBeTruthy(); choose();
  await screen.findByRole('img',{name:'Your profile photo'});
  const call=fetchMock.mock.calls.find(([url,options])=>url.endsWith('/users/me/avatar') && options.method==='POST');
  expect(call[1].body).toBeInstanceOf(FormData); expect([...call[1].body.keys()]).toEqual(['image']);
  expect(call[1].headers['Content-Type']).toBeUndefined(); expect(call[1].headers.Authorization).toBe('Bearer secret-access');
  expect(screen.getByText('Profile photo updated.')).toBeTruthy();
});

test('replacement and removal release old object URLs and show confirmed empty state', async()=>{
  let present=true;
  setup(options=>{if(options.method==='POST')return Promise.resolve(response(200,{cleanup_pending:true}));if(options.method==='DELETE'){present=false;return Promise.resolve(response(200,{cleanup_pending:false}));}return Promise.resolve(present?image():response(404));});
  await open(); choose(); await screen.findByText('Profile photo updated. Old-file cleanup is pending.');
  await waitFor(()=>expect(screen.getByRole('img').getAttribute('src')).toBe('blob:test-photo-2'));
  expect(revoke).toHaveBeenCalledWith('blob:test-photo-1');
  fireEvent.click(screen.getByRole('button',{name:'Remove photo'}));
  await screen.findByText('Profile photo removed.'); await screen.findByText('No profile photo.');
  expect(revoke).toHaveBeenCalledWith('blob:test-photo-2');
});

test('invalid files and pending duplicate actions are blocked before unsafe replay', async()=>{
  let finish;
  setup(options=>options.method==='POST'?new Promise(resolve=>{finish=resolve;}):Promise.resolve(response(404)));
  await open(); choose(new File(['svg'],'bad.svg',{type:'image/svg+xml'}));
  expect(screen.getByRole('alert').textContent).toContain('five MiB');
  choose(new File([new Uint8Array(5*1024*1024+1)],'large.png',{type:'image/png'}));
  expect(fetchMock.mock.calls.filter(([url,options])=>url.endsWith('/users/me/avatar') && options.method==='POST')).toHaveLength(0);
  choose(); choose();
  expect(screen.getByLabelText('Upload or replace profile photo').disabled).toBe(true);
  expect(fetchMock.mock.calls.filter(([url,options])=>url.endsWith('/users/me/avatar') && options.method==='POST')).toHaveLength(1);
  await act(async()=>finish(response(400,{detail:'SENSITIVE_FILENAME'})));
  expect(screen.getByRole('alert').textContent).not.toContain('SENSITIVE');
  expect(screen.queryByText('Profile photo updated.')).toBeNull();
});

test('failed replacement preserves the existing preview and allows retry without claiming save', async()=>{
  let fail=true;
  setup(options=>options.method==='POST'?(fail?Promise.reject(new Error('SENSITIVE_NETWORK')):Promise.resolve(response(200,{}))):Promise.resolve(image()));
  await open(); choose(); await screen.findByRole('alert');
  expect(screen.getByRole('img').getAttribute('src')).toBe('blob:test-photo-1');
  expect(revoke).not.toHaveBeenCalled(); expect(screen.queryByText('Profile photo updated.')).toBeNull();
  fail=false; choose(); await screen.findByText('Profile photo updated.');
  expect(fetchMock.mock.calls.filter(([url,options])=>url.endsWith('/users/me/avatar') && options.method==='POST')).toHaveLength(2);
});

test('photo load errors provide retry and authorization failure removes protected controls', async()=>{
  let fail=true;
  setup(options=>options.method==='DELETE'?Promise.resolve(response(401)):Promise.resolve(fail?response(500):image()));
  await open(); expect(screen.getByRole('alert').textContent).toContain('could not be loaded');
  expect(screen.getByText('Photo preview is unavailable.')).toBeTruthy();
  fail=false; fireEvent.click(screen.getByRole('button',{name:'Retry loading photo'})); await screen.findByRole('img');
  fireEvent.click(screen.getByRole('button',{name:'Remove photo'})); await screen.findByRole('heading',{name:'Sign in'});
  expect(screen.queryByLabelText('Upload or replace profile photo')).toBeNull();
  expect(fetchMock.mock.calls.filter(([,options])=>options.method==='DELETE')).toHaveLength(1);
});
