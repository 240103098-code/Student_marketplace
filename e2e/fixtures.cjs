const fs=require('node:fs');
const path=require('node:path');
const crypto=require('node:crypto');
const {spawnSync}=require('node:child_process');
const {test:base,expect}=require('@playwright/test');
const test=base.extend({
 identity:async({},use)=>{await use({email:'e2e-'+crypto.randomUUID()+'@sdu.edu.kz',password:crypto.randomBytes(24).toString('hex')});},
 journey:async({page,identity},use,testInfo)=>{
  const stages=[],completed=[];let responses=0,external=0;const statuses={};
  page.on('response',r=>{if(r.url().startsWith(process.env.E2E_ORIGIN+'/api/')){responses++;statuses[r.status()]=(statuses[r.status()]||0)+1;}});
  page.on('request',r=>{if(/^https?:/.test(r.url())&&!r.url().startsWith(process.env.E2E_ORIGIN+'/'))external++;});
  async function stage(name,fn){stages.push(name);await fn();completed.push(name);}
  const journey={page,identity,stage,async verified(){
   await stage('ui-register',async()=>{await page.goto('/register');await page.getByLabel('University email',{exact:true}).fill(identity.email);await page.getByLabel('Password',{exact:true}).fill(identity.password);await page.getByRole('button',{name:'Create account',exact:true}).click();await page.getByLabel('Verification code',{exact:true}).waitFor();});
   await stage('private-smtp',async()=>{const file=path.join(process.env.E2E_MAIL,identity.email+'.json');await expect.poll(()=>fs.existsSync(file),{timeout:15000}).toBe(true);const message=JSON.parse(fs.readFileSync(file));expect(message.purpose).toBe('registration');expect(message.tls&&message.authenticated).toBe(true);await page.getByLabel('Verification code',{exact:true}).fill(message.code);fs.unlinkSync(file);});
   await stage('ui-verify',async()=>{await page.getByRole('button',{name:'Verify email',exact:true}).click();await page.getByRole('link',{name:'Continue to sign in',exact:true}).waitFor();});
  },async login(){await stage('ui-login',async()=>{await page.goto('/login');await page.getByLabel('University email',{exact:true}).fill(identity.email);await page.getByLabel('Password',{exact:true}).fill(identity.password);await page.getByRole('button',{name:'Sign in',exact:true}).click();await expect(page.getByRole('heading',{name:'Marketplace',exact:true})).toBeVisible();});},async promote(){await stage('operator-admin',async()=>{const result=spawnSync(process.env.E2E_PYTHON,[path.join(__dirname,'..','tools','e2e_stack.py'),'admin'],{input:identity.email,encoding:'utf8',stdio:['pipe','pipe','pipe'],timeout:30000});expect(result.status===0).toBe(true);});}};
  try{await use(journey);}finally{
   const id=testInfo.title.includes('admin')?'admin':'student';
   fs.writeFileSync(path.join(process.env.E2E_SAFE_DIR,id+'-stages.json'),JSON.stringify({stages,completed,smtp_tls_authenticated_registration:completed.includes('private-smtp'),responses,statuses,external,browser:page.context().browser().version()}));
   if(testInfo.status!==testInfo.expectedStatus){
    // Whole document masked: no account, code, error text, DOM snapshot or native output escapes.
    await page.screenshot({path:path.join(process.env.E2E_SAFE_DIR,id+'-masked.png'),mask:[page.locator('html')],maskColor:'#324951'}).catch(()=>{});
   }
   expect(external).toBe(0);
  }
 }
});
module.exports={test,expect};
