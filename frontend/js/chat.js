/**
 * chat.js – chat UI with preference extraction.
 */
import { api } from './api.js';

export class ChatUI {
  constructor(containerEl, onPreferencesReady) {
    this.container = containerEl;
    this.onPreferencesReady = onPreferencesReady;
    this.history = [];
    this.sessionId = crypto.randomUUID();
    this._render();
  }

  _render() {
    this.container.innerHTML = `
      <div class="chat-area">
        <div class="chat-messages" id="chat-messages"></div>
        <div class="chat-input-row">
          <textarea class="chat-input" id="chat-input" placeholder="Where would you like to go?" rows="1"></textarea>
          <button class="btn-primary" id="chat-send">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
          </button>
        </div>
      </div>`;
    this.messagesEl = this.container.querySelector('#chat-messages');
    this.inputEl = this.container.querySelector('#chat-input');
    this.sendBtn = this.container.querySelector('#chat-send');

    this.sendBtn.addEventListener('click', () => this._send());
    this.inputEl.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); this._send(); }
    });
    this.inputEl.addEventListener('input', () => {
      this.inputEl.style.height = 'auto';
      this.inputEl.style.height = Math.min(this.inputEl.scrollHeight, 120) + 'px';
    });

    this._addMessage('assistant', "Hi! I'm Wayfare, your AI travel assistant powered by IBM Granite. Tell me where you'd like to go — for example: \"Plan a 5-day trip from Delhi to Goa next month for 2 adults.\"");
  }

  _addMessage(role, text, extra = '') {
    const div = document.createElement('div');
    div.className = `chat-bubble ${role}`;
    div.innerHTML = `${escapeHtml(text)}${extra}`;
    this.messagesEl.appendChild(div);
    this.messagesEl.scrollTop = this.messagesEl.scrollHeight;
    return div;
  }

  _addTyping() {
    const div = document.createElement('div');
    div.className = 'chat-bubble assistant';
    div.innerHTML = '<span class="spinner"></span>';
    div.id = 'typing-indicator';
    this.messagesEl.appendChild(div);
    this.messagesEl.scrollTop = this.messagesEl.scrollHeight;
    return div;
  }

  async _send() {
    const msg = this.inputEl.value.trim();
    if (!msg) return;
    this.inputEl.value = '';
    this.inputEl.style.height = 'auto';
    this.sendBtn.disabled = true;

    this._addMessage('user', msg);
    this.history.push({ role: 'user', content: msg });
    const typing = this._addTyping();

    try {
      // Try to extract preferences first
      const context = this.history.slice(-4).map(m => `${m.role}: ${m.content}`).join('\n');
      const prefResult = await api.extractPreferences(msg, context);

      typing.remove();

      if (prefResult.ready && !prefResult.preferences?.clarifying_question) {
        // Preferences complete — ask for confirmation
        const prefs = prefResult.preferences;
        const reply = `Got it! Here's what I understood:\n\n📍 **${prefs.origin} → ${prefs.destination}**\n📅 ${prefs.start_date} to ${prefs.end_date}\n👥 ${prefs.num_adults} adult${prefs.num_adults > 1 ? 's' : ''}${prefs.num_children ? `, ${prefs.num_children} child${prefs.num_children > 1 ? 'ren' : ''}` : ''}\n\nShall I build the full itinerary?`;
        this._addMessage('assistant', reply, `
          <div style="margin-top:0.75rem;display:flex;gap:0.5rem;">
            <button class="btn-primary" id="confirm-plan">Yes, build it →</button>
            <button class="btn-ghost" id="modify-plan">Modify</button>
          </div>`);

        this.container.querySelector('#confirm-plan')?.addEventListener('click', () => {
          this.onPreferencesReady?.(prefs);
        });
      } else {
        // Send to chat for clarification or general reply
        const chatResp = await api.chat({
          session_id: this.sessionId,
          message: msg,
          history: this.history.slice(-8),
        });
        this.history.push({ role: 'assistant', content: chatResp.reply });
        this._addMessage('assistant', chatResp.reply);
      }
    } catch (err) {
      typing.remove();
      this._addMessage('assistant', `Sorry, something went wrong: ${err.message}`);
    } finally {
      this.sendBtn.disabled = false;
    }
  }
}

function escapeHtml(str) {
  return str
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/\n/g, '<br>').replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
}
