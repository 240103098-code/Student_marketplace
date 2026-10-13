import React, { useEffect, useRef, useState } from 'react';
import { ApiError } from './api.js';
import { useAuth } from './Auth.jsx';
import { listingPrice } from './listingValidation.js';

const statuses=['active','sold','pending','rejected','removed'];
function label(value){return value[0].toUpperCase()+value.slice(1);}
function validPage(data,status,offset){
  if(!data||!Array.isArray(data.items)||data.limit!==20||data.offset!==offset||data.status!==(status==='all'?null:status)||!Number.isSafeInteger(data.total)||data.total<0||data.count!==data.items.length||data.count>20)throw new ApiError('response');
  for(const item of data.items){
    if(!Number.isSafeInteger(item.id)||item.id<1||typeof item.title!=='string'||typeof item.description!=='string'||!statuses.includes(item.status)||typeof item.price!=='string'||listingPrice(item.price)!==item.price||item.currency!=='KZT'||!Array.isArray(item.photos)||(item.rejection_reason!==null&&typeof item.rejection_reason!=='string'))throw new ApiError('response');
    if(item.status==='removed'&&item.photos.length)throw new ApiError('response');
    let previous=0;
    for(const [index,photo] of item.photos.entries()){
      if(!Number.isSafeInteger(photo.id)||photo.id<1||!Number.isInteger(photo.position)||photo.position<=previous||photo.position>5||photo.is_main!==(index===0)||photo.url!==`/listings/${item.id}/photos/${photo.id}`)throw new ApiError('response');
      previous=photo.position;
    }
  }
  return data;
}
function Thumbnail({photo}){
  const auth=useAuth();
  const [preview,setPreview]=useState(null);
  const [error,setError]=useState(false);
  const [loading,setLoading]=useState(true);
  const objectUrl=useRef(null);
  useEffect(()=>{
    let active=true;setLoading(true);setError(false);
    auth.get(photo.url,true).then(result=>{
      if(!['image/jpeg','image/png','image/webp'].includes(result.data?.type))throw new ApiError('response');
      if(active){objectUrl.current=URL.createObjectURL(result.data);setPreview(objectUrl.current);}
    }).catch(()=>{if(active)setError(true);}).finally(()=>{if(active)setLoading(false);});
    return()=>{active=false;if(objectUrl.current)URL.revokeObjectURL(objectUrl.current);objectUrl.current=null;};
  },[auth.get,photo.url]);
  return loading?<p>Loading private photo…</p>:error?<p>Photo is unavailable.</p>:<img className="listing-thumbnail" src={preview} alt="Main listing photo"/>;
}
function SoldAction({item,onSaved}){
 const auth=useAuth();const [confirm,setConfirm]=useState(false),[pending,setPending]=useState(false),[error,setError]=useState('');const busy=useRef(false);
 async function submit(){if(busy.current)return;busy.current=true;setPending(true);setError('');try{const result=await auth.post(`/listings/${item.id}/sold`);if(result.status!==200||result.data?.id!==item.id||result.data.status!=='sold')throw new ApiError('response');onSaved();}catch{setError('Sold status could not be confirmed. Review or reload your listings before retrying.');}finally{busy.current=false;setPending(false);}}
 return <div>{confirm?<><p>Mark this listing Sold? Buyers will lose access; there is no undo.</p><button className="button primary" disabled={pending} onClick={submit}>{pending?'Marking Sold…':'Confirm Sold'}</button><button className="button secondary" disabled={pending} onClick={()=>{setConfirm(false);setError('');}}>Cancel</button></>:<button className="button secondary" onClick={()=>setConfirm(true)}>Mark Sold</button>}{pending&&<p role="status">Confirming Sold status…</p>}{error&&<p role="alert" className="form-feedback error">{error}</p>}</div>;
}
function DeleteAction({item,onDeleted,onReview}){
 const auth=useAuth();const [confirm,setConfirm]=useState(false),[pending,setPending]=useState(false),[error,setError]=useState('');const busy=useRef(false);
 async function submit(){if(busy.current)return;busy.current=true;setPending(true);setError('');try{const result=await auth.remove(`/listings/${item.id}`);if(result.status!==200||result.data?.id!==item.id||result.data.deleted!==true||typeof result.data.cleanup_pending!=='boolean')throw new ApiError('response');onDeleted(result.data);}catch{setError('Deletion could not be confirmed. Reload My Listings to review before retrying; the listing may already be absent.');}finally{busy.current=false;setPending(false);}}
 return <div>{confirm?<><p>Permanently delete this listing and its photos? This cannot be undone.</p><button className="button primary" autoFocus disabled={pending} onClick={submit}>{pending?'Deleting…':'Confirm deletion'}</button><button className="button secondary" disabled={pending} onClick={()=>{setConfirm(false);setError('');}}>Cancel deletion</button></>:<button className="button secondary" onClick={()=>setConfirm(true)}>Delete listing</button>}{pending&&<p role="status">Confirming deletion…</p>}{error&&<><p role="alert" className="form-feedback error">{error}</p><button className="button secondary" disabled={pending} onClick={onReview}>Reload listings to review</button></>}</div>;
}
export function MyListings({navigate}){
  const auth=useAuth();
  const [status,setStatus]=useState('all');
  const [offset,setOffset]=useState(0);
  const [retry,setRetry]=useState(0);
  const [page,setPage]=useState(null);
  const [loading,setLoading]=useState(true);
  const [error,setError]=useState('');
  const [notice,setNotice]=useState('');
  useEffect(()=>{
    let active=true;setLoading(true);setPage(null);setError('');
    const query=new URLSearchParams({limit:'20',offset:String(offset)});if(status!=='all')query.set('status',status);
    auth.get(`/listings/mine?${query}`).then(result=>{
      const data=validPage(result.data,status,offset);if(active){if(offset>0&&!data.count&&data.total<=offset){setOffset(Math.floor(Math.max(0,data.total-1)/20)*20);return;}setPage(data);}
    }).catch(()=>{if(active)setError('Your listings could not be loaded. Please retry.');}).finally(()=>{if(active)setLoading(false);});
    return()=>{active=false;};
  },[auth.get,status,offset,retry]);
  return <section aria-label="Own listings">
    <div className="dashboard-controls"><label htmlFor="mine-status">Listing status</label><select id="mine-status" value={status} onChange={event=>{setStatus(event.target.value);setOffset(0);}}><option value="all">All statuses</option>{statuses.map(value=><option key={value} value={value}>{label(value)}</option>)}</select><a className="button primary" href="/listings/new" onClick={navigate}>Create a new listing</a></div>
    <p className="field-help">Pending listings wait for manual admin review. Sold, Rejected and Removed listings are not shown in public browsing.</p>
    {notice&&<p role="status" className="form-feedback">{notice}</p>}
    {loading&&<p role="status">Loading your listings…</p>}
    {error&&<><p role="alert" className="form-feedback error">{error}</p><button className="button secondary" onClick={()=>setRetry(value=>value+1)}>Retry listings</button></>}
    {page&&<>
      <p role="status">{page.total} own {status==='all'?'listings':`${label(status)} listings`}. {page.count?`Showing ${offset+1}–${offset+page.count}.`:'No items on this page.'}</p>
      {!page.items.length&&<p>{page.total?'No listings on this page.':'No listings in this view.'}</p>}
      <ul className="listing-cards">{page.items.map(item=><li key={item.id} className="listing-card"><h2>{item.title}</h2><p>{item.price} KZT · {label(item.status)}</p>
        {item.photos.length?<Thumbnail key={item.photos[0].id} photo={item.photos[0]}/>:<p>{item.status==='removed'?'Photos are unavailable for Removed listings.':'No photo.'}</p>}
        {item.status!=='removed'&&item.photos.length>0&&<p>{item.photos.length} saved {item.photos.length===1?'photo':'photos'}.</p>}
        {item.status==='pending'&&<p>Awaiting manual admin review; not public.</p>}
        {item.status==='rejected'&&<p>Rejected: {item.rejection_reason||'No reason is available.'} Editing is unavailable; deletion and recreation are required.</p>}
        {item.status==='removed'&&<p>Removed by moderation; editing and photos are unavailable.</p>}
        <DeleteAction item={item} onReview={()=>setRetry(value=>value+1)} onDeleted={result=>{setNotice(result.cleanup_pending?'Listing deleted. Some photo-file cleanup is still pending.':'Listing deleted. Stored photo cleanup completed.');setRetry(value=>value+1);}}/>
        {item.status==='active'&&<SoldAction item={item} onSaved={()=>setRetry(value=>value+1)}/>}
        {['pending','active','sold'].includes(item.status)&&<a href={`/listings/${item.id}/edit`} onClick={navigate}>Edit price or description</a>}
      </li>)}</ul>
      <div className="actions"><button className="button secondary" disabled={loading||offset===0} onClick={()=>setOffset(value=>Math.max(0,value-20))}>Previous page</button><button className="button secondary" disabled={loading||offset+20>=page.total} onClick={()=>setOffset(value=>value+20)}>Next page</button></div>
    </>}
  </section>;
}
