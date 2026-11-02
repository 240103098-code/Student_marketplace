const fs=require('node:fs');
const {chromium}=require(process.env.CONTAINER_PLAYWRIGHT_MODULE);
(async()=>{
 const {origin,password}=JSON.parse(fs.readFileSync(0,'utf8'));
 const browser=await chromium.launch({executablePath:process.env.CONTAINER_BROWSER||'/usr/bin/google-chrome',headless:true,args:['--no-sandbox']});
 try{
  const page=await browser.newPage();let real=0;
  page.on('response',r=>{if(r.url().startsWith(origin+'/api/'))real++;});
  await page.goto(origin+'/login');
  await page.getByLabel('University email',{exact:true}).fill('container-test@sdu.edu.kz');
  await page.getByLabel('Password',{exact:true}).fill(password);
  await page.getByRole('button',{name:'Sign in',exact:true}).click();
  await page.getByRole('heading',{name:'Marketplace',exact:true}).waitFor();
  await page.reload();await page.getByRole('heading',{name:'Marketplace',exact:true}).waitFor();
  await page.screenshot({path:'container-desktop.png'});await page.setViewportSize({width:390,height:844});await page.screenshot({path:'container-mobile.png'});
  await page.goto(origin+'/listings/1');await page.getByText('This listing is unavailable.',{exact:false}).waitFor();
  if(real<3)throw new Error('Real API browser traffic missing');
  console.log(JSON.stringify({result:'PASS',version:browser.version(),real_api_responses:real}));
 }finally{await browser.close();}
})().catch(()=>{console.error('Packaged browser verification failed');process.exit(1);});
