import React,{useEffect,useRef,useState} from 'react';
import {useAuth} from './Auth.jsx';
import {ApiError} from './api.js';
import {listingPrice} from './listingValidation.js';
import {Photo} from './Photo.jsx';
import {Button,Dialog,Loading,EmptyState,ErrorState} from './ui/index.js';
import {ListingCard,CatalogSkeleton} from './ListingCard.jsx';
import {CategoryChips} from './CategoryChips.jsx';
export {Photo};

const empty={q:'',category_id:'',condition:'',min_price:'',max_price:''};
const categoryKeys=['electronics','clothing','books','furniture','other'];
function categoriesValid(data){
 if(!Array.isArray(data)||data.length!==5||data.some((c,index)=>c.id!==index+1||c.key!==categoryKeys[index]||typeof c.label!=='string'||!c.label.trim()))throw new ApiError('response');
 return data;
}
export function pageValid(data,offset){
 if(!data||!Array.isArray(data.items)||data.limit!==20||data.offset!==offset||!Number.isSafeInteger(data.total)||data.total<0||data.count!==data.items.length||data.count>20||data.count>Math.max(0,data.total-offset))throw new ApiError('response');
 const ids=new Set();
 for(const card of data.items){
  if(!Number.isSafeInteger(card.id)||card.id<1||ids.has(card.id)||typeof card.title!=='string'||card.title.trim().length<3||card.title.length>120||typeof card.price!=='string'||listingPrice(card.price)!==card.price||card.currency!=='KZT'||!Number.isInteger(card.category_id)||card.category_id<1||card.category_id>5||!['new','used'].includes(card.condition)||typeof card.published_at!=='string'||!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.test(card.published_at)||!Number.isFinite(Date.parse(card.published_at)))throw new ApiError('response');
  ids.add(card.id);const photo=card.main_photo;
  if(photo!==null&&(!photo||!Number.isSafeInteger(photo.id)||photo.id<1||!Number.isInteger(photo.position)||photo.position<1||photo.position>5||photo.is_main!==true||photo.url!==`/listings/${card.id}/photos/${photo.id}`))throw new ApiError('response');
 }
 return data;
}

function useSheet(){
 const query='(max-width: 768px)',read=()=>typeof window!=='undefined'&&typeof window.matchMedia==='function'&&window.matchMedia(query).matches,[sheet,setSheet]=useState(read);
 useEffect(()=>{if(typeof window.matchMedia!=='function')return undefined;const list=window.matchMedia(query),sync=()=>setSheet(list.matches);sync();list.addEventListener?.('change',sync);return()=>list.removeEventListener?.('change',sync);},[]);
 return sheet;
}
const skeletonCount=8;
export function Marketplace({navigate}){
 const auth=useAuth(),[categories,setCategories]=useState(null),[categoryError,setCategoryError]=useState(false),[categoryRetry,setCategoryRetry]=useState(0),[draft,setDraft]=useState(empty),[applied,setApplied]=useState(empty),[offset,setOffset]=useState(0),[page,setPage]=useState(null),[loading,setLoading]=useState(true),[error,setError]=useState(false),[validation,setValidation]=useState(''),[retry,setRetry]=useState(0),[open,setOpen]=useState(false),sheet=useSheet(),anchor=useRef(null),conditionRef=useRef(null);
 useEffect(()=>{let active=true;setCategories(null);setCategoryError(false);auth.get('/categories').then(result=>{if(result.status!==200)throw new ApiError('response');const data=categoriesValid(result.data);if(active)setCategories(data);}).catch(()=>{if(active)setCategoryError(true);});return()=>{active=false;};},[auth.get,categoryRetry]);
 useEffect(()=>{let active=true;setLoading(true);setPage(null);setError(false);const query=new URLSearchParams({limit:'20',offset:String(offset)});for(const [key,value] of Object.entries(applied)){if(value!=='')query.set(key,value);}
  auth.get(`/listings?${query}`).then(result=>{if(result.status!==200)throw new ApiError('response');const data=pageValid(result.data,offset);if(active)setPage(data);}).catch(()=>{if(active)setError(true);}).finally(()=>{if(active)setLoading(false);});return()=>{active=false;};
 },[auth.get,applied,offset,retry]);
 function change(event){setDraft({...draft,[event.target.name]:event.target.value});}
 function apply(event){event.preventDefault();let message='',filterField=false;const next={...draft,q:draft.q.trim()};
  if(Array.from(draft.q).length>200||/[\u0000-\u001f\u007f-\u009f]/u.test(draft.q))message='Search must be at most 200 characters without control characters.';
  if(draft.category_id!==''&&!/^[1-5]$/.test(draft.category_id)){message='Choose a listed category.';filterField=true;}
  if(draft.condition!==''&&!['new','used'].includes(draft.condition)){message='Choose New or Used.';filterField=true;}
  for(const key of ['min_price','max_price']){if(draft[key]!==''&&!listingPrice(draft[key])){message='Use an unsigned KZT price from 0 to 1,000,000,000 with at most two meaningful decimal places.';filterField=true;}}
  if(!message&&draft.min_price!==''&&draft.max_price!==''){
   const cents=value=>BigInt(listingPrice(value).replace('.',''));if(cents(draft.min_price)>cents(draft.max_price)){message='Minimum price must not exceed maximum price.';filterField=true;}
  }
  setValidation(message);if(message){if(filterField)setOpen(true);return;}setPage(null);setOffset(0);setApplied(next);if(sheet)setOpen(false);
 }
 function reset(){setDraft(empty);setApplied({...empty});setOffset(0);setPage(null);setValidation('');if(sheet)setOpen(false);}
 function pick(id){setDraft(d=>({...d,category_id:id}));setApplied(a=>({...a,category_id:id}));setOffset(0);setPage(null);setValidation('');}
 function go(next){setPage(null);setOffset(next);const node=anchor.current;if(node){node.scrollIntoView?.({block:'start'});node.focus({preventScroll:true});}}
 const filterCount=['category_id','condition','min_price','max_price'].filter(key=>applied[key]!=='').length,anyFilter=Object.values(applied).some(v=>v!=='')||Object.values(draft).some(v=>v!==''),emptyWithFilters=Boolean(page&&page.total===0&&Object.values(applied).some(v=>v!=='')),panelShown=open,resetInPanel=panelShown,resetInEmpty=!panelShown&&emptyWithFilters,resetInBar=!panelShown&&!emptyWithFilters&&anyFilter;
 const lastPage=page?Math.max(1,Math.ceil(page.total/20)):1,pageNumber=Math.floor(offset/20)+1;
 const alert=validation&&<p role="alert" className="form-feedback error">{validation}</p>;
 const fields=<div className="catalog-fields">
  <div className="catalog-field"><label htmlFor="market-category">Category</label><select id="market-category" name="category_id" value={draft.category_id} onChange={change} disabled={!categories}><option value="">All categories</option>{categories?.map(c=><option key={c.id} value={c.id}>{c.label}</option>)}</select></div>
  <div className="catalog-field"><label htmlFor="market-condition">Condition</label><select id="market-condition" name="condition" ref={conditionRef} value={draft.condition} onChange={change}><option value="">New and Used</option><option value="new">New</option><option value="used">Used</option></select></div>
  <div className="catalog-field"><label htmlFor="market-min">Minimum price (KZT)</label><input id="market-min" name="min_price" inputMode="decimal" value={draft.min_price} onChange={change}/></div>
  <div className="catalog-field"><label htmlFor="market-max">Maximum price (KZT)</label><input id="market-max" name="max_price" inputMode="decimal" value={draft.max_price} onChange={change}/></div>
  <div className="catalog-fields__actions"><Button variant="primary" type="submit">Apply filters</Button>{resetInPanel&&<Button onClick={reset}>Reset filters</Button>}</div>
 </div>;
 const sheetOpen=sheet&&open;
 return <section aria-label="Marketplace listings" className="catalog">
  <form className="catalog-form" aria-label="Search and filter listings" onSubmit={apply} noValidate>
   <div className="catalog-search"><label className="sr-only" htmlFor="market-q">Search listings</label><input id="market-q" name="q" type="text" value={draft.q} onChange={change} aria-describedby="market-help" placeholder="Search listings"/><Button variant="primary" type="submit">Search</Button></div>
   <p id="market-help" className="field-help catalog-help">Search title or description. Prices include both bounds. Results show newest published items first.</p>
   <CategoryChips categories={categories} error={categoryError} value={draft.category_id} onSelect={pick} onRetry={()=>setCategoryRetry(n=>n+1)}/>
   <div className="catalog-toolbar"><Button className="catalog-filters-toggle" aria-expanded={open} aria-controls="catalog-filter-panel" onClick={()=>setOpen(o=>!o)}>Filters{filterCount?` (${filterCount})`:''}</Button>{resetInBar&&<Button variant="ghost" onClick={reset}>Reset filters</Button>}</div>
   {!sheet&&<div id="catalog-filter-panel" className="catalog-panel" hidden={!open}>{fields}</div>}
   {!sheetOpen&&alert}
  </form>
  {sheet&&<Dialog open={open} onClose={()=>setOpen(false)} title="Filters" closeLabel="Close filters" initialFocusRef={conditionRef}><form id="catalog-filter-panel" className="catalog-sheet" aria-label="Search and filter listings" onSubmit={apply} noValidate>{fields}{alert}</form></Dialog>}
  <p ref={anchor} tabIndex={-1} className="catalog-results" role="status">{page?`${page.total} matching listings. ${page.count?`Showing ${offset+1}–${offset+page.count}.`:'No items on this page.'}`:''}</p>
  {loading&&<Loading label="Loading marketplace listings…"><div className="catalog-grid" aria-hidden="true">{Array.from({length:skeletonCount},(_,i)=><CatalogSkeleton key={i}/>)}</div></Loading>}
  {error&&<ErrorState title="Listings could not be loaded" message="Marketplace listings could not be loaded. Please retry." retryLabel="Retry marketplace" onRetry={()=>setRetry(n=>n+1)}/>}
  {page&&<>
   {!page.count&&<EmptyState showTag={false} title={page.total?'No listings on this page.':'No matching listings. Try different filters.'} action={page.total?<Button onClick={()=>go(0)}>Back to first page</Button>:resetInEmpty?<Button variant="primary" onClick={reset}>Reset filters</Button>:null}/>}
   {page.count>0&&<ul className="catalog-grid">{page.items.map((card,index)=><ListingCard key={card.id} card={card} index={index} categories={categories} categoryError={categoryError} navigate={navigate}/>)}</ul>}
   {page.total>0&&<nav className="catalog-pager" aria-label="Pagination"><Button disabled={offset===0||loading} onClick={()=>go(Math.max(0,offset-20))}>Previous page</Button><p className="catalog-pager__label">Page {pageNumber} of {lastPage}</p><Button disabled={offset+20>=page.total||loading} onClick={()=>go(offset+20)}>Next page</Button></nav>}
  </>}
 </section>;
}
