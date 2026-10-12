export class ApiError extends Error {
  constructor(kind, status = 0) {
    super('The request could not be confirmed.');
    this.kind = kind;
    this.status = status;
  }
}

function apiOrigin() {
  const fallback = window.location.hostname === '127.0.0.1' ? 'http://127.0.0.1:8000' : 'http://localhost:8000';
  try {
    const url = new URL(import.meta.env.VITE_API_ORIGIN || fallback);
    if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password || url.search || url.hash || !['', '/'].includes(url.pathname)) throw new Error();
    return url.origin;
  } catch {
    throw new ApiError('configuration');
  }
}

export async function requestJson(path, { method = 'GET', payload, body, responseType, headers = {} } = {}) {
  let response;
  try {
    response = await fetch(`${apiOrigin()}${path}`, {
      method, credentials: 'include', headers: { ...(payload === undefined ? {} : { 'Content-Type': 'application/json' }), ...headers }, ...(payload === undefined ? (body === undefined ? {} : { body }) : { body: JSON.stringify(payload) }),
    });
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new ApiError('network');
  }
  if (!response.ok) throw new ApiError('http', response.status);
  let data;
  try {
    data = response.status === 204 ? null : responseType === 'blob' ? await response.blob() : await response.json();
  } catch {
    throw new ApiError('response');
  }
  const retryHeader = response.headers.get('Retry-After');
  const retry = /^\d+$/.test(retryHeader || '') ? Number(retryHeader) : 60;
  return { status: response.status, data, retryAfter: Number.isFinite(retry) ? Math.max(60, retry) : 60 };
}

export function postJson(path, payload) { return requestJson(path, { method: 'POST', payload }); }

export function universityEmail(value) {
  const trimmed = value.trim();
  const domain = trimmed.slice(trimmed.lastIndexOf('@') + 1);
  const normalized = trimmed.toLowerCase();
  if (!/^[\x00-\x7f]+$/.test(domain) || !/^[^\s@]+@sdu\.edu\.kz$/.test(normalized) || Array.from(normalized).length > 254) return null;
  return normalized;
}
