export const API = "/api";

// Храним JWT access в localStorage (простая стратегия)
export function setAccess(token) { if (token) localStorage.setItem('access', token); else localStorage.removeItem('access'); }
export function getAccess() { return localStorage.getItem('access') || null; }
export function hAuth() { const t = getAccess(); return t ? { "Authorization": "Bearer " + t } : {}; }
