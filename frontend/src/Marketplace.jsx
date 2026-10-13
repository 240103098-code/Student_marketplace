import React,{useEffect,useState} from 'react';
import {useAuth} from './Auth.jsx';
import {ApiError} from './api.js';
import {listingPrice} from './listingValidation.js';

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
export function Photo({photo,alt="Main listing photo"}){
 const auth=useAuth(),[src,setSrc]=useState(null),[error,setError]=useState(false);
 useEffect(()=>{let active=true,url=null;setSrc(null);setError(false);auth.get(photo.url,true).then(result=>{
  if(result.status!==200||!['image/jpeg','image/png','image/webp'].includes(result.data?.type))throw new ApiError('response');
  if(active){url=URL.createObjectURL(result.data);setSrc(url);}
 }).catch(()=>{if(active)setError(true);});return()=>{active=false;if(url)URL.revokeObjectURL(url);};},[auth.get,photo.url]);
 return error?<p>Photo is unavailable.</p>:src?<img className="marketplace-thumbnail" src={src} alt={alt}/>:<p>Loading private photo…</p>;
}
export function Marketplace({navigate}){
 const auth=useAuth(),[categories,setCategories]=useState(null),[categoryError,setCategoryError]=useState(false),[categoryRetry,setCategoryRetry]=useState(0),[draft,setDraft]=useState(empty),[applied,setApplied]=useState(empty),[offset,setOffset]=useState(0),[page,setPage]=useState(null),[loading,setLoading]=useState(true),[error,setError]=useState(false),[validation,setValidation]=useState(''),[retry,setRetry]=useState(0);
 useEffect(()=>{let active=true;setCategories(null);setCategoryError(false);auth.get('/categories').then(result=>{if(result.status!==200)throw new ApiError('response');const data=categoriesValid(result.data);if(active)setCategories(data);}).catch(()=>{if(active)setCategoryError(true);});return()=>{active=false;};},[auth.get,categoryRetry]);
 useEffect(()=>{let active=true;setLoading(true);setPage(null);setError(false);const query=new URLSearchParams({limit:'20',offset:String(offset)});for(const [key,value] of Object.entries(applied)){if(value!=='')query.set(key,value);}
  auth.get(`/listings?${query}`).then(result=>{if(result.status!==200)throw new ApiError('response');const data=pageValid(result.data,offset);if(active)setPage(data);}).catch(()=>{if(active)setError(true);}).finally(()=>{if(active)setLoading(false);});return()=>{active=false;};
 },[auth.get,applied,offset,retry]);
 function change(event){setDraft({...draft,[event.target.name]:event.target.value});}
 function apply(event){event.preventDefault();let message='';const next={...draft,q:draft.q.trim()};
  if(Array.from(draft.q).length>200||/[\u0000-\u001f\u007f-\u009f]/u.test(draft.q))message='Search must be at most 200 characters without control characters.';
  if(draft.category_id!==''&&!/^[1-5]$/.test(draft.category_id))message='Choose a listed category.';
  if(draft.condition!==''&&!['new','used'].includes(draft.condition))message='Choose New or Used.';
  for(const key of ['min_price','max_price']){if(draft[key]!==''&&!listingPrice(draft[key]))message='Use an unsigned KZT price from 0 to 1,000,000,000 with at most two meaningful decimal places.';}
  if(!message&&draft.min_price!==''&&draft.max_price!==''){
   const cents=value=>BigInt(listingPrice(value).replace('.',''));if(cents(draft.min_price)>cents(draft.max_price))message='Minimum price must not exceed maximum price.';
  }
  setValidation(message);if(message)return;setPage(null);setOffset(0);setApplied(next);
 }
 function reset(){setDraft(empty);setApplied({...empty});setOffset(0);setPage(null);setValidation('');}
 return <section aria-label="Marketplace listings">
  <form className="marketplace-filters" aria-label="Search and filter listings" onSubmit={apply} noValidate>
   <div><label htmlFor="market-q">Search listings</label><input id="market-q" name="q" value={draft.q} onChange={change} aria-describedby="market-help"/></div>
   <div><label htmlFor="market-category">Category</label><select id="market-category" name="category_id" value={draft.category_id} onChange={change} disabled={!categories}><option value="">All categories</option>{categories?.map(c=><option key={c.id} value={c.id}>{c.label}</option>)}</select></div>
   <div><label htmlFor="market-condition">Condition</label><select id="market-condition" name="condition" value={draft.condition} onChange={change}><option value="">New and Used</option><option value="new">New</option><option value="used">Used</option></select></div>
   <div><label htmlFor="market-min">Minimum price (KZT)</label><input id="market-min" name="min_price" inputMode="decimal" value={draft.min_price} onChange={change}/></div>
   <div><label htmlFor="market-max">Maximum price (KZT)</label><input id="market-max" name="max_price" inputMode="decimal" value={draft.max_price} onChange={change}/></div>
   <p id="market-help" className="field-help">Search title or description. Prices include both bounds. Results show newest published items first.</p>
   <div className="form-actions"><button className="button primary" type="submit">Apply filters</button><button className="button secondary" type="button" onClick={reset}>Reset filters</button></div>
   {validation&&<p role="alert" className="form-feedback error">{validation}</p>}
  </form>
  {!categories&&!categoryError&&<p role="status">Loading categories…</p>}{categoryError&&<><p role="alert">Categories could not be loaded.</p><button className="button secondary" onClick={()=>setCategoryRetry(n=>n+1)}>Retry categories</button></>}
  {loading&&<p role="status">Loading marketplace listings…</p>}{error&&<><p role="alert">Marketplace listings could not be loaded. Please retry.</p><button className="button secondary" onClick={()=>setRetry(n=>n+1)}>Retry marketplace</button></>}
  {page&&<><p role="status">{page.total} matching listings. {page.count?`Showing ${offset+1}–${offset+page.count}.`:'No items on this page.'}</p>{!page.count&&<p>{page.total?'No listings on this page.':'No matching listings. Try different filters.'}</p>}
   <ul className="listing-cards">{page.items.map(card=><li className="listing-card" key={card.id}><h2><a href={`/listings/${card.id}`} onClick={navigate}>{card.title}</a></h2>{card.main_photo?<Photo key={card.main_photo.url} photo={card.main_photo}/>:<p>No photo.</p>}<p>{card.price} KZT</p><p>{categories?.find(c=>c.id===card.category_id)?.label||(categoryError?'Category unavailable':'Category loading')} · {card.condition==='new'?'New':'Used'}</p><p>Published <time dateTime={card.published_at}>{new Date(card.published_at).toLocaleDateString()}</time></p></li>)}</ul>
   <div className="actions"><button className="button secondary" disabled={offset===0||loading} onClick={()=>{setPage(null);setOffset(n=>Math.max(0,n-20));}}>Previous page</button><button className="button secondary" disabled={offset+20>=page.total||loading} onClick={()=>{setPage(null);setOffset(n=>n+20);}}>Next page</button></div>
  </>}
 </section>;
}
