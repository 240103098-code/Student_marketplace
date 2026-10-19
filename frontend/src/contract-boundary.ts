// Compile-only consumers of the gradual declaration boundary; no JSX conversion.
import {requestJson} from './api.js';
import type {SessionUser,Profile,Page,ListingCard,ListingDetail,OwnListing,AdminUser,AdminListing,Report,AccessGrant,Category,Photo} from './contracts';
export const boundary={
 me:()=>requestJson<SessionUser>('/auth/me'),
 login:(email:string,password:string)=>requestJson<AccessGrant>('/auth/login',{method:'POST',payload:{email,password}}),
 profile:()=>requestJson<Profile>('/users/me'),
 categories:()=>requestJson<Category[]>('/categories'),
 catalog:()=>requestJson<Page<ListingCard>>('/listings'),
 detail:(id:number)=>requestJson<ListingDetail>(`/listings/${id}`),
 mine:()=>requestJson<Page<OwnListing>&{status:string|null}>('/listings/mine'),
 users:()=>requestJson<Page<AdminUser>>('/admin/users'),
 listings:()=>requestJson<Page<AdminListing>>('/admin/listings'),
 reports:()=>requestJson<Page<Report>&{state:string}>('/admin/reports'),
 photo:(url:string)=>requestJson<Blob>(url,{responseType:'blob'}),
 upload:(id:number,file:File)=>{const body=new FormData();body.append('image',file);return requestJson<Photo>(`/listings/${id}/photos`,{method:'POST',body});},
};
