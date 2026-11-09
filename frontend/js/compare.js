/**
 * compare.js – price comparison UI with Cheapest/Fastest/Best Value badges.
 * ONLY shown in normal planning mode, never during replan.
 */
import { api } from './api.js';

export async function renderCompareView(containerEl, origin, destination, date) {
  containerEl.innerHTML = `<div class="flex items-center gap-2"><span class="spinner"></span><span class="text-muted text-sm">Comparing prices…</span></div>`;

  try {
    const data = await api.comparePrices(origin, destination, date);
    containerEl.innerHTML = '';

    const header = document.createElement('div');
    header.className = 'flex items-center gap-2 mb-2';
    header.innerHTML = `<h2>Price comparison</h2><span class="pill">${origin} → ${destination}</span>`;
    containerEl.appendChild(header);

    if (data.granite_reason) {
      const reason = document.createElement('div');
      reason.className = 'granite-reason mb-2';
      reason.innerHTML = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/></svg> ${escHtml(data.granite_reason)}`;
      containerEl.appendChild(reason);
    }

    // Transport tabs
    const tabs = document.createElement('div');
    tabs.className = 'tabs';
    tabs.innerHTML = `
      <button class="tab active" data-tab="trains">Trains (${data.trains?.length || 0})</button>
      <button class="tab" data-tab="flights">Flights (${data.flights?.length || 0})</button>
      <button class="tab" data-tab="buses">Buses (${data.buses?.length || 0})</button>
      <button class="tab" data-tab="stays">Stays (${data.stays?.length || 0})</button>`;
    containerEl.appendChild(tabs);

    const content = document.createElement('div');
    content.id = 'compare-content';
    containerEl.appendChild(content);

    function showTab(name) {
      tabs.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.dataset.tab === name));
      content.innerHTML = '';
      const items = data[name] || [];
      if (!items.length) {
        content.innerHTML = '<p class="text-muted text-sm mt-2">No options found.</p>';
        return;
      }
      for (const item of items) {
        content.appendChild(renderTransportCard(item, name));
      }
    }

    tabs.addEventListener('click', (e) => {
      const tab = e.target.closest('[data-tab]');
      if (tab) showTab(tab.dataset.tab);
    });

    showTab('trains');

    // Stays section
    if (data.stays?.length) {
      const staysHeader = document.createElement('h3');
      staysHeader.className = 'mt-3 mb-1';
      staysHeader.textContent = 'Stays';
      containerEl.appendChild(staysHeader);

      const staysGrid = document.createElement('div');
      staysGrid.className = 'grid-3';
      for (const s of data.stays) staysGrid.appendChild(renderStayCard(s));
      containerEl.appendChild(staysGrid);
    }
  } catch (err) {
    containerEl.innerHTML = `<p class="text-muted text-sm">Could not load comparison: ${err.message}</p>`;
  }
}

function renderTransportCard(item, type) {
  const card = document.createElement('div');
  card.className = 'transport-card mt-1';
  const badges = (item.badges || []).map(b => `<span class="badge badge-${b.toLowerCase().replace(' ', '')}">${b}</span>`).join('');
  const name = item.train_name || item.airline || item.operator || '';
  const id = item.train_number || item.flight_number || item.bus_id || '';
  const price = item.fare_inr ?? (item.fare_inr ? item.fare_inr : Object.values(item.fare_inr || {})[0] || 0);
  const fareDisplay = typeof item.fare_inr === 'object'
    ? 'from ₹' + Math.min(...Object.values(item.fare_inr)).toLocaleString('en-IN')
    : '₹' + (item.fare_inr || 0).toLocaleString('en-IN');

  card.innerHTML = `
    <div class="transport-info">
      <div class="transport-route fw-medium">${escHtml(name)} <span class="text-muted text-xs">(${escHtml(id)})</span></div>
      <div class="transport-detail">${escHtml(item.departure || '')} → ${escHtml(item.arrival || '')} · ${item.duration_minutes ? Math.floor(item.duration_minutes / 60) + 'h ' + (item.duration_minutes % 60) + 'm' : ''}</div>
      <div class="transport-badges">${badges}${item.source === 'mock' ? '<span class="sample-notice" style="font-size:0.7rem">Sample data</span>' : ''}</div>
    </div>
    <div class="transport-price">${fareDisplay}</div>`;
  return card;
}

function renderStayCard(s) {
  const card = document.createElement('div');
  card.className = 'stay-card';
  card.innerHTML = `
    ${s.image ? `<img class="stay-img" src="${escHtml(s.image)}" alt="${escHtml(s.name)}" loading="lazy">` : '<div class="stay-img" style="background:var(--surface-2)"></div>'}
    <div class="stay-info">
      <div class="stay-name">${escHtml(s.name)}</div>
      <div class="stay-price">₹${s.price_per_night.toLocaleString('en-IN')}/night</div>
      ${s.rating ? `<div class="stay-rating">★ ${s.rating}</div>` : ''}
      ${s.best_value ? '<span class="badge badge-bestvalue">Best Value</span>' : ''}
      ${s.source === 'mock' ? '<div><span class="sample-notice" style="font-size:0.7rem;margin-top:0.25rem">Sample data</span></div>' : ''}
    </div>`;
  return card;
}

function escHtml(str) {
  if (!str) return '';
  return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
