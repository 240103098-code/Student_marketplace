import React from 'react';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import { App } from './App.jsx';

let fetchMock,create,revoke;
function item(id,status='active',photos=[]){return {id,title:`Own item ${id}`,description:'A useful description.',price:'12.34',currency:'KZT',category_id:1,condition:'used',status,created_at:'2026-10-13T00:00:00Z',published_at:status==='active'||status==='sold'?'2026-10-13T00:00:00Z':null,rejection_reason:status==='rejected'?'Prohibited item.':null,photos};}
function response(status,data={}){return new Response(JSON.stringify(data),{status});}
function page(items,total=items.length,status=null,offset=0){return {items,total,count:items.length,limit:20,offset,status};}
function setup(load,photo=()=>Promise.resolve(new Response(new Uint8Array([1,2]),{status:200,headers:{'Content-Type':'image/png'}})),sold,remove){
 fetchMock.mockImplementation((url,options)=>{
  const parsed=new URL(url),path=parsed.pathname;
  if(path==='/auth/csrf')return Promise.resolve(response(200,{csrf_token:'a'.repeat(64)}));
  if(path==='/auth/refresh')return Promise.resolve(response(200,{access_token:'secret-access',token_type:'bearer',expires_in:900}));
  if(path==='/auth/me')return Promise.resolve(response(200,{id:1,email:'student@sdu.edu.kz',verified:true,is_admin:false}));
  if(path==='/listings/mine')return load(parsed.searchParams,options);
  if(path==='/listings/7/edit')return Promise.resolve(response(200,{id:7,title:'Own item 7',price:'12.34',description:'A useful description.',status:'active',published_at:'2026-10-13T00:00:00Z'}));
  if(path.includes('/photos/'))return photo(options);
  if(path.endsWith('/sold'))return sold(options);
  if(options.method==='DELETE'&&path==='/listings/7')return remove(options);
  throw new Error('Unexpected test route');
 });
}
async function open(){window.history.replaceState(null,'','/my-listings');const view=render(<App/>);await screen.findByRole('heading',{name:'My Listings'});return view;}
beforeEach(()=>{fetchMock=vi.fn();vi.stubGlobal('fetch',fetchMock);let index=0;create=vi.fn(()=>`blob:private-${++index}`);revoke=vi.fn();vi.stubGlobal('URL',class extends URL{});URL.createObjectURL=create;URL.revokeObjectURL=revoke;});
afterEach(()=>{vi.unstubAllGlobals();vi.restoreAllMocks();});

test('own dashboard loading/error/retry and empty view are honest',async()=>{
 let finish,attempt=0;setup(()=>++attempt===1?new Promise(resolve=>{finish=resolve;}):Promise.resolve(response(200,page([]))));await open();
 await screen.findByText('Loading your listings…');await waitFor(()=>expect(typeof finish).toBe('function'));
 await act(async()=>finish(response(500,{detail:'SENSITIVE_DRIVER'})));
 expect(screen.getByRole('alert').textContent).toContain('could not be loaded');fireEvent.click(screen.getByRole('button',{name:'Retry listings'}));
 await screen.findByText('No listings in this view.');expect(screen.getByRole('button',{name:'Next page'}).disabled).toBe(true);
 expect(screen.getByRole('link',{name:'Create a new listing'}).getAttribute('href')).toBe('/listings/new');
});

test('status views reset bounded pagination and preserve query contract',async()=>{
 setup(params=>{const status=params.get('status'),offset=Number(params.get('offset'));return Promise.resolve(response(200,page(offset? [item(25,status||'active')]:Array.from({length:20},(_,i)=>item(i+1,status||'active')),25,status,offset)));});await open();
 await screen.findByRole('heading',{name:'Own item 1'});fireEvent.click(screen.getByRole('button',{name:'Next page'}));await screen.findByRole('heading',{name:'Own item 25'});
 expect(screen.getByRole('button',{name:'Next page'}).disabled).toBe(true);expect(screen.getByRole('button',{name:'Previous page'}).disabled).toBe(false);
 fireEvent.change(screen.getByLabelText('Listing status'),{target:{value:'sold'}});await screen.findByRole('heading',{name:'Own item 1'});
 const calls=fetchMock.mock.calls.filter(([url])=>new URL(url).pathname==='/listings/mine');
 expect(new URL(calls[1][0]).searchParams.get('offset')).toBe('20');expect(new URL(calls[2][0]).searchParams.get('offset')).toBe('0');expect(new URL(calls[2][0]).searchParams.get('status')).toBe('sold');
 expect(calls.every(([url])=>new URL(url).searchParams.get('limit')==='20')).toBe(true);
});

test('cards expose only allowed real actions and rejection/Removed guidance without private photo URLs',async()=>{
 const rows=['pending','active','sold','rejected','removed'].map((status,index)=>item(index+1,status));setup(()=>Promise.resolve(response(200,page(rows))));await open();await screen.findByRole('heading',{name:'Own item 1'});
 expect(screen.getAllByRole('link',{name:'Edit price or description'})).toHaveLength(3);
 const rejected=screen.getByRole('heading',{name:'Own item 4'}).closest('li');expect(within(rejected).queryByRole('link')).toBeNull();expect(rejected.textContent).toContain('Prohibited item.');
 const removed=screen.getByRole('heading',{name:'Own item 5'}).closest('li');expect(within(removed).queryByRole('link')).toBeNull();expect(removed.textContent).toContain('Photos are unavailable');
 expect(screen.getAllByRole('button',{name:'Mark Sold'})).toHaveLength(1);expect(screen.getAllByRole('button',{name:'Delete listing'})).toHaveLength(5);expect(screen.queryByRole('button',{name:/approve/i})).toBeNull();expect(fetchMock.mock.calls.some(([url])=>url.includes('/photos/'))).toBe(false);
});

test('main thumbnail fetch is authenticated binary and object URLs release on view change/unmount',async()=>{
 const photos=[{id:71,position:1,is_main:true,url:'/listings/7/photos/71'},{id:72,position:2,is_main:false,url:'/listings/7/photos/72'}];
 setup(params=>Promise.resolve(response(200,page([item(7,params.get('status')||'active',photos)],1,params.get('status')))));
 const view=await open();await screen.findByRole('img',{name:'Main listing photo'});
 const calls=fetchMock.mock.calls.filter(([url])=>url.includes('/photos/'));expect(calls).toHaveLength(1);expect(calls[0][0]).toContain('/photos/71');expect(calls[0][1].headers.Authorization).toBe('Bearer secret-access');expect(calls[0][1].credentials).toBe('include');
 expect(screen.getByRole('img').getAttribute('src')).toBe('blob:private-1');expect(screen.getByRole('img').src).not.toContain('secret-access');
 fireEvent.change(screen.getByLabelText('Listing status'),{target:{value:'sold'}});await waitFor(()=>expect(screen.getByRole('img').getAttribute('src')).toBe('blob:private-2'));expect(revoke).toHaveBeenCalledWith('blob:private-1');
 view.unmount();expect(revoke).toHaveBeenCalledWith('blob:private-2');
});

test('edit link navigates to actual own form and contact/photo values never persist in storage',async()=>{
 const storage=vi.spyOn(Storage.prototype,'setItem');setup(()=>Promise.resolve(response(200,page([item(7)]))));await open();await screen.findByRole('heading',{name:'Own item 7'});
 fireEvent.click(screen.getByRole('link',{name:'Edit price or description'}));await screen.findByRole('form',{name:'Edit listing'});expect(window.location.pathname).toBe('/listings/7/edit');expect(storage).not.toHaveBeenCalled();
});

test('revoked thumbnail authorization removes protected dashboard instead of retaining a public image',async()=>{
 let rotations=0;
 setup(()=>Promise.resolve(response(200,page([item(7,'active',[{id:71,position:1,is_main:true,url:'/listings/7/photos/71'}])]))),()=>Promise.resolve(response(401)));
 const previous=fetchMock.getMockImplementation();fetchMock.mockImplementation((url,options)=>url.endsWith('/auth/refresh')&&++rotations>1?Promise.resolve(response(401)):previous(url,options));
 await open();await screen.findByRole('heading',{name:'Sign in'});expect(screen.queryByRole('img')).toBeNull();expect(screen.queryByRole('heading',{name:'Own item 7'})).toBeNull();expect(create).not.toHaveBeenCalled();
});


test('sold confirmation cancel sends nothing; pending success reloads authoritative dashboard',async()=>{
 let finish,state='active';
 setup(()=>Promise.resolve(response(200,page([item(7,state)]))),undefined,()=>new Promise(resolve=>{finish=resolve;}));await open();await screen.findByRole('button',{name:'Mark Sold'});
 fireEvent.click(screen.getByRole('button',{name:'Mark Sold'}));fireEvent.click(screen.getByRole('button',{name:'Cancel'}));expect(fetchMock.mock.calls.filter(([url])=>url.endsWith('/sold'))).toHaveLength(0);
 fireEvent.click(screen.getByRole('button',{name:'Mark Sold'}));fireEvent.click(screen.getByRole('button',{name:'Confirm Sold'}));
 expect(screen.getByRole('button',{name:'Marking Sold…'}).disabled).toBe(true);fireEvent.click(screen.getByRole('button',{name:'Marking Sold…'}));
 const calls=fetchMock.mock.calls.filter(([url])=>url.endsWith('/sold'));expect(calls).toHaveLength(1);expect(calls[0][1].method).toBe('POST');expect(calls[0][1].body).toBeUndefined();expect(calls[0][1].headers.Authorization).toBe('Bearer secret-access');
 await act(async()=>{state='sold';finish(response(200,{id:7,status:'sold',published_at:item(7).published_at}));});
 await screen.findByText('12.34 KZT · Sold');expect(screen.queryByRole('button',{name:'Mark Sold'})).toBeNull();
});

test('failed sold action retains Active and never automatically replays or claims Sold',async()=>{
 setup(()=>Promise.resolve(response(200,page([item(7)]))),undefined,()=>Promise.reject(new Error('SENSITIVE_NETWORK')));await open();await screen.findByRole('button',{name:'Mark Sold'});
 fireEvent.click(screen.getByRole('button',{name:'Mark Sold'}));fireEvent.click(screen.getByRole('button',{name:'Confirm Sold'}));await screen.findByRole('alert');
 expect(screen.getByRole('alert').textContent).toContain('could not be confirmed');expect(screen.getByText('12.34 KZT · Active')).toBeTruthy();expect(fetchMock.mock.calls.filter(([url])=>url.endsWith('/sold'))).toHaveLength(1);
});

test('delete cancel sends nothing and confirmed pending cleanup reloads authoritative data',async()=>{
 let finish,deleted=false;
 setup(()=>Promise.resolve(response(200,page(deleted?[]:[item(7,'rejected')]))),undefined,undefined,()=>new Promise(resolve=>{finish=resolve;}));await open();await screen.findByRole('button',{name:'Delete listing'});
 fireEvent.click(screen.getByRole('button',{name:'Delete listing'}));fireEvent.click(screen.getByRole('button',{name:'Cancel deletion'}));expect(fetchMock.mock.calls.filter(([,o])=>o.method==='DELETE')).toHaveLength(0);
 fireEvent.click(screen.getByRole('button',{name:'Delete listing'}));fireEvent.click(screen.getByRole('button',{name:'Confirm deletion'}));await waitFor(()=>expect(typeof finish).toBe('function'));
 expect(screen.getByRole('button',{name:'Deleting…'}).disabled).toBe(true);fireEvent.click(screen.getByRole('button',{name:'Deleting…'}));
 const calls=fetchMock.mock.calls.filter(([,o])=>o.method==='DELETE');expect(calls).toHaveLength(1);expect(calls[0][1].body).toBeUndefined();expect(calls[0][1].headers.Authorization).toBe('Bearer secret-access');
 await act(async()=>{deleted=true;finish(response(200,{id:7,deleted:true,cleanup_pending:true}));});await screen.findByText('No listings in this view.');expect(screen.getByText('Listing deleted. Some photo-file cleanup is still pending.')).toBeTruthy();
});
test('ambiguous deletion requires review and never automatically replays or claims success',async()=>{
 let absent=false;setup(()=>Promise.resolve(response(200,page(absent?[]:[item(7)]))),undefined,undefined,()=>Promise.reject(new Error('PRIVATE_NETWORK')));await open();await screen.findByRole('button',{name:'Delete listing'});
 fireEvent.click(screen.getByRole('button',{name:'Delete listing'}));fireEvent.click(screen.getByRole('button',{name:'Confirm deletion'}));await screen.findByRole('alert');expect(screen.getByRole('alert').textContent).toContain('may already be absent');expect(screen.queryByText(/Listing deleted\./)).toBeNull();
 absent=true;fireEvent.click(screen.getByRole('button',{name:'Reload listings to review'}));await screen.findByText('No listings in this view.');expect(fetchMock.mock.calls.filter(([,o])=>o.method==='DELETE')).toHaveLength(1);
});
test('deleting the last item on the last page reloads the nearest valid page',async()=>{
 let deleted=false;setup(params=>{const offset=Number(params.get('offset'));return Promise.resolve(response(200,page(offset?(deleted?[]:[item(7)]):Array.from({length:20},(_,i)=>item(i+30)),deleted?20:21,null,offset)));},undefined,undefined,()=>{deleted=true;return Promise.resolve(response(200,{id:7,deleted:true,cleanup_pending:false}));});await open();await screen.findByRole('heading',{name:'Own item 30'});fireEvent.click(screen.getByRole('button',{name:'Next page'}));await screen.findByRole('heading',{name:'Own item 7'});fireEvent.click(screen.getByRole('button',{name:'Delete listing'}));fireEvent.click(screen.getByRole('button',{name:'Confirm deletion'}));await screen.findByRole('heading',{name:'Own item 30'});expect(screen.getByRole('button',{name:'Previous page'}).disabled).toBe(true);expect(screen.getByRole('button',{name:'Next page'}).disabled).toBe(true);
});
