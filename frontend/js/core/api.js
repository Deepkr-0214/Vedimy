import { AppState } from './state.js';

const API_BASE = '/api';

async function request(method, path, body = null, requiresAuth = true) {
  const headers = { 'Content-Type': 'application/json' };
  if (requiresAuth) {
    headers['Authorization'] = `Bearer ${AppState.getToken()}`;
  }
  const config = { method, headers };
  if (body) config.body = JSON.stringify(body);

  const res = await fetch(API_BASE + path, config);
  const data = await res.json();
  
  if (!res.ok) throw new Error(data.error || 'Request failed');
  return data;
}

export const api = {
  get: (path, auth = true) => request('GET', path, null, auth),
  post: (path, body, auth = true) => request('POST', path, body, auth),
  delete: (path, auth = true) => request('DELETE', path, null, auth),
};
