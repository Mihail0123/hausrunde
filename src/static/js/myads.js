import { esc } from "./utils.js";
import {getAccess} from "./config.js";
import { fetchAds, createAd, patchAd, uploadAdImages, deleteImage, replaceImage, fetchAd } from "./api.js";

export function mountMyAds(root){
  if (!getAccess()) {
    root.innerHTML = `<div class="card">Please <b>login</b> on the Auth tab to see and manage your ads.</div>`;
    return;
  }
  root.innerHTML = `
  
    <h2>My Ads</h2>
    <div id="mineList" class="grid"></div>
    <div class="card" style="margin-top:10px;">
      <h3>Create ad</h3>
      <div class="grid grid-3" id="createForm">
        <input name="title" placeholder="Title">
        <input name="location" placeholder="Location">
        <input name="housing_type" placeholder="Housing type">
        <textarea name="description" rows="2" placeholder="Description" style="grid-column:1/-1"></textarea>
        <input name="price" type="number" placeholder="Price (€/day)">
        <input name="rooms" type="number" placeholder="Rooms">
        <input name="area" type="number" step="0.01" placeholder="Area">
        <div style="grid-column:1/-1">
            <div id="createMap" style="height:220px;border:1px solid #ddd;border-radius:10px;margin-bottom:6px;"></div>
            <div class="muted">Click on map to set coordinates</div>
            <input name="latitude" type="hidden">
            <input name="longitude" type="hidden">
          </div>
        <button class="btn" id="btnCreate" style="grid-column:1/-1">Create</button>
        <div class="muted" id="createMsg" style="grid-column:1/-1"></div>
      </div>
    </div>
    <div id="adModal" class="section"></div>
  `;

  async function loadMine(){
    const data = await fetchAds({ mine:true, page_size:50 });
    const items = data.results||[];
    const wrap = root.querySelector('#mineList');
    if(!items.length){ wrap.innerHTML = `<div class="muted">No ads yet.</div>`; return; }
    wrap.innerHTML = items.map(a => `
      <div class="card" data-id="${a.id}" style="cursor:pointer">
        <div><b>${esc(a.title)}</b></div>
        <div class="muted">${esc(a.location)}</div>
        <div>€${Number(a.price||0).toLocaleString()}</div>
      </div>
    `).join('');
    wrap.querySelectorAll('.card').forEach(el=>{
      el.addEventListener('click', async ()=>{
        const id = Number(el.getAttribute('data-id'));
        const full = await fetchAd(id);
        openAdEditor(full);
      });
    });
  }

  root.querySelector('#btnCreate').addEventListener('click', async ()=>{
    const f = root.querySelector('#createForm');
    const payload = Object.fromEntries(new FormData(f));
    payload.price = Number(payload.price||0);
    payload.rooms = Number(payload.rooms||0);
    payload.area  = payload.area ? Number(payload.area) : null;
    try{
      await createAd(payload);
      f.reset(); root.querySelector('#createMsg').textContent = 'Created';
      loadMine();
    }catch(e){ root.querySelector('#createMsg').textContent = 'Error: ' + e.message; }
  });

  // карта-пикер для координат
  (function initCreateMap(){
    const map = L.map('createMap').setView([52.52, 13.405], 11);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19 }).addTo(map);
    let marker = null;
    map.on('click', (e)=>{
      const { lat, lng } = e.latlng;
      if (!marker) marker = L.marker([lat,lng]).addTo(map);
      else marker.setLatLng([lat,lng]);
      const f = root.querySelector('#createForm');
      f.elements.latitude.value  = lat.toFixed(6);
      f.elements.longitude.value = lng.toFixed(6);
    });
  })();

  function openAdEditor(ad){
    const m = root.querySelector('#adModal');
    m.classList.add('card','active');
    m.innerHTML = `
      <h3>Edit #${ad.id}</h3>
      <div class="grid grid-3" id="editForm">
        <input name="title" value="${esc(ad.title||'')}" placeholder="Title">
        <input name="location" value="${esc(ad.location||'')}" placeholder="Location">
        <input name="housing_type" value="${esc(ad.housing_type||'')}" placeholder="Housing type">
        <textarea name="description" rows="2" placeholder="Description" style="grid-column:1/-1">${esc(ad.description||'')}</textarea>
        <input name="price" type="number" value="${Number(ad.price||0)}" placeholder="Price">
        <input name="rooms" type="number" value="${Number(ad.rooms||0)}" placeholder="Rooms">
        <input name="area" type="number" step="0.01" value="${ad.area!=null?Number(ad.area):''}" placeholder="Area">
        <label><input type="checkbox" name="is_active" ${ad.is_active?'checked':''}> Active</label>
        <div style="grid-column:1/-1" class="row">
          <button class="btn" id="btnSave">Save</button>
          <button class="btn-outline" id="btnClose">Close</button>
        </div>
      </div>
      <div style="margin-top:10px;">
        <b>Images</b>
        <div class="row">
          <input type="file" id="upFiles" multiple>
          <input type="text" id="cap" placeholder="Caption (optional)">
          <button class="btn" id="btnUpload">Upload</button>
        </div>
        <div id="gallery" class="row" style="margin-top:8px;"></div>
      </div>
    `;
    const gal = m.querySelector('#gallery');
    renderGallery();

    async function renderGallery(){
      const fresh = await fetchAd(ad.id);
      ad = fresh;
      gal.innerHTML = (ad.images||[]).map(im=>`
        <div class="card" style="padding:8px">
          <img src="${im.image_url||im.image_path||''}" alt="" style="height:100px; display:block; border-radius:6px; border:1px solid #eee">
          <div class="row">
            <input type="text" data-cap="${im.id}" value="${esc(im.caption||'')}" placeholder="caption">
            <input type="file" data-file="${im.id}">
            <button data-repl="${im.id}">Replace</button>
            <button data-del="${im.id}" class="btn-outline">Delete</button>
          </div>
        </div>
      `).join('');
      gal.querySelectorAll('button[data-del]').forEach(btn=>{
        btn.addEventListener('click', async ()=>{
          await deleteImage(Number(btn.getAttribute('data-del')));
          renderGallery();
        });
      });
      gal.querySelectorAll('button[data-repl]').forEach(btn=>{
        btn.addEventListener('click', async ()=>{
          const id = Number(btn.getAttribute('data-repl'));
          const file = gal.querySelector(`input[data-file="${id}"]`)?.files?.[0];
          const cap  = gal.querySelector(`input[data-cap="${id}"]`)?.value || '';
          if(!file) return alert('Choose a file first');
          await replaceImage(id, file, cap);
          renderGallery();
        });
      });
    }

    m.querySelector('#btnUpload').addEventListener('click', async ()=>{
      const files = m.querySelector('#upFiles').files;
      const cap = m.querySelector('#cap').value;
      if(!files || !files.length) return;
      await uploadAdImages(ad.id, Array.from(files), cap);
      m.querySelector('#upFiles').value = "";
      m.querySelector('#cap').value = "";
      await renderGallery();
    });

    m.querySelector('#btnSave').addEventListener('click', async ()=>{
      const f = m.querySelector('#editForm');
      const payload = Object.fromEntries(new FormData(f));
      payload.price = Number(payload.price||0);
      payload.rooms = Number(payload.rooms||0);
      payload.area  = payload.area ? Number(payload.area) : null;
      payload.is_active = !!payload.is_active;
      await patchAd(ad.id, payload);
      loadMine();
    });
    m.querySelector('#btnClose').addEventListener('click', ()=>{ m.classList.remove('active'); m.innerHTML=""; });
  }

  loadMine();
}
