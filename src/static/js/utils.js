export const qs  = (sel, root=document)=> root.querySelector(sel);
export const qsa = (sel, root=document)=> Array.from(root.querySelectorAll(sel));
export const enc = (obj)=> new URLSearchParams(obj).toString();
export const esc = (s)=> String(s||'').replace(/[&<>"']/g, m=>({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[m]));
export function fmtDMY(s){ if(!s) return ''; const d=new Date(s); if(isNaN(d)) return s; return `${String(d.getDate()).padStart(2,'0')}.${String(d.getMonth()+1).padStart(2,'0')}.${d.getFullYear()}`; }
export const truthy = (v)=> ['1','true','yes','on'].includes(String(v||'').toLowerCase());
