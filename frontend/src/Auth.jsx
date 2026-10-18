import React, { createContext, useContext, useEffect, useRef, useState } from 'react';
import { ApiError, requestJson } from './api.js';

const AuthContext = createContext(null);
const expiredMessage = 'Your session expired or is unavailable. Please sign in again.';

// Each provider owns one client. Credentials live only in this closure.
export function createSessionClient(notify) {
  let token = null;
  let csrf = null;
  let refreshFlight = null;
  let generation = 0;
  let confirmedUser=null;
  function clear(message = '') {
    generation += 1;
    confirmedUser=null;
    token = null;
    csrf = null;
    notify({ status: 'anonymous', user: null, message });
  }
  function access(data) {
    if (typeof data?.access_token !== 'string' || !data.access_token || data.token_type !== 'bearer' || data.expires_in !== 900) throw new ApiError('response');
    return data.access_token;
  }
  async function bootstrap() {
    const { data } = await requestJson('/auth/csrf');
    if (!/^[a-f0-9]{64}$/.test(data?.csrf_token || '')) throw new ApiError('response');
    return data.csrf_token;
  }
  async function confirm(candidate) {
    const { data } = await requestJson('/auth/me', { headers: { Authorization: `Bearer ${candidate}` } });
    if (!Number.isInteger(data?.id) || data.id < 1 || typeof data.email !== 'string' || data.verified !== true || typeof data.is_admin!=='boolean') throw new ApiError('response');
    return { id: data.id, email: data.email, verified: true,is_admin:data.is_admin };
  }
  function refresh() {
    if (!refreshFlight) {
      const started = generation;
      refreshFlight = (async () => {
        if (!csrf) {
          const nextCsrf = await bootstrap();
          if (generation !== started) throw new ApiError('session');
          csrf = nextCsrf;
        }
        const { data } = await requestJson('/auth/refresh', { method: 'POST', headers: { 'X-CSRF-Token': csrf } });
        const candidate = access(data);
        if (generation !== started) throw new ApiError('session');
        token = candidate;
        return candidate;
      })().finally(() => { refreshFlight = null; });
    }
    return refreshFlight;
  }
  return {
    async restore() {
      const started = generation;
      let hadSession = false;
      try {
        const nextCsrf = await bootstrap();
        if (started !== generation) return;
        csrf = nextCsrf;
        hadSession = true;
        const candidate = await refresh();
        const user = await confirm(candidate);
        if (started === generation) {confirmedUser=user;notify({ status: 'authenticated', user, message: '' });}
      } catch (error) {
        if (started === generation) clear(error.status === 401 && !hadSession ? '' : expiredMessage);
      }
    },
    async login(email, password) {
      generation += 1;
      const started = generation;
      try {
        const { data } = await requestJson('/auth/login', { method: 'POST', payload: { email, password } });
        const candidate = access(data);
        const user = await confirm(candidate);
        const nextCsrf = await bootstrap();
        if (started !== generation) throw new ApiError('session');
        token = candidate;
        csrf = nextCsrf;
        confirmedUser=user;notify({ status: 'authenticated', user, message: '' });
      } catch (error) {
        if (started === generation) clear();
        throw error;
      }
    },
    async get(path, binary = false, keepForbidden=false) {
      // Only read-only GET contracts are automatically retried; mutations are explicit.
      if (!token) throw new ApiError('session');
      const previous = token;
      const started = generation;
      try { return await requestJson(path, { responseType: binary ? 'blob' : undefined, headers: { Authorization: `Bearer ${previous}` } }); }
      catch (error) {
        if (error.status !== 401) {
          if (error.status === 403&&!keepForbidden) clear(expiredMessage);
          throw error;
        }
      }
      try {
        if (!token || started !== generation) throw new ApiError('session');
        const renewed = token && token !== previous ? token : await refresh();
        return await requestJson(path, { responseType: binary ? 'blob' : undefined, headers: { Authorization: `Bearer ${renewed}` } });
      } catch (error) { if(error.status!==403||!keepForbidden)clear(expiredMessage); throw error; }
    },
    async adminCheck(){
      const started=generation;
      try{const result=await this.get('/admin/me',false,true);if(started!==generation||result.status!==200||result.data?.id!==confirmedUser?.id||result.data?.is_admin!==true)throw new ApiError('response');if(!confirmedUser.is_admin){confirmedUser={...confirmedUser,is_admin:true};notify({status:'authenticated',user:confirmedUser,message:''});}return result;}
      catch(error){if(started===generation&&error.status===403&&confirmedUser){confirmedUser={...confirmedUser,is_admin:false};notify({status:'authenticated',user:confirmedUser,message:''});}throw error;}
    },
    async adminGet(path){
      const started=generation;
      try{return await this.get(path,false,true);}
      catch(error){if(started===generation&&error.status===403&&confirmedUser){confirmedUser={...confirmedUser,is_admin:false};notify({status:'authenticated',user:confirmedUser,message:''});}throw error;}
    },
    async adminPatch(path,payload){
      if(!token)throw new ApiError('session');const started=generation;
      try{return await requestJson(path,{method:'PATCH',payload,headers:{Authorization:`Bearer ${token}`}});}
      catch(error){if(started===generation){if(error.status===401)clear(expiredMessage);else if(error.status===403&&confirmedUser){confirmedUser={...confirmedUser,is_admin:false};notify({status:'authenticated',user:confirmedUser,message:''});}}throw error;}
    },
    async remove(path) {
      if(!token)throw new ApiError('session');
      try{return await requestJson(path,{method:'DELETE',headers:{Authorization:`Bearer ${token}`}});}
      catch(error){if([401,403].includes(error.status))clear(expiredMessage);throw error;}
    },
    async post(path,payload,file) {
      if (!token) throw new ApiError('session');
      const body=file?new FormData():undefined;
      if(file)body.append('image',file);
      try { return await requestJson(path,{method:'POST',payload:file?undefined:payload,body,headers:{Authorization:`Bearer ${token}`}}); }
      catch(error) { if([401,403].includes(error.status))clear(expiredMessage);throw error; }
    },
    async avatar(file) {
      if (!token) throw new ApiError('session');
      const body = file ? new FormData() : undefined;
      if (file) body.append('image', file);
      try { return await requestJson('/users/me/avatar', { method: file ? 'POST' : 'DELETE', body, headers: { Authorization: `Bearer ${token}` } }); }
      catch (error) {
        if ([401, 403].includes(error.status)) clear(expiredMessage);
        throw error;
      }
    },
    async patch(path, payload) {
      if (!token) throw new ApiError('session');
      try { return await requestJson(path, { method: 'PATCH', payload, headers: { Authorization: `Bearer ${token}` } }); }
      catch (error) {
        if ([401, 403].includes(error.status)) clear(expiredMessage);
        throw error;
      }
    },
    async resetPassword(email, code, newPassword) {
      const result = await requestJson('/auth/reset-password', { method: 'POST',
        payload: { email, code, new_password: newPassword } });
      if (result.status !== 204) throw new ApiError('response');
      clear('Your password was reset and all sessions were revoked. Please sign in again.');
    },
    async changePassword(currentPassword, newPassword) {
      if (refreshFlight) await refreshFlight;
      if (!token) throw new ApiError('session');
      try {
        const result = await requestJson('/auth/change-password', { method: 'POST',
          headers: { Authorization: `Bearer ${token}` },
          payload: { current_password: currentPassword, new_password: newPassword } });
        if (result.status !== 204) throw new ApiError('response');
        clear('Your password changed and all sessions were revoked. Please sign in again.');
      } catch (error) {
        if ([401, 403].includes(error.status)) clear(expiredMessage);
        throw error;
      }
    },
    async logout() {
      // Wait for any already-running rotation before revoking the browser's family.
      if (refreshFlight) await refreshFlight;
      if (!csrf) csrf = await bootstrap();
      try { await requestJson('/auth/logout', { method: 'POST', headers: { 'X-CSRF-Token': csrf } }); }
      catch (error) {
        if ([401, 403].includes(error.status)) clear(expiredMessage);
        throw error;
      }
      clear('You have signed out.');
    },
    dispose() { generation += 1; token = null; csrf = null; },
  };
}

export function AuthProvider({ children }) {
  const [state, setState] = useState({ status: 'loading', user: null, message: '' });
  const client = useRef(null);
  if (!client.current) client.current = createSessionClient(setState);
  useEffect(() => {
    client.current.restore();
    return () => client.current.dispose();
  }, []);
  return <AuthContext.Provider value={{ ...state, login: client.current.login, logout: client.current.logout, get: client.current.get, adminCheck: client.current.adminCheck, adminGet:client.current.adminGet, adminPatch:client.current.adminPatch, post: client.current.post, remove: client.current.remove, patch: client.current.patch, avatar: client.current.avatar, changePassword: client.current.changePassword, resetPassword: client.current.resetPassword }}>{children}</AuthContext.Provider>;
}
export function useAuth() { return useContext(AuthContext); }
