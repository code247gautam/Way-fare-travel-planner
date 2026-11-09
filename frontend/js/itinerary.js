/**
 * itinerary.js – renders the day-by-day itinerary with transport and stays.
 */
import { api } from './api.js';

export function renderItinerary(itinerary, containerEl) {
  if (!itinerary || !containerEl) return;
  containerEl.innerHTML = '';

  // Header
  const header = document.createElement('div');
  header.className = 'card mb-2';
  header.innerHTML = `
    <div class="flex items-center gap-2 mb-1">
      <h2>${escHtml(itinerary.title)}</h2>
      ${itinerary.source === 'mock' ? '<span class="sample-notice"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>Sample data</span>' : '<span class="badge badge-live">Live</span>'}
    </div>
    <p class="text-muted text-sm">${escHtml(itinerary.granite_summary || '')}</p>
    ${itinerary.total_budget_inr ? `<p class="text-sm mt-1"><strong>Estimated budget:</strong> ₹${itinerary.total_budget_inr.toLocaleString('en-IN')}</p>` : ''}
  `;
  containerEl.appendChild(header);

  // Days
  for (const day of itinerary.days) {
    const dayEl = document.createElement('div');
    dayEl.className = 'day-card';
    dayEl.innerHTML = `
      <div class="day-label">Day ${day.day_number} · ${formatDate(day.date)}</div>
      <div class="fw-medium mb-1">${escHtml(day.city)}</div>
      ${day.weather_summary ? `<div class="weather-widget text-xs mb-1"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>${escHtml(day.weather_summary)}</div>` : ''}
      ${renderTransport(day.transport)}
      ${renderActivities(day.activities)}
      ${renderStay(day.stay)}
    `;
    containerEl.appendChild(dayEl);
  }

  // Action row
  const actions = document.createElement('div');
  actions.className = 'flex gap-2 mt-2';
  actions.innerHTML = `
    <button class="btn-primary" id="btn-share-trip">Share trip</button>
    <button class="btn-secondary" id="btn-export-trip">Export</button>
    <button class="btn-secondary" id="btn-simulate-disruption">Simulate disruption</button>
  `;
  containerEl.appendChild(actions);
}

function renderTransport(t) {
  if (!t) return '';
  const icon = modeIcon(t.mode);
  const badges = (t.badges || []).map(b => `<span class="badge badge-${b.toLowerCase().replace(' ', '')}">${b}</span>`).join('');
  return `
    <div class="transport-card mt-1">
      <div class="transport-icon">${icon}</div>
      <div class="transport-info">
        <div class="transport-route">${escHtml(t.origin)} → ${escHtml(t.destination)}</div>
        <div class="transport-detail">${escHtml(t.provider_name)} · ${escHtml(t.service_id)} · ${escHtml(t.departure)} – ${escHtml(t.arrival)}</div>
        <div class="transport-badges">${badges}${t.source === 'mock' ? '<span class="sample-notice" style="font-size:0.7rem">Sample data</span>' : ''}</div>
      </div>
      <div class="transport-price">₹${(t.price_inr || 0).toLocaleString('en-IN')}</div>
    </div>`;
}

function renderStay(s) {
  if (!s) return '';
  return `
    <div class="stay-card mt-1" style="display:flex;gap:0.75rem;padding:0.75rem;border-radius:var(--radius-sm);border:1px solid var(--border);">
      ${s.image ? `<img src="${s.image}" alt="${escHtml(s.name)}" style="width:72px;height:72px;border-radius:var(--radius-sm);object-fit:cover;flex-shrink:0;" loading="lazy">` : ''}
      <div>
        <div class="fw-medium text-sm">${escHtml(s.name)}</div>
        <div class="text-muted text-xs">${escHtml(s.city)}</div>
        <div class="text-sm mt-1" style="color:var(--accent)">₹${s.price_per_night.toLocaleString('en-IN')}/night${s.rating ? ` · ★ ${s.rating}` : ''}</div>
        ${s.source === 'mock' ? '<span class="sample-notice" style="font-size:0.7rem;margin-top:0.25rem">Sample data</span>' : ''}
      </div>
    </div>`;
}

function renderActivities(activities) {
  if (!activities?.length) return '';
  return activities.map(a => `
    <div class="flex gap-2 mt-1 text-sm">
      <span class="text-muted" style="min-width:48px;flex-shrink:0">${escHtml(a.time)}</span>
      <span>
        <strong>${escHtml(a.title)}</strong>
        ${a.description ? `<span class="text-muted"> – ${escHtml(a.description)}</span>` : ''}
        ${a.cost_inr ? `<span class="text-muted text-xs"> · ₹${a.cost_inr.toLocaleString('en-IN')}</span>` : ''}
      </span>
    </div>`).join('');
}

function modeIcon(mode) {
  const icons = {
    train: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="4" y="3" width="16" height="16" rx="2"/><path d="M4 11h16"/><path d="M9 3v8"/><path d="M15 3v8"/><path d="M7 19l-2 2"/><path d="M17 19l2 2"/></svg>',
    flight: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M17.8 19.2 16 11l3.5-3.5C21 6 21 4 19.5 2.5 18 1 16 1 14.5 2.5L11 6 2.8 4.2c-.5-.1-.9.1-1.1.5l-.3.5c-.2.5-.1 1 .3 1.3L9 12l-2 3H4l-1 1 3 2 2 3 1-1v-3l3-2 5.5 6.3c.3.4.8.5 1.3.3l.5-.2c.4-.3.6-.7.5-1.2z"/></svg>',
    bus: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M8 6v6"/><path d="M15 6v6"/><path d="M2 12h19.6"/><path d="M18 18h3s.5-1.7.8-4.8A44.8 44.8 0 0 0 22 5c0-1.7-.8-2-2-2H4c-2 0-2 .3-2 2 0 0 .3 6 .2 8.2-.2 3.2.8 4.8.8 4.8h3"/><circle cx="7" cy="18" r="2"/><circle cx="17" cy="18" r="2"/></svg>',
    cab: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M19 17H5a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v6a2 2 0 0 1-2 2z"/><path d="M7 17v2"/><path d="M17 17v2"/><path d="M9 9h6"/></svg>',
  };
  return icons[mode] || icons.cab;
}

function formatDate(d) {
  if (!d) return '';
  try { return new Date(d).toLocaleDateString('en-IN', { weekday: 'short', day: 'numeric', month: 'short' }); }
  catch { return d; }
}

function escHtml(str) {
  if (!str) return '';
  return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
