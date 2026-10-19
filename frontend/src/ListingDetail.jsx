import React,{useEffect,useState} from 'react';
import {ListingReport} from './ListingReport.jsx';
import {useAuth} from './Auth.jsx';
import {ApiError} from './api.js';
import {profileChangeError} from './profileValidation.js';
import {pageValid,Photo} from './Marketplace.jsx';
const labels=['Electronics','Clothing','Books','Furniture','Other'];
function validDetail(data,id){
 if(!data||String(data.id)!==id||typeof data.description!=='string'||data.description.length<10||data.description.length>2000||!Array.isArray(data.photos)||data.photos.length>5||!data.seller)throw new ApiError('response');
 pageValid({items:[{...data,main_photo:null}],total:1,count:1,limit:20,offset:0},0);
 let previous=0;const ids=new Set();for(const [index,p] of data.photos.entries()){
  if(!p||!Number.isSafeInteger(p.id)||p.id<1||ids.has(p.id)||!Number.isInteger(p.position)||p.position<=previous||p.position>5||p.is_main!==(index===0)||p.url!==`/listings/${id}/photos/${p.id}`)throw new ApiError('response');previous=p.position;ids.add(p.id);
 }
 const seller=data.seller;
 for(const key of ['name','phone','telegram_username','external_contact_url']){if(seller[key]!==null&&typeof seller[key]!=='string')throw new ApiError('response');}
 const fields=Object.fromEntries(Object.entries(seller).filter(([key,value])=>['name','phone','telegram_username','external_contact_url'].includes(key)&&value!==null));
 if(profileChangeError(fields)||(seller.name!==null&&!seller.name.trim()))throw new ApiError('response');return data;
}
export function ListingDetail({listingId,navigate}){
 const auth=useAuth(),[detail,setDetail]=useState(null),[error,setError]=useState(''),[loading,setLoading]=useState(true),[retry,setRetry]=useState(0),[selected,setSelected]=useState(0);
 useEffect(()=>{let active=true;setDetail(null);setError('');setLoading(true);setSelected(0);auth.get(`/listings/${listingId}`).then(result=>{
  if(result.status!==200)throw new ApiError('response');const data=validDetail(result.data,listingId);if(active)setDetail(data);
 }).catch(error=>{if(active)setError(error.status===404?'This listing is unavailable.':'Listing details could not be loaded. Please retry.');}).finally(()=>{if(active)setLoading(false);});return()=>{active=false;};},[auth.get,listingId,retry]);
 const seller=detail?.seller,contact=seller?.telegram_username?`https://t.me/${seller.telegram_username}`:seller?.external_contact_url;
 return <section aria-label="Listing detail"><a href="/marketplace" onClick={navigate}>Back to marketplace</a>{loading&&<p role="status">Loading listing details…</p>}{error&&<><p role="alert">{error}</p><button className="button secondary" onClick={()=>setRetry(n=>n+1)}>Retry listing</button></>}{detail&&<>
  <div className="listing-overview"><h2>{detail.title}</h2><p className="detail-price">{detail.price} KZT · {labels[detail.category_id-1]} · {detail.condition==='new'?'New':'Used'}</p><p>Published <time dateTime={detail.published_at}>{new Date(detail.published_at).toLocaleDateString()}</time></p><p className="listing-description">{detail.description}</p></div>
  <div className="detail-columns"><section aria-label="Listing photo gallery">{detail.photos.length?<><Photo key={detail.photos[selected].url} photo={detail.photos[selected]} alt={`Listing photo ${selected+1}`}/><p role="status">Photo {selected+1} of {detail.photos.length}{selected===0?' · Main photo':''}</p><div className="actions">{detail.photos.map((p,index)=><button className="button secondary" key={p.id} aria-pressed={selected===index} onClick={()=>setSelected(index)}>Photo {index+1}</button>)}</div></>:<p>No photos for this listing.</p>}</section>
  <div className="detail-sidebar"><section aria-label="Seller contact"><h3>Seller contact</h3>{seller.name&&<p>{seller.name}</p>}{contact&&<a className="button primary" href={contact} target="_blank" rel="noopener noreferrer">Contact Seller</a>}{seller.phone&&<p><a href={`tel:${seller.phone}`}>Call seller: {seller.phone}</a></p>}{seller.telegram_username&&seller.external_contact_url&&<p><a href={seller.external_contact_url} target="_blank" rel="noopener noreferrer">Other external contact</a></p>}{!contact&&!seller.phone&&<p>Seller contact is currently unavailable.</p>}<p>Negotiate, pay and arrange pickup directly with the seller. The marketplace does not process payments or provide chat.</p></section>
 <ListingReport listingId={listingId} /></div></div></>}</section>;
}
