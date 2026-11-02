const fs=require('node:fs');
const {chromium}=require(process.env.CONTAINER_PLAYWRIGHT_MODULE);
(async()=>{
 const {origin,password,listing}=JSON.parse(fs.readFileSync(0,'utf8'));
 const browser=await chromium.launch({executablePath:process.env.CONTAINER_BROWSER||'/usr/bin/google-chrome',headless:true,args:['--no-sandbox']});
 try{
  const page=await browser.newPage();let real=0,external=0;
  page.on('response',r=>{if(r.url().startsWith(origin+'/api/'))real++;});
  page.on('request',r=>{if(/^https?:/.test(r.url())&&!r.url().startsWith(origin+'/'))external++;});
  await page.goto(origin+'/login');
  await page.getByLabel('University email',{exact:true}).fill('container-test@sdu.edu.kz');
  await page.getByLabel('Password',{exact:true}).fill(password);
  await page.getByRole('button',{name:'Sign in',exact:true}).click();
  await page.getByRole('heading',{name:'Marketplace',exact:true}).waitFor();
  await page.reload();await page.getByRole('heading',{name:'Marketplace',exact:true}).waitFor();
  await page.goto(origin+'/listings/'+listing);
  await page.getByRole('heading',{name:'Compose persistence item',exact:true}).waitFor();
  await page.screenshot({path:'compose-desktop.png'});
  await page.setViewportSize({width:390,height:844});await page.screenshot({path:'compose-mobile.png'});
  if(real<5||external!==0)throw new Error('Actual local Compose traffic expected');
  console.log(JSON.stringify({result:'PASS',version:browser.version(),real_api_responses:real,external_requests:external}));
 }finally{await browser.close();}
})().catch(()=>{console.error('Compose browser verification failed');process.exit(1);});
