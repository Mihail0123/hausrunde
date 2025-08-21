// static/js/myads.js
import { esc, qs } from "./utils.js";
import { getAccess } from "./config.js";
import {
  fetchAdsAuth, createAd, patchAd,
  uploadAdImages, deleteImage
} from "./api.js";

export function mountMyAds(root){
  if (!getAccess()) {
    root.innerHTML = `<div class="card">Please <b>login</b> on the Auth tab to see and manage your ads.</div>`;
    return;
  }

  root.innerHTML = `
    <h2>My Ads</h2>
    <div id="mineBox" class="grid grid-1"><div class="muted">Loading…</div></div>

    <div class="card" style="margin-top:12px">
      <h3>Create ad</h3>
      <div class="grid grid-3" id="createForm">
        <input name="title" placeholder="Title">
        <input name="location" placeholder="Location (city)">
        <input name="housing_type" placeholder="Housing type">
        <textarea name="description" rows="2" placeholder="Description" style="grid-column:1/-1"></textarea>
        <input name="price" type="number" placeholder="Price (€/day)">
        <input name="rooms" type="number" placeholder="Rooms">
        <input name="area" type="number" step="0.01" placeholder="Area (m²)">
        <div style="grid-column:1/-1">
          <div id="createMap" style="height:220px;border:1px solid #ddd;border-radius:10px;margin-bottom:6px;"></div>
          <div class="muted">Click on map to set coordinates. Type a city in “Location” to jump.</div>
          <input name="latitude" type="hidden">
          <input name="longitude" type="hidden">
        </div>
        <button class="btn" id="btnCreate" style="grid-column:1/-1">Create</button>
        <div class="muted" id="createMsg" style="grid-column:1/-1"></div>
      </div>
    </div>
  `;

  const mineBox = qs('#mineBox', root);

  async function loadMine(){
    try{
      const data  = await fetchAdsAuth({ mine: true, page_size: 50 });
      const items = data?.results ?? data ?? [];
      if (!items.length) {
        mineBox.innerHTML = `<div class="muted">You have no ads yet.</div>`;
        return;
      }
      mineBox.innerHTML = items.map(ad => renderEditable(ad)).join('');
      bindEditors();
    }catch(e){
      mineBox.innerHTML = `<div class="card" style="color:#b00">Error: ${esc(e.message || e)}</div>`;
    }
  }

  const imgSrc = (img) => img?.url || img?.image || img?.file || img?.src || img?.image_url || "";

  function renderEditable(ad){
    return `
      <div class="card" data-id="${ad.id}">
        <h4>#${ad.id} · ${esc(ad.title)}</h4>
        <div class="grid grid-3">
          <input name="title" value="${esc(ad.title)}">
          <input name="location" value="${esc(ad.location || '')}">
          <input name="housing_type" value="${esc(ad.housing_type || '')}">
          <textarea name="description" rows="2" style="grid-column:1/-1">${esc(ad.description || '')}</textarea>
          <input name="price" type="number" value="${Number(ad.price)||0}">
          <input name="rooms" type="number" value="${Number(ad.rooms)||0}">
          <input name="area" type="number" step="0.01" value="${ad.area!=null?Number(ad.area):''}">
          <label class="row" style="align-items:center;gap:6px"><input type="checkbox" name="is_active" ${ad.is_active?'checked':''}> Active</label>
          <div style="grid-column:1/-1" class="row" >
            <button class="btn" data-act="save">Save</button>
          </div>
        </div>

        <div style="margin-top:8px">
          <h5>Images</h5>
          <input type="file" multiple id="f${ad.id}">
          <input type="text" placeholder="Caption (optional)" id="c${ad.id}">
          <button class="btn-outline" data-act="upload" data-id="${ad.id}">Upload</button>
          <div class="row" style="flex-wrap:wrap;gap:8px;margin-top:6px">
            ${(ad.images||[]).map(img=>`
              <div class="card" style="padding:6px">
                <img src="${esc(imgSrc(img))}" loading="lazy"
                     style="width:140px;height:90px;object-fit:cover;border-radius:6px;border:1px solid #eee">
                <div class="row" style="margin-top:6px;gap:6px">
                  <button class="btn-outline" data-act="delimg" data-img="${img.id}">Delete</button>
                </div>
              </div>
            `).join('')}
          </div>
        </div>
      </div>
    `;
  }

  function bindEditors(){
    mineBox.querySelectorAll('[data-act="save"]').forEach(btn=>{
      btn.addEventListener('click', async ()=>{
        const card = btn.closest('[data-id]');
        const id   = Number(card.dataset.id);
        const areaVal = card.querySelector('input[name="area"]').value;

        const patch = {
          title: card.querySelector('input[name="title"]').value.trim(),
          location: card.querySelector('input[name="location"]').value.trim(),
          housing_type: card.querySelector('input[name="housing_type"]').value.trim(),
          description: card.querySelector('textarea[name="description"]').value.trim(),
          price: Number(card.querySelector('input[name="price"]').value || 0),
          rooms: Number(card.querySelector('input[name="rooms"]').value || 0),
          is_active: card.querySelector('input[name="is_active"]').checked,
        };
        if (areaVal !== '') patch.area = Number(areaVal);

        btn.disabled = true;
        try { await patchAd(id, patch); await loadMine(); }
        catch(e){ alert(e.message || e); }
        finally { btn.disabled = false; }
      });
    });

    mineBox.querySelectorAll('[data-act="upload"]').forEach(btn=>{
      btn.addEventListener('click', async ()=>{
        const adId = Number(btn.dataset.id);
        const files = root.querySelector(`#f${adId}`).files;
        const caption = root.querySelector(`#c${adId}`).value;
        btn.disabled = true;
        try { await uploadAdImages(adId, files, caption); await loadMine(); }
        catch(e){ alert(e.message || e); }
        finally { btn.disabled = false; }
      });
    });

    mineBox.querySelectorAll('[data-act="delimg"]').forEach(btn=>{
      btn.addEventListener('click', async ()=>{
        const imgId = Number(btn.dataset.img);
        btn.disabled = true;
        try { await deleteImage(imgId); await loadMine(); }
        catch(e){ alert(e.message || e); }
        finally { btn.disabled = false; }
      });
    });
  }

  // --- Create Ad: мини-карта + геокодинг локации ---------------------------
  let createMap = null, createMarker = null;
  (function initCreateMap(){
    createMap = L.map('createMap').setView([52.52, 13.405], 11);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19 }).addTo(createMap);
    createMap.on('click', (e)=>{
      const { lat, lng } = e.latlng;
      if (!createMarker) createMarker = L.marker([lat,lng]).addTo(createMap);
      else createMarker.setLatLng([lat,lng]);
      const f = root.querySelector('#createForm');
      f.elements.latitude.value  = lat.toFixed(6);
      f.elements.longitude.value = lng.toFixed(6);
    });
  })();

  // геокодинг: прыжок по городу
  const locInput = root.querySelector('#createForm input[name="location"]');
  let geoTimer = null;
  locInput.addEventListener('input', ()=>{
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
          createMap.setView([lat, lon], 12);
        }
      }catch{}
    }, 600);
  });

  // создание — не шлём null/"" полей, чтобы не ловить валидацию
  function compact(obj) {
    const out = {};
    for (const [k,v] of Object.entries(obj)) {
      if (v === "" || v === null || v === undefined) continue;
      out[k] = v;
    }
    return out;
  }

  root.querySelector('#btnCreate').addEventListener('click', async ()=>{
    const f = root.querySelector('#createForm');
    const payload = compact({
      title: f.elements.title.value.trim(),
      location: f.elements.location.value.trim(),
      housing_type: f.elements.housing_type.value.trim(),
      description: f.elements.description.value.trim(),
      price: Number(f.elements.price.value || 0),
      rooms: Number(f.elements.rooms.value || 0),
      area:  f.elements.area.value === '' ? undefined : Number(f.elements.area.value),
      latitude:  f.elements.latitude.value ? Number(f.elements.latitude.value) : undefined,
      longitude: f.elements.longitude.value ? Number(f.elements.longitude.value) : undefined,
    });
    const msg = qs('#createMsg', root);
    msg.textContent = 'Creating…';
    try{
      await createAd(payload);
      msg.textContent = 'Created';
      f.reset();
      if (createMarker) { createMap.removeLayer(createMarker); createMarker = null; }
      await loadMine();
    }catch(e){
      msg.textContent = 'Error: ' + (e.message || e);
    }
  });

  loadMine();
}
