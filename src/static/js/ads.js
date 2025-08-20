import { qs, esc } from "./utils.js";
import { fetchAds, fetchAd } from "./api.js";

/**
 * Рисует раздел Ads (форма фильтров + карта + список).
 * @param {HTMLElement} root
 * @param {{ onOpenAd?: (ad) => void, onNeedBBox: (register: (bbox)=>void) => void }} hooks
 */
export function mountAds(root, { onOpenAd, onNeedBBox }) {
  root.innerHTML = `
    <h2>Ads</h2>

    <form class="grid grid-3" id="adsFilter" autocomplete="off">
      <input name="q"               placeholder="Search (q)">
      <input name="location"       placeholder="Location">
      <input name="housing_type"   placeholder="Housing type">

      <input name="price_min" type="number" placeholder="Price min">
      <input name="price_max" type="number" placeholder="Price max">
      <input name="rooms_min" type="number" placeholder="Rooms min">

      <input name="rooms_max" type="number" placeholder="Rooms max">
      <input name="rating_min" type="number" step="0.1" min="0" max="5" placeholder="Min rating">
      <select name="ordering">
        <option value="">Ordering</option>
        <option value="-created_at">new → old</option>
        <option value="created_at">old → new</option>
        <option value="price">price ↑</option>
        <option value="-price">price ↓</option>
        <option value="-views_count">most viewed</option>
        <option value="-reviews_count">most reviewed</option>
        <option value="-average_rating">rating ↓</option>
        <option value="average_rating">rating ↑</option>
      </select>

      <input name="area_min" type="number" step="0.1" placeholder="Area ≥">
      <input name="area_max" type="number" step="0.1" placeholder="Area ≤">
      <input name="available_from" type="date" placeholder="From">

      <input name="available_to" type="date" placeholder="To">
      <select name="page_size"><option>10</option><option>20</option><option>50</option></select>

      <div class="row" style="grid-column:1/-1">
        <button class="btn" id="adsSearch">Search</button>
        <button class="btn-outline" id="adsReset">Reset</button>
      </div>
    </form>

    <div class="grid grid-2" style="margin-top:10px;">
      <div>
        <div id="map" style="margin-bottom:10px;"></div>
        <div class="muted">Drag/zoom the map — bbox will be applied automatically.</div>
      </div>
      <div>
        <div id="adsList"></div>
        <div class="row" id="adsPager" style="justify-content:space-between"></div>
      </div>
    </div>
  `;

  const filter = qs("#adsFilter", root);
  const list   = qs("#adsList", root);
  const pager  = qs("#adsPager", root);

  let page = 1;
  let bbox = null; // {lat_min, lat_max, lon_min, lon_max}

  // --- helpers --------------------------------------------------------------
  const toNumber = (v) => (v === "" || v === undefined || v === null ? undefined : Number(v));
  function buildParams() {
    const fd  = new FormData(filter);
    const obj = Object.fromEntries(fd);

    // нормализуем пустые строки → undefined
    for (const k of Object.keys(obj)) if (obj[k] === "") obj[k] = undefined;

    // числовые поля
    ["price_min","price_max","rooms_min","rooms_max","area_min","area_max","rating_min","page_size"]
      .forEach(k => { if (obj[k] !== undefined) obj[k] = toNumber(obj[k]); });

    // дефолт сортировки (если не выбрано)
    if (!obj.ordering) obj.ordering = "-created_at";

    // пагинация
    obj.page = page;

    // bbox (если есть)
    return { ...obj, ...(bbox || {}) };
  }

  async function load() {
    list.innerHTML = `<div class="muted">Loading...</div>`;
    pager.innerHTML = "";
    try {
      // 1) пробуем с bbox (если он уже получен от карты)
      let data  = await fetchAds(buildParams());
      let items = data.results || data || [];

      // 2) если пусто — пробуем повтор без bbox (глобально)
      if (!items.length) {
        const p = buildParams();
        delete p.lat_min; delete p.lat_max; delete p.lon_min; delete p.lon_max;
        data  = await fetchAds(p);
        items = data.results || data || [];
      }

      render(data);
    } catch (e) {
      list.innerHTML = `<div class="card" style="color:#b00">Error loading ads: ${esc(e.message || e)}</div>`;
    }
  }

  function render(data) {
    const items = data.results || [];
    if (!items.length) {
      list.innerHTML = `<div class="muted">No results.</div>`;
      pager.innerHTML = "";
      return;
    }

    list.innerHTML = items.map(ad => `
      <div class="card" data-id="${ad.id}" style="cursor:pointer">
        <b>${esc(ad.title)}</b> — €${Number(ad.price||0).toLocaleString()}
        <div class="muted">
          ${esc(ad.location || ad.city || '')}
          · ${Number(ad.rooms)||0} rooms
          · ${ad.area!=null ? `${Number(ad.area)} m²` : '—'}
          · rating ${ad.average_rating!=null ? Number(ad.average_rating).toFixed(1) : '—'} (${ad.reviews_count||0})
        </div>
      </div>
    `).join('');

    // клик по карточке → onOpenAd(full)
    list.querySelectorAll('.card').forEach(el=>{
      el.addEventListener('click', async ()=>{
        const id = Number(el.getAttribute('data-id'));
        const full = await fetchAd(id);
        onOpenAd && onOpenAd(full);
      });
    });

    // пагинация
    const total = data.count ?? items.length;
    const size  = buildParams().page_size || 10;
    const pages = Math.max(1, Math.ceil(total / size));

    pager.innerHTML = `
      <div class="muted">Total: ${total}</div>
      <div class="row">
        <button class="btn-outline" id="pPrev" ${page<=1?'disabled':''}>Prev</button>
        <div>${page}/${pages}</div>
        <button class="btn-outline" id="pNext" ${page>=pages?'disabled':''}>Next</button>
      </div>
    `;
    qs('#pPrev', pager)?.addEventListener('click', ()=>{ page = Math.max(1, page - 1); load(); });
    qs('#pNext', pager)?.addEventListener('click', ()=>{ page = Math.min(pages, page + 1); load(); });
  }

  // --- events ---------------------------------------------------------------
  // submit формы
  filter.addEventListener('submit', (e) => { e.preventDefault(); page = 1; load(); });

  // кнопки
  qs('#adsSearch', filter).addEventListener('click', (e) => {
    e.preventDefault();
    filter.requestSubmit();
  });
  qs('#adsReset',  filter).addEventListener('click', (e) => {
    e.preventDefault();
    filter.reset(); bbox = null; page = 1; load();
  });

  // карта сообщает bbox через коллбек
  onNeedBBox((b) => { bbox = b; page = 1; load(); });

  // первичная загрузка (на случай, если bbox ещё не пришёл)
  load();
}
