// static/js/api.js
import { API, hAuth, getAccess, setAccess } from "./config.js";

// --------------------- helpers ---------------------
function buildQS(params = {}) {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === "") continue;
    qs.append(k, v);
  }
  return qs.toString();
}

async function handle(r, label = "", url = "") {
  if (r.ok) {
    // 204 No Content
    if (r.status === 204) return true;
    try { return await r.json(); }
    catch { return true; }
  }
  let body = "";
  try { body = await r.text(); } catch {}
  // автоочистка access, если он протух/невалиден
  if (r.status === 401 && /token_not_valid|expired/i.test(body)) {
    setAccess(null);
  }
  throw new Error(`${label ? label + " " : ""}${r.status} ${r.statusText}${url ? " at " + url : ""}\n${body}`);
}

// --------------------- AUTH ------------------------
export async function login(email, password) {
  const url = `${API}/auth/token/`;
  const r = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  return handle(r, "AUTH", url);
}

export async function register(payload) {
  const url = `${API}/auth/register/`;
  const r = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(r, "REGISTER", url);
}

// --------------------- ADS (PUBLIC) ----------------
export async function fetchAds(params = {}) {
  const qs = buildQS(params);
  const url = `${API}/ads/?${qs}`;
  const r = await fetch(url); // без Authorization
  return handle(r, "ADS", url);
}

export async function fetchAd(id) {
  const url = `${API}/ads/${id}/`;
  const r = await fetch(url); // без Authorization
  return handle(r, "AD", url);
}

// --------------------- ADS (AUTH) ------------------
// использовать для mine=true и любых защищённых операций
export async function fetchAdsAuth(params = {}) {
  const qs = buildQS(params);
  const url = `${API}/ads/?${qs}`;
  const r = await fetch(url, { headers: hAuth() });
  return handle(r, "ADS AUTH", url);
}

export async function createAd(payload) {
  const url = `${API}/ads/`;
  const r = await fetch(url, {
    method: "POST",
    headers: { ...hAuth(), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(r, "AD CREATE", url);
}

export async function patchAd(id, payload) {
  const url = `${API}/ads/${id}/`;
  const r = await fetch(url, {
    method: "PATCH",
    headers: { ...hAuth(), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(r, "AD PATCH", url);
}

// --------------------- IMAGES ----------------------
export async function uploadAdImages(adId, files, caption = "") {
  const url = `${API}/ads/${adId}/images/`;
  const fd = new FormData();
  for (const f of files || []) fd.append("images", f);
  if (caption) fd.append("caption", caption);
  const r = await fetch(url, { method: "POST", headers: { ...hAuth() }, body: fd });
  return handle(r, "IMG UPLOAD", url);
}

export async function replaceImage(imageId, file, caption = "") {
  const url = `${API}/ad-images/${imageId}/replace/`;
  const fd = new FormData();
  fd.append("image", file);
  if (caption) fd.append("caption", caption);
  const r = await fetch(url, { method: "POST", headers: { ...hAuth() }, body: fd });
  return handle(r, "IMG REPLACE", url);
}

export async function deleteImage(imageId) {
  const url = `${API}/ad-images/${imageId}/`;
  const r = await fetch(url, { method: "DELETE", headers: hAuth() });
  return handle(r, "IMG DELETE", url);
}

// --------------------- BOOKINGS (AUTH) -------------
export async function fetchBookings() {
  const url = `${API}/bookings/`;
  const r = await fetch(url, { headers: hAuth() });
  return handle(r, "BOOKINGS", url);
}

export async function createBooking(payload) {
  const url = `${API}/bookings/`;
  const r = await fetch(url, {
    method: "POST",
    headers: { ...hAuth(), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(r, "BOOK CREATE", url);
}

export async function cancelQuote(bookingId) {
  const url = `${API}/bookings/${bookingId}/cancel-quote/`;
  const r = await fetch(url, { headers: hAuth() });
  return handle(r, "BOOK QUOTE", url);
}

export async function cancelBooking(bookingId) {
  const url = `${API}/bookings/${bookingId}/cancel/`;
  const r = await fetch(url, { method: "POST", headers: hAuth() });
  return handle(r, "BOOK CANCEL", url);
}

export async function confirmBooking(bookingId) {
  const url = `${API}/bookings/${bookingId}/confirm/`;
  const r = await fetch(url, { method: "POST", headers: hAuth() });
  return handle(r, "BOOK CONFIRM", url);
}

export async function rejectBooking(bookingId) {
  const url = `${API}/bookings/${bookingId}/reject/`;
  const r = await fetch(url, { method: "POST", headers: hAuth() });
  return handle(r, "BOOK REJECT", url);
}

// --------------------- REVIEWS (обычно AUTH) -------
export async function fetchReviews(adId) {
  const url = `${API}/reviews/?ad=${encodeURIComponent(adId)}`;
  const r = await fetch(url, { headers: hAuth() });
  return handle(r, "REVIEWS", url);
}

export async function createReview(payload) {
  const url = `${API}/reviews/`;
  const r = await fetch(url, {
    method: "POST",
    headers: { ...hAuth(), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(r, "REVIEW CREATE", url);
}

// --------------------- SEARCH ANALYTICS (PUBLIC) ---
export async function topSearches(limit = 10) {
  const url = `${API}/search/top/?limit=${encodeURIComponent(limit)}`;
  const r = await fetch(url); // без Authorization
  return handle(r, "TOP SEARCHES", url);
}
