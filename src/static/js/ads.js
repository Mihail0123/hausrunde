// static/js/ads.js
import { qs, esc } from "./utils.js";
import { fetchAds, fetchAd } from "./api.js";
import { createBooking } from "./api.js"; // используем в модалке (с умной попыткой ниже)

export function mountAds(root) {
  let page = 1;
  let pageSize = Number(localStorage.getItem("ads_page_size") || 10);
  let bbox = null;                  // { lat_min, lat_max, lon_min, lon_max }
  let mapRef = null;                // L.Map
  let draw = { active: false, start: null, rect: null };
  let loadTimer = null;

  const areaOptions = (() => {
    const opts = ['<option value="">Area</option>'];
    for (let m = 20; m <= 900; m += 20) opts.push(`<option value="${m}">${m} m²</option>`);
    opts.push(`<option value="901">900+ m²</option>`);
    return opts.join('');
  })();

  root.innerHTML = `
    <h2>Ads</h2>

    <form class="grid grid-3" id="adsFilter" autocomplete="off">
      <input name="q"               placeholder="Search (q)">
      <input name="location"       placeholder="Location (city)">
      <select name="housing_type">
        <option value="">Housing type</option>
        <option value="wohnung">Wohnung</option>
        <option value="house">House</option>
        <option value="room">Room</option>
        <option value="studio">Studio</option>
      </select>

      <input name="price_min" type="number" placeholder="Price min">
      <input name="price_max" type="number" placeholder="Price max">
      <input name="rooms_min" type="number" placeholder="Rooms min">

      <input name="rooms_max" type="number" placeholder="Rooms max">
      <input name="rating_min" type="number" step="0.1" min="0" max="5" placeholder="Min rating">
      <select name="ordering">
        <option value="">Ordering</option>
        <option value="-created_at" selected>new → old</option>
        <option value="created_at">old → new</option>
        <option value="price">price ↑</option>
        <option value="-price">price ↓</option>
        <option value="-views_count">most viewed</option>
        <option value="-reviews_count">most reviewed</option>
        <option value="-average_rating">rating ↓</option>
        <option value="average_rating">rating ↑</option>
      </select>

      <select name="area_min">${areaOptions}</select>
      <select name="area_max">${areaOptions.replace('Area','Area ≤')}</select>

      <div class="row" style="grid-column:1/-1;gap:10px;align-items:center">
        <div class="row" style="gap:8px;align-items:center">
          <span class="muted">Check-in</span>
          <input name="available_from" type="date" style="width:180px">
        </div>
        <div class="row" style="gap:8px;align-items:center">
          <span class="muted">Check-out</span>
          <input name="available_to" type="date" style="width:180px">
        </div>
      </div>

      <div class="row" style="grid-column:1/-1">
        <button class="btn" id="adsSearch" type="submit">Search</button>
        <button class="btn-outline" id="adsReset" type="button">Reset</button>
      </div>
    </form>

    <div class="grid grid-2" style="margin-top:10px;">
      <div>
        <div class="row" style="margin-bottom:6px;gap:8px">
          <button class="btn-outline" id="btnDraw">Draw zone</button>
          <button class="btn-outline" id="btnClearZone">Clear zone</button>
        </div>
        <div id="map" style="margin-bottom:10px;"></div>
        <div class="muted">Move/zoom map — bbox applies. Use <b>Draw zone</b> to select rectangle.</div>
      </div>
      <div>
        <div id="adsList"></div>
        <div class="row" id="adsPager" style="justify-content:space-between;align-items:center;margin-top:8px"></div>
      </div>
    </div>

    <div id="adModal" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.4);z-index:9999;align-items:center;justify-content:center">
      <div style="background:#fff;max-width:920px;width:92%;max-height:90vh;overflow:auto;border-radius:12px;padding:12px;box-shadow:0 10px 30px rgba(0,0,0,.3)">
        <div class="row" style="justify-content:space-between;align-items:center">
          <h3 id="mTitle" style="margin:6px 0"></h3>
          <button id="mClose" class="btn-outline">Close</button>
        </div>
        <div id="mBody"></div>
      </div>
    </div>
  `;

  const filter = qs("#adsFilter", root);
  const list   = qs("#adsList", root);
  const pager  = qs("#adsPager", root);
  const modal  = qs("#adModal", root);

  // ------- init Leaflet map (без зависимости от внешнего map.js)
  initMap();

  function initMap() {
    mapRef = L.map('map').setView([52.52, 13.405], 11);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19 }).addTo(mapRef);

    // первичный bbox с текущих границ
    applyBoundsDebounced();

    mapRef.on('moveend', () => {
      if (!draw.active) applyBoundsDebounced();
    });
  }
  function applyBoundsDebounced() {
    clearTimeout(loadTimer);
    loadTimer = setTimeout(() => {
      const b = mapRef.getBounds();
      bbox = {
        lat_min: b.getSouth(),
        lat_max: b.getNorth(),
        lon_min: b.getWest(),
        lon_max: b.getEast(),
      };
      page = 1;
      load();
    }, 120);
  }

  // ------- даты: аккуратное выравнивание и автокоррекция
  const inEl  = filter.elements.available_from;
  const outEl = filter.elements.available_to;
  inEl?.addEventListener('change', () => {
    if (!inEl.value) return;
    outEl.min = inEl.value;
    if (!outEl.value || outEl.value < inEl.value) outEl.value = inEl.value;
    outEl.focus();
  });
  outEl?.addEventListener('change', () => {
    if (!outEl.value) return;
    if (inEl.value && outEl.value < inEl.value) outEl.value = inEl.value;
  });

  // ------- геокодинг: прыжок по полю Location
  const locInput = filter.elements.location;
  let geoTimer = null;
  locInput?.addEventListener('input', ()=>{
    clearTimeout(geoTimer);
    const q = locInput.value.trim();
    if (q.length < 2) return;
    geoTimer = setTimeout(async ()=>{
      try{
        const url = `https://nominatim.openstreetmap.org/search?format=json&limit=1&q=${encodeURIComponent(q)}`;
        const r = await fetch(url, { headers: { 'Accept':'application/json' }});
        const data = await r.json();
        if (Array.isArray(data) && data[0]) {
          const lat = Number(data[0].lat), lon = Number(data[0].lon);
          mapRef.setView([lat, lon], 12);
          // moveend сам вызовет load()
        }
      }catch{}
    }, 600);
  });

  // ------- формы: поиск/сброс
  filter.addEventListener('submit', (e)=>{
    e.preventDefault();
    page = 1;
    load();
  });
  qs('#adsReset', filter).addEventListener('click', ()=>{
    filter.reset();
    bbox = null;
    page = 1;
    load();
  });

  // ------- helpers
  const num = (v) => (v === "" || v === undefined || v === null ? undefined : Number(v));
  function clean(obj){
    const out = {};
    for (const [k,v] of Object.entries(obj)){
      if (v === undefined || v === null || v === "") continue;
      out[k] = v;
    }
    return out;
  }
  function buildParams() {
    const fd  = new FormData(filter);
    const raw = Object.fromEntries(fd);
    const p = clean({
      q: raw.q, location: raw.location, housing_type: raw.housing_type,
      price_min: num(raw.price_min), price_max: num(raw.price_max),
      rooms_min: num(raw.rooms_min), rooms_max: num(raw.rooms_max),
      rating_min: num(raw.rating_min),
      area_min: num(raw.area_min), area_max: num(raw.area_max),
      available_from: raw.available_from, available_to: raw.available_to,
      ordering: raw.ordering || "-created_at",
      page_size: pageSize,
      page,
      ...(bbox || {})
    });
    // 900+ → без верхнего ограничения
    if (p.area_max && Number(p.area_max) >= 901) delete p.area_max;
    return p;
  }

  // ------- загрузка/отрисовка
  async function load() {
    list.innerHTML = `<div class="muted">Loading...</div>`;
    pager.innerHTML = "";
    try {
      // попытка 1: с bbox (если есть)
      let data  = await fetchAds(buildParams());
      let items = data.results || data || [];

      // попытка 2: без bbox, если пусто (чтобы не казалось, что ничего не работает)
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

  function stars(v) {
    if (v == null) return '—';
    const n = Math.max(0, Math.min(5, Math.round(Number(v))));
    return '★'.repeat(n) + '☆'.repeat(5 - n);
  }

  function render(data) {
    const items = data.results || [];
    if (!items.length) {
      list.innerHTML = `<div class="muted">No results.</div>`;
      pager.innerHTML = bottomPager(0, 1, 1);
      bindPager(1, 1);
      return;
    }

    list.innerHTML = items.map(ad => `
      <div class="card" data-id="${ad.id}" style="cursor:pointer">
        <b>#${ad.id}</b> · ${esc(ad.title)} — €${Number(ad.price||0).toLocaleString()}
        <div class="muted">
          ${esc(ad.location || ad.city || '')}
          · ${Number(ad.rooms)||0} rooms
          · ${ad.area!=null ? `${Number(ad.area)} m²` : '—'}
        </div>
        <div class="muted">
          ${stars(ad.average_rating)} (${ad.reviews_count ?? 0}) · 👁️ ${ad.views_count ?? 0}
        </div>
      </div>
    `).join('');

    list.querySelectorAll('.card').forEach(el=>{
      el.addEventListener('click', async ()=>{
        const id = Number(el.getAttribute('data-id'));
        try {
          const full = await fetchAd(id);
          openModal(full);
        } catch (e) {
          alert(e.message || e);
        }
      });
    });

    const total = data.count ?? items.length;
    const pages = Math.max(1, Math.ceil(total / pageSize));
    pager.innerHTML = bottomPager(total, page, pages);
    bindPager(page, pages);
  }

  function bottomPager(total, cur, pages){
    return `
      <div class="muted">Total: ${total}</div>
      <div class="row" style="gap:8px;align-items:center">
        <div class="row" style="gap:6px;align-items:center">
          <span class="muted">Per page</span>
          <select id="pageSize"><option ${pageSize===10?'selected':''}>10</option><option ${pageSize===20?'selected':''}>20</option><option ${pageSize===50?'selected':''}>50</option></select>
        </div>
        <button class="btn-outline" id="pPrev" ${cur<=1?'disabled':''}>Prev</button>
        <div>${cur}/${pages}</div>
        <button class="btn-outline" id="pNext" ${cur>=pages?'disabled':''}>Next</button>
      </div>
    `;
  }
  function bindPager(cur, pages){
    qs('#pageSize', pager)?.addEventListener('change', (e)=>{
      pageSize = Number(e.target.value || 10);
      localStorage.setItem('ads_page_size', String(pageSize));
      page = 1; load();
    });
    qs('#pPrev', pager)?.addEventListener('click', ()=>{ page = Math.max(1, cur - 1); load(); });
    qs('#pNext', pager)?.addEventListener('click', ()=>{ page = Math.min(pages, cur + 1); load(); });
  }

  // ------- рисование прямоугольной зоны
  const btnDraw  = qs('#btnDraw', root);
  const btnClear = qs('#btnClearZone', root);

  btnDraw.addEventListener('click', () => {
    if (!mapRef) return alert('Map is not ready yet');
    if (draw.active) return;
    draw.active = true;
    mapRef.dragging.disable();
    btnDraw.disabled = true;

    const onDown = (e) => {
      draw.start = e.latlng;
      draw.rect && mapRef.removeLayer(draw.rect);
      draw.rect = null;

      const onMove = (ev) => {
        if (!draw.start) return;
        const bounds = L.latLngBounds(draw.start, ev.latlng);
        if (!draw.rect) {
          draw.rect = L.rectangle(bounds, { color:'#3388ff', weight:1, fillOpacity:0.05 }).addTo(mapRef);
        } else {
          draw.rect.setBounds(bounds);
        }
      };
      const onUp = () => {
        mapRef.off('mousemove', onMove);
        mapRef.off('mouseup', onUp);
        mapRef.dragging.enable();
        draw.active = false;
        btnDraw.disabled = false;

        if (draw.rect) {
          const b = draw.rect.getBounds();
          bbox = {
            lat_min: b.getSouth(),
            lat_max: b.getNorth(),
            lon_min: b.getWest(),
            lon_max: b.getEast(),
          };
          page = 1; load();
        }
      };

      mapRef.on('mousemove', onMove);
      mapRef.on('mouseup', onUp);
    };

    mapRef.once('mousedown', onDown);
  });

  btnClear.addEventListener('click', ()=>{
    if (draw.rect) { mapRef && mapRef.removeLayer(draw.rect); draw.rect = null; }
    bbox = null; page = 1; load();
  });

  // ------- модалка: деталка + бронирование
  function imgSrc(img) {
    return img?.url || img?.image || img?.file || img?.src || img?.image_url || "";
  }

  async function createBookingSmart(adId, from, to) {
    // пробуем разные ключи, чтобы не гадать схему сериализатора
    const variants = [
      { ad: adId, date_from: from, date_to: to },
      { ad: adId, from, to },
      { ad_id: adId, from, to },
      { ad: adId, start: from, end: to },
      { ad: adId, check_in: from, check_out: to },
    ];
    let lastErr = null;
    for (const payload of variants) {
      try { return await createBooking(payload); }
      catch (e) { lastErr = e; }
    }
    throw lastErr || new Error("Booking failed");
  }

  function openModal(ad) {
    qs('#mTitle', root).textContent = `#${ad.id} · ${ad.title || `Ad`}`;

    const imgs = Array.isArray(ad.images) ? ad.images : [];
    const body = qs('#mBody', root);
    const gallery = imgs.length
      ? `<div class="row" style="gap:8px;flex-wrap:wrap">
           ${imgs.map(im=>`<img src="${esc(imgSrc(im))}" loading="lazy" style="width:180px;height:120px;object-fit:cover;border-radius:8px;border:1px solid #eee">`).join('')}
         </div>`
      : `<div class="muted">No images</div>`;

    const fIn  = filter.elements.available_from?.value || "";
    const fOut = filter.elements.available_to?.value   || "";

    body.innerHTML = `
      <div class="muted">
        ${esc(ad.location||'')} · ${ad.rooms||0} rooms · ${ad.area!=null?ad.area+' m²':'—'}
      </div>
      <div class="muted" style="margin:4px 0 10px">
        ${stars(ad.average_rating)} (${ad.reviews_count ?? 0}) · 👁️ ${ad.views_count ?? 0}
      </div>
      <p style="white-space:pre-wrap">${esc(ad.description||'')}</p>
      ${gallery}
      <div class="card" style="margin-top:12px">
        <h4>Request booking</h4>
        <div class="row" style="gap:8px;align-items:center;flex-wrap:wrap">
          <label class="row" style="gap:6px;align-items:center">Check-in <input id="bkIn"  type="date" value="${esc(fIn)}"></label>
          <label class="row" style="gap:6px;align-items:center">Check-out<input id="bkOut" type="date" value="${esc(fOut)}"></label>
          <button class="btn" id="bkBtn">Request</button>
          <div class="muted" id="bkMsg"></div>
        </div>
      </div>
    `;
    modal.style.display = 'flex';

    qs('#bkBtn', body)?.addEventListener('click', async ()=>{
      const from = qs('#bkIn', body).value;
      const to   = qs('#bkOut', body).value;
      const msg  = qs('#bkMsg', body);
      if (!from || !to) { msg.textContent = 'Select both dates'; return; }
      msg.textContent = 'Sending…';
      try {
        await createBookingSmart(ad.id, from, to);
        msg.textContent = 'Requested ✔';
      } catch (e) {
        msg.textContent = `Error: ${e.message || e}`;
      }
    });
  }

  qs('#mClose', root)?.addEventListener('click', ()=> modal.style.display='none');
  modal.addEventListener('click', (e)=> { if (e.target === modal) modal.style.display='none'; });

  // первичная загрузка
  load();
}
