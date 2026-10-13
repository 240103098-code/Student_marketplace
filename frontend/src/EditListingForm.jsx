import React, { useEffect, useRef, useState } from 'react';
import { ApiError } from './api.js';
import { useAuth } from './Auth.jsx';
import { listingPrice } from './listingValidation.js';

function confirmed(data,id) {
  if(!Number.isSafeInteger(data?.id)||String(data.id)!==id||typeof data.title!=='string'||typeof data.description!=='string'||typeof data.price!=='string'||listingPrice(data.price)!==data.price||!['pending','active','sold','rejected','removed'].includes(data.status)||(data.published_at!==null&&typeof data.published_at!=='string'))throw new ApiError('response');
  return data;
}
export function EditListingForm({ listingId }) {
  const auth=useAuth();
  const [baseline,setBaseline]=useState(null);
  const [price,setPrice]=useState('');
  const [description,setDescription]=useState('');
  const [loading,setLoading]=useState(true);
  const [retry,setRetry]=useState(0);
  const [pending,setPending]=useState(false);
  const [error,setError]=useState('');
  const [blocked,setBlocked]=useState(false);
  const [feedback,setFeedback]=useState('');
  const busy=useRef(false);
  useEffect(()=>{
    let active=true;setLoading(true);setError('');
    auth.get(`/listings/${listingId}/edit`).then(result=>{
      const data=confirmed(result.data,listingId);
      if(active){setBlocked(false);setBaseline(data);setPrice(data.price);setDescription(data.description);}
    }).catch(failure=>{if(active)setError(failure.status===404?'Listing is unavailable or does not belong to your account.':'The listing could not be loaded. Please retry.');})
      .finally(()=>{if(active)setLoading(false);});
    return()=>{active=false;};
  },[auth.get,listingId,retry]);
  const forbidden=blocked||(baseline&&!['pending','active','sold'].includes(baseline.status));
  const canonical=listingPrice(price);
  const trimmed=description.trim();
  const changes={};
  if(baseline){
    if(canonical!==baseline.price)changes.price=canonical;
    if(trimmed!==baseline.description)changes.description=trimmed;
  }
  const changed=Object.keys(changes).length>0;
  async function save(event){
    event.preventDefault();if(busy.current||forbidden||!changed)return;
    if(canonical===null){setError('Use a KZT decimal price from 0 to 1,000,000,000 with at most two meaningful decimal places.');return;}
    if(Array.from(trimmed).length<10||Array.from(trimmed).length>2000||/\u0000/.test(trimmed)){setError('Use a description of 10–2000 characters after trimming.');return;}
    busy.current=true;setPending(true);setError('');setFeedback('');
    try{
      const result=await auth.patch(`/listings/${listingId}`,changes);
      const data=confirmed(result.data,listingId);
      if(result.status!==200)throw new ApiError('response');
      setBaseline(data);setPrice(data.price);setDescription(data.description);setFeedback('Listing changes saved. Approval and publication were preserved.');
    }catch(failure){if(failure.status===409)setBlocked(true);setError(failure.status===409?'This listing can no longer be edited. Rejected listings need deletion and recreation; Removed listings cannot be changed.':failure.status===404?'Listing is unavailable or does not belong to your account.':'Save could not be confirmed. Your edits remain here; check and retry.');}
    finally{busy.current=false;setPending(false);}
  }
  if(loading)return <p role="status">Loading your listing…</p>;
  if(!baseline)return <section><p role="alert" className="form-feedback error">{error}</p><button className="button secondary" onClick={()=>setRetry(value=>value+1)}>Retry listing</button></section>;
  return <form className="account-form" aria-label="Edit listing" aria-busy={pending} onSubmit={save} noValidate>
    <label htmlFor="edit-title">Title (read-only)</label><input id="edit-title" value={baseline.title} readOnly/>
    <label htmlFor="edit-status">Status (read-only)</label><input id="edit-status" value={baseline.status} readOnly/>
    <label htmlFor="edit-publication">Publication (read-only)</label><input id="edit-publication" value={baseline.published_at||'Not published'} readOnly/>
    <label htmlFor="edit-price">Price (KZT)</label><input id="edit-price" inputMode="decimal" value={price} onChange={event=>{setPrice(event.target.value);setFeedback('');}} disabled={pending||forbidden} aria-describedby="edit-price-help"/>
    <p id="edit-price-help" className="field-help">0–1,000,000,000 KZT; at most two meaningful decimal places.</p>
    <label htmlFor="edit-description">Description</label><textarea id="edit-description" value={description} onChange={event=>{setDescription(event.target.value);setFeedback('');}} disabled={pending||forbidden} aria-describedby="edit-description-help"/>
    <p id="edit-description-help" className="field-help">10–2000 characters after trimming. Title, category, condition and photos cannot be changed here.</p>
    {forbidden&&<p role="status" className="form-feedback">{baseline.status==='rejected'?'Rejected listings cannot be edited; they need deletion and recreation.':baseline.status==='removed'?'Removed listings cannot be edited.':'This listing cannot currently be edited. Reload its current state.'}</p>}
    {error&&<p role="alert" className="form-feedback error">{error}</p>}
    {feedback&&<p role="status" className="form-feedback">{feedback}</p>}
    {blocked&&<button className="button secondary" type="button" onClick={()=>setRetry(value=>value+1)}>Reload listing state</button>}
    {pending&&<p role="status">Saving listing changes…</p>}
    <button className="button primary" disabled={pending||forbidden||!changed}>{pending?'Saving changes…':'Save changes'}</button>
    {!changed&&!feedback&&<p className="field-help">No changes to save.</p>}
  </form>;
}
