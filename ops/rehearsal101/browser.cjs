// Trust is installed only in this process's temporary HOME NSS database by the controller.
const {chromium}=require('../../e2e/node_modules/@playwright/test');
const fs=require('node:fs');
(async()=>{
 const config=JSON.parse(fs.readFileSync(process.env.REHEARSAL101_BROWSER_CONFIG));
 const browser=await chromium.launch({args:['--host-resolver-rules=MAP dev.marketplace.test 127.0.0.1, MAP prod.marketplace.test 127.0.0.1']});
 try{
  const context=await browser.newContext();
  const page=await context.newPage();
  let unexpected=0;
  await context.route('**/*',route=>{
   const u=new URL(route.request().url());
   if(!config.stacks.some(s=>u.origin===s.origin)){unexpected++;return route.abort();}
   return route.continue();
  });
  const results=[];
  for(const stack of config.stacks){
   await page.goto(stack.origin+'/login');
   await page.getByLabel('University email',{exact:true}).fill(stack.email);
   await page.getByLabel('Password',{exact:true}).fill(stack.password);
   await page.getByRole('button',{name:'Sign in',exact:true}).click();
   await page.getByRole('heading',{name:'Marketplace',exact:true}).waitFor();
   const own=await context.cookies(stack.origin+'/api/auth/refresh');
   const other=config.stacks.find(s=>s.origin!==stack.origin);
   const otherCookies=await context.cookies(other.origin+'/api/auth/refresh');
   const cookie=own.find(c=>c.name==='refresh_token');
   if(!cookie||!cookie.secure||!cookie.httpOnly||cookie.domain!==new URL(stack.origin).hostname||cookie.path!=='/api/auth')throw Error('cookie flags');
   if(otherCookies.some(c=>c.value===cookie.value))throw Error('cross host cookie');
   // Actual browser request: Set-Cookie jar must not emit source cookie to other host.
   const seen=[]; const observe=request=>{if(request.url()===other.origin+'/api/auth/refresh')seen.push(request.allHeaders());};
   page.on('request',observe);
   await page.goto(other.origin+'/api/auth/refresh');
   page.off('request',observe);
   const headers=await Promise.all(seen);
   if(!headers.length||headers.some(h=>(h.cookie||'').includes(cookie.value)))throw Error('cookie transmission');
   results.push({environment:stack.name,trusted_navigation:true,secure_host_only_cookie:true,cross_host_cookie_absent:true});
  }
  if(unexpected)throw Error('external request');
  fs.writeFileSync(config.output,JSON.stringify({result:'PASS',browser:browser.version(),stacks:results,external_requests:unexpected}));
 }finally{await browser.close();}
})().catch(()=>{process.stderr.write('Browser isolation fixture failed\n');process.exit(1);});
