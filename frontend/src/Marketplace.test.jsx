import React from 'react';
import {act,fireEvent,render,screen,waitFor,within} from '@testing-library/react';
import {beforeEach,afterEach,test,expect,vi} from 'vitest';
import {App} from './App.jsx';
let mock,create,revoke;
const categories=['Electronics','Clothing','Books','Furniture','Other'].map((label,i)=>({id:i+1,key:['electronics','clothing','books','furniture','other'][i],label}));
const photo={id:71,position:1,is_main:true,url:'/listings/7/photos/71'};
const card=(id=7,image=null)=>({id,title:`Campus item ${id}`,price:'12.34',currency:'KZT',category_id:1,condition:'used',published_at:'2026-10-13T00:00:00Z',main_photo:image});
const page=(items,total=items.length,offset=0)=>({items,total,count:items.length,limit:20,offset});
const res=(status,data)=>new Response(JSON.stringify(data),{status});
function setup(feed,category=()=>Promise.resolve(res(200,categories)),image=()=>Promise.resolve(new Response(new Uint8Array([1]),{status:200,headers:{'Content-Type':'image/png'}}))){mock.mockImplementation((url,options)=>{const parsed=new URL(url),path=parsed.pathname;
 if(path==='/auth/csrf')return Promise.resolve(res(200,{csrf_token:'a'.repeat(64)}));if(path==='/auth/refresh')return Promise.resolve(res(200,{access_token:'secret',token_type:'bearer',expires_in:900}));if(path==='/auth/me')return Promise.resolve(res(200,{id:1,email:'s@sdu.edu.kz',verified:true,is_admin:false}));if(path==='/categories')return category();if(path==='/listings')return feed(parsed.searchParams);if(path.includes('/photos/'))return image();throw Error('Unexpected fixture');});}
async function open(path='/marketplace'){window.history.replaceState(null,'',path);const view=render(<App/>);await screen.findByRole('heading',{name:'Marketplace'});return view;}
const change=(label,value)=>fireEvent.change(screen.getByLabelText(label),{target:{value}});
const apply=()=>fireEvent.submit(screen.getByRole('form',{name:'Search and filter listings'}));
const feeds=()=>mock.mock.calls.filter(([url])=>new URL(url).pathname==='/listings');
beforeEach(()=>{mock=vi.fn();vi.stubGlobal('fetch',mock);let n=0;create=vi.fn(()=>`blob:market-${++n}`);revoke=vi.fn();URL.createObjectURL=create;URL.revokeObjectURL=revoke;});
afterEach(()=>{vi.unstubAllGlobals();vi.restoreAllMocks();});
test('home, combined encoded filters, pagination and apply/reset retain server cards',async()=>{
 setup(p=>Promise.resolve(res(200,page([card(Number(p.get('offset'))?8:7)],21,Number(p.get('offset'))))));await open('/');await screen.findByRole('heading',{name:'Campus item 7'});await waitFor(()=>expect(screen.getByLabelText('Category').disabled).toBe(false));expect(window.location.pathname).toBe('/marketplace');
 change('Search listings','  book %_!  ');change('Category','1');change('Condition','used');change('Minimum price (KZT)','0.1000');change('Maximum price (KZT)','100.00');apply();await screen.findByRole('heading',{name:'Campus item 7'});fireEvent.click(screen.getByRole('button',{name:'Next page'}));await screen.findByRole('heading',{name:'Campus item 8'});
 const call=feeds().at(-1);expect(Object.fromEntries(new URL(call[0]).searchParams)).toEqual({limit:'20',offset:'20',q:'book %_!',category_id:'1',condition:'used',min_price:'0.1000',max_price:'100.00'});expect(call[1].headers.Authorization).toBe('Bearer secret');expect(call[1].credentials).toBe('include');apply();await screen.findByRole('heading',{name:'Campus item 7'});fireEvent.click(screen.getByRole('button',{name:'Reset filters'}));await waitFor(()=>expect(Object.fromEntries(new URL(feeds().at(-1)[0]).searchParams)).toEqual({limit:'20',offset:'0'}));expect(screen.getByText('12.34 KZT')).toBeTruthy();expect(screen.queryByRole('link',{name:/details|contact/i})).toBeNull();
});
test('exact prices/range/search bounds prevent invalid requests',async()=>{
 setup(()=>Promise.resolve(res(200,page([]))));await open();await screen.findByText('No matching listings. Try different filters.');for(const value of ['1e2','-1','01','1.001','1000000000.01',' 1']){change('Minimum price (KZT)',value);apply();expect(screen.getByRole('alert')).toBeTruthy();expect(feeds()).toHaveLength(1);}change('Minimum price (KZT)','2');change('Maximum price (KZT)','1');apply();expect(screen.getByRole('alert').textContent).toContain('must not exceed');change('Minimum price (KZT)','');change('Maximum price (KZT)','');change('Search listings','x'.repeat(201));apply();expect(screen.getByRole('alert').textContent).toContain('200');change('Search listings','a\u0085b');apply();expect(feeds()).toHaveLength(1);change('Search listings','x'.repeat(200));apply();await waitFor(()=>expect(feeds()).toHaveLength(2));
});
test('loading, malformed/error and retries remain distinct from empty results',async()=>{
 let finish,cat,a=0,b=0;setup(()=>++a===1?new Promise(r=>{finish=r;}):Promise.resolve(res(200,page([]))),()=>++b===1?new Promise(r=>{cat=r;}):Promise.resolve(res(200,categories)));await open();await screen.findByText('Loading categories…');await waitFor(()=>expect(typeof finish).toBe('function'));await waitFor(()=>expect(typeof cat).toBe('function'));await act(async()=>{finish(res(200,{items:[]}));cat(res(500,{}));});expect(screen.getAllByRole('alert')).toHaveLength(2);expect(screen.queryByText('No matching listings. Try different filters.')).toBeNull();fireEvent.click(screen.getByRole('button',{name:'Retry categories'}));fireEvent.click(screen.getByRole('button',{name:'Retry marketplace'}));await screen.findByText('No matching listings. Try different filters.');await waitFor(()=>expect(screen.getByLabelText('Category').disabled).toBe(false));
});
test('new query wins over stale feed/photo and releases private blobs',async()=>{
 let feed,image;setup(p=>p.get('q')==='old'?new Promise(r=>{feed=r;}):Promise.resolve(res(200,page([card(p.get('q')==='new'?9:7,p.get('q')==='new'?null:photo)]))),undefined,()=>new Promise(r=>{image=r;}));const view=await open();await screen.findByRole('heading',{name:'Campus item 7'});await waitFor(()=>expect(typeof image).toBe('function'));change('Search listings','old');apply();await waitFor(()=>expect(typeof feed).toBe('function'));change('Search listings','new');apply();await screen.findByRole('heading',{name:'Campus item 9'});await act(async()=>{feed(res(200,page([card(8)])));image(new Response(new Uint8Array([1]),{status:200,headers:{'Content-Type':'image/png'}}));});expect(screen.queryByRole('heading',{name:'Campus item 8'})).toBeNull();expect(screen.queryByRole('img')).toBeNull();expect(create).not.toHaveBeenCalled();view.unmount();
});
test('main images use Bearer binary routes and revoke on apply/unmount',async()=>{
 setup(()=>Promise.resolve(res(200,page([card(7,photo)]))));const view=await open();await screen.findByRole('img');const call=mock.mock.calls.find(([url])=>url.includes('/photos/'));expect(call[1].headers.Authorization).toBe('Bearer secret');expect(call[0]).not.toContain('secret');expect(screen.getByRole('img').getAttribute('src')).toBe('blob:market-1');apply();await waitFor(()=>expect(revoke).toHaveBeenCalledWith('blob:market-1'));await screen.findByRole('img');view.unmount();expect(revoke).toHaveBeenCalledWith('blob:market-2');
});
test('unsafe linkage fails feed without image fetch or false empty result',async()=>{
 setup(()=>Promise.resolve(res(200,page([card(7,{...photo,url:'https://outside.test/image'})]))));await open();await screen.findByRole('alert');expect(mock.mock.calls.some(([url])=>url.includes('outside.test'))).toBe(false);expect(screen.queryByText('No matching listings. Try different filters.')).toBeNull();
});
test('revoked photo authorization removes marketplace, anonymous visitors fetch no protected data',async()=>{
 let refresh=0;setup(()=>Promise.resolve(res(200,page([card(7,photo)]))),undefined,()=>Promise.resolve(res(401,{})));const previous=mock.getMockImplementation();mock.mockImplementation((url,o)=>url.endsWith('/auth/refresh')&&++refresh>1?Promise.resolve(res(401,{})):previous(url,o));const view=await open();await screen.findByRole('heading',{name:'Sign in'});expect(screen.queryByRole('heading',{name:'Campus item 7'})).toBeNull();expect(create).not.toHaveBeenCalled();view.unmount();mock.mockReset();mock.mockResolvedValue(res(401,{}));window.history.replaceState(null,'','/marketplace');render(<App/>);await screen.findByRole('heading',{name:'Sign in'});expect(feeds()).toHaveLength(0);expect(mock.mock.calls.some(([url])=>url.includes('/photos/'))).toBe(false);
});
test('photo transport errors retain honest cards and server order without leaking details',async()=>{
 setup(()=>Promise.resolve(res(200,page([card(7,photo),card(8)]))),undefined,()=>Promise.resolve(res(500,{detail:'PRIVATE_DRIVER'})));await open();await screen.findByText('Photo is unavailable.');expect(screen.getAllByRole('heading',{level:2}).map(h=>h.textContent)).toEqual(['Campus item 7','Campus item 8']);expect(screen.getByText('No photo.')).toBeTruthy();expect(screen.queryByText('PRIVATE_DRIVER')).toBeNull();expect(screen.queryByRole('img')).toBeNull();
});

const feedParams=()=>Object.fromEntries(new URL(feeds().at(-1)[0]).searchParams);
test('category chips mirror the server categories, send category_id at offset 0 and stay in sync with the select',async()=>{
 setup(p=>Promise.resolve(res(200,page([card(7)],21,Number(p.get('offset'))))));await open();await screen.findByRole('heading',{name:'Campus item 7'});await waitFor(()=>expect(screen.getByLabelText('Category').disabled).toBe(false));
 const group=screen.getByRole('group',{name:'Filter by category'});expect(within(group).getAllByRole('button').map(b=>b.textContent)).toEqual(['All','Electronics','Clothing','Books','Furniture','Other']);expect(within(group).getByRole('button',{name:'All'}).getAttribute('aria-pressed')).toBe('true');
 fireEvent.click(screen.getByRole('button',{name:'Next page'}));await waitFor(()=>expect(feedParams().offset).toBe('20'));await screen.findByRole('heading',{name:'Campus item 7'});
 fireEvent.click(within(group).getByRole('button',{name:'Books'}));await waitFor(()=>expect(feedParams()).toEqual({limit:'20',offset:'0',category_id:'3'}));expect(screen.getByLabelText('Category').value).toBe('3');expect(within(group).getByRole('button',{name:'Books'}).getAttribute('aria-pressed')).toBe('true');expect(within(group).getByRole('button',{name:'All'}).getAttribute('aria-pressed')).toBe('false');
 change('Category','2');expect(within(group).getByRole('button',{name:'Clothing'}).getAttribute('aria-pressed')).toBe('true');
 await screen.findByRole('heading',{name:'Campus item 7'});fireEvent.click(within(group).getByRole('button',{name:'All'}));await waitFor(()=>expect(feedParams()).toEqual({limit:'20',offset:'0'}));
});
test('chips show skeletons while loading and a retry when categories fail; the feed still renders',async()=>{
 let cat;setup(()=>Promise.resolve(res(200,page([card(7)]))),()=>cat?Promise.resolve(res(500,{})):new Promise(r=>{cat=r;}));const {container}=await open();expect(container.querySelectorAll('.chip--skeleton').length).toBeGreaterThan(0);expect(screen.queryByRole('group',{name:'Filter by category'})).toBeNull();expect(screen.getByLabelText('Category').disabled).toBe(true);
 await act(async()=>{cat(res(500,{}));});expect(screen.getByRole('alert').textContent).toBe('Categories could not be loaded.');expect(screen.getByRole('button',{name:'Retry categories'})).toBeTruthy();await screen.findByRole('heading',{name:'Campus item 7'});expect(screen.getByText(/Category unavailable/)).toBeTruthy();
});
test('Filters toggle exposes aria-expanded/aria-controls, counts applied filters and keeps the form name',async()=>{
 setup(()=>Promise.resolve(res(200,page([card(7)]))));await open();await screen.findByRole('heading',{name:'Campus item 7'});const toggle=screen.getByRole('button',{name:'Filters'});expect(toggle.getAttribute('aria-expanded')).toBe('false');const panel=document.getElementById(toggle.getAttribute('aria-controls'));expect(panel.hidden).toBe(true);
 fireEvent.click(toggle);expect(toggle.getAttribute('aria-expanded')).toBe('true');expect(panel.hidden).toBe(false);expect(within(panel).getByLabelText('Minimum price (KZT)').getAttribute('inputmode')).toBe('decimal');expect(within(screen.getByRole('form',{name:'Search and filter listings'})).getByRole('button',{name:'Apply filters'})).toBeTruthy();
 change('Condition','new');change('Minimum price (KZT)','5');apply();await waitFor(()=>expect(feedParams()).toEqual({limit:'20',offset:'0',condition:'new',min_price:'5'}));expect(screen.getByRole('button',{name:'Filters (2)'})).toBeTruthy();fireEvent.click(screen.getByRole('button',{name:'Filters (2)'}));expect(screen.getByRole('button',{name:'Filters (2)'}).getAttribute('aria-expanded')).toBe('false');
});
test('closing the inline panel animates for 200ms but updates state at once and is inert meanwhile',async()=>{
 setup(()=>Promise.resolve(res(200,page([card(7)]))));await open();await screen.findByRole('heading',{name:'Campus item 7'});const toggle=screen.getByRole('button',{name:'Filters'});fireEvent.click(toggle);const panel=document.getElementById('catalog-filter-panel');expect(panel.inert).toBe(false);expect(panel.className).not.toContain('closing');
 fireEvent.click(toggle);expect(toggle.getAttribute('aria-expanded')).toBe('false');expect(panel.hidden).toBe(false);expect(panel.inert).toBe(true);expect(panel.className).toContain('catalog-panel--closing');
 await waitFor(()=>expect(panel.hidden).toBe(true));expect(panel.className).not.toContain('closing');fireEvent.click(toggle);expect(panel.hidden).toBe(false);expect(panel.inert).toBe(false);
});
test('with reduced motion the inline panel closes without a closing state',async()=>{
 vi.stubGlobal('matchMedia',q=>({matches:q.includes('reduce'),media:q,addEventListener(){},removeEventListener(){}}));
 setup(()=>Promise.resolve(res(200,page([card(7)]))));await open();await screen.findByRole('heading',{name:'Campus item 7'});const toggle=screen.getByRole('button',{name:'Filters'});fireEvent.click(toggle);fireEvent.click(toggle);expect(document.getElementById('catalog-filter-panel').hidden).toBe(true);
});
test('at 768px aria-controls is only present while the sheet is open',async()=>{
 vi.stubGlobal('matchMedia',q=>({matches:q.includes('768'),media:q,addEventListener(){},removeEventListener(){}}));
 setup(()=>Promise.resolve(res(200,page([card(7)]))));await open();await screen.findByRole('heading',{name:'Campus item 7'});const toggle=screen.getByRole('button',{name:'Filters'});expect(toggle.hasAttribute('aria-controls')).toBe(false);fireEvent.click(toggle);expect(document.getElementById(toggle.getAttribute('aria-controls'))).toBeTruthy();
});
test('an invalid price in a closed panel opens it and sends no request',async()=>{
 setup(()=>Promise.resolve(res(200,page([card(7)]))));await open();await screen.findByRole('heading',{name:'Campus item 7'});const toggle=screen.getByRole('button',{name:'Filters'});change('Minimum price (KZT)','1e2');apply();expect(screen.getByRole('alert').textContent).toContain('Use an unsigned KZT price');expect(toggle.getAttribute('aria-expanded')).toBe('true');expect(feeds()).toHaveLength(1);
});
test('page indicator and first/last page buttons follow total and offset',async()=>{
 setup(p=>Promise.resolve(res(200,page(Number(p.get('offset'))?[card(8)]:[card(7)],21,Number(p.get('offset'))))));await open();await screen.findByRole('heading',{name:'Campus item 7'});expect(screen.getByText('Page 1 of 2')).toBeTruthy();expect(screen.getByRole('button',{name:'Previous page'}).disabled).toBe(true);expect(screen.getByRole('button',{name:'Next page'}).disabled).toBe(false);
 fireEvent.click(screen.getByRole('button',{name:'Next page'}));await screen.findByRole('heading',{name:'Campus item 8'});expect(screen.getByText('Page 2 of 2')).toBeTruthy();expect(screen.getAllByRole('heading',{level:2})).toHaveLength(1);expect(screen.getByRole('button',{name:'Next page'}).disabled).toBe(true);expect(screen.getByRole('button',{name:'Previous page'}).disabled).toBe(false);
});
test('exactly 20 results is one page with both buttons disabled',async()=>{
 setup(()=>Promise.resolve(res(200,page(Array.from({length:20},(_,i)=>card(i+1)),20))));const {container}=await open();await screen.findByRole('heading',{name:'Campus item 20'});expect(screen.getByText('Page 1 of 1')).toBeTruthy();expect(screen.queryByText(/Page 2/)).toBeNull();expect(screen.getByRole('button',{name:'Next page'}).disabled).toBe(true);expect(screen.getByRole('button',{name:'Previous page'}).disabled).toBe(true);
 const delays=[...container.querySelectorAll('.catalog-card')].map(li=>Number(li.style.getPropertyValue('--i')));expect(delays).toHaveLength(20);expect(Math.max(...delays)).toBe(8);expect(delays.slice(0,3)).toEqual([0,1,2]);
});
test('cards are photo-first with one link, full price text, metadata and a 4:3 media box',async()=>{
 setup(()=>Promise.resolve(res(200,page([card(7,photo),card(8)]))));const {container}=await open();await screen.findByRole('img');const cards=[...container.querySelectorAll('li.catalog-card')];expect(cards).toHaveLength(2);
 for(const li of cards){expect(li.querySelectorAll('a')).toHaveLength(1);expect(li.firstElementChild.className).toBe('catalog-card__media');}
 const link=within(cards[0]).getByRole('link',{name:'Campus item 7'});expect(link.getAttribute('href')).toBe('/listings/7');expect(link.getAttribute('title')).toBe('Campus item 7');expect(within(cards[0]).getByText('12.34 KZT')).toBeTruthy();expect(within(cards[0]).getByText(/Electronics · Used/)).toBeTruthy();expect(cards[0].querySelector('time').getAttribute('datetime')).toBe('2026-10-13T00:00:00Z');expect(within(cards[0]).getByRole('img').getAttribute('alt')).toBe('Campus item 7');expect(within(cards[1]).getByText('No photo.')).toBeTruthy();
});
test('empty results offer Reset filters only when a filter is applied; an empty page offers a way back',async()=>{
 setup(p=>Promise.resolve(res(200,p.get('offset')==='40'?page([],21,40):page([]))));await open();await screen.findByText('No matching listings. Try different filters.');expect(screen.queryByRole('button',{name:'Reset filters'})).toBeNull();
 change('Search listings','zzz');apply();await waitFor(()=>expect(feedParams().q).toBe('zzz'));await screen.findByText('No matching listings. Try different filters.');const reset=screen.getAllByRole('button',{name:'Reset filters'});expect(reset).toHaveLength(1);fireEvent.click(reset[0]);await waitFor(()=>expect(feedParams()).toEqual({limit:'20',offset:'0'}));expect((screen.getByLabelText('Search listings')).value).toBe('');
});
test('an empty page beyond the end links back to the first page',async()=>{
 setup(p=>Promise.resolve(res(200,Number(p.get('offset'))>=20?page([],21,Number(p.get('offset'))):page([card(7)],21,0))));await open();await screen.findByRole('heading',{name:'Campus item 7'});fireEvent.click(screen.getByRole('button',{name:'Next page'}));await screen.findByText('No listings on this page.');fireEvent.click(screen.getByRole('button',{name:'Back to first page'}));await screen.findByRole('heading',{name:'Campus item 7'});expect(feedParams().offset).toBe('0');
});
test('at 768px and narrower filters open in the shared dialog: named form, Esc closes, focus returns, invalid input stays open',async()=>{
 vi.stubGlobal('matchMedia',q=>({matches:true,media:q,addEventListener(){},removeEventListener(){}}));
 setup(()=>Promise.resolve(res(200,page([card(7)]))));await open();await screen.findByRole('heading',{name:'Campus item 7'});const toggle=screen.getByRole('button',{name:'Filters'});expect(screen.queryByRole('dialog')).toBeNull();toggle.focus();fireEvent.click(toggle);
 const dialog=screen.getByRole('dialog',{name:'Filters'});expect(toggle.getAttribute('aria-expanded')).toBe('true');expect(document.body.style.overflow).toBe('hidden');expect(within(dialog).getByRole('form',{name:'Search and filter listings'})).toBeTruthy();
 fireEvent.change(within(dialog).getByLabelText('Maximum price (KZT)'),{target:{value:'abc'}});fireEvent.submit(within(dialog).getByRole('form',{name:'Search and filter listings'}));expect(within(dialog).getByRole('alert').textContent).toContain('Use an unsigned KZT price');expect(feeds()).toHaveLength(1);
 fireEvent.keyDown(document,{key:'Escape'});expect(screen.queryByRole('dialog')).toBeNull();await waitFor(()=>expect(document.activeElement).toBe(toggle));expect(document.body.style.overflow).not.toBe('hidden');
 fireEvent.click(toggle);fireEvent.change(screen.getByLabelText('Maximum price (KZT)'),{target:{value:'9'}});fireEvent.submit(within(screen.getByRole('dialog')).getByRole('form',{name:'Search and filter listings'}));await waitFor(()=>expect(feedParams().max_price).toBe('9'));expect(screen.queryByRole('dialog')).toBeNull();
});
