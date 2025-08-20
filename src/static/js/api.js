import { API, hAuth } from "./config.js";

// --- Auth (JWT) ---
export async function login(email, password){
  const r = await fetch(`${API}/auth/token/`, {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ email, password })
  });
  if(!r.ok) throw new Error('Invalid credentials');
  return r.json(); // {access, refresh}
}
export async function register(payload){
  const r = await fetch(`${API}/auth/register/`, {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify(payload)
  });
  if(!r.ok) throw new Error(await r.text());
  return r.json();
}

// --- Ads ---
export async function fetchAds(params){
  const qs = new URLSearchParams(params);
  const url = `${API}/ads/?${qs}`;
  const r = await fetch(url, { headers: hAuth() });
  if (!r.ok) {
    const body = await r.text();
    throw new Error(`ADS ${r.status} at ${url}\n${body}`);
  }
  return r.json();
}
}
export async function fetchAd(id){
  const r = await fetch(`${API}/ads/${id}/`, { headers: hAuth() });
  if(!r.ok) throw new Error(`AD ${r.status}`);
  return r.json();
}
export async function createAd(payload){
  const r = await fetch(`${API}/ads/`, { method:'POST', headers:{...hAuth(), 'Content-Type':'application/json'}, body: JSON.stringify(payload) });
  if(!r.ok) throw new Error(await r.text());
  return r.json();
}
export async function patchAd(id, payload){
  const r = await fetch(`${API}/ads/${id}/`, { method:'PATCH', headers:{...hAuth(), 'Content-Type':'application/json'}, body: JSON.stringify(payload) });
  if(!r.ok) throw new Error(await r.text());
  return r.json();
}
export async function adAvailability(adId, status){ // status: PENDING|CONFIRMED optional
  const r = await fetch(`${API}/ads/${adId}/availability?${status ? 'status='+status : ''}`, { headers: hAuth() });
  if(!r.ok) throw new Error(await r.text());
  return r.json(); // [{start:..., end:...}, ...]
}

// Images
export async function uploadAdImages(adId, files, caption=""){
  const fd = new FormData();
  for(const f of files) fd.append('images', f);
  if(caption) fd.append('caption', caption);
  const r = await fetch(`${API}/ads/${adId}/images/`, { method:'POST', headers: { ...hAuth() }, body: fd });
  if(!r.ok) throw new Error(await r.text());
  return r.json();
}
export async function replaceImage(imageId, file, caption=""){
  const fd = new FormData();
  fd.append('image', file);
  if(caption) fd.append('caption', caption);
  const r = await fetch(`${API}/ad-images/${imageId}/replace/`, { method:'POST', headers:{...hAuth()}, body: fd });
  if(!r.ok) throw new Error(await r.text());
  return r.json();
}
export async function deleteImage(imageId){
  const r = await fetch(`${API}/ad-images/${imageId}/`, { method:'DELETE', headers: hAuth() });
  if(!r.ok) throw new Error(await r.text());
  return true;
}

// --- Bookings ---
export async function fetchBookings(){
  const r = await fetch(`${API}/bookings/`, { headers: hAuth() });
  if(!r.ok) throw new Error(await r.text());
  return r.json();
}
export async function createBooking(payload){
  const r = await fetch(`${API}/bookings/`, { method:'POST', headers:{...hAuth(),'Content-Type':'application/json'}, body: JSON.stringify(payload) });
  if(!r.ok) throw new Error(await r.text());
  return r.json();
}
export async function cancelQuote(bookingId){
  const r = await fetch(`${API}/bookings/${bookingId}/cancel-quote/`, { headers: hAuth() });
  if(!r.ok) throw new Error(await r.text());
  return r.json(); // {days_until, fee_pct, fee_amount, total_cost, message}
}
export async function cancelBooking(bookingId){
  const r = await fetch(`${API}/bookings/${bookingId}/cancel/`, { method:'POST', headers: hAuth() });
  if(!r.ok) throw new Error(await r.text());
  return true;
}
export async function confirmBooking(bookingId){
  const r = await fetch(`${API}/bookings/${bookingId}/confirm/`, { method:'POST', headers: hAuth() });
  if(!r.ok) throw new Error(await r.text());
  return true;
}
export async function rejectBooking(bookingId){
  const r = await fetch(`${API}/bookings/${bookingId}/reject/`, { method:'POST', headers: hAuth() });
  if(!r.ok) throw new Error(await r.text());
  return true;
}

// --- Reviews ---
export async function fetchReviews(adId){
  const r = await fetch(`${API}/reviews/?ad=${adId}`, { headers: hAuth() });
  if(!r.ok) throw new Error(await r.text());
  return r.json(); // paginated
}
export async function createReview(payload){
  const r = await fetch(`${API}/reviews/`, { method:'POST', headers:{...hAuth(),'Content-Type':'application/json'}, body: JSON.stringify(payload) });
  if(!r.ok) throw new Error(await r.text());
  return r.json();
}

// --- Search analytics ---
export async function topSearches(limit=10){
  const r = await fetch(`${API}/search/top/?limit=${limit}`, { headers: hAuth() }); // публично доступно
  if(!r.ok) throw new Error(await r.text());
  return r.json(); // [{q,count},...]
}
