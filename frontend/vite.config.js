import {defineConfig,loadEnv} from 'vite';
export default defineConfig(({command,mode})=>{
 const service=process.env.VITE_SERVICE_MODE||loadEnv(mode,process.cwd(),'VITE_').VITE_SERVICE_MODE||'real';
 if(!['real','mock'].includes(service)||command==='build'&&service==='mock')throw new Error('Mock service mode is development/test only. Production builds require real mode.');
 return {test:{environment:'jsdom',setupFiles:['./src/test-setup.js']}};
});
