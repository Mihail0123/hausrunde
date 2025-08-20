import { buildBBoxParams } from './api.js';
import { fmt } from './ui.js';
import { initSearch } from './search.js';


const boundsLabel = document.getElementById('boundsLabel');
const listEl = document.getElementById('list');
const markers = L.layerGroup();


function getViewportParams() {
const b = window.MAP.getBounds();
boundsLabel.textContent = `lat:[${fmt(b.getSouth())}..${fmt(b.getNorth())}], lon:[${fmt(b.getWest())}..${fmt(b.getEast())}]`;
return { ...buildBBoxParams(b) };
}


function drawMarkers(items) {
markers.clearLayers();
items.forEach(ad => {
const { latitude, longitude, title, location, price } = ad;
if (latitude==null || longitude==null) return;
const m = L.marker([parseFloat(latitude), parseFloat(longitude)]).addTo(markers);
m.bindPopup(`<strong>${title}</strong><br>${location||''} · €${price??'—'}`);
});
}


function hookListObserver() {
const observer = new MutationObserver(() => {
// redraw markers when list re-renders
const data = Array.from(listEl.querySelectorAll('.ad')).map(card => {
// not ideal: in real life we would keep last items copy in state
return card; // placeholder — markers are drawn from map events in this scaffold
});
});
observer.observe(listEl, { childList: true });
}


(function bootstrap() {
window.MAP = L.map('map', { scrollWheelZoom: true }).setView([52.52, 13.405], 12);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19, attribution: '&copy; OpenStreetMap' }).addTo(window.MAP);
markers.addTo(window.MAP);


const search = initSearch(window.MAP, getViewportParams, (latlng) => {
window.MAP.flyTo(latlng, Math.max(window.MAP.getZoom(), 14), { duration: 0.5 });
});


let debounceId = null;
window.MAP.on('moveend', () => {
clearTimeout(debounceId);
debounceId = setTimeout(() => search.refreshFromMap(), 200);
});


search.runInitial();
hookListObserver();
})();