import {afterEach,expect,test,vi} from 'vitest';
import {requestJson} from './api.js';
afterEach(()=>{vi.unstubAllEnvs();vi.unstubAllGlobals();});
test('same-origin prefix preserves credentials, bearer, CSRF and binary response',async()=>{
 vi.stubEnv('VITE_API_PREFIX','/api');
 const fetcher=vi.fn().mockResolvedValue(new Response(new Blob(['photo']),{status:200}));vi.stubGlobal('fetch',fetcher);
 const result=await requestJson('/users/me/avatar',{responseType:'blob',headers:{Authorization:'Bearer synthetic','X-CSRF-Token':'synthetic'}});
 expect(fetcher).toHaveBeenCalledWith('/api/users/me/avatar',expect.objectContaining({credentials:'include',headers:{Authorization:'Bearer synthetic','X-CSRF-Token':'synthetic'}}));expect(result.data).toBeInstanceOf(Blob);
});
test.each(['//evil.invalid','https://evil.invalid/api','/api/../private','/api?x=1','/api#fragment','/api/','/api%2fprivate','/api\\private'])('unsafe prefix %s fails before fetch',async prefix=>{
 vi.stubEnv('VITE_API_PREFIX',prefix);const fetcher=vi.fn();vi.stubGlobal('fetch',fetcher);await expect(requestJson('/auth/me')).rejects.toMatchObject({kind:'configuration'});expect(fetcher).not.toHaveBeenCalled();
});
