import React,{useRef,useState} from 'react';
import {useAuth} from './Auth.jsx';
import {ApiError} from './api.js';
const reasons=['spam','prohibited_items','misleading_information'];
export function ListingReport({listingId}){
 const auth=useAuth(),[reason,setReason]=useState(''),[pending,setPending]=useState(false),[error,setError]=useState(''),[accepted,setAccepted]=useState(false),busy=useRef(false);
 async function submit(event){event.preventDefault();if(busy.current)return;if(!reasons.includes(reason)){setError('Choose a report reason.');return;}busy.current=true;setPending(true);setError('');setAccepted(false);
  try{const result=await auth.post(`/listings/${listingId}/reports`,{reason});if(result.status!==202||result.data?.accepted!==true)throw new ApiError('response');setAccepted(true);}
  catch(error){setError(error.status===400?'You cannot report your own listing.':error.status===404?'This listing is no longer available to report.':'Report submission could not be confirmed. You can retry; repeated reports are accepted without duplicates.');}
  finally{busy.current=false;setPending(false);}
 }
 return <section aria-label="Report listing"><h3>Report listing</h3><p>Flag spam, prohibited items or misleading information for later moderation review. Reports do not automatically remove listings.</p><form className="account-form" aria-label="Report listing" onSubmit={submit} noValidate><label htmlFor="report-reason">Report reason</label><select id="report-reason" value={reason} disabled={pending} onChange={e=>{setReason(e.target.value);setAccepted(false);setError('');}}><option value="">Choose a reason</option><option value="spam">Spam</option><option value="prohibited_items">Prohibited items</option><option value="misleading_information">Misleading information</option></select><button className="button secondary" disabled={pending}>{pending?'Submitting report…':'Submit report'}</button>{pending&&<p role="status">Confirming report submission…</p>}{accepted&&<p role="status" className="form-feedback">Report accepted for later moderation review. Repeating a report keeps the original report.</p>}{error&&<p role="alert" className="form-feedback error">{error}</p>}</form></section>;
}
