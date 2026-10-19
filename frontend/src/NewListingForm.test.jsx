import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import { App } from './App.jsx';

const categories=['Electronics','Clothing','Books','Furniture','Other'].map((label,index)=>({id:index+1,key:label.toLowerCase(),label}));
let fetchMock,create,revoke;
function response(status,data={}){return new Response(JSON.stringify(data),{status});}
function metadata(){return {id:7,title:'Useful book',description:'A useful textbook.',price:'12.34',currency:'KZT',category_id:3,condition:'used',status:'pending',created_at:'2026-10-13T00:00:00Z',published_at:null};}
function photo(position){return {id:100+position,listing_id:7,position,is_main:position===1,url:`/listings/7/photos/${100+position}`};}
function setup({load,createListing,upload}={}){
 fetchMock.mockImplementation((url,options)=>{
  const path=new URL(url).pathname;
  if(path==='/auth/csrf')return Promise.resolve(response(200,{csrf_token:'a'.repeat(64)}));
  if(path==='/auth/refresh')return Promise.resolve(response(200,{access_token:'secret-token',token_type:'bearer',expires_in:900}));
  if(path==='/auth/me')return Promise.resolve(response(200,{id:1,email:'student@sdu.edu.kz',verified:true,is_admin:false}));
  if(path==='/categories')return load?load():Promise.resolve(response(200,categories));
  if(path==='/listings')return createListing?createListing(options):Promise.resolve(response(201,metadata()));
  if(path==='/listings/7/photos')return upload(options);
  throw new Error('Unexpected test route');
 });
}
async function open(){window.history.replaceState(null,'','/listings/new');const view=render(<App/>);await screen.findByRole('form',{name:'New listing'});return view;}
function fill(price='12.3400'){
 fireEvent.change(screen.getByLabelText('Title'),{target:{value:'  Useful book  '}});
 fireEvent.change(screen.getByLabelText('Description'),{target:{value:'  A useful textbook.  '}});
 fireEvent.change(screen.getByLabelText('Price (KZT)'),{target:{value:price}});
 fireEvent.change(screen.getByLabelText('Category'),{target:{value:'3'}});
}
function file(name='one.png'){return new File(['image'],name,{type:'image/png'});}
function select(files){fireEvent.change(screen.getByLabelText('Optional photos'),{target:{files}});}
function submit(){fireEvent.submit(screen.getByRole('form',{name:'New listing'}));}
function creations(){return fetchMock.mock.calls.filter(([url])=>url.endsWith('/listings'));}
function uploads(){return fetchMock.mock.calls.filter(([url])=>url.endsWith('/listings/7/photos'));}
beforeEach(()=>{
 fetchMock=vi.fn();vi.stubGlobal('fetch',fetchMock);let index=0;create=vi.fn(()=>`blob:selection-${++index}`);revoke=vi.fn();
 vi.stubGlobal('URL',class extends URL{});URL.createObjectURL=create;URL.revokeObjectURL=revoke;
});
afterEach(()=>{vi.unstubAllGlobals();vi.restoreAllMocks();});

test('category loading/retry is safe and metadata-only submission is exact Pending creation',async()=>{
 let finish,attempt=0;
 setup({load:()=>++attempt===1?new Promise(resolve=>{finish=resolve;}):Promise.resolve(response(200,categories))});
 window.history.replaceState(null,'','/listings/new');render(<App/>);
 await screen.findByText('Loading categories…');await waitFor(()=>expect(typeof finish).toBe('function'));
 await act(async()=>finish(response(500,{detail:'SENSITIVE_DRIVER'})));
 expect(screen.getByRole('alert').textContent).toContain('could not be loaded');
 fireEvent.click(screen.getByRole('button',{name:'Retry categories'}));await screen.findByRole('form',{name:'New listing'});
 fill();submit();await screen.findByText('Creation complete. Awaiting manual admin review.');
 expect(JSON.parse(creations()[0][1].body)).toEqual({title:'Useful book',description:'A useful textbook.',price:'12.34',category_id:3,condition:'used'});
 expect(creations()[0][1].headers.Authorization).toBe('Bearer secret-token');expect(uploads()).toHaveLength(0);
 expect(screen.getByText(/Listing #7 saved as Pending/)).toBeTruthy();expect(screen.getByText(/is not public/)).toBeTruthy();
 expect(screen.getByRole('link',{name:'Go to your profile'}).getAttribute('href')).toBe('/profile');
});

test('strict text/decimal/category/file validation blocks invalid creation and accepts five ordered previews',async()=>{
 setup();await open();fill();
 for(const value of ['1.005','-1','1e2','01','1000000000.01','1,20']){fireEvent.change(screen.getByLabelText('Price (KZT)'),{target:{value}});submit();expect(screen.getByRole('alert').textContent).toContain('decimal');}
 fill();fireEvent.change(screen.getByLabelText('Title'),{target:{value:'ab'}});submit();expect(screen.getByRole('alert').textContent).toContain('3–120');
 fill();fireEvent.change(screen.getByLabelText('Category'),{target:{value:''}});submit();expect(screen.getByRole('alert').textContent).toContain('Choose a category');
 select(Array.from({length:6},(_,i)=>file(`${i}.png`)));expect(screen.getByRole('alert').textContent).toContain('at most five');
 select([new File(['svg'],'bad.svg',{type:'image/svg+xml'})]);expect(screen.getByRole('alert').textContent).toContain('JPEG');
 select([new File([new Uint8Array(5*1024*1024+1)],'big.png',{type:'image/png'})]);expect(screen.getByRole('alert').textContent).toContain('five MiB');
 select(Array.from({length:5},(_,i)=>file(`${i}.png`)));
 expect(screen.getAllByRole('img')).toHaveLength(5);expect(screen.getByRole('img',{name:'Selected photo 1 (main)'})).toBeTruthy();
 expect(creations()).toHaveLength(0);
});

test('preview removal/reselection/unmount revoke URLs without exposing credentials',async()=>{
 setup();const view=await open();select([file('one.png'),file('two.png')]);
 fireEvent.click(screen.getByRole('button',{name:'Remove selection 1'}));expect(revoke).toHaveBeenCalledWith('blob:selection-1');
 expect(screen.getByRole('img').getAttribute('src')).toBe('blob:selection-2');
 select([file('replacement.png')]);expect(revoke).toHaveBeenCalledWith('blob:selection-2');
 expect(screen.getByRole('img').getAttribute('src')).not.toContain('secret-token');
 view.unmount();expect(revoke).toHaveBeenCalledWith('blob:selection-3');
});

test('metadata and sequential uploads have pending protection and multipart order',async()=>{
 let finishCreation,finishFirst;let uploadCount=0;
 setup({createListing:()=>new Promise(resolve=>{finishCreation=resolve;}),upload:()=>++uploadCount===1?new Promise(resolve=>{finishFirst=resolve;}):Promise.resolve(response(201,photo(uploadCount)))});
 await open();fill();select([file('first.png'),file('second.png')]);submit();submit();expect(creations()).toHaveLength(1);
 expect(screen.getByRole('button',{name:'Saving…'}).disabled).toBe(true);
 await act(async()=>finishCreation(response(201,metadata())));await waitFor(()=>expect(typeof finishFirst).toBe('function'));
 expect(uploads()).toHaveLength(1);expect(uploads()[0][1].body.get('image').name).toBe('first.png');
 expect([...uploads()[0][1].body.keys()]).toEqual(['image']);expect(uploads()[0][1].headers['Content-Type']).toBeUndefined();
 expect(screen.getByLabelText('Optional photos').disabled).toBe(true);submit();expect(creations()).toHaveLength(1);
 await act(async()=>finishFirst(response(201,photo(1))));await screen.findByText('Creation complete. Awaiting manual admin review.');
 expect(uploads()).toHaveLength(2);expect(uploads()[1][1].body.get('image').name).toBe('second.png');
 expect(screen.getByText(/2 of 2 selected photos confirmed saved/)).toBeTruthy();
});

test('known failed upload retries only remaining photos and never recreates metadata',async()=>{
 let count=0;
 setup({upload:()=>Promise.resolve(++count===2?response(400):response(201,photo(count===3?2:1)))});
 await open();fill();select([file('first.png'),file('second.png')]);submit();
 await screen.findByRole('alert');expect(screen.getByText(/1 of 2 selected photos confirmed saved/)).toBeTruthy();
 expect(screen.queryByText('Creation complete. Awaiting manual admin review.')).toBeNull();
 expect(screen.getByRole('button',{name:'Remove selection 1'}).disabled).toBe(true);
 fireEvent.click(screen.getByRole('button',{name:'Retry remaining photos'}));await screen.findByText('Creation complete. Awaiting manual admin review.');
 expect(creations()).toHaveLength(1);expect(uploads()).toHaveLength(3);
 expect(uploads().map(([,options])=>options.body.get('image').name)).toEqual(['first.png','second.png','second.png']);
});

test('contact prerequisite gives a real profile action without claiming creation',async()=>{
 setup({createListing:()=>Promise.resolve(response(400,{detail:'SENSITIVE_CONTACT'}))});await open();fill();submit();
 await screen.findByRole('link',{name:'Add your profile contact'});expect(screen.getByRole('alert').textContent).toContain('valid contact');
 expect(screen.queryByText(/Listing #7/)).toBeNull();expect(screen.getByRole('button',{name:'Create Pending listing'}).disabled).toBe(false);
});

test.each([['creation','network'],['photo','network'],['creation','server'],['photo','server'],['creation','response'],['photo','response']])('ambiguous %s %s response blocks blind retry and preserves confirmed boundary',async(stage,kind)=>{
 const storage=vi.spyOn(Storage.prototype,'setItem');
 const failure=()=>kind==='network'?Promise.reject(new Error('SENSITIVE_NETWORK')):Promise.resolve(kind==='server'?response(503,{detail:'SENSITIVE_SERVER'}):response(201,{}));
 setup({createListing:stage==='creation'?failure:undefined,upload:failure});
 await open();fill();if(stage==='photo')select([file()]);submit();await screen.findByRole('alert');
 expect(screen.getByRole('alert').textContent).toContain('uncertain');expect(screen.getByRole('alert').textContent).not.toContain('SENSITIVE');
 expect(screen.getByRole('button',{name:stage==='creation'?'Create Pending listing':'Retry remaining photos'}).disabled).toBe(true);
 submit();expect(creations()).toHaveLength(1);expect(uploads()).toHaveLength(stage==='photo'?1:0);
 expect(screen.queryByText('Creation complete. Awaiting manual admin review.')).toBeNull();expect(storage).not.toHaveBeenCalled();expect(window.location.search).toBe('');
 if(stage==='photo')expect(screen.getByText(/0 of 1 selected photos confirmed saved/)).toBeTruthy();
});

test('listing quota rejection is safe retry guidance without uncertain creation or false success',async()=>{setup({createListing:()=>Promise.resolve(new Response('{}',{status:429,headers:{'Retry-After':'240'}}))});await open();fill();submit();await screen.findByRole('alert');expect(screen.getByRole('alert').textContent).toContain('Retry after 240 seconds');expect(screen.getByRole('alert').textContent).not.toContain('may have been created');expect(screen.getByLabelText('Title').disabled).toBe(false);expect(fetchMock.mock.calls.filter(([url])=>new URL(url).pathname==='/listings')).toHaveLength(1);});
