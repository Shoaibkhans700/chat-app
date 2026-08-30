// All requests go through the same-origin "/api" prefix.
// - In `vite dev`, vite.config.js proxies /api -> http://localhost:8000
// - In the Docker/Kubernetes build, nginx.conf.template proxies /api -> the backend service
// This means the frontend never needs to know the backend's real hostname at build time.
const API_BASE = '/api';

function getToken() {
  return localStorage.getItem('token');
}

async function request(path, { method = 'GET', body, auth = true } = {}) {
  const headers = { 'Content-Type': 'application/json' };
  if (auth) {
    const token = getToken();
    if (token) headers['Authorization'] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const data = await res.json();
      if (data?.detail) detail = data.detail;
    } catch {
      // response wasn't JSON - keep the generic message
    }
    throw new Error(detail);
  }

  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  register: (username, email, password) =>
    request('/register', { method: 'POST', body: { username, email, password }, auth: false }),

  login: (username, password) =>
    request('/login', { method: 'POST', body: { username, password }, auth: false }),

  me: () => request('/me'),

  listUsers: () => request('/users'),

  getConversation: (userId) => request(`/messages/${userId}`),

  sendMessage: (receiverId, message) =>
    request('/messages', { method: 'POST', body: { receiver_id: receiverId, message } }),
};

export function setToken(token) {
  localStorage.setItem('token', token);
}

export function clearToken() {
  localStorage.removeItem('token');
}

export function hasToken() {
  return Boolean(getToken());
}
