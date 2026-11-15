// Browser-private passive observation; no request/response substitution or storage.
function installRegistrationObserver(origin){
 const nativeFetch=globalThis.fetch,endpoint=origin+'/api/auth/register',rows=[];let sequence=0;
 Object.defineProperty(globalThis,'__registrationObservation',{value:{async take(status,expectedSequence){
  const row=rows.shift();
  if(!row||row.status!==status||row.sequence!==expectedSequence||row.redirected)throw new Error('Registration observation mismatch');
  let timer;
  try{
   const result=await Promise.race([row.body,new Promise(resolve=>{timer=setTimeout(()=>resolve({failed:true}),5000);})]);
   if(result.failed)throw new Error('Registration body observation unavailable');
   return result.body;
  }finally{clearTimeout(timer);}
 }}});
 globalThis.fetch=async function(...args){
  const response=await Reflect.apply(nativeFetch,this,args);
  const input=args[0],options=args[1];
  const url=new URL(typeof input==='string'?input:input.url||input.href,origin).href;
  const method=String(options?.method||input.method||'GET').toUpperCase();
  if(url===endpoint&&method==='POST'){
   let body;
   try{body=response.clone().text().then(body=>({body}),()=>({failed:true}));}catch{body=Promise.resolve({failed:true});}
   rows.push({sequence:++sequence,status:response.status,redirected:response.redirected||response.url!==endpoint,body});
  }
  return response;
 };
}
module.exports={installRegistrationObserver};
