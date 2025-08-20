// static/js/api.js
import { API, hAuth } from "./config.js";

// ---- helpers
async function handle(r, urlLabel = "") {
  if (r.ok) return r.json();
  const body = await r.text().catch(() => "");
  throw new Error(`${urlLabel}${urlLabel ? " " : ""}${r.status} ${r.statusText}\n${body}`);
}

// ---- Auth
export async function login(email, password){
  const r = await fetch(`${API}/auth/token/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password })
  });
  return handle(r, "AUTH");
}
export async function register(payload){
  const r = await fetch(`${API}/auth/register/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  return handle(r, "REGISTER");
}

// ---- Ads
export async function fetchAds(params){
  const qs = new URLSearchParams();
  for (const [k,v] of Object.entries(params || {})) {
    if (v === undefined || v === null || v === "") continue;
    qs.append(k, v);
  }
  const url = `${API}/ads/?${qs.toString()}`;
  const r = await fetch(url, { headers: hAuth() });
  if (!r.ok) {
    const body = await r.text().catch(() => "");
    throw new Error(`ADS ${r.status} at ${url}\n${body}`);
  }
  return r.json();
}
export async function fetchAd(id){
  const r = await fetch(`${API}/ads/${id}/`, { headers: hAuth() });
  return handle(r, "AD");
}
export async function createAd(payload){
  const r = await fetch(`${API}/ads/`, {
    method: "POST",
    headers: { ...hAuth(), "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  return handle(r, "AD CREATE");
}
export async function patchAd(id, payload){
  const r = await fetch(`${API}/ads/${id}/`, {
    method: "PATCH",
    headers: { ...hAuth(), "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  return handle(r, "AD PATCH");
}

// ---- Images
export async function uploadAdImages(adId, files, caption=""){
  const fd = new FormData();
  for (const f of files) fd.append("images", f);
  if (caption) fd.append("caption", caption);
  const r = await fetch(`${API}/ads/${adId}/images/`, {
    method: "POST",
    headers: { ...hAuth() },
    body: fd
  });
  return handle(r, "IMG UPLOAD");
}
export async function replaceImage(imageId, file, caption=""){
  const fd = new FormData();
  fd.append("image", file);
  if (caption) fd.append("caption", caption);
  const r = await fetch(`${API}/ad-images/${imageId}/replace/`, {
    method: "POST",
    headers: { ...hAuth() },
    body: fd
  });
  return handle(r, "IMG REPLACE");
}
export async function deleteImage(imageId){
  const r = await fetch(`${API}/ad-images/${imageId}/`, {
    method: "DELETE",
    headers: hAuth()
  });
  if (!r.ok) {
    const body = await r.text().catch(()=> "");
    throw new Error(`IMG DELETE ${r.status}\n${body}`);
  }
  return true;
}

// ---- Bookings
export async function fetchBookings(){
  const r = await fetch(`${API}/bookings/`, { headers: hAuth() });
  return handle(r, "BOOKINGS");
}
export async function createBooking(payload){
  const r = await fetch(`${API}/bookings/`, {
    method: "POST",
    headers: { ...hAuth(), "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  return handle(r, "BOOK CREATE");
}
export async function cancelQuote(bookingId){
  const r = await fetch(`${API}/bookings/${bookingId}/cancel-quote/`, { headers: hAuth() });
  return handle(r, "BOOK QUOTE");
}
export async function cancelBooking(bookingId){
  const r = await fetch(`${API}/bookings/${bookingId}/cancel/`, { method: "POST", headers: hAuth() });
  if (!r.ok) {
    const body = await r.text().catch(()=> "");
    throw new Error(`BOOK CANCEL ${r.status}\n${body}`);
  }
  return true;
}
export async function confirmBooking(bookingId){
  const r = await fetch(`${API}/bookings/${bookingId}/confirm/`, { method: "POST", headers: hAuth() });
  if (!r.ok) {
    const body = await r.text().catch(()=> "");
    throw new Error(`BOOK CONFIRM ${r.status}\n${body}`);
  }
  return true;
}
export async function rejectBooking(bookingId){
  const r = await fetch(`${API}/bookings/${bookingId}/reject/`, { method: "POST", headers: hAuth() });
  if (!r.ok) {
    const body = await r.text().catch(()=> "");
    throw new Error(`BOOK REJECT ${r.status}\n${body}`);
  }
  return true;
}

// ---- Reviews
export async function fetchReviews(adId){
  const r = await fetch(`${API}/reviews/?ad=${adId}`, { headers: hAuth() });
  return handle(r, "REVIEWS");
}
export async function createReview(payload){
  const r = await fetch(`${API}/reviews/`, {
    method: "POST",
    headers: { ...hAuth(), "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  return handle(r, "REVIEW CREATE");
}

// ---- Search analytics
export async function topSearches(limit=10){
  const r = await fetch(`${API}/search/top/?limit=${limit}`, { headers: hAuth() });
  return handle(r, "TOP SEARCHES");
}
