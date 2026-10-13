import React,{useEffect,useState} from 'react';
import {useAuth} from './Auth.jsx';
export function AdminLanding({navigate}){
 const auth=useAuth(),[checked,setChecked]=useState(false),[loading,setLoading]=useState(true),[error,setError]=useState(''),[retry,setRetry]=useState(0);
 useEffect(()=>{let active=true;setChecked(false);setLoading(true);setError('');auth.adminCheck().then(()=>{if(active)setChecked(true);}).catch(e=>{if(active)setError(e.status===403?'Administrator access is required.':'Administrator access could not be checked. Please retry.');}).finally(()=>{if(active)setLoading(false);});return()=>{active=false;};},[auth.adminCheck,retry]);
 return <section aria-label="Administrator access">{loading&&<p role="status">Checking administrator access…</p>}{error&&<><p role="alert">{error}</p><button className="button secondary" onClick={()=>setRetry(n=>n+1)}>Retry admin access</button></>}{checked&&!loading&&<><h2>Admin access confirmed</h2><p>Your current account has administrator access. User, listing and report management screens are coming in subsequent tasks.</p></>}<p><a href="/marketplace" onClick={navigate}>Back to marketplace</a></p></section>;
}
