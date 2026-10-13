import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import { App, safeReturnPath } from './App.jsx';

const item={id:7,title:'Original title',price:'12.34',description:'Original description.',status:'active',published_at:'2026-10-13T00:00:00Z'};
let fetchMock;
function response(status,data={}){return new Response(JSON.stringify(data),{status});}
function setup({load,save,listing=item}={}){
 fetchMock.mockImplementation((url,options)=>{
  const path=new URL(url).pathname;
  if(path==='/auth/csrf')return Promise.resolve(response(200,{csrf_token:'a'.repeat(64)}));
  if(path==='/auth/refresh')return Promise.resolve(response(200,{access_token:'secret-token',token_type:'bearer',expires_in:900}));
  if(path==='/auth/me')return Promise.resolve(response(200,{id:1,email:'student@sdu.edu.kz',verified:true}));
  if(path==='/listings/7/edit')return load?load():Promise.resolve(response(200,listing));
  if(path==='/listings/7')return save?save(options):Promise.resolve(response(200,{...listing,...JSON.parse(options.body)}));
  throw new Error('Unexpected test route');
 });
}
async function open(){window.history.replaceState(null,'','/listings/7/edit');render(<App/>);await screen.findByRole('form',{name:'Edit listing'});}
function change(label,value){fireEvent.change(screen.getByLabelText(label),{target:{value}});}
function submit(){fireEvent.submit(screen.getByRole('form',{name:'Edit listing'}));}
function patches(){return fetchMock.mock.calls.filter(([,options])=>options.method==='PATCH');}
beforeEach(()=>{fetchMock=vi.fn();vi.stubGlobal('fetch',fetchMock);});
afterEach(()=>{vi.unstubAllGlobals();vi.restoreAllMocks();});

test('exact owner edit route loads safely and retries before showing read-only metadata',async()=>{
 let finish,attempt=0;
 setup({load:()=>++attempt===1?new Promise(resolve=>{finish=resolve;}):Promise.resolve(response(200,item))});
 window.history.replaceState(null,'','/listings/7/edit');render(<App/>);await screen.findByText('Loading your listing…');await waitFor(()=>expect(typeof finish).toBe('function'));
 await act(async()=>finish(response(500,{detail:'SENSITIVE'})));expect(screen.getByRole('alert').textContent).toContain('could not be loaded');
 fireEvent.click(screen.getByRole('button',{name:'Retry listing'}));await screen.findByRole('form',{name:'Edit listing'});
 for(const label of ['Title (read-only)','Status (read-only)','Publication (read-only)'])expect(screen.getByLabelText(label).readOnly).toBe(true);
 expect(screen.getByLabelText('Title (read-only)').value).toBe(item.title);
 expect(safeReturnPath('/listings/7/edit')).toBe('/listings/7/edit');
 for(const path of ['/listings/07/edit','/listings/7/edit?next=evil','//evil.test/edit','/listings/%37/edit','/listings/9223372036854775808/edit'])expect(safeReturnPath(path)).toBe('/marketplace');
});

test('changed-only exact price PATCH uses returned authoritative status and blocks empty save',async()=>{
 setup({save:options=>Promise.resolve(response(200,{...item,...JSON.parse(options.body),status:'sold'}))});await open();submit();expect(patches()).toHaveLength(0);
 expect(screen.getByRole('button',{name:'Save changes'}).disabled).toBe(true);
 change('Price (KZT)','15.6700');submit();await screen.findByText('Listing changes saved. Approval and publication were preserved.');
 expect(JSON.parse(patches()[0][1].body)).toEqual({price:'15.67'});expect(patches()[0][1].headers.Authorization).toBe('Bearer secret-token');
 expect(screen.getByLabelText('Status (read-only)').value).toBe('sold');expect(screen.getByLabelText('Price (KZT)').value).toBe('15.67');
 expect(screen.getByRole('button',{name:'Save changes'}).disabled).toBe(true);
});

test('description trims and validation rejects bad limits/precision without forbidden mutations',async()=>{
 setup();await open();
 for(const price of ['1.005','-1','1000000000.01','1e2']){change('Price (KZT)',price);submit();expect(screen.getByRole('alert').textContent).toContain('decimal');}
 change('Price (KZT)','12.34');
 for(const description of [' ', 'x'.repeat(9),'x'.repeat(2001)]){change('Description',description);submit();expect(screen.getByRole('alert').textContent).toContain('10–2000');}
 expect(patches()).toHaveLength(0);
 change('Description','  Updated description.  ');submit();await screen.findByText('Listing changes saved. Approval and publication were preserved.');
 expect(JSON.parse(patches()[0][1].body)).toEqual({description:'Updated description.'});
});

test('pending save prevents duplicates and failure preserves edits without automatic replay',async()=>{
 let finish;setup({save:()=>new Promise(resolve=>{finish=resolve;})});await open();change('Price (KZT)','20.00');submit();submit();
 expect(patches()).toHaveLength(1);expect(screen.getByRole('button',{name:'Saving changes…'}).disabled).toBe(true);expect(screen.getByLabelText('Description').disabled).toBe(true);
 await act(async()=>finish(response(500,{detail:'SENSITIVE_DRIVER'})));
 expect(screen.getByRole('alert').textContent).toContain('could not be confirmed');expect(screen.getByLabelText('Price (KZT)').value).toBe('20.00');
 expect(screen.queryByText('Listing changes saved. Approval and publication were preserved.')).toBeNull();expect(patches()).toHaveLength(1);
});

test.each(['rejected','removed'])('%s current state is readable but price/description cannot be edited',async status=>{
 setup({listing:{...item,status,published_at:null}});await open();
 expect(screen.getByLabelText('Price (KZT)').disabled).toBe(true);expect(screen.getByRole('button',{name:'Save changes'}).disabled).toBe(true);
 submit();expect(patches()).toHaveLength(0);expect(screen.getByRole('status').textContent).toContain('cannot be edited');
});

test('missing owner listing is safe and stale state rejection blocks editing until reload',async()=>{
 let missing=true;
 setup({load:()=>Promise.resolve(missing?response(404):response(200,item)),save:()=>Promise.resolve(response(409))});
 window.history.replaceState(null,'','/listings/7/edit');render(<App/>);await screen.findByRole('alert');expect(screen.queryByRole('form',{name:'Edit listing'})).toBeNull();
 missing=false;fireEvent.click(screen.getByRole('button',{name:'Retry listing'}));await screen.findByRole('form',{name:'Edit listing'});
 change('Price (KZT)','20.00');submit();await screen.findByRole('button',{name:'Reload listing state'});
 expect(screen.getByLabelText('Price (KZT)').value).toBe('20.00');expect(screen.getByRole('button',{name:'Save changes'}).disabled).toBe(true);
 expect(patches()).toHaveLength(1);
});
