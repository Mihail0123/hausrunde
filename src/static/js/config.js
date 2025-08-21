// База API. Можно переопределить через meta-тег:
// <meta name="api-base" content="/api">
export const API =
  document.querySelector('meta[name="api-base"]')?.content ||
  '/api';

// ----- Хранение access-токена (localStorage) -----

export function setAccess(token) {
  if (!token) {
    localStorage.removeItem('access');
  } else {
    localStorage.setItem('access', token);
  }
}

// Читаем access и проверяем exp (если это JWT)
export function getAccess() {
  const t = localStorage.getItem('access');
  if (!t) return null;
  try {
    const [, p] = t.split('.');
    const json = JSON.parse(atob(p.replace(/-/g, '+').replace(/_/g, '/')));
    if (json.exp && Math.floor(Date.now() / 1000) >= json.exp) {
      localStorage.removeItem('access'); // истёк — чистим
      return null;
    }
  } catch {
    // не JWT — просто вернём как есть
  }
  return t;
}

// Заголовок авторизации для защищённых эндпойнтов
export function hAuth() {
  const t = getAccess();
  return t ? { Authorization: `Bearer ${t}` } : {};
}