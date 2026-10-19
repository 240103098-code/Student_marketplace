/** @typedef {import('./contracts').Transport} Transport */
/** Explicit selection: real failures are never an invitation to switch providers. */
export function createTransport({mode='real',development=false,fetcher=(...args)=>fetch(...args),loadMock=()=>{if(import.meta.env.DEV)return import('./mockService.js');throw new Error('Mock code is excluded from production.');}}={}) {
 if(!['real','mock'].includes(mode)||mode==='mock'&&!development)throw new Error('Invalid service mode; mocks require development.');
 let mock;
 return async (url,options)=>mode==='real'?fetcher(url,options):(mock??=loadMock().then(module=>module.mockService)).then(service=>service.fetch(url,options));
}
export const isMockMode=import.meta.env.DEV&&import.meta.env.VITE_SERVICE_MODE==='mock';
export const transport=import.meta.env.DEV?createTransport({mode:import.meta.env.VITE_SERVICE_MODE||'real',development:true}):(...args)=>fetch(...args);
