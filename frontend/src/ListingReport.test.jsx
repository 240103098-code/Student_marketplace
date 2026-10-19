import React from 'react';
import {act,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {beforeEach,afterEach,test,expect,vi} from 'vitest';
import {App} from './App.jsx';
let mock;
const res=(status,data)=>new Response(JSON.stringify(data),{status});
function setup(report){mock.mockImplementation((url,o)=>{const path=new URL(url).pathname;if(path==='/auth/csrf')return Promise.resolve(res(200,{csrf_token:'a'.repeat(64)}));if(path==='/auth/refresh')return Promise.resolve(res(200,{access_token:'secret',token_type:'bearer',expires_in:900}));if(path==='/auth/me')return Promise.resolve(res(200,{id:1,email:'s@sdu.edu.kz',verified:true,is_admin:false}));if(path==='/listings/7')return Promise.resolve(res(200,{id:7,title:'A useful book',description:'A useful textbook.',price:'12.34',currency:'KZT',category_id:3,condition:'used',published_at:'2026-10-13T00:00:00Z',photos:[],seller:{name:null,phone:null,telegram_username:null,external_contact_url:null}}));if(path==='/listings/7/reports')return report(o);throw Error('Unexpected fixture');});}
async function open(){window.history.replaceState(null,'','/listings/7');render(<App/>);await screen.findByRole('form',{name:'Report listing'});}
const submit=()=>fireEvent.submit(screen.getByRole('form',{name:'Report listing'}));
const choose=value=>fireEvent.change(screen.getByLabelText('Report reason'),{target:{value}});
const reports=()=>mock.mock.calls.filter(([url])=>url.endsWith('/reports'));
beforeEach(()=>{mock=vi.fn();vi.stubGlobal('fetch',mock);});afterEach(()=>vi.unstubAllGlobals());
test('report reason validation, exact payload, pending prevention and confirmed acceptance',async()=>{
 let finish;setup(()=>new Promise(r=>{finish=r;}));await open();submit();expect(screen.getByRole('alert').textContent).toBe('Choose a report reason.');expect(reports()).toHaveLength(0);choose('prohibited_items');submit();await waitFor(()=>expect(typeof finish).toBe('function'));expect(screen.getByLabelText('Report reason').disabled).toBe(true);expect(screen.getByRole('button',{name:'Submitting report…'}).disabled).toBe(true);submit();expect(reports()).toHaveLength(1);const call=reports()[0];expect(JSON.parse(call[1].body)).toEqual({reason:'prohibited_items'});expect(call[1].headers.Authorization).toBe('Bearer secret');expect(call[1].method).toBe('POST');await act(async()=>finish(res(202,{accepted:true})));await screen.findByText('Report accepted for later moderation review. Repeating a report keeps the original report.');expect(screen.getByLabelText('Report reason').disabled).toBe(false);
});
test('ambiguous network failure never claims acceptance and explicit retry is safe',async()=>{
 let attempt=0;setup(()=>++attempt===1?Promise.reject(Error('PRIVATE_NETWORK')):Promise.resolve(res(202,{accepted:true})));await open();choose('spam');submit();await screen.findByRole('alert');expect(screen.getByRole('alert').textContent).toContain('could not be confirmed');expect(screen.getByRole('alert').textContent).toContain('retry');expect(reports()).toHaveLength(1);expect(screen.queryByText(/Report accepted for/)).toBeNull();submit();await screen.findByText('Report accepted for later moderation review. Repeating a report keeps the original report.');expect(reports()).toHaveLength(2);
});
test('self/private/malformed response errors are safe without changing logged-in account',async()=>{
 let status=400;setup(()=>Promise.resolve(res(status,status===202?{id:'private'}:{})));await open();choose('misleading_information');submit();await screen.findByText('You cannot report your own listing.');expect(screen.getByRole('button',{name:'Sign out'})).toBeTruthy();status=404;submit();await screen.findByText('This listing is no longer available to report.');status=202;submit();await screen.findByText('Report submission could not be confirmed. You can retry; repeated reports are accepted without duplicates.');expect(screen.queryByText(/Report accepted for/)).toBeNull();
});
test('current-session failure removes protected report content',async()=>{
 setup(()=>Promise.resolve(res(401,{})));await open();choose('spam');submit();await screen.findByRole('heading',{name:'Sign in'});expect(screen.queryByRole('form',{name:'Report listing'})).toBeNull();expect(reports()).toHaveLength(1);
});

test('quota rejection retains report input with honest Retry-After and no acceptance',async()=>{setup(()=>Promise.resolve(new Response('{}',{status:429,headers:{'Retry-After':'180'}})));await open();choose('spam');submit();await screen.findByRole('alert');expect(screen.getByRole('alert').textContent).toContain('Retry after 180 seconds');expect(screen.queryByText(/Report accepted for/)).toBeNull();expect(reports()).toHaveLength(1);});
