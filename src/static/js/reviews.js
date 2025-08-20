import { esc } from "./utils.js";
import { fetchReviews, createReview } from "./api.js";

export function mountReviews(root){
  root.innerHTML = `
    <h3>Reviews</h3>
    <div id="rList"></div>
    <div class="grid grid-3" id="rForm" style="margin-top:8px;">
      <input name="ad" type="number" placeholder="Ad ID">
      <select name="rating"><option value="">Rating 1–5</option><option>1</option><option>2</option><option>3</option><option>4</option><option>5</option></select>
      <input name="text" placeholder="Comment (optional)" style="grid-column:1/-1">
      <button class="btn" id="rSend" style="grid-column:1/-1">Send review</button>
      <div class="muted" id="rMsg" style="grid-column:1/-1"></div>
    </div>
  `;
  const lst = root.querySelector('#rList');
  const frm = root.querySelector('#rForm');
  const msg = root.querySelector('#rMsg');

  async function load(adId){
    const data = await fetchReviews(adId);
    const items = data.results||[];
    if(!items.length){ lst.innerHTML = `<div class="muted">No reviews.</div>`; return; }
    lst.innerHTML = items.map(r=>`
      <div class="card">
        <b>${r.rating}/5</b> — ${esc(r.tenant||'')}</div>
        <div>${esc(r.text||'')}</div>
      </div>
    `).join('');
  }

  frm.querySelector('#rSend').addEventListener('click', async ()=>{
    const fd = new FormData(frm);
    const ad = Number(fd.get('ad'));
    const payload = { ad, rating: Number(fd.get('rating')), text: String(fd.get('text')||'') };
    try{
      await createReview(payload);
      msg.textContent = 'Review added';
      load(ad);
    }catch(e){ msg.textContent = 'Error: ' + e.message; }
  });

  // публичная функция
  return { load };
}
