const fs=require('node:fs');
const IDS={'verified student smoke':'student','verified operator admin smoke':'admin','registration contract':'registration'};
const SELECTIONS={smoke:['student','admin'],registration:['registration'],full:['student','admin','registration']};
class SafeReporter {
 onBegin(config,suite){this.rows=[];const expected=SELECTIONS[process.env.E2E_SELECTION||'smoke'];const actual=suite.allTests().map(t=>IDS[t.title]);if(!expected||config.workers!==1||config.projects.length!==1||actual.length!==expected.length||actual.some(x=>!x)||expected.some(x=>!actual.includes(x)))throw new Error('Unsupported execution topology');}
 onTestEnd(test,result){const id=IDS[test.title];if(!id)throw new Error('Unsupported test');this.rows.push({test:id,status:['passed','failed','timedOut','interrupted','skipped'].includes(result.status)?result.status:'unknown'});}
 onEnd(result){fs.writeFileSync(process.env.E2E_SAFE_REPORT,JSON.stringify({status:result.status,tests:this.rows},null,2));}
 printsToStdio(){return false;}
}
module.exports=SafeReporter;
const REGISTRATION_STEPS=new Set(['duplicate-form','duplicate-http','duplicate-feedback','duplicate-state','duplicate-delivery-count','duplicate-response-body','duplicate-page-text','duplicate-storage','duplicate-privacy','duplicate-no-navigation','duplicate-layout']);
class RegistrationProgress {
 constructor(){this.started=performance.now();this.rows=[];}
 async step(name,action){
  if(!REGISTRATION_STEPS.has(name)||this.rows.length>=32)throw new Error('Unsupported registration step');
  const row={step:name,started_ms:Math.floor(performance.now()-this.started)};this.rows.push(row);
  const value=await action();row.completed_ms=Math.floor(performance.now()-this.started);return value;
 }
}
module.exports.RegistrationProgress=RegistrationProgress;
