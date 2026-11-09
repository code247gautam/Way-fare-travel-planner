/**
 * replan.js – Smart Replan modal: Before vs After, Granite explanation, one-tap approve.
 * NO deals or promotions shown.
 */
import { api } from './api.js';

export class ReplanModal {
  constructor() {
    this._build();
  }

  _build() {
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.id = 'replan-modal';
    overlay.innerHTML = `
      <div class="modal" style="max-width:640px">
        <div class="flex items-center gap-2 mb-2">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--warn)" stroke-width="2"><path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
          <h2>Travel disruption detected</h2>
        </div>
        <div id="replan-loading" class="flex items-center gap-2"><span class="spinner"></span><span class="text-muted text-sm">Finding alternatives…</span></div>
        <div id="replan-content" class="hidden">
          <div id="replan-disruption" class="disruption-banner mb-2">
            <div class="disruption-icon"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg></div>
            <div class="disruption-text" id="replan-disruption-text"></div>
          </div>
          <div class="granite-reason mb-2" id="replan-explanation"></div>
          <div class="replan-before-after">
            <div>
              <div class="replan-label before">Before</div>
              <div id="replan-before"></div>
            </div>
            <div>
              <div class="replan-label after">After</div>
              <div id="replan-after"></div>
            </div>
          </div>
          <div class="flex gap-2 mt-2">
            <button class="btn-primary" id="replan-approve">✓ Approve replan</button>
            <button class="btn-secondary" id="replan-dismiss">Dismiss</button>
          </div>
        </div>
      </div>`;
    document.body.appendChild(overlay);
    this.overlay = overlay;

    overlay.querySelector('#replan-dismiss').addEventListener('click', () => this.close());
    overlay.addEventListener('click', (e) => { if (e.target === overlay) this.close(); });
  }

  async open(tripId, { simulate = false, serviceId = '', serviceType = 'train', disruption = null } = {}) {
    this.overlay.classList.add('open');
    this.overlay.querySelector('#replan-loading').classList.remove('hidden');
    this.overlay.querySelector('#replan-content').classList.add('hidden');

    try {
      const result = await api.replan(tripId, simulate, serviceId, serviceType, disruption);
      this._populate(tripId, result);
    } catch (err) {
      this.overlay.querySelector('#replan-loading').innerHTML = `<p class="text-muted text-sm">Error: ${escHtml(err.message)}</p>`;
    }
  }

  _populate(tripId, result) {
    this.overlay.querySelector('#replan-loading').classList.add('hidden');
    const content = this.overlay.querySelector('#replan-content');
    content.classList.remove('hidden');

    this.overlay.querySelector('#replan-disruption-text').textContent = result.disruption_description || '';
    this.overlay.querySelector('#replan-explanation').textContent = result.granite_explanation || '';

    this.overlay.querySelector('#replan-before').innerHTML = renderDaySummaries(result.before_days);
    this.overlay.querySelector('#replan-after').innerHTML = renderDaySummaries(result.after_days);

    const approveBtn = this.overlay.querySelector('#replan-approve');
    approveBtn.onclick = async () => {
      approveBtn.disabled = true;
      approveBtn.textContent = 'Approving…';
      try {
        await api.approveReplan(tripId, result.after_days);
        approveBtn.textContent = '✓ Approved';
        setTimeout(() => this.close(), 1500);
        document.dispatchEvent(new CustomEvent('wayfare:replan-approved', { detail: { tripId, afterDays: result.after_days } }));
      } catch (err) {
        approveBtn.disabled = false;
        approveBtn.textContent = 'Approve replan';
        alert('Could not approve: ' + err.message);
      }
    };
  }

  close() {
    this.overlay.classList.remove('open');
  }
}

function renderDaySummaries(days) {
  if (!days?.length) return '<p class="text-muted text-sm">No days</p>';
  return days.slice(0, 3).map(d => `
    <div style="padding:0.5rem 0;border-bottom:1px solid var(--border);">
      <div class="text-xs text-muted">Day ${d.day_number} · ${d.date}</div>
      <div class="text-sm fw-medium">${escHtml(d.city)}</div>
      ${d.transport ? `<div class="text-xs text-muted">${escHtml(d.transport.mode)} · ${escHtml(d.transport.service_id)} ${escHtml(d.transport.departure)}</div>` : ''}
    </div>`).join('') + (days.length > 3 ? `<p class="text-xs text-muted mt-1">+${days.length - 3} more days</p>` : '');
}

function escHtml(str) {
  if (!str) return '';
  return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
