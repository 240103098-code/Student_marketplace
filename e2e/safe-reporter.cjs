const fs=require('node:fs');
class SafeReporter {
 onBegin(config,suite){this.rows=[];this.valid=config.workers===1&&config.projects.length===1&&suite.allTests().length===2; if(!this.valid)throw new Error('Unsupported execution topology');}
 onTestEnd(test,result){const id={'verified student smoke':'student','verified operator admin smoke':'admin'}[test.title];this.rows.push({test:id||'unknown',status:['passed','failed','timedOut','interrupted','skipped'].includes(result.status)?result.status:'unknown'});}
 onEnd(result){fs.writeFileSync(process.env.E2E_SAFE_REPORT,JSON.stringify({status:result.status,tests:this.rows},null,2));}
 printsToStdio(){return false;}
}
module.exports=SafeReporter;
