export function initMap(containerId='map'){
  const map = L.map(containerId).setView([52.52, 13.405], 11); // Berlin default
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19 }).addTo(map);
  let bboxCb = null;

  function notify(){
    const b = map.getBounds();
    if (bboxCb){
      bboxCb({
        lat_min: b.getSouth(),
        lat_max: b.getNorth(),
        lon_min: b.getWest(),
        lon_max: b.getEast(),
      });
    }
  }
  map.on('moveend', notify);
  return {
    map,
    onBoundsChange(cb){ bboxCb = cb; notify(); },
    setMarker(lat, lon){ L.marker([lat, lon]).addTo(map); },
    fit(lat, lon, z=13){ map.setView([lat, lon], z); }
  };
}
