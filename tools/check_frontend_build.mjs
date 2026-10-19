// Verify the actual production output and fail-closed build selection.
import {spawnSync} from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
const frontend=path.resolve(import.meta.dirname,'../frontend');
const build=spawnSync(process.execPath,['node_modules/vite/bin/vite.js','build'],{cwd:frontend,env:{...process.env,VITE_SERVICE_MODE:'real'},encoding:'utf8',windowsHide:true});
assert.equal(build.status,0,build.stderr);
const assets=path.join(frontend,'dist/assets');
for(const name of fs.readdirSync(assets)){
 const content=fs.readFileSync(path.join(assets,name),'utf8');
 for(const marker of ['student-demo@sdu.edu.kz','Synthetic campus textbook','SYNTHETIC DEMO','Reset synthetic fixtures','mockService'])assert.ok(!content.includes(marker),'Mock marker in production: '+marker);
 assert.ok(!name.startsWith('mock'),'Mock chunk emitted');
}
for(const mode of ['production','development']){
 const rejected=spawnSync(process.execPath,['node_modules/vite/bin/vite.js','build','--mode',mode],{cwd:frontend,env:{...process.env,VITE_SERVICE_MODE:'mock'},encoding:'utf8',windowsHide:true});
 assert.notEqual(rejected.status,0,'Mock production build must fail');
 assert.ok(rejected.stderr.includes('development/test only'),'Expected explicit mode guard');
}
console.log('PASS real production build excludes mock fixtures/controls; mock builds refused.');
