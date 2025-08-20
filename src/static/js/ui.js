export function escapeHtml(s) { const d = document.createElement('div'); d.innerText = String(s ?? ''); return d.innerHTML; }
export const fmt = (n, d=2) => Number(n).toFixed(d);

export function renderAds(listEl, items, onFocus) {
  listEl.innerHTML = '';
  items.forEach(ad => {
    const { id, title, price, rooms, location, latitude, longitude, average_rating, reviews_count } = ad;
    const card = document.createElement('div');
    card.className = 'ad';
    card.innerHTML = `
      <h4>${escapeHtml(title)}</h4>
      <div class="muted">${escapeHtml(location || '')}</div>
      <div style="display:flex; gap:8px; margin:8px 0;">
        <span class="pill">€${price ?? '—'}</span>
        ${rooms ? `<span class="pill">${rooms} rooms</span>` : ''}
        ${average_rating ? `<span class="pill">⭐ ${Number(average_rating).toFixed(1)} ${reviews_count?`(${reviews_count})`:''}</span>`:''}
      </div>
      <div style="display:flex; gap:8px;">
        <a class="btn" href="/ads/${id}/">Open</a>
        ${latitude!=null && longitude!=null ? `<button class="btn ghost" data-focus="${id}">Focus</button>`:''}
      </div>
    `;
    if (latitude!=null && longitude!=null) {
      card.querySelector('[data-focus]')?.addEventListener('click', () => onFocus([parseFloat(latitude), parseFloat(longitude)]));
    }
    listEl.appendChild(card);
  });
}

export function renderEmpty(listEl, message, onAction) {
  listEl.innerHTML = '';
  const wrap = document.createElement('div');
  wrap.className = 'ad';
  wrap.innerHTML = `<div class="muted" style="margin-bottom:8px;">${escapeHtml(message)}</div>`;
  if (onAction) {
    const btn = document.createElement('button');
    btn.className = 'btn ghost';
    btn.textContent = 'Search everywhere';
    btn.addEventListener('click', onAction);
    wrap.appendChild(btn);
  }
  listEl.appendChild(wrap);
}
