// static/js/bookings.js
import { qs, esc } from "./utils.js";
import { getAccess } from "./config.js";
import { fetchBookings, cancelBooking, cancelQuote, confirmBooking, rejectBooking } from "./api.js";

export function mountBookings(root) {
  root.innerHTML = `
    <h2>Bookings</h2>
    <div class="row" id="bkToolbar" style="margin-bottom:8px">
      <button class="btn" id="bkReload">Reload</button>
      <div class="muted" id="bkMsg"></div>
    </div>
    <div id="bkList" class="grid grid-1"></div>
  `;

  const box   = qs('#bkList', root);
  const msgEl = qs('#bkMsg', root);
  const setMsg = (t) => msgEl.textContent = t || '';

  const pick = (obj, keys) => { for (const k of keys) { const v = obj?.[k]; if (v!=null && v!=='') return v; } return ''; };

  async function load() {
    if (!getAccess()) {
      box.innerHTML = `<div class="card">Please <b>login</b> on the Auth tab to see your bookings.</div>`;
      setMsg(''); return;
    }
    box.innerHTML = `<div class="muted">Loading…</div>`; setMsg('');
    try {
      const data  = await fetchBookings();
      const items = data?.results ?? data ?? [];
      if (!items.length) { box.innerHTML = `<div class="muted">No bookings yet.</div>`; return; }
      box.innerHTML = items.map(renderCard).join('');
      box.querySelectorAll('[data-act]').forEach(btn=>{
        btn.addEventListener('click', async ()=>{
          const id  = Number(btn.getAttribute('data-id'));
          const act = btn.getAttribute('data-act');
          btn.disabled = true; setMsg('Working…');
          try {
            if (act==='cancel') await cancelBooking(id);
            else if (act==='cancelq') await cancelQuote(id);
            else if (act==='confirm') await confirmBooking(id);
            else if (act==='reject') await rejectBooking(id);
            await load();
          } catch(e){ setMsg(`Error: ${e.message || e}`); btn.disabled = false; }
        });
      });
    } catch (e) {
      box.innerHTML = `<div class="card" style="color:#b00">Error: ${esc(e.message || e)}</div>`;
    }
  }

  function renderCard(b) {
    const adId   = pick(b, ['ad_id']) || b?.ad?.id || '';
    const adTitle= pick(b, ['ad_title']) || b?.ad?.title || '';
    const from   = pick(b, ['from','date_from','start','start_date','check_in','checkin']);
    const to     = pick(b, ['to','date_to','end','end_date','check_out','checkout']);
    const status = String(b?.status ?? '').toLowerCase();

    const tenant = pick(b, ['tenant_email','tenant_name','tenant_username']) ||
                   pick(b?.tenant, ['email','name','username']) || '';
    const owner  = pick(b, ['owner_email','ad_owner_email','owner_name','owner_username']) ||
                   pick(b?.owner, ['email','name','username']) ||
                   pick(b?.ad_owner, ['email','name','username']) || '';

    const actions = [];
    if (b?.can_cancel)        actions.push(btn('Cancel','cancel',b.id));
    if (b?.can_cancel_quote)  actions.push(btn('Cancel quote','cancelq',b.id));
    if (b?.can_confirm)       actions.push(btn('Confirm','confirm',b.id));
    if (b?.can_reject)        actions.push(btn('Reject','reject',b.id));

    return `
      <div class="card">
        <b>#${b.id}</b> · Ad <b>#${esc(String(adId||'—'))}</b> — ${esc(adTitle || '')}
        <div class="muted">
          ${from && to ? `${esc(from)} → ${esc(to)} · ` : ''}${esc(status || 'unknown')}
        </div>
        <div class="muted">tenant: ${esc(tenant || '—')} · owner: ${esc(owner || '—')}</div>
        ${actions.length ? `<div class="row" style="margin-top:6px">${actions.join('')}</div>` : ''}
      </div>`;
  }
  const btn = (label, act, id) => `<button class="btn-outline" data-act="${act}" data-id="${id}">${esc(label)}</button>`;

  qs('#bkReload', root).addEventListener('click', load);
  load();
}
