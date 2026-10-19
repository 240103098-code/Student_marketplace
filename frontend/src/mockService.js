// Synthetic, bounded UI demonstration. Never imported by a production real-mode build.
import {listingPrice} from './listingValidation.js';
const stamp='2026-01-01T12:00:00Z';
const categories=['Electronics','Clothing','Books','Furniture','Other'].map((label,i)=>({id:i+1,key:label.toLowerCase(),label}));
const reasons=['spam','prohibited_items','misleading_information'];
const png=()=>new Blob([Uint8Array.from(atob('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII='),c=>c.charCodeAt(0))],{type:'image/png'});
const reply=(status,data,headers={})=>new Response(status===204?null:JSON.stringify(data),{status,headers:{'Content-Type':'application/json','Cache-Control':'private, no-store',...headers}});
const failure=status=>reply(status,{detail:'Synthetic demo request was rejected.'},status===429?{'Retry-After':'60'}:{});
const copy=value=>structuredClone(value);
export function createMockService(){
 let users,items,reports,avatars,images,current,token,counter,nextId,scenario;
 function reset(){
  users=[['student-demo','Synthetic student','student'],['admin-demo','Synthetic administrator','admin'],['seller-demo','Synthetic seller','student'],['buyer-demo','Synthetic buyer','student']].map(([local,name,role],i)=>({id:i+1,email:local+'@sdu.edu.kz',name,role,verified:true,suspended:false,created_at:stamp,phone:null,telegram_username:null,external_contact_url:'https://example.invalid/synthetic-contact'}));
  items=[{id:1,owner_id:3,title:'Synthetic campus textbook',description:'Clearly synthetic book for development UI demonstrations only.',price:'2500.00',currency:'KZT',category_id:3,condition:'used',status:'active',created_at:stamp,published_at:stamp,rejection_reason:null,photoIds:[1]}];
  images=new Map([[1,png()]]);avatars=new Map();reports=[];current=null;token=null;counter=0;nextId=10;scenario='normal';
 }
 reset();
 const eligible=u=>u&&u.verified&&!u.suspended;
 const visible=item=>item?.status==='active'&&item.published_at&&eligible(users.find(u=>u.id===item.owner_id));
 const profile=u=>Object.fromEntries(['id','email','verified','name','phone','telegram_username','external_contact_url'].map(k=>[k,u[k]]));
 const identity=u=>({id:u.id,email:u.email,verified:true,is_admin:u.role==='admin'});
 const photo=(item,id,index,admin=false)=>({id,position:index+1,is_main:index===0,url:`${admin?'/admin':''}/listings/${item.id}/photos/${id}`});
 const photos=(item,admin=false)=>item.photoIds.map((id,i)=>photo(item,id,i,admin));
 const card=item=>Object.fromEntries(['id','title','price','currency','category_id','condition','published_at'].map(k=>[k,item[k]]));
 const base=item=>Object.fromEntries(['id','title','description','price','currency','category_id','condition','status','created_at','published_at'].map(k=>[k,item[k]]));
 const own=item=>({...base(item),rejection_reason:item.rejection_reason,photos:item.status==='removed'?[]:photos(item)});
 const seller=item=>{const u=users.find(u=>u.id===item.owner_id);return {id:u.id,email:u.email,name:u.name};};
 function page(rows,q,extra={}){const limit=Number(q.get('limit')||20),offset=Number(q.get('offset')||0);if(!Number.isInteger(limit)||limit<1||limit>50||!Number.isInteger(offset)||offset<0||offset>100000)return failure(422);const list=scenario==='empty'?[]:rows;const selected=list.slice(offset,offset+limit);return reply(200,{items:selected,total:list.length,count:selected.length,limit,offset,...extra});}
 function validListing(body){return typeof body.title==='string'&&body.title.trim().length>=3&&body.title.trim().length<=120&&typeof body.description==='string'&&body.description.trim().length>=10&&body.description.trim().length<=2000&&typeof body.price==='string'&&listingPrice(body.price)!==null&&Number.isInteger(body.category_id)&&body.category_id>=1&&body.category_id<=5&&['new','used'].includes(body.condition);}
 async function fetchMock(url,options={}){
  const parsed=new URL(url),path=parsed.pathname,q=parsed.searchParams,method=options.method||'GET',headers=new Headers(options.headers);
  if(scenario==='loading'&&method==='GET')await new Promise(resolve=>setTimeout(resolve,800));
  if(['network','error','rate'].includes(scenario)){const selected=scenario;scenario='normal';if(selected==='network')throw new TypeError('Synthetic network failure');return failure(selected==='rate'?429:503);}
  let body={};try{if(typeof options.body==='string')body=JSON.parse(options.body);}catch{return failure(422);}
  // Passwords and request credentials are inspected only for shape, never retained.
  if(path==='/auth/login'&&method==='POST'){
   const user=users.find(u=>u.email===body.email);if(!eligible(user)||typeof body.password!=='string'||body.password.length<12||body.password.length>128)return failure(401);
   current=user;token='synthetic-access-'+(++counter);return reply(200,{access_token:token,token_type:'bearer',expires_in:900});
  }
  if(path==='/auth/csrf')return eligible(current)?reply(200,{csrf_token:'d'.repeat(64)}):failure(401);
  if(path==='/auth/refresh'&&method==='POST'){if(!eligible(current))return failure(401);if(headers.get('X-CSRF-Token')!=='d'.repeat(64))return failure(403);token='synthetic-access-'+(++counter);return reply(200,{access_token:token,token_type:'bearer',expires_in:900});}
  if(path==='/auth/logout'&&method==='POST'){if(current&&headers.get('X-CSRF-Token')!=='d'.repeat(64))return failure(403);current=null;token=null;return reply(204);}
  if(path==='/auth/register'&&method==='POST'){
   if(!/^[a-z0-9._+-]+@sdu\.edu\.kz$/.test(body.email||'')||typeof body.password!=='string'||body.password.length<12||body.password.length>128)return failure(422);
   if(users.some(u=>u.email===body.email))return failure(409);if(users.length>=30)return failure(429);
   const user={...copy(users[0]),id:nextId++,email:body.email,name:null,role:'student',verified:false,phone:null,telegram_username:null,external_contact_url:null};users.push(user);return reply(201,{id:user.id,email:user.email,verified:false});
  }
  if(path==='/auth/resend-verification'||path==='/auth/forgot-password')return reply(202,{detail:'Request accepted.'},{'Retry-After':'60'});
  if(path==='/auth/verify-email'&&method==='POST'){const user=users.find(u=>u.email===body.email);if(!user||user.verified||user.suspended||body.code!=='000000')return failure(400);user.verified=true;return reply(200,{verified:true});}
  if(path==='/auth/reset-password'&&method==='POST'){if(body.code!=='000000'||typeof body.new_password!=='string'||body.new_password.length<12)return failure(400);current=null;token=null;return reply(204);}
  const user=current;
  if(!eligible(user)||headers.get('Authorization')!==`Bearer ${token}`)return failure(401);
  if(path.startsWith('/admin')&&(user.role!=='admin'||scenario==='permission'))return failure(403);
  if(path==='/auth/me')return reply(200,identity(user));
  if(path==='/admin/me')return reply(200,{id:user.id,is_admin:true});
  if(path==='/auth/change-password'&&method==='POST'){if(typeof body.current_password!=='string'||typeof body.new_password!=='string'||body.new_password.length<12)return failure(422);current=null;token=null;return reply(204);}
  if(path==='/users/me/avatar'){
   if(method==='GET')return avatars.has(user.id)?new Response(avatars.get(user.id),{headers:{'Content-Type':'image/png','Cache-Control':'private, no-store'}}):failure(404);
   if(method==='POST'){if(!(options.body instanceof FormData)||!(options.body.get('image') instanceof Blob))return failure(400);avatars.set(user.id,png());return reply(200,{detail:'Profile photo updated.',cleanup_pending:false});}
   if(method==='DELETE'){avatars.delete(user.id);return reply(200,{detail:'Profile photo removed.',cleanup_pending:false});}
  }
  if(path==='/users/me'){
   if(method==='PATCH'){const allowed=['name','phone','telegram_username','external_contact_url'];if(Object.keys(body).some(k=>!allowed.includes(k)))return failure(422);Object.assign(user,body);}
   if(method==='DELETE'){const ids=items.filter(i=>i.owner_id===user.id).map(i=>i.id);for(const item of items.filter(i=>i.owner_id===user.id))for(const photoId of item.photoIds)images.delete(photoId);items=items.filter(i=>i.owner_id!==user.id);reports=reports.filter(r=>r.reporter_id!==user.id&&!ids.includes(r.listing_id));users=users.filter(u=>u!==user);avatars.delete(user.id);current=null;token=null;return reply(200,{deleted:true,cleanup_pending:false});}
   return reply(200,profile(user));
  }
  if(path==='/categories')return reply(200,categories);
  if(path==='/listings'&&method==='POST'){
   if(!validListing(body)||Object.keys(body).some(k=>!['title','description','price','category_id','condition'].includes(k)))return failure(422);
   if(!user.phone&&!user.telegram_username&&!user.external_contact_url)return failure(400);if(items.length>=50)return failure(429);
   const item={...body,id:nextId++,owner_id:user.id,title:body.title.trim(),description:body.description.trim(),price:listingPrice(body.price),currency:'KZT',status:'pending',created_at:new Date().toISOString(),published_at:null,rejection_reason:null,photoIds:[]};items.unshift(item);return reply(201,base(item));
  }
  if(path==='/listings'&&method==='GET'){
   let rows=items.filter(visible);const query=(q.get('q')||'').trim().toLocaleLowerCase();if(query)rows=rows.filter(i=>(i.title+' '+i.description).toLocaleLowerCase().includes(query));
   for(const field of ['category_id','condition'])if(q.has(field))rows=rows.filter(i=>String(i[field])===q.get(field));
   if(q.has('min_price'))rows=rows.filter(i=>Number(i.price)>=Number(q.get('min_price')));if(q.has('max_price'))rows=rows.filter(i=>Number(i.price)<=Number(q.get('max_price')));
   rows.sort((a,b)=>b.published_at.localeCompare(a.published_at)||b.id-a.id);return page(rows.map(i=>({...card(i),main_photo:photos(i)[0]||null})),q);
  }
  if(path==='/listings/mine'){const status=q.get('status');return page(items.filter(i=>i.owner_id===user.id&&(!status||i.status===status)).sort((a,b)=>b.created_at.localeCompare(a.created_at)||b.id-a.id).map(own),q,{status:status||null});}
  if(path==='/admin/users')return page(users.map(u=>Object.fromEntries(['id','email','name','role','verified','suspended','created_at'].map(k=>[k,u[k]]))),q);
  const suspension=path.match(/^\/admin\/users\/(\d+)\/suspension$/);
  if(suspension&&method==='PATCH'){const target=users.find(u=>u.id===Number(suspension[1]));if(!target)return failure(404);if(target===user||target.role==='admin')return failure(409);if(typeof body.suspended!=='boolean')return failure(422);target.suspended=body.suspended;return reply(200,{id:target.id,suspended:target.suspended});}
  if(path==='/admin/listings'){const status=q.get('status');return page(items.filter(i=>!status||i.status===status).map(i=>({...base(i),seller:seller(i)})),q,{status:status||null});}
  if(path==='/admin/reports'){const state=q.get('state')||'unreviewed';const rows=reports.filter(r=>state==='all'||(state==='reviewed')===!!r.reviewed_at).map(r=>({id:r.id,reason:r.reason,created_at:r.created_at,reviewed_at:r.reviewed_at,listing:{id:r.listing_id,title:items.find(i=>i.id===r.listing_id).title,status:items.find(i=>i.id===r.listing_id).status,url:`/admin/listings/${r.listing_id}`}}));return page(rows,q,{state});}
  const review=path.match(/^\/admin\/reports\/(\d+)\/review$/);
  if(review&&method==='POST'){const report=reports.find(r=>r.id===Number(review[1]));if(!report)return failure(404);report.reviewed_at??=new Date().toISOString();return reply(200,{id:report.id,reviewed_at:report.reviewed_at});}
  const match=path.match(/^(\/admin)?\/listings\/(\d+)(?:\/(.*))?$/);
  if(match){
   const admin=!!match[1],item=items.find(i=>i.id===Number(match[2])),action=match[3]||'';
   if(!item)return failure(404);const owner=item.owner_id===user.id;
   if(action.startsWith('photos')){
    if(method==='POST'&&!admin){if(!owner)return failure(404);if(item.status!=='pending'||item.photoIds.length>=5)return failure(409);if(!(options.body instanceof FormData)||!(options.body.get('image') instanceof Blob))return failure(400);const id=nextId++;images.set(id,png());item.photoIds.push(id);return reply(201,{...photo(item,id,item.photoIds.length-1),listing_id:item.id});}
    const id=Number(action.split('/')[1]);if(!item.photoIds.includes(id)||!admin&&!(owner&&item.status!=='removed')&&!visible(item))return failure(404);return new Response(images.get(id),{headers:{'Content-Type':'image/png','Cache-Control':'private, no-store'}});
   }
   if(admin){
    if(method==='GET'&&!action)return reply(200,{...base(item),rejection_reason:item.rejection_reason,seller:seller(item),photos:photos(item,true)});
    if(method==='POST'&&action==='remove'){item.status='removed';return reply(200,{id:item.id,status:item.status,published_at:item.published_at});}
    if(method==='POST'&&action==='approve'){if(!['pending','active'].includes(item.status))return failure(409);if(!eligible(users.find(u=>u.id===item.owner_id)))return failure(409);item.status='active';item.published_at??=new Date().toISOString();return reply(200,{id:item.id,status:item.status,published_at:item.published_at,rejection_reason:null});}
    if(method==='POST'&&action==='reject'){if(typeof body.reason!=='string'||!body.reason.trim()||body.reason.trim().length>300)return failure(422);if(item.status!=='pending'&&!(item.status==='rejected'&&item.rejection_reason===body.reason.trim()))return failure(409);item.status='rejected';item.rejection_reason=body.reason.trim();return reply(200,{id:item.id,status:item.status,published_at:item.published_at,rejection_reason:item.rejection_reason});}
   }
   if(action==='reports'&&method==='POST'){if(!visible(item))return failure(404);if(owner)return failure(400);if(!reasons.includes(body.reason))return failure(422);if(!reports.some(r=>r.reporter_id===user.id&&r.listing_id===item.id)){if(reports.length>=100)return failure(429);reports.unshift({id:nextId++,reporter_id:user.id,listing_id:item.id,reason:body.reason,created_at:new Date().toISOString(),reviewed_at:null});}return reply(202,{accepted:true});}
   if(action==='edit'&&method==='GET'){if(!owner)return failure(404);return reply(200,base(item));}
   if(method==='PATCH'&&!action){if(!owner)return failure(404);if(!['pending','active','sold'].includes(item.status))return failure(409);if(!Object.keys(body).length||Object.keys(body).some(k=>!['price','description'].includes(k))||body.price!==undefined&&listingPrice(body.price)===null||body.description!==undefined&&(typeof body.description!=='string'||body.description.trim().length<10||body.description.trim().length>2000))return failure(422);Object.assign(item,body,...(body.price!==undefined?[{price:listingPrice(body.price)}]:[]));return reply(200,base(item));}
   if(method==='DELETE'&&!action){if(!owner)return failure(404);items=items.filter(i=>i!==item);reports=reports.filter(r=>r.listing_id!==item.id);for(const id of item.photoIds)images.delete(id);return reply(200,{id:item.id,deleted:true,cleanup_pending:false});}
   if(method==='POST'&&action==='sold'){if(!owner)return failure(404);if(!['active','sold'].includes(item.status))return failure(409);item.status='sold';return reply(200,{id:item.id,status:'sold',published_at:item.published_at});}
   if(method==='GET'&&!action){if(!visible(item))return failure(404);return reply(200,{...card(item),description:item.description,photos:photos(item),seller:Object.fromEntries(['name','phone','telegram_username','external_contact_url'].map(k=>[k,users.find(u=>u.id===item.owner_id)[k]]))});}
  }
  return failure(404);
 }
 return {fetch:fetchMock,reset,scenario(value){if(!['normal','loading','empty','network','error','rate','permission'].includes(value))throw new Error('Unknown synthetic scenario');scenario=value;}};
}
export const mockService=createMockService();
