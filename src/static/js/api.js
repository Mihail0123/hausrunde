// Centralized API functions. Adjust API_BASE and endpoints to your project.
const API_BASES = ['/api/v1', '/api']; // пробуем оба

function qs(params = {}) {
  const sp = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v === undefined || v === null || v === '') return;
    sp.append(k, v);
  });
  return sp.toString();
}

async function getJson(url) {
  const res = await fetch(url);
  if (!res.ok) {
    const err = new Error(`GET ${url} -> ${res.status}`);
    err.status = res.status;
    throw err;
  }
  return res.json();
}

export async function fetchAds(params = {}) {
  const query = qs(params);
  for (const base of API_BASES) {
    try {
      const data = await getJson(`${base}/ads/?${query}`);
      return Array.isArray(data) ? data : (data.results || []);
    } catch (e) {
      if (e.status === 404) continue;
      throw e;
    }
  }
  throw new Error('ads endpoint not found at /api/v1 or /api');
}

export async function fetchTopSearches(limit = 10) {
  const bases = ['/api/v1', '/api'];
  const paths = ['/search/history/top/', '/search/top/']; // оба варианта
  for (const base of bases) {
    for (const p of paths) {
      const url = `${base}${p}?limit=${encodeURIComponent(limit)}`;
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        // backend возвращает ПЛОСКИЙ список [{q, count}, ...]
        return Array.isArray(data) ? data : (data.results || []);
      }
    }
  }
  return [];
}

export async function logSearchTerm(query) {
  if (!query) return;
  const payload = JSON.stringify({ query });
  for (const base of ['/api/v1', '/api']) {
    try {
      await fetch(`${base}/search/log/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: payload,
      });
      return; // успех на первом попавшемся — выходим
    } catch (_) {
      // молча пробуем следующий base
    }
  }
}

