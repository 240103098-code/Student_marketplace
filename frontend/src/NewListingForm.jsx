import React, { useEffect, useRef, useState } from 'react';
import { ApiError } from './api.js';
import { useAuth } from './Auth.jsx';
import { listingPrice } from './listingValidation.js';

const knownFailures=new Set([400,401,403,404,409,413,422]);

export function NewListingForm({ navigate }) {
  const auth=useAuth();
  const [categories,setCategories]=useState(null);
  const [categoryError,setCategoryError]=useState('');
  const [retry,setRetry]=useState(0);
  const [fields,setFields]=useState({title:'',description:'',price:'',category_id:'',condition:'used'});
  const [files,setFiles]=useState([]);
  const [listing,setListing]=useState(null);
  const [savedPhotos,setSavedPhotos]=useState([]);
  const [pending,setPending]=useState('');
  const [error,setError]=useState('');
  const [contactError,setContactError]=useState(false);
  const [uncertain,setUncertain]=useState(false);
  const [complete,setComplete]=useState(false);
  const busy=useRef(false);
  const filesRef=useRef([]);
  const listingRef=useRef(null);
  const savedRef=useRef([]);
  const input=useRef(null);
  useEffect(()=>{
    let active=true;setCategories(null);setCategoryError('');
    auth.get('/categories').then(result=>{
      if(!Array.isArray(result.data)||result.data.length!==5||result.data.some((item,index)=>item.id!==index+1||typeof item.key!=='string'||typeof item.label!=='string'))throw new ApiError('response');
      if(active)setCategories(result.data);
    }).catch(()=>{if(active)setCategoryError('Categories could not be loaded. Please retry.');});
    return()=>{active=false;};
  },[auth.get,retry]);
  useEffect(()=>()=>{filesRef.current.forEach(item=>URL.revokeObjectURL(item.url));},[]);
  function replaceFiles(next){filesRef.current=next;setFiles(next);setComplete(false);}
  function select(event){
    if(busy.current||uncertain)return;
    const selected=Array.from(event.target.files||[]);
    const preserved=filesRef.current.slice(0,savedRef.current.length);
    if(selected.length+preserved.length>5){setError('Choose at most five photos in total.');if(input.current)input.current.value='';return;}
    if(selected.some(file=>!['image/jpeg','image/png','image/webp'].includes(file.type)||file.size>5*1024*1024)){setError('Choose JPEG, PNG or WebP photos up to five MiB each.');if(input.current)input.current.value='';return;}
    filesRef.current.slice(savedRef.current.length).forEach(item=>URL.revokeObjectURL(item.url));
    replaceFiles([...preserved,...selected.map(file=>({file,url:URL.createObjectURL(file)}))]);setError('');
  }
  function remove(index){
    if(busy.current||uncertain||index<savedRef.current.length)return;
    URL.revokeObjectURL(filesRef.current[index].url);
    replaceFiles(filesRef.current.filter((_,position)=>position!==index));setError('');
  }
  function update(key,value){setFields(previous=>({...previous,[key]:value}));}
  async function submit(event){
    event.preventDefault();if(busy.current||uncertain||complete||!categories)return;
    const title=fields.title.trim(),description=fields.description.trim(),price=listingPrice(fields.price);
    if(!listingRef.current){
      if(Array.from(title).length<3||Array.from(title).length>120||Array.from(description).length<10||Array.from(description).length>2000||/\u0000/.test(title+description)){setError('Use a title of 3–120 characters and a description of 10–2000 characters.');return;}
      if(price===null){setError('Use a KZT decimal price from 0 to 1,000,000,000 with at most two meaningful decimal places.');return;}
      if(!categories.some(item=>String(item.id)===fields.category_id)||!['new','used'].includes(fields.condition)){setError('Choose a category and New or Used condition.');return;}
    }
    busy.current=true;setError('');setContactError(false);
    try{
      if(!listingRef.current){
        setPending('Creating your Pending listing…');
        const result=await auth.post('/listings',{title,description,price,category_id:Number(fields.category_id),condition:fields.condition});
        if(result.status!==201||!Number.isSafeInteger(result.data?.id)||result.data.id<1||result.data.status!=='pending'||result.data.published_at!==null||result.data.currency!=='KZT')throw new ApiError('response');
        listingRef.current=result.data;setListing(result.data);
      }
      while(savedRef.current.length<filesRef.current.length){
        const position=savedRef.current.length+1;
        setPending(`Uploading photo ${position} of ${filesRef.current.length}…`);
        const result=await auth.post(`/listings/${listingRef.current.id}/photos`,undefined,filesRef.current[position-1].file);
        const photo=result.data;
        if(result.status!==201||!Number.isSafeInteger(photo?.id)||photo.id<1||photo.listing_id!==listingRef.current.id||photo.position!==position||photo.is_main!==(position===1)||photo.url!==`/listings/${listingRef.current.id}/photos/${photo.id}`)throw new ApiError('response');
        savedRef.current=[...savedRef.current,photo];setSavedPhotos(savedRef.current);
      }
      setComplete(true);
    }catch(failure){
      if(!knownFailures.has(failure.status)){
        setUncertain(true);
        setError(listingRef.current?'The last photo response is uncertain. It may have been saved. Do not upload it again blindly; check saved listings before retrying when that screen is available.':'The creation response is uncertain. A listing may have been created. Do not submit again blindly; check saved listings before retrying when that screen is available.');
      }else if(!listingRef.current){
        setContactError(failure.status===400);
        setError(failure.status===400?'Add a valid contact method to your profile before creating a listing.':'Listing creation was rejected or rolled back. Check your details and retry.');
      }else setError('Your listing was saved, but the last photo was rejected or rolled back. Correct or remove the remaining selections, then retry only those photos.');
    }finally{busy.current=false;setPending('');}
  }
  if(!categories)return <section>{categoryError?<><p role="alert" className="form-feedback error">{categoryError}</p><button className="button secondary" onClick={()=>setRetry(previous=>previous+1)}>Retry categories</button></>:<p role="status">Loading categories…</p>}</section>;
  const locked=!!listing||!!pending||uncertain;
  return <form className="account-form" aria-label="New listing" aria-busy={!!pending} onSubmit={submit} noValidate>
    <label htmlFor="listing-title">Title</label><input id="listing-title" value={fields.title} onChange={event=>update('title',event.target.value)} disabled={locked} aria-describedby="listing-title-help"/>
    <p id="listing-title-help" className="field-help">3–120 characters after trimming.</p>
    <label htmlFor="listing-description">Description</label><textarea id="listing-description" value={fields.description} onChange={event=>update('description',event.target.value)} disabled={locked} aria-describedby="listing-description-help"/>
    <p id="listing-description-help" className="field-help">10–2000 characters after trimming.</p>
    <label htmlFor="listing-price">Price (KZT)</label><input id="listing-price" inputMode="decimal" value={fields.price} onChange={event=>update('price',event.target.value)} disabled={locked} aria-describedby="listing-price-help"/>
    <p id="listing-price-help" className="field-help">0–1,000,000,000 KZT; at most two meaningful decimal places.</p>
    <label htmlFor="listing-category">Category</label><select id="listing-category" value={fields.category_id} onChange={event=>update('category_id',event.target.value)} disabled={locked}><option value="">Choose category</option>{categories.map(item=><option key={item.id} value={item.id}>{item.label}</option>)}</select>
    <label htmlFor="listing-condition">Condition</label><select id="listing-condition" value={fields.condition} onChange={event=>update('condition',event.target.value)} disabled={locked}><option value="new">New</option><option value="used">Used</option></select>
    <label htmlFor="listing-photos">Optional photos</label><input ref={input} id="listing-photos" type="file" multiple accept="image/jpeg,image/png,image/webp" disabled={!!pending||uncertain||complete} onChange={select} aria-describedby="listing-photos-help"/>
    <p id="listing-photos-help" className="field-help">Up to five JPEG, PNG or WebP photos, five MiB each and twenty million pixels. Selection order is upload order; first photo is main. Selecting files again replaces only unsubmitted selections.</p>
    {files.length>0&&<ol className="listing-previews">{files.map((item,index)=><li key={item.url}><img src={item.url} alt={`Selected photo ${index+1}${index===0?' (main)':''}`}/><p>Photo {index+1}{index===0?' · Main':''} · {index<savedPhotos.length?'Confirmed saved':'Not confirmed saved'}</p><button className="button secondary" type="button" disabled={!!pending||uncertain||index<savedPhotos.length||complete} onClick={()=>remove(index)}>Remove selection {index+1}</button></li>)}</ol>}
    {listing&&<p role="status" className="form-feedback">Listing #{listing.id} saved as Pending. {savedPhotos.length} of {files.length} selected photos confirmed saved. It is awaiting manual admin review and is not public.</p>}
    {complete&&<p role="status">Creation complete. Awaiting manual admin review.</p>}
    {pending&&<p role="status">{pending}</p>}
    {error&&<p role="alert" className="form-feedback error">{error}</p>}
    {contactError&&<a href="/profile" onClick={navigate}>Add your profile contact</a>}
    <button className="button primary" disabled={!!pending||uncertain||complete}>{pending?'Saving…':listing?'Retry remaining photos':'Create Pending listing'}</button>
    {(listing||uncertain)&&<a href="/profile" onClick={navigate}>Go to your profile</a>}
  </form>;
}
