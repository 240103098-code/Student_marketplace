import React from 'react';
import {fireEvent,render,screen} from '@testing-library/react';
import {afterEach,test,expect,vi} from 'vitest';
import {App} from './App.jsx';
afterEach(()=>{vi.unstubAllGlobals();vi.restoreAllMocks();});
test.each([['/register','Registration'],['/login','Sign in'],['/forgot-password','Password recovery'],['/verify','Email verification']])('429 on %s gives server retry guidance without email or account success',async(path,form)=>{
 const mock=vi.fn((url)=>Promise.resolve(url.endsWith('/auth/csrf')?new Response('{}',{status:401}):new Response('{}',{status:429,headers:{'Retry-After':'321'}})));vi.stubGlobal('fetch',mock);window.history.replaceState(null,'',path);render(<App/>);await screen.findByRole('form',{name:form});fireEvent.change(screen.getByLabelText('University email'),{target:{value:'student@sdu.edu.kz'}});if(['/register','/login'].includes(path))fireEvent.change(screen.getByLabelText('Password'),{target:{value:'TEST_SECURITY_PASSWORD_123'}});if(path==='/verify')fireEvent.click(screen.getByRole('button',{name:'Request new code'}));else fireEvent.submit(screen.getByRole('form',{name:form}));const alert=await screen.findByRole('alert');expect(alert.textContent).toContain('Retry after 321 seconds');expect(alert.textContent).toContain('No action was performed');expect(mock.mock.calls.filter(([url])=>!url.endsWith('/auth/csrf'))).toHaveLength(1);expect(window.location.pathname).toBe(path);expect(screen.queryByText(/may arrive|account was created|email is verified/i)).toBeNull();
});
