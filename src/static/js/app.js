const root = document.getElementById('app') || document.body;
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));

// рендер ошибки вместо белого экрана
function showFatal(err) {
  const msg = err?.stack || err?.message || String(err);
  root.innerHTML = `
    <div style="max-width:960px;margin:40px auto;padding:16px;border:1px solid #eee;border-radius:12px;background:#fff;font-family:system-ui">
      <h2 style="margin:0 0 8px">Frontend crashed</h2>
      <pre style="white-space:pre-wrap">${esc(msg)}</pre>
    </div>`;
  console.error(err);
}

// Вся логика — внутри IIFE с try/catch, чтобы поймать даже ошибки импортов
(async () => {
  try {
    // динамические импорты (если любой модуль упадёт — попадём в catch)
    const { setAccess, getAccess } = await import('./config.js');
    const { qs } = await import('./utils.js');
    const api      = await import('./api.js');
    const mapMod   = await import('./map.js');
    const adsMod   = await import('./ads.js');
    const myadsMod = await import('./myads.js');
    const bookMod  = await import('./bookings.js');
    const revMod   = await import('./reviews.js');

    // каркас UI
    root.innerHTML = `
      <div class="container">
        <h1>Hausrunde</h1>
        <div class="tabs" id="tabs">
          <button class="tab active" data-tab="ads">Ads</button>
          <button class="tab" data-tab="my">My Ads</button>
          <button class="tab" data-tab="book">Bookings</button>
          <button class="tab" data-tab="auth">Auth</button>
          <button class="tab" data-tab="analytics">Analytics</button>
        </div>

        <section class="section active" id="sec-ads"></section>
        <section class="section" id="sec-my"></section>
        <section class="section" id="sec-book"></section>
        <section class="section" id="sec-auth"></section>
        <section class="section" id="sec-analytics"></section>
      </div>
    `;

    // табы
    function activate(name){
      document.querySelectorAll('.tab').forEach(b=> b.classList.toggle('active', b.dataset.tab===name));
      document.querySelectorAll('.section').forEach(s=> s.classList.toggle('active', s.id===`sec-${name}`));
    }
    document.querySelectorAll('.tab').forEach(btn=>{
      btn.addEventListener('click', ()=> activate(btn.dataset.tab));
    });

    // === Ads (карта + bbox) ===
    const secAds = qs('#sec-ads');
    adsMod.mountAds(secAds, {
      onOpenAd: (ad)=> { activate('analytics'); revCtl.load(ad.id); },
      onNeedBBox: (registerBBox) => {
        // создаём карту только после того, как секция вставит <div id="map">
        const mapCtl = mapMod.initMap('map');
        mapCtl.onBoundsChange(b => registerBBox(b));
      }
    });

    // === My Ads ===
    myadsMod.mountMyAds(qs('#sec-my'));

    // === Bookings ===
    bookMod.mountBookings(qs('#sec-book'));

    // === Auth ===
    qs('#sec-auth').innerHTML = `
      <h2>Auth</h2>
      <div class="grid grid-2">
        <div class="card">
          <h3>Login</h3>
          <input id="email" placeholder="Email">
          <input id="password" type="password" placeholder="Password">
          <button class="btn" id="btnLogin">Login</button>
          <div class="muted" id="authMsg"></div>
        </div>
        <div class="card">
          <h3>Register</h3>
          <input id="r_email" placeholder="Email">
          <input id="r_password" type="password" placeholder="Password">
          <button class="btn" id="btnReg">Register</button>
          <div class="muted" id="regMsg"></div>
        </div>
      </div>
    `;
    qs('#btnLogin').addEventListener('click', async ()=>{
      try {
        const tok = await api.login(qs('#email').value.trim(), qs('#password').value);
        setAccess(tok.access);
        qs('#authMsg').textContent = 'Logged in';
      } catch(e){ qs('#authMsg').textContent = 'Error: ' + e.message; }
    });
    qs('#btnReg').addEventListener('click', async ()=>{
      try {
        await api.register({ email: qs('#r_email').value.trim(), password: qs('#r_password').value });
        qs('#regMsg').textContent = 'Registered. Now login.';
      } catch(e){ qs('#regMsg').textContent = 'Error: ' + e.message; }
    });

    // === Analytics (Top searches) ===
    qs('#sec-analytics').innerHTML = `<h2>Search analytics</h2><div id="topBox" class="row"></div>`;
const topBox = qs('#topBox');
async function loadTop(){
  try{
    const items = await api.topSearches(15);
    topBox.innerHTML = `<span class="muted">Top searches:</span>` + items.map(i=>`<span class="tab" data-q="${esc(i.q)}">${esc(i.q||'(empty)')} · ${i.count}</span>`).join('');
    topBox.querySelectorAll('[data-q]').forEach(ch=>{
      ch.addEventListener('click', ()=>{
        activate('ads');
        const field = document.querySelector('#sec-ads input[name="q"]');
        if (field) field.value = ch.getAttribute('data-q')==='(empty)'?'':ch.getAttribute('data-q');
        document.querySelector('#sec-ads #adsSearch')?.click();
      });
    });
  }catch(e){ topBox.textContent = 'Error: ' + e.message; }
}
await loadTop();
 } catch (err) {
    showFatal(err);
  }
})();
