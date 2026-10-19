import {test,expect,beforeEach,afterEach,vi} from 'vitest';
import {Blob as NativeBlob} from 'node:buffer';
// Native Response consumes the native Blob; jsdom's Blob would stringify in Node.
beforeEach(()=>vi.stubGlobal('Blob',NativeBlob));afterEach(()=>vi.unstubAllGlobals());
import fs from 'node:fs';import path from 'node:path';import {createHash} from 'node:crypto';
import {createMockService} from './mockService.js';
import {photoFixtures} from './mockPhotos.js';
import provenance from '../../_docs/mock-photo-provenance.json';
const root=path.resolve(import.meta.dirname,'../..');
const send=(service,path,token,method='GET',body)=>service.fetch('http://mock'+path,{method,headers:{Authorization:'Bearer '+token},...(body?{body:JSON.stringify(body)}:{})});
async function login(service,email='buyer-demo@sdu.edu.kz'){return (await (await service.fetch('http://mock/auth/login',{method:'POST',body:JSON.stringify({email,password:'synthetic-test-password'})})).json()).access_token;}
function service(){const calls=[];return {calls,api:createMockService({readAsset:async url=>{calls.push(url);const name=new URL(url,'http://mock').pathname.split('/').at(-1);const bytes=fs.readFileSync(path.join(root,'frontend/src/mock-assets',name));return new Blob([bytes],{type:'image/jpeg'});}})};}
test('all six seed mappings and original JPEG bytes/hashes match recorded user source',async()=>{
 const {api,calls}=service(),token=await login(api);const page=await (await send(api,'/listings',token)).json();expect(page.items).toHaveLength(6);expect(page.items.map(x=>[x.id,x.title,x.category_id,x.condition,x.price])).toEqual(provenance.photos.map(x=>[x.id,x.title,x.category_id,x.condition,x.demo_price]));
 for(const [index,item] of page.items.entries()){
  const source=provenance.photos[index];const response=await send(api,item.main_photo.url,token);expect(response.status).toBe(200);expect(response.headers.get('Content-Type')).toBe('image/jpeg');expect(response.headers.get('Cache-Control')).toContain('no-store');const bytes=Buffer.from(await response.arrayBuffer());expect(bytes.subarray(0,2)).toEqual(Buffer.from([255,216]));expect(bytes.length).toBe(source.bytes);expect(createHash('sha256').update(bytes).digest('hex')).toBe(source.sha256);expect(bytes).toEqual(fs.readFileSync(path.join(root,source.target_path)));
 }
 expect(calls).toHaveLength(6);expect(photoFixtures).toHaveLength(6);
});
test('authorization and photo linkage are checked before local assets; owner/admin/delete/reset remain isolated',async()=>{
 const {api,calls}=service();expect((await send(api,'/listings/1/photos/1',null)).status).toBe(401);let token=await login(api);expect((await send(api,'/listings/1/photos/2',token)).status).toBe(404);expect(calls).toHaveLength(0);
 token=await login(api,'seller-demo@sdu.edu.kz');let mine=await (await send(api,'/listings/mine',token)).json();expect(mine.items).toHaveLength(6);expect((await send(api,mine.items[0].photos[0].url,token)).status).toBe(200);await send(api,'/listings/1',token,'DELETE');expect((await send(api,'/listings/1/photos/1',token)).status).toBe(404);expect((await send(api,'/listings/2/photos/2',token)).status).toBe(200);
 api.reset();token=await login(api,'admin-demo@sdu.edu.kz');const detail=await (await send(api,'/admin/listings/1',token)).json();expect(detail.photos[0].url).toBe('/admin/listings/1/photos/1');await send(api,'/admin/listings/1/remove',token,'POST');expect((await send(api,'/admin/listings/1/photos/1',token)).status).toBe(200);token=await login(api);expect((await send(api,'/listings/1/photos/1',token)).status).toBe(404);expect((await send(api,'/listings/2/photos/2',token)).status).toBe(200);api.reset();token=await login(api);expect((await (await send(api,'/listings',token)).json()).total).toBe(6);expect((await send(api,'/listings/1/photos/1',token)).headers.get('Content-Type')).toBe('image/jpeg');
});
