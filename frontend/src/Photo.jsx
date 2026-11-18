import React,{useEffect,useState} from 'react';
import {useAuth} from './Auth.jsx';
import {ApiError} from './api.js';
export function Photo({photo,alt="Main listing photo",admin=false}){
 const auth=useAuth(),[src,setSrc]=useState(null),[error,setError]=useState(false);
 const get=admin?auth.adminGet:auth.get;
 useEffect(()=>{let active=true,url=null;setSrc(null);setError(false);get.call(auth,photo.url,true).then(result=>{
  if(result.status!==200||!['image/jpeg','image/png','image/webp'].includes(result.data?.type))throw new ApiError('response');
  if(active){url=URL.createObjectURL(result.data);setSrc(url);}
 }).catch(()=>{if(active)setError(true);});return()=>{active=false;if(url)URL.revokeObjectURL(url);};},[get,photo.url]);
 return error?<p className="photo-state photo-state--error">Photo is unavailable.</p>:src?<img className="marketplace-thumbnail" src={src} alt={alt}/>:<p className="photo-state photo-state--loading">Loading private photo…</p>;
}
