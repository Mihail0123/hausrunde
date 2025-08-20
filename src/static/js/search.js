import { fetchAds, fetchTopSearches } from './api.js';
import { renderAds, renderEmpty } from './ui.js';

const LS_KEY = 'hausrunde_recent_searches';
const loadRecent = () => { try { return JSON.parse(localStorage.getItem(LS_KEY)) || []; } catch { return []; } };
const saveRecent = (arr) => { try { localStorage.setItem(LS_KEY, JSON.stringify(arr.slice(0, 15))); } catch {} };
const pushRecent = (term) => { if (!term) return; const l = loadRecent().filter(x => x !== term); l.unshift(term); saveRecent(l); };

export function initSearch(map, getViewportParams, onFocus, onResults) {
  const form   = document.getElementById('searchForm');
  const panel  = document.getElementById('filtersPanel');
  const toggle = document.getElementById('btnFiltersToggle');
  const clear  = document.getElementById('btnClear');
  const topBtn = document.getElementById('btnTopSearches');
  const listEl = document.getElementById('list');

  let lastParams = {};

  toggle?.addEventListener('click', () => panel.classList.toggle('hidden'));
  clear?.addEventListener('click', async () => { form.reset(); await run(); });
  form?.addEventListener('submit', async (e) => { e.preventDefault(); await run(); });

  // "Top searches" сначала сервер, если пусто — localStorage
  topBtn?.addEventListener('click', async () => {
    const fromServer = await fetchTopSearches(15);
    const serverNames = (fromServer || []).map(x => (typeof x === 'string' ? x : x.q)).filter(Boolean);
    const names = serverNames.length ? serverNames : loadRecent();
    if (!names.length) { alert('Top searches are empty.'); return; }
    const pick = prompt('Top searches:\n' + names.map((n,i)=>`${i+1}. ${n}`).join('\n') + '\n\nType exact query:');
    if (pick) { document.getElementById('q').value = pick; await run(); }
  });

  async function run(extra = {}) {
    const fd = new FormData(form);
    const params = Object.fromEntries(fd.entries());

    // Совместимость: бэку нужен q, но если вдруг front шлёт search — перекинем
    if (!params.q && params.search) params.q = params.search;

    // В твоём бэке default ordering — '-created_at'
    if (!params.ordering) params.ordering = '-created_at';

    const viewport = getViewportParams();
    const withBBox = { ...params, ...viewport, ...extra };
    lastParams = withBBox;

    // 1) пробуем с bbox
    let items = await fetchAds(withBBox);

    // 2) если пусто — повтор без bbox (чтобы список не пустовал)
    if (!items.length) {
      const noBBox = { ...params, ...extra };
      items = await fetchAds(noBBox);
      lastParams = noBBox;
    }

    // локально копим недавние запросы
    if (params.q) pushRecent(params.q);

    if (!items.length) {
      renderEmpty(listEl, 'No results. Try widening the map or clearing filters.', async () => {
        form.reset(); await run({});
      });
      onResults?.([]);
      return [];
    }

    renderAds(listEl, items, (latlng) => {
      map.flyTo(latlng, Math.max(map.getZoom(), 14), { duration: 0.5 });
    });
    onResults?.(items);
    return items;
  }

  return {
    refreshFromMap: () => run(),
    runInitial: () => run(),
    getLastParams: () => lastParams,
  };
}
