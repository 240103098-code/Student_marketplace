const {test,expect}=require('./fixtures.cjs');
test('verified student smoke',async({journey,browser})=>{
 await journey.verified();await journey.login();
 await journey.stage('protected-reload',async()=>{await journey.page.reload();await expect(journey.page.getByRole('heading',{name:'Marketplace',exact:true})).toBeVisible();});
 await journey.stage('fresh-context-denied',async()=>{const context=await browser.newContext();try{const response=await context.request.get(process.env.E2E_ORIGIN+'/api/auth/me');expect(response.status()).toBe(401);const page=await context.newPage();await page.goto(process.env.E2E_ORIGIN+'/marketplace');await expect(page.getByRole('button',{name:'Sign in',exact:true})).toBeVisible();}finally{await context.close();}});
 await journey.stage('controlled-failure-check',async()=>{expect(process.env.E2E_INTENTIONAL_FAILURE==='1').toBe(false);});
});
test('verified operator admin smoke',async({journey})=>{await journey.verified();await journey.promote();await journey.login();await journey.stage('admin-role-access',async()=>{await journey.page.goto('/admin');await expect(journey.page.getByRole('heading',{name:'Admin access confirmed',exact:true})).toBeVisible();});});
