// static/js/app.js

// --- маленькие утилиты (без внешних зависимостей)
const $ = (sel, el = document) => el.querySelector(sel);
const esc = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (m) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[m]));

// локальный "error boundary" — не роняет всю страницу
function renderSectionError(host, err) {
  host.innerHTML = `
    <div class="card" style="border-color:#f4c2c2;background:#fff">
      <b style="color:#b00">Error</b>
      <div class="muted" style="white-space:pre-wrap">${esc(err?.message || err)}</div>
    </div>`;
  console.error(err);
}

(async () => {
  let stage = "bootstrap";
  const root = document.getElementById("app") || document.body;

  try {
    stage = "config.js"; const cfg = await import("./config.js");

    // --- каркас приложения ---------------------------------------------------
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

        <section class="section active" id="sec-ads"><div class="muted">Loading…</div></section>
        <section class="section" id="sec-my"></section>
        <section class="section" id="sec-book"></section>
        <section class="section" id="sec-auth"></section>
        <section class="section" id="sec-analytics"></section>
      </div>
    `;

    // переключение табов + ленивые монтирования
    const mounted = new Set();

    function activate(name) {
      document.querySelectorAll(".tab").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
      document.querySelectorAll(".section").forEach((s) => s.classList.toggle("active", s.id === `sec-${name}`));
      lazyMount(name);
    }

    document.querySelectorAll(".tab").forEach((btn) => {
      btn.addEventListener("click", () => activate(btn.dataset.tab));
    });

    async function lazyMount(name) {
      if (mounted.has(name)) return;
      mounted.add(name);

      try {
        if (name === "ads") {
          const [{ mountAds }, mapMod] = await Promise.all([
            import("./ads.js"),
            import("./map.js"),           // ожидается initMap('map')
          ]);

          const host = $("#sec-ads");
          host.innerHTML = "";

          try {
            // передаем в ads.js колбэк регистрации bbox и саму карту
            mountAds(host, {
              onOpenAd: null, // можно навесить модалку, если понадобится
              onNeedBBox: (registerBBox, exposeMap) => {
                const ctl = mapMod.initMap("map");         // должен вернуть контрол с .map или сам L.Map
                if (typeof exposeMap === "function") exposeMap(ctl);
                ctl.onBoundsChange((b) => registerBBox(b)); // отдаём bbox при движении карты
              },
            });
          } catch (e) {
            renderSectionError(host, e);
          }
        }

        if (name === "my") {
          const [{ mountMyAds }] = await Promise.all([import("./myads.js")]);
          const host = $("#sec-my");
          try {
            mountMyAds(host);
          } catch (e) {
            renderSectionError(host, e);
          }
        }

        if (name === "book") {
          const [{ mountBookings }] = await Promise.all([import("./bookings.js")]);
          const host = $("#sec-book");
          try {
            mountBookings(host);
          } catch (e) {
            renderSectionError(host, e);
          }
        }

        if (name === "auth") {
          const [api] = await Promise.all([import("./api.js")]);
          const host = $("#sec-auth");

          host.innerHTML = `
            <h2>Auth</h2>
            <div class="grid grid-2">
              <div class="card">
                <h3>Login</h3>
                <input id="email" placeholder="Email">
                <input id="password" type="password" placeholder="Password">
                <div class="row">
                  <button class="btn" id="btnLogin">Login</button>
                  <button class="btn-outline" id="btnLogout">Logout</button>
                </div>
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

          $("#btnLogin").addEventListener("click", async () => {
            const email = $("#email").value.trim();
            const pass = $("#password").value;
            $("#authMsg").textContent = "Logging in…";
            try {
              const tok = await api.login(email, pass);
              cfg.setAccess(tok.access);
              $("#authMsg").textContent = "Logged in";
            } catch (e) {
              $("#authMsg").textContent = `Error: ${e.message || e}`;
            }
          });

          $("#btnLogout").addEventListener("click", () => {
            cfg.setAccess(null);
            $("#authMsg").textContent = "Logged out";
          });

          $("#btnReg").addEventListener("click", async () => {
            const email = $("#r_email").value.trim();
            const pass = $("#r_password").value;
            $("#regMsg").textContent = "Registering…";
            try {
              await api.register({ email, password: pass });
              $("#regMsg").textContent = "Registered. Now login.";
            } catch (e) {
              $("#regMsg").textContent = `Error: ${e.message || e}`;
            }
          });

          // текущее состояние
          $("#authMsg").textContent = cfg.getAccess() ? "Token present" : "Not logged in";
        }

        if (name === "analytics") {
          const [api] = await Promise.all([import("./api.js")]);
          const host = $("#sec-analytics");

          host.innerHTML = `<h2>Search analytics</h2><div id="topBox" class="row"></div>`;
          const topBox = $("#topBox");
          topBox.textContent = "Loading…";

          try {
            const items = await api.topSearches(15);
            topBox.innerHTML =
              `<span class="muted">Top searches:</span>` +
              items
                .map(
                  (i) =>
                    `<span class="tab" data-q="${esc(i.q)}">${esc(i.q || "(empty)")} · ${i.count}</span>`
                )
                .join("");

            topBox.querySelectorAll("[data-q]").forEach((ch) => {
              ch.addEventListener("click", () => {
                const q = ch.getAttribute("data-q");
                activate("ads");
                const field = document.querySelector('#sec-ads input[name="q"]');
                if (field) field.value = q === "(empty)" ? "" : q;
                document.querySelector("#sec-ads #adsSearch")?.click();
              });
            });
          } catch (e) {
            renderSectionError(host, e);
          }
        }
      } catch (err) {
        // если сломалось внутри ленивого модуля — выводим ошибку в секции
        const host = document.getElementById(`sec-${name}`) || root;
        renderSectionError(host, err);
      }
    }

    // по умолчанию грузим только Ads
    await lazyMount("ads");
  } catch (err) {
    // если упало раньше разметки — рисуем общий crash box
    root.innerHTML = `
      <div style="max-width:960px;margin:40px auto;padding:16px;border:1px solid #eee;border-radius:12px;background:#fff;font-family:system-ui">
        <h2 style="margin:0 0 8px">Frontend crashed</h2>
        <pre style="white-space:pre-wrap">${esc(err?.message || err)}</pre>
      </div>`;
    console.error(`[${stage}]`, err);
  }
})();

