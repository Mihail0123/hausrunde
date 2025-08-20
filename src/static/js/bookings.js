import { esc, fmtDMY } from "./utils.js";
import { fetchBookings, cancelQuote, cancelBooking, confirmBooking, rejectBooking } from "./api.js";

export function mountBookings(root){
  root.innerHTML = `<h2>Bookings</h2><div id="bList"></div>`;
  const box = root.querySelector('#bList');

  async function load(){
    const data = await fetchBookings();
    const items = data.results||[];
    if(!items.length){ box.innerHTML = `<div class="muted">No bookings.</div>`; return; }
    box.innerHTML = items.map(b=>`
      <div class="card" data-id="${b.id}">
        <b>#${b.id}</b> — ${esc(b.ad_title||b.ad?.title||'Ad')} — ${fmtDMY(b.date_from)} → ${fmtDMY(b.date_to)}
        <div class="muted">status: ${b.status}</div>
        <div class="row">
          ${b.status==='PENDING'?'<button class="btn" data-act="confirm">Confirm</button><button class="btn-outline" data-act="reject">Reject</button>':''}
          ${(b.status==='PENDING' || b.status==='CONFIRMED')?'<button class="btn-outline" data-act="quote">Cancel quote</button><button class="btn-outline" data-act="cancel">Cancel</button>':''}
        </div>
        <div class="muted" data-msg></div>
      </div>
    `).join('');

    box.querySelectorAll('.card').forEach(card=>{
      const id = Number(card.getAttribute('data-id'));
      card.querySelectorAll('button[data-act]').forEach(btn=>{
        const act = btn.getAttribute('data-act');
        btn.addEventListener('click', async ()=>{
          const msg = card.querySelector('[data-msg]');
          try{
            if(act==='quote'){ const q=await cancelQuote(id); msg.textContent = q.message; }
            if(act==='cancel'){ await cancelBooking(id); msg.textContent = 'Cancelled'; load(); }
            if(act==='confirm'){ await confirmBooking(id); msg.textContent = 'Confirmed'; load(); }
            if(act==='reject'){ await rejectBooking(id); msg.textContent = 'Rejected'; load(); }
          }catch(e){ msg.textContent = 'Error: ' + e.message; }
        });
      });
    });
  }

  load();
}
