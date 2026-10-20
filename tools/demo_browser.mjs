import assert from 'node:assert/strict';
import fs from 'node:fs';
import readline from 'node:readline';
import {createRequire} from 'node:module';
import {chromium,request} from '../frontend/node_modules/playwright/index.mjs';
const require=createRequire(import.meta.url);
const input=readline.createInterface({input:process.stdin});
const replies=[];input.on('line',line=>{replies.shift()?.(JSON.parse(line));});
const ipc=event=>new Promise(resolve=>{replies.push(resolve);console.log(JSON.stringify(event));});
let step='browser-start',browser;
const contexts=[];
const stages=[];
function stage(name){step=name;stages.push(name);console.log(JSON.stringify({event:'stage',name}));}
const web=process.env.SMOKE_WEB,api=process.env.SMOKE_API,password=process.env.SMOKE_PASSWORD;
try{
 browser=await chromium.launch({headless:true,...(process.env.SMOKE_BROWSER_EXECUTABLE?{executablePath:process.env.SMOKE_BROWSER_EXECUTABLE}:{})});
 let realResponses=0,directRequests=0,externalRequests=0;

 async function account(role){
  stage('register-verify-'+role);
  const context=await browser.newContext({viewport:{width:1280,height:900}});contexts.push(context);
  const page=await context.newPage();page.setDefaultTimeout(8000);page.on('response',r=>{if(r.url().startsWith(api))realResponses++;});page.on('request',r=>{if(/^https?:/.test(r.url())&&![new URL(web).origin,new URL(api).origin].includes(new URL(r.url()).origin))externalRequests++;});
  await page.goto(web+'/register');await page.getByLabel('University email',{exact:true}).fill(`demo-${role}@sdu.edu.kz`);await page.getByLabel('Password',{exact:true}).fill(password);await page.getByRole('button',{name:'Create account',exact:true}).click();
  await page.getByRole('form',{name:'Email verification',exact:true}).waitFor();
  const {code}=await ipc({event:'code',email:`demo-${role}@sdu.edu.kz`});
  await page.getByLabel('Verification code',{exact:true}).fill(code);await page.getByRole('button',{name:'Verify email',exact:true}).click();await page.getByText('Your university email is verified.',{exact:true}).waitFor();
  if(role==='admin')assert.equal((await ipc({event:'promote'})).promoted,true);
  await page.getByRole('link',{name:'Continue to sign in',exact:true}).click();await page.getByLabel('University email',{exact:true}).fill(`demo-${role}@sdu.edu.kz`);await page.getByLabel('Password',{exact:true}).fill(password);await page.getByRole('button',{name:'Sign in',exact:true}).click();await page.getByRole('button',{name:'Sign out',exact:true}).waitFor();return page;
 }
 const seller=await account('seller'),buyer=await account('buyer'),admin=await account('admin');
 assert.equal(await buyer.getByText('SYNTHETIC DEMO — no real authentication, email or marketplace data.',{exact:true}).count(),0);
 stage('seller-profile-listing-photo');
 await seller.goto(web+'/profile');await seller.getByLabel('Name',{exact:true}).fill('Demo seller');await seller.getByLabel('External contact URL',{exact:true}).fill('https://example.invalid/student-demo');await seller.getByRole('button',{name:'Save profile',exact:true}).click();await seller.getByText('Your profile was saved.',{exact:true}).waitFor();
 await seller.goto(web+'/listings/new');await seller.getByLabel('Title',{exact:true}).fill('Demo campus textbook');await seller.getByLabel('Description',{exact:true}).fill('A synthetic textbook listing for a local demonstration.');await seller.getByLabel('Price (KZT)',{exact:true}).fill('2500.00');await seller.getByLabel('Category',{exact:true}).selectOption('3');await seller.getByLabel('Condition',{exact:true}).selectOption('used');await seller.getByLabel('Optional photos',{exact:true}).setInputFiles(process.env.SMOKE_IMAGE);
 const created=seller.waitForResponse(r=>r.url()===api+'/listings'&&r.request().method()==='POST');await seller.getByRole('button',{name:'Create Pending listing',exact:true}).click();const listing=(await (await created).json());assert.equal(listing.status,'pending');assert.equal(listing.published_at,null);await seller.getByText('Creation complete. Awaiting manual admin review.',{exact:true}).waitFor();
 stage('pending-private');await buyer.goto(web+'/marketplace');await buyer.getByLabel('Search listings',{exact:true}).waitFor();await buyer.getByText('Loading marketplace listings…').waitFor({state:'hidden'});assert.equal(await buyer.getByRole('link',{name:'Demo campus textbook',exact:true}).count(),0);await buyer.goto(web+`/listings/${listing.id}`);await buyer.getByText('This listing is unavailable.',{exact:true}).waitFor();
 stage('admin-approve');await admin.goto(web+`/admin/listings/${listing.id}`);await admin.getByRole('button',{name:'Approve listing',exact:true}).click();await admin.getByRole('button',{name:'Confirm approval',exact:true}).click();await admin.getByText('Approval confirmed. Reloading current listing state.',{exact:true}).waitFor();await admin.getByRole('button',{name:'Approve listing',exact:true}).waitFor({state:'hidden'});
 stage('buyer-search-filter-detail');await buyer.goto(web+'/marketplace');await buyer.getByRole('link',{name:'Demo campus textbook',exact:true}).waitFor();await buyer.getByLabel('Search listings',{exact:true}).fill('campus');await buyer.getByLabel('Category',{exact:true}).selectOption('3');await buyer.getByLabel('Condition',{exact:true}).selectOption('used');await buyer.getByLabel('Minimum price (KZT)',{exact:true}).fill('2500');await buyer.getByLabel('Maximum price (KZT)',{exact:true}).fill('2500.00');const filtered=buyer.waitForResponse(r=>r.url().startsWith(api+'/listings?')&&r.url().includes('q=campus'));await buyer.getByRole('button',{name:'Apply filters',exact:true}).click();assert.equal((await (await filtered).json()).total,1);await buyer.getByRole('img',{name:'Main listing photo',exact:true}).waitFor();await buyer.screenshot({path:process.env.SMOKE_EVIDENCE+'/demo-desktop.png',fullPage:true});
 await buyer.getByRole('link',{name:'Demo campus textbook',exact:true}).click();await buyer.getByRole('img',{name:'Listing photo 1',exact:true}).waitFor();assert.equal(await buyer.getByRole('link',{name:'Contact Seller',exact:true}).getAttribute('href'),'https://example.invalid/student-demo');assert.equal(await buyer.getByRole('link',{name:'Contact Seller',exact:true}).getAttribute('rel'),'noopener noreferrer');
 await buyer.setViewportSize({width:390,height:844});await buyer.getByRole('button',{name:'Photo 1',exact:true}).focus();await buyer.keyboard.press('Enter');assert.equal(await buyer.getByRole('button',{name:'Photo 1',exact:true}).getAttribute('aria-pressed'),'true');assert.equal(await buyer.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),true);await buyer.screenshot({path:process.env.SMOKE_EVIDENCE+'/demo-mobile.png',fullPage:true});
 if(process.env.SMOKE_SQLITE_RESTART==='1'){
  stage('sqlite-backend-restart');assert.equal((await ipc({event:'restart',phase:'approved-listing'})).restarted,true);
  const restored=buyer.waitForResponse(r=>r.url()===api+'/auth/refresh'&&r.request().method()==='POST');
  await buyer.reload();assert.equal((await restored).status(),200);await buyer.getByRole('img',{name:'Listing photo 1',exact:true}).waitFor();
  assert.equal(await buyer.getByRole('link',{name:'Contact Seller',exact:true}).getAttribute('href'),'https://example.invalid/student-demo');
  assert.equal(await buyer.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),true);
  await buyer.screenshot({path:process.env.SMOKE_EVIDENCE+'/sqlite-after-restart.png',fullPage:true});
 }
 stage('buyer-report-admin-queue');await buyer.getByLabel('Report reason',{exact:true}).selectOption('misleading_information');await buyer.getByRole('button',{name:'Submit report',exact:true}).click();await buyer.getByText('Report accepted for later moderation review. Repeating a report keeps the original report.',{exact:true}).waitFor();await admin.goto(web+'/admin/reports');await admin.getByRole('button',{name:'Mark reviewed',exact:true}).waitFor();await admin.screenshot({path:process.env.SMOKE_EVIDENCE+'/demo-admin-reports.png',fullPage:true});await admin.getByRole('button',{name:'Mark reviewed',exact:true}).click();await admin.getByText('Report review confirmed. Listing moderation is separate.',{exact:true}).waitFor();await admin.getByLabel('Report state',{exact:true}).selectOption('reviewed');await admin.getByRole('link',{name:'Review listing: Demo campus textbook',exact:true}).click();
 if(process.env.SMOKE_SQLITE_RESTART==='1'){
  stage('sqlite-reviewed-report-restart');assert.equal((await ipc({event:'restart',phase:'reviewed-report'})).restarted,true);
  const restored=admin.waitForResponse(r=>r.url()===api+'/auth/refresh'&&r.request().method()==='POST');
  await admin.goto(web+'/admin/reports');assert.equal((await restored).status(),200);
  await admin.getByLabel('Report state',{exact:true}).selectOption('reviewed');
  await admin.getByRole('link',{name:'Review listing: Demo campus textbook',exact:true}).waitFor();
  await admin.screenshot({path:process.env.SMOKE_EVIDENCE+'/sqlite-reviewed-after-restart.png',fullPage:true});
  await admin.getByRole('link',{name:'Review listing: Demo campus textbook',exact:true}).click();
  await admin.getByRole('img',{name:'Admin listing photo 1',exact:true}).waitFor();
 }
 stage('admin-remove-buyer-hidden');await admin.getByRole('button',{name:'Remove listing',exact:true}).click();await admin.getByRole('button',{name:'Confirm removal',exact:true}).click();await admin.getByText('This listing is Removed; its records and photos are retained for review.',{exact:true}).waitFor();await admin.getByRole('img',{name:'Admin listing photo 1',exact:true}).waitFor();await buyer.goto(web+`/listings/${listing.id}`);await buyer.getByText('This listing is unavailable.',{exact:true}).waitFor();
 // Complement the principal UI path with real API checks, never mocked transport.
 const http=await request.newContext({baseURL:api});
 async function call(method,path,token,data,status=200){directRequests++;const result=await http.fetch(path,{method,headers:token?{Authorization:`Bearer ${token}`}:{},...(data===undefined?{}:{data})});assert.equal(result.status(),status);return status===204?null:await result.json();}
 async function login(role){return (await call('POST','/auth/login',null,{email:`demo-${role}@sdu.edu.kz`,password})).access_token;}
 const ownerToken=await login('seller'),adminToken=await login('admin');let buyerToken=await login('buyer');const buyerId=(await call('GET','/auth/me',buyerToken)).id;
 const payload={title:'Demo private listing',description:'A synthetic representative lifecycle item.',price:'10.00',category_id:3,condition:'used'};
 stage('rejection-owner-feedback');const rejected=await call('POST','/listings',ownerToken,payload,201);await call('POST',`/admin/listings/${rejected.id}/reject`,adminToken,{reason:'Demo feedback: replace with an accurate listing.'});await seller.goto(web+'/my-listings');await seller.getByText('Demo feedback: replace with an accurate listing.',{exact:false}).waitFor();await call('GET',`/listings/${rejected.id}`,buyerToken,undefined,404);
 stage('suspension-session-denial');await call('PATCH',`/admin/users/${buyerId}/suspension`,adminToken,{suspended:true});await call('GET','/auth/me',buyerToken,undefined,401);await buyer.goto(web+'/marketplace');await buyer.getByRole('form',{name:'Sign in',exact:true}).waitFor();await call('PATCH',`/admin/users/${buyerId}/suspension`,adminToken,{suspended:false});buyerToken=await login('buyer');
 stage('sold-delete');const sold=await call('POST','/listings',ownerToken,{...payload,title:'Demo sold listing'},201);await call('POST',`/admin/listings/${sold.id}/approve`,adminToken);await call('POST',`/listings/${sold.id}/sold`,ownerToken);await call('GET',`/listings/${sold.id}`,buyerToken,undefined,404);assert.equal((await call('DELETE',`/listings/${sold.id}`,ownerToken)).deleted,true);
 stage('account-cleanup');directRequests++;const image=await http.post('/users/me/avatar',{headers:{Authorization:`Bearer ${ownerToken}`},multipart:{image:{name:'synthetic.png',mimeType:'image/png',buffer:fs.readFileSync(process.env.SMOKE_IMAGE)}}});assert.equal(image.status(),200);await seller.goto(web+'/profile');await seller.getByRole('button',{name:'Delete my account',exact:true}).click();await seller.getByLabel('Current password for deletion',{exact:true}).fill(password);const deleted=seller.waitForResponse(r=>r.url()===api+'/users/me'&&r.request().method()==='DELETE');await seller.getByRole('button',{name:'Permanently delete account',exact:true}).click();assert.deepEqual(await (await deleted).json(),{deleted:true,cleanup_pending:false});await seller.getByRole('form',{name:'Sign in',exact:true}).waitFor();await call('GET','/auth/me',ownerToken,undefined,401);
 if(process.env.SMOKE_MEMORY_RESTART==='1'){
  stage('memory-live-private-state');
  await call('PATCH','/users/me',buyerToken,{phone:'+77001234567'});
  const pending=await call('POST','/listings',buyerToken,{...payload,title:'Volatile reset proof'},201);
  directRequests++;const photo=await http.post(`/listings/${pending.id}/photos`,{headers:{Authorization:`Bearer ${buyerToken}`},multipart:{image:{name:'synthetic.png',mimeType:'image/png',buffer:fs.readFileSync(process.env.SMOKE_IMAGE)}}});assert.equal(photo.status(),201);const privatePhoto=(await photo.json()).url;
  directRequests++;assert.equal((await http.post('/users/me/avatar',{headers:{Authorization:`Bearer ${buyerToken}`},multipart:{image:{name:'synthetic.png',mimeType:'image/png',buffer:fs.readFileSync(process.env.SMOKE_IMAGE)}}})).status(),200);
  stage('memory-sign-in-existing-buyer');await buyer.setViewportSize({width:1280,height:900});await buyer.goto(web+'/login');await buyer.getByLabel('University email',{exact:true}).fill('demo-buyer@sdu.edu.kz');await buyer.getByLabel('Password',{exact:true}).fill(password);await buyer.getByRole('button',{name:'Sign in',exact:true}).click();await buyer.getByRole('button',{name:'Sign out',exact:true}).waitFor();
  stage('memory-private-photo-ui');await buyer.goto(web+'/my-listings');await buyer.getByText('Volatile reset proof',{exact:true}).waitFor();await buyer.getByRole('img',{name:'Main listing photo',exact:true}).waitFor();
  stage('memory-cookie-bootstrap');directRequests++;const csrfReply=await http.get('/auth/csrf',{headers:{Origin:web}});assert.equal(csrfReply.status(),200);const csrf=(await csrfReply.json()).csrf_token;
  stage('memory-backend-restart-loss');const reset=await ipc({event:'memory-restart'});assert.equal(reset.state_reset,true);assert.equal(reset.private_images_removed,true);
  await call('GET','/auth/me',buyerToken,undefined,401);
  for(const path of [privatePhoto,'/users/me/avatar']){directRequests++;assert.equal((await http.get(path,{headers:{Authorization:`Bearer ${buyerToken}`}})).status(),401);}
  directRequests++;assert.equal((await http.post('/auth/refresh',{headers:{Origin:web,'X-CSRF-Token':csrf}})).status(),401);
  await call('POST','/auth/login',null,{email:'demo-buyer@sdu.edu.kz',password},401);
  await buyer.reload();await buyer.getByRole('form',{name:'Sign in',exact:true}).waitFor();
  await buyer.setViewportSize({width:390,height:844});assert.equal(await buyer.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  await buyer.screenshot({path:process.env.SMOKE_EVIDENCE+'/memory-after-restart.png',fullPage:true});
 }
 await http.dispose();assert.ok(realResponses>30);assert.equal(externalRequests,0);const version=browser.version();for(const context of contexts)await context.close();await browser.close();browser=null;
 fs.writeFileSync(process.env.SMOKE_EVIDENCE+'/demo-result.json',JSON.stringify({result:'PASS',node:process.version,playwright:require('../frontend/node_modules/playwright/package.json').version,browser:version,real_api_responses:realResponses+directRequests,browser_api_responses:realResponses,direct_api_requests:directRequests,external_requests:externalRequests,stages,desktop:'demo-desktop.png',mobile:'demo-mobile.png',admin:'demo-admin-reports.png',smtp:'controlled loopback protocol; external inbox unverified'},null,2)+'\n');console.log(JSON.stringify({event:'pass'}));input.close();
}catch(error){const p=contexts[1]?.pages()[0];const view=p?{route:new URL(p.url()).pathname,sign_in_forms:await p.getByRole('form',{name:'Sign in',exact:true}).count(),sign_out_buttons:await p.getByRole('button',{name:'Sign out',exact:true}).count(),alerts:await p.getByRole('alert').count()}:{};console.log(JSON.stringify({event:'fail',step,kind:error.name,view,...(typeof error.actual==='number'?{actual:error.actual}:{}),...(typeof error.expected==='number'?{expected:error.expected}:{})}));if(browser)await browser.close();input.close();process.exitCode=1;}
