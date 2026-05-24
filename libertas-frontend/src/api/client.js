import axios from 'axios';

const API_BASE = '/api';

const client = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
});

client.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

client.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401 || err.response?.status === 403) {
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      window.location.href = '/login';
    }
    return Promise.reject(err);
  }
);

export default client;

// ── Auth ──
export const login = (username, password) =>
  client.post('/auth/login', { username, password });

export const register = (data) =>
  client.post('/auth/register', data);

export const changePassword = (oldPassword, newPassword) =>
  client.patch('/auth/change-password', { old_password: oldPassword, new_password: newPassword });

// ── Chat ──
export const createSession = (title) =>
  client.post('/chat/sessions', { title });

export const getSessions = () =>
  client.get('/chat/sessions');

export const getMessages = (sessionId) =>
  client.get(`/chat/sessions/${sessionId}/messages`);

export const sendMessage = (sessionId, message) =>
  client.post('/chat/send', { session_id: sessionId, message });

export const sendVoice = (sessionId, audioBlob) => {
  const form = new FormData();
  form.append('session_id', sessionId);
  form.append('audio', audioBlob, 'recording.webm');
  return client.post('/chat/voice', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
};

export const getTTS = (text) =>
  client.get('/chat/tts', { params: { text }, responseType: 'blob' });

export const deleteSession = (sessionId) =>
  client.delete(`/chat/sessions/${sessionId}`);

// ── Admin ──
export const getUsers = () => client.get('/admin/users');
export const createUser = (data) => client.post('/admin/users', data);
export const deleteUser = (userId) => client.delete(`/admin/users/${userId}`);
export const getUserSessions = (userId) => client.get(`/admin/users/${userId}/sessions`);
export const getSessionMessages = (sessionId) => client.get(`/admin/sessions/${sessionId}/messages`);
export const getDangerEvents = () => client.get('/admin/danger-events');
export const updateDangerStatus = (eventId, status) =>
  client.patch(`/admin/danger-events/${eventId}/status`, { status });

// ── 機構設定 ──
export const getInstitution = () => client.get('/admin/institution');
export const updateInstitution = (data) => client.put('/admin/institution', data);

// ── 知識庫重建 ──
export const rebuildKB = () => client.post('/admin/rebuild-kb');
export const getKBStatus = () => client.get('/admin/kb-status');
