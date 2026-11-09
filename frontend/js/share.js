/**
 * share.js – collaborative dashboard: share link, comments, checklist, budget split.
 * Polls every 5 seconds for updates.
 */
import { api } from './api.js';

export class SharePanel {
  constructor(containerEl, tripId, shareToken) {
    this.container = containerEl;
    this.tripId = tripId;
    this.shareToken = shareToken;
    this.role = 'owner';
    this._pollTimer = null;
    this._render();
  }

  _render() {
    this.container.innerHTML = `
      <div class="collab-section">
        <div class="flex items-center gap-2 mb-2">
          <h3>Share trip</h3>
          <span class="role-badge owner" id="role-badge">owner</span>
        </div>
        <div class="share-link-box mb-2">
          <input id="share-link-input" readonly value="Loading…">
          <button class="btn-ghost" id="copy-link-btn">Copy</button>
        </div>
        <div class="flex gap-1 mb-2">
          <button class="btn-secondary text-sm" id="gen-editor-link">Editor link</button>
          <button class="btn-secondary text-sm" id="gen-viewer-link">Viewer link</button>
        </div>

        <div class="collab-section">
          <h3>Comments</h3>
          <div id="comments-list"></div>
          <div class="flex gap-1 mt-1" id="comment-form" style="display:none!important">
            <input id="comment-input" placeholder="Add a comment…" style="flex:1">
            <button class="btn-primary text-sm" id="comment-submit">Post</button>
          </div>
        </div>

        <div class="collab-section">
          <h3>Packing checklist</h3>
          <div id="checklist-list"></div>
        </div>

        <div class="collab-section">
          <h3>Budget split</h3>
          <div id="budget-list"></div>
        </div>
      </div>`;

    this._wireActions();
    this._generateShareLink();
  }

  _wireActions() {
    this.container.querySelector('#copy-link-btn').addEventListener('click', () => {
      const val = this.container.querySelector('#share-link-input').value;
      navigator.clipboard.writeText(val).then(() => {
        this.container.querySelector('#copy-link-btn').textContent = 'Copied!';
        setTimeout(() => { this.container.querySelector('#copy-link-btn').textContent = 'Copy'; }, 2000);
      });
    });

    this.container.querySelector('#gen-editor-link').addEventListener('click', () => this._generateShareLink('editor'));
    this.container.querySelector('#gen-viewer-link').addEventListener('click', () => this._generateShareLink('viewer'));
  }

  async _generateShareLink(role = 'viewer') {
    try {
      const resp = await api.shareTrip(this.tripId, role);
      this.shareToken = resp.share_token;
      const url = `${window.location.origin}/shared.html?token=${resp.share_token}`;
      const input = this.container.querySelector('#share-link-input');
      if (input) input.value = url;
    } catch (err) {
      console.warn('Share failed:', err);
    }
  }

  loadSharedData(data) {
    this.role = data.role;
    const badge = this.container.querySelector('#role-badge');
    if (badge) { badge.textContent = data.role; badge.className = `role-badge ${data.role}`; }

    this._renderComments(data.comments || []);
    this._renderChecklist(data.checklist || []);
    this._renderBudget(data.budget_split || []);

    // Show comment form for non-viewers with edit rights
    const form = this.container.querySelector('#comment-form');
    if (form) form.style.display = 'flex';
    this.container.querySelector('#comment-input')?.addEventListener('keydown', async (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        await this._postComment();
      }
    });
    this.container.querySelector('#comment-submit')?.addEventListener('click', () => this._postComment());
  }

  _renderComments(comments) {
    const el = this.container.querySelector('#comments-list');
    if (!el) return;
    if (!comments.length) { el.innerHTML = '<p class="text-muted text-sm">No comments yet.</p>'; return; }
    el.innerHTML = comments.map(c => `
      <div class="comment-item">
        <div class="comment-author">${escHtml(c.author_name)}</div>
        <div>${escHtml(c.text)}</div>
        <div class="comment-time">${formatTime(c.created_at)}</div>
      </div>`).join('');
  }

  _renderChecklist(items) {
    const el = this.container.querySelector('#checklist-list');
    if (!el) return;
    if (!items.length) { el.innerHTML = '<p class="text-muted text-sm">Checklist is empty.</p>'; return; }
    el.innerHTML = items.map(item => `
      <div class="checklist-item${item.done ? ' done' : ''}">
        <input type="checkbox" ${item.done ? 'checked' : ''} data-item-id="${escHtml(item.item_id)}">
        <span>${escHtml(item.text)}</span>
      </div>`).join('');

    el.querySelectorAll('input[type=checkbox]').forEach(cb => {
      cb.addEventListener('change', async () => {
        try { await api.updateChecklist(this.shareToken, cb.dataset.itemId, cb.checked); }
        catch (err) { cb.checked = !cb.checked; }
      });
    });
  }

  _renderBudget(entries) {
    const el = this.container.querySelector('#budget-list');
    if (!el) return;
    if (!entries.length) { el.innerHTML = '<p class="text-muted text-sm">No budget entries.</p>'; return; }
    const total = entries.reduce((s, e) => s + e.amount_inr, 0);
    el.innerHTML = entries.map(e => `
      <div class="budget-row">
        <span>${escHtml(e.member_name)}</span>
        <span class="fw-medium">₹${e.amount_inr.toLocaleString('en-IN')}</span>
      </div>`).join('') + `<div class="budget-row fw-medium" style="color:var(--accent)"><span>Total</span><span>₹${total.toLocaleString('en-IN')}</span></div>`;
  }

  async _postComment() {
    const input = this.container.querySelector('#comment-input');
    const text = input?.value.trim();
    if (!text || !this.shareToken) return;
    try {
      await api.addComment(this.shareToken, text);
      input.value = '';
      this._poll();
    } catch (err) { console.warn('Comment failed:', err); }
  }

  startPolling() {
    this._pollTimer = setInterval(() => this._poll(), 5000);
  }

  stopPolling() {
    clearInterval(this._pollTimer);
  }

  async _poll() {
    if (!this.shareToken) return;
    try {
      const data = await api.getSharedTrip(this.shareToken);
      this.loadSharedData(data);
    } catch {}
  }
}

function escHtml(str) {
  if (!str) return '';
  return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function formatTime(iso) {
  if (!iso) return '';
  try { return new Date(iso).toLocaleString('en-IN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }); }
  catch { return iso; }
}
