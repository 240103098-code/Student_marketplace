import React from 'react';
import {act,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {beforeEach,afterEach,test,expect,vi} from 'vitest';
import {App} from './App.jsx';
let mock;
const res=(status,data)=>new Response(JSON.stringify(data),{status});
function setup(capability,proof){mock.mockImplementation((url,o)=>{const path=new URL(url).pathname;if(path==='/auth/csrf')return Promise.resolve(res(200,{csrf_token:'a'.repeat(64)}));if(path==='/auth/refresh'||path==='/auth/login')return Promise.resolve(res(200,{access_token:'secret',token_type:'bearer',expires_in:900}));if(path==='/auth/me')return Promise.resolve(res(200,{id:1,email:'s@sdu.edu.kz',verified:true,is_admin:capability}));if(path==='/admin/me')return proof(o);if(path==='/listings')return Promise.resolve(res(200,{items:[],total:0,count:0,limit:20,offset:0}));if(path==='/categories')return Promise.resolve(res(200,['Electronics','Clothing','Books','Furniture','Other'].map((label,i)=>({id:i+1,key:['electronics','clothing','books','furniture','other'][i],label}))));throw Error('Unexpected fixture');});}
function open(path='/admin'){window.history.replaceState(null,'',path);render(<App/>);}
beforeEach(()=>{mock=vi.fn();vi.stubGlobal('fetch',mock);});afterEach(()=>vi.unstubAllGlobals());
test('restored admin capability shows navigation but landing waits for genuine proof',async()=>{
 let finish;setup(true,()=>new Promise(r=>{finish=r;}));open();await screen.findByText('Checking administrator access…');expect(screen.getByRole('link',{name:'Admin'})).toBeTruthy();expect(screen.queryByRole('heading',{name:'Admin access confirmed'})).toBeNull();await waitFor(()=>expect(typeof finish).toBe('function'));const call=mock.mock.calls.find(([url])=>url.endsWith('/admin/me'));expect(call[1].headers.Authorization).toBe('Bearer secret');await act(async()=>finish(res(200,{id:1,is_admin:true})));await screen.findByRole('heading',{name:'Admin access confirmed'});expect(screen.queryByRole('link',{name:/manage|queue|reports/i})).toBeNull();
});
test('ordinary direct route and server demotion deny admin without logging student out',async()=>{
 setup(true,()=>Promise.resolve(res(403,{})));open();await screen.findByText('Administrator access is required.');expect(screen.queryByRole('link',{name:'Admin'})).toBeNull();expect(screen.getByRole('button',{name:'Sign out'})).toBeTruthy();expect(screen.queryByRole('heading',{name:'Admin access confirmed'})).toBeNull();fireEvent.click(screen.getByRole('link',{name:'Back to marketplace'}));await screen.findByRole('heading',{name:'Marketplace'});
});
test('check errors and malformed proof show retry without admin flash',async()=>{
 let attempt=0;setup(true,()=>Promise.resolve(++attempt===1?res(500,{}):attempt===2?res(200,{id:2,is_admin:true}):res(200,{id:1,is_admin:true})));open();await screen.findByRole('alert');expect(screen.queryByRole('heading',{name:'Admin access confirmed'})).toBeNull();fireEvent.click(screen.getByRole('button',{name:'Retry admin access'}));await screen.findByRole('alert');expect(screen.queryByRole('heading',{name:'Admin access confirmed'})).toBeNull();fireEvent.click(screen.getByRole('button',{name:'Retry admin access'}));await screen.findByRole('heading',{name:'Admin access confirmed'});
});
test('login confirms capability and ordinary restoration never trusts token/local flags',async()=>{
 setup(false,()=>Promise.resolve(res(403,{})));open('/marketplace');await screen.findByRole('heading',{name:'Marketplace'});expect(screen.queryByRole('link',{name:'Admin'})).toBeNull();
});
test('malformed capability cannot grant a restored session or admin content',async()=>{
 setup('true',()=>Promise.resolve(res(200,{id:1,is_admin:true})));open();await screen.findByRole('heading',{name:'Sign in'});expect(screen.queryByRole('link',{name:'Admin'})).toBeNull();expect(mock.mock.calls.some(([url])=>url.endsWith('/admin/me'))).toBe(false);
});
test('login accepts only server boolean capability and exposes admin navigation after confirmation',async()=>{
 let csrf=0;setup(true,()=>Promise.resolve(res(200,{id:1,is_admin:true})));const previous=mock.getMockImplementation();mock.mockImplementation((url,o)=>url.endsWith('/auth/csrf')&&++csrf===1?Promise.resolve(res(401,{})):previous(url,o));open('/login');await screen.findByRole('heading',{name:'Sign in'});await waitFor(()=>expect(csrf).toBe(1));fireEvent.change(screen.getByLabelText('University email'),{target:{value:'s@sdu.edu.kz'}});fireEvent.change(screen.getByLabelText('Password'),{target:{value:'PASSWORD_123456'}});fireEvent.submit(screen.getByRole('form',{name:'Sign in'}));await screen.findByRole('link',{name:'Admin'});fireEvent.click(screen.getByRole('link',{name:'Admin'}));await screen.findByRole('heading',{name:'Admin access confirmed'});
});
test('ordinary direct admin navigation has honest access denial and retains student session',async()=>{
 setup(false,()=>Promise.resolve(res(403,{})));open();await screen.findByText('Administrator access is required.');expect(screen.queryByRole('link',{name:'Admin'})).toBeNull();expect(screen.getByRole('button',{name:'Sign out'})).toBeTruthy();
});
