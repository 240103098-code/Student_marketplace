const {test,expect}=require('@playwright/test');
const fs=require('node:fs');const path=require('node:path');const crypto=require('node:crypto');const {spawnSync}=require('node:child_process');
const {RegistrationProgress}=require('../safe-reporter.cjs');
const {installRegistrationObserver}=require('../registration-observer.cjs');
const STAGES=['keyboard-normalized-success','duplicate-preserved','invalid-addresses','password-bounds','smtp-rollback-retry','anonymous-denied'];
test('registration contract',async({page,browser})=>{
 const progress=new RegistrationProgress(),stageTimings=[];
 const stages=[],completed=[],statuses={};let requests=0,external=0,bodySequence=0;const secrets=[];
 const root=process.env.E2E_PRIVATE,mail=process.env.E2E_MAIL;
 page.on('request',r=>{if(r.url()===process.env.E2E_ORIGIN+'/api/auth/register')requests++;if(/^https?:/.test(r.url())&&!r.url().startsWith(process.env.E2E_ORIGIN+'/'))external++;});
 const identity=kind=>process.env.E2E_ID_PREFIX+kind+'@sdu.edu.kz';
 const password=n=>crypto.randomBytes(n).toString('hex').slice(0,n);
 function state(email,pass,operation='snapshot'){
  const result=spawnSync(process.env.E2E_PYTHON,[path.join(__dirname,'..','..','tools','e2e_stack.py'),'state'],{input:JSON.stringify({email,password:pass,operation}),encoding:'utf8',stdio:['pipe','pipe','pipe'],timeout:30000});expect(result.status===0).toBe(true);return JSON.parse(result.stdout);
 }
 function events(email){const file=path.join(root,'mail-events.jsonl');return fs.existsSync(file)?fs.readFileSync(file,'utf8').trim().split('\n').filter(Boolean).map(x=>JSON.parse(x)).filter(x=>x.recipient===email):[];}
 async function absent(email,pass){const value=state(email,pass);expect([value.users,value.codes,value.sessions]).toEqual([0,0,0]);}
 async function safe(response,duplicate=false){const measure=(name,action)=>duplicate?progress.step(name,action):action();const body=response?await measure('duplicate-response-body',()=>page.evaluate(({status,sequence})=>globalThis.__registrationObservation.take(status,sequence),{status:response.status(),sequence:++bodySequence})):'';const visible=await measure('duplicate-page-text',()=>page.locator('body').innerText());const storage=await measure('duplicate-storage',()=>page.evaluate(()=>JSON.stringify([Object.entries(localStorage),Object.entries(sessionStorage)])));for(const secret of secrets){expect([body,visible,storage,page.url()].every(x=>!x.includes(secret))).toBe(true);}expect(/\$argon2|password_hash|access_token|refresh_token/.test(body+visible+storage)).toBe(false);if(response)expect(response.headers()['set-cookie']===undefined).toBe(true);}
 async function layout(){expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);for(const locator of [page.getByLabel('University email',{exact:true}),page.getByRole('button',{name:/Create account|Verify email/,exact:true}),...await page.getByLabel('Password',{exact:true}).all(),...await page.getByRole('alert').all(),...await page.getByText(/Codes last ten minutes/).all()]){await expect(locator).toBeVisible();const box=await locator.boundingBox();expect(box.x>=0&&box.x+box.width<=390).toBe(true);}}
 async function form(email,pass){bodySequence=0;await page.goto('/register');await page.getByLabel('University email',{exact:true}).fill(email);await page.getByLabel('Password',{exact:true}).fill(pass);await expect(page.getByLabel('Password',{exact:true})).toHaveAttribute('type','password');}
 async function submit(status){const pending=page.waitForResponse(r=>r.url()===process.env.E2E_ORIGIN+'/api/auth/register'&&r.request().method()==='POST');await page.getByRole('button',{name:'Create account',exact:true}).click();const response=await pending;expect(response.status()).toBe(status);statuses[status]=(statuses[status]||0)+1;return response;}
 async function success(response,email,pass){await expect(page.getByLabel('Verification code',{exact:true})).toBeVisible();await expect(page.getByText(/Codes last ten minutes/)).toBeVisible();const data=await response.json();expect(Object.keys(data).sort()).toEqual(['email','id','verified']);expect(Number.isInteger(data.id)&&data.id>0).toBe(true);expect(data.email===email&&data.verified===false).toBe(true);await expect.poll(()=>events(email).length).toBe(1);const event=events(email)[0];expect(event.outcome==='stored'&&event.tls&&event.authenticated).toBe(true);const message=JSON.parse(fs.readFileSync(path.join(mail,email+'.json')));secrets.push(message.code);const value=state(email,pass);expect([value.users,value.codes,value.sessions]).toEqual([1,1,0]);expect(value.unverified_student&&value.registration_code&&value.one_way_password).toBe(true);await safe(response);}
 async function stage(name,fn){expect(STAGES.includes(name)).toBe(true);stages.push(name);const timing={stage:name,started_ms:Math.floor(performance.now()-progress.started)};stageTimings.push(timing);await fn();completed.push(name);timing.completed_ms=Math.floor(performance.now()-progress.started);}
 try{
  await page.addInitScript(installRegistrationObserver,process.env.E2E_ORIGIN);
  await page.setViewportSize({width:390,height:844});
  const email=identity('accepted'),pass=password(12);secrets.push(pass);
  await stage('keyboard-normalized-success',async()=>{
   await absent(email,pass);await form('  '+email.toUpperCase()+'  ',pass);await layout();const field=page.getByLabel('University email',{exact:true});await field.focus();await expect(field).toBeFocused();expect(await field.evaluate(e=>{const s=getComputedStyle(e);return s.outlineStyle!=='none'||s.boxShadow!=='none';})).toBe(true);await page.keyboard.press('Tab');await expect(page.getByLabel('Password',{exact:true})).toBeFocused();await page.keyboard.press('Tab');await expect(page.getByRole('button',{name:'Create account',exact:true})).toBeFocused();const pending=page.waitForResponse(r=>r.url()===process.env.E2E_ORIGIN+'/api/auth/register');await page.keyboard.press('Enter');const response=await pending;expect(response.status()).toBe(201);statuses[201]=1;await success(response,email,pass);await layout();
  });
  await stage('duplicate-preserved',async()=>{
   const duplicate=password(128);secrets.push(duplicate);
   await progress.step('duplicate-form',()=>form(email.toUpperCase(),duplicate));
   const response=await progress.step('duplicate-http',()=>submit(409));
   await progress.step('duplicate-feedback',()=>expect(page.getByRole('alert')).toContainText('already registered'));
   await progress.step('duplicate-state',()=>expect(state(email,pass,'compare').unchanged).toBe(true));
   await progress.step('duplicate-delivery-count',()=>expect(events(email).length).toBe(1));
   await progress.step('duplicate-privacy',()=>safe(response,true));
   await progress.step('duplicate-no-navigation',()=>expect(page.getByLabel('Verification code',{exact:true})).toHaveCount(0));
   await progress.step('duplicate-layout',()=>layout());
  });
  await stage('invalid-addresses',async()=>{
   const candidates=[process.env.E2E_ID_PREFIX+'malformed',identity('ordinary').replace('sdu.edu.kz','example.com'),identity('subdomain').replace('sdu.edu.kz','student.sdu.edu.kz'),identity('suffix')+'.example.com',identity('unicode').replace('sdu','sd\u0443')];
   for(const [index,candidate] of candidates.entries()){
    const target=candidate;await absent(target,pass);const before=requests;await form(candidate,pass);const nativeInvalid=await page.getByLabel('University email',{exact:true}).evaluate(e=>!e.validity.valid);if(index===0)expect(nativeInvalid).toBe(true);await page.getByRole('button',{name:'Create account',exact:true}).click();await expect(page.getByRole('alert')).toContainText('university email');expect(requests).toBe(before);expect(state(target,pass,'compare').unchanged).toBe(true);await expect(page.getByLabel('Verification code',{exact:true})).toHaveCount(0);await layout();await safe();
   }
  });
  await stage('password-bounds',async()=>{for(const length of [11,129]){const address=identity('password-'+length),invalid=password(length);secrets.push(invalid);await absent(address,invalid);const before=requests;await form(address,invalid);await page.getByRole('button',{name:'Create account',exact:true}).click();await expect(page.getByRole('alert')).toContainText('12–128');expect(requests).toBe(before);expect(state(address,invalid,'compare').unchanged).toBe(true);await expect(page.getByLabel('Verification code',{exact:true})).toHaveCount(0);await safe();await layout();}});
  await stage('smtp-rollback-retry',async()=>{
   const address=identity('retry'),valid=password(128);secrets.push(valid);await absent(address,valid);fs.writeFileSync(path.join(root,'fail-delivery'),'');let response;
   try{await form(address,valid);response=await submit(503);await expect(page.getByRole('alert')).toContainText('unavailable');await expect(page.getByLabel('Verification code',{exact:true})).toHaveCount(0);expect(state(address,valid,'compare').unchanged).toBe(true);expect(events(address).length).toBe(1);expect(events(address)[0].outcome==='rejected'&&events(address)[0].tls&&events(address)[0].authenticated).toBe(true);await safe(response);await layout();}finally{fs.unlinkSync(path.join(root,'fail-delivery'));}
   response=await submit(201);await expect(page.getByLabel('Verification code',{exact:true})).toBeVisible();const history=events(address);expect(history.map(e=>e.outcome)).toEqual(['rejected','stored']);const value=state(address,valid);expect(value.users===1&&value.codes===1&&value.sessions===0&&value.one_way_password&&value.registration_code&&value.unverified_student).toBe(true);const message=JSON.parse(fs.readFileSync(path.join(mail,address+'.json')));secrets.push(message.code);expect(Object.keys(await response.json()).sort()).toEqual(['email','id','verified']);await safe(response);await layout();
  });
  await stage('anonymous-denied',async()=>{expect((await page.context().cookies()).some(c=>/refresh/i.test(c.name))).toBe(false);const context=await browser.newContext();try{expect((await context.request.get(process.env.E2E_ORIGIN+'/api/auth/me')).status()).toBe(401);}finally{await context.close();}});
 }finally{
  fs.writeFileSync(path.join(process.env.E2E_SAFE_DIR,'registration-stages.json'),JSON.stringify({stages,completed,stage_timings:stageTimings,steps:progress.rows,requests,statuses,external,viewport:390,smtp_stored:completed.includes('keyboard-normalized-success')&&completed.includes('smtp-rollback-retry'),smtp_rejected:completed.includes('smtp-rollback-retry')}));
  if(test.info().status!==test.info().expectedStatus)await page.screenshot({path:path.join(process.env.E2E_SAFE_DIR,'registration-masked.png'),mask:[page.locator('html')],maskColor:'#324951'}).catch(()=>{});
  expect(external).toBe(0);
 }
});
