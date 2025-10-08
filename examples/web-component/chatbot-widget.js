/**
 * Chatbot Widget - Web Component
 * A standalone custom element that integrates with the DPIT Chatbot API
 * 
 * Usage:
 * <chatbot-widget 
 *   api-url="http://127.0.0.1:8000"
 *   theme="#6915CF"
 *   height="600px"
 * ></chatbot-widget>
 */

class ChatbotWidget extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
  }

  connectedCallback() {
    const apiUrl = this.getAttribute('api-url') || 'http://127.0.0.1:8000';
    const theme = this.getAttribute('theme') || '#6915CF';
    const height = this.getAttribute('height') || '600px';
    // NEW: capture optional user name (supports user-name or username)
    const userNameAttr = this.getAttribute('user-name') || this.getAttribute('username') || '';
    this.userName = (userNameAttr || '').toString().trim();

    this.render(apiUrl, theme, height);
    this.setupEventListeners();
    this.fetchWelcome();
  }

  render(apiUrl, theme, height) {
    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          font-family: system-ui, -apple-system, sans-serif;
        }
        
        .chat-container {
          background: #fff;
          border: 1px solid #e5e7eb;
          border-radius: 12px;
          height: ${height};
          display: flex;
          flex-direction: column;
          box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        }
        
        .chat-header {
          background: ${theme};
          color: white;
          padding: 12px 16px;
          font-weight: 600;
          border-radius: 12px 12px 0 0;
          display: flex;
          justify-content: space-between;
          align-items: center;
        }
        
        .chat-messages {
          flex: 1;
          overflow-y: auto;
          padding: 16px;
          background: #f9fafb;
        }
        
        .message {
          margin-bottom: 16px;
          display: flex;
          gap: 10px;
          animation: slideIn 0.2s ease;
        }
        
        @keyframes slideIn {
          from { opacity: 0; transform: translateY(10px); }
          to { opacity: 1; transform: translateY(0); }
        }
        
        .message.user {
          justify-content: flex-end;
        }
        
        .avatar {
          width: 32px;
          height: 32px;
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          font-weight: 700;
          font-size: 12px;
          flex-shrink: 0;
        }
        
        .message.user .avatar {
          background: #1d4ed8;
          color: white;
        }
        
        .message.bot .avatar {
          background: #16a34a;
          color: white;
        }
        
        .message-bubble {
          max-width: 70%;
          padding: 10px 14px;
          border-radius: 12px;
          line-height: 1.5;
          word-wrap: break-word;
        }
        
        .message.user .message-bubble {
          background: #e8f3ff;
          border: 1px solid #93c5fd;
        }
        
        .message.bot .message-bubble {
          background: #eefbf2;
          border: 1px solid #86efac;
        }
        
        .chat-input-container {
          border-top: 1px solid #e5e7eb;
          padding: 12px;
          display: flex;
          gap: 8px;
          background: white;
          border-radius: 0 0 12px 12px;
        }
        
        .chat-input {
          flex: 1;
          padding: 10px 12px;
          border: 1px solid #d1d5db;
          border-radius: 8px;
          font-size: 14px;
          font-family: inherit;
          resize: none;
          min-height: 44px;
          max-height: 120px;
        }
        
        .chat-input:focus {
          outline: none;
          border-color: ${theme};
          box-shadow: 0 0 0 3px ${theme}20;
        }
        
        .send-button {
          background: ${theme};
          color: white;
          border: none;
          padding: 10px 20px;
          border-radius: 8px;
          font-weight: 600;
          cursor: pointer;
          transition: opacity 0.2s;
        }
        
        .send-button:hover:not(:disabled) {
          opacity: 0.9;
        }
        
        .send-button:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }
        
        .typing-indicator {
          display: inline-flex;
          gap: 4px;
          padding: 8px 0;
        }
        
        .dot {
          width: 8px;
          height: 8px;
          background: #94a3b8;
          border-radius: 50%;
          animation: bounce 1.2s infinite;
        }
        
        .dot:nth-child(2) { animation-delay: 0.15s; }
        .dot:nth-child(3) { animation-delay: 0.3s; }
        
        @keyframes bounce {
          0%, 80%, 100% { 
            opacity: 0.3; 
            transform: translateY(0); 
          }
          40% { 
            opacity: 1; 
            transform: translateY(-4px); 
          }
        }
        
        .error-message {
          background: #fee2e2;
          border: 1px solid #fecaca;
          color: #991b1b;
        }
        
        .new-chat-btn {
          background: rgba(255,255,255,0.2);
          border: 1px solid rgba(255,255,255,0.3);
          color: white;
          padding: 6px 12px;
          border-radius: 6px;
          cursor: pointer;
          font-size: 13px;
        }
        
        .new-chat-btn:hover {
          background: rgba(255,255,255,0.3);
        }
      </style>
      
      <div class="chat-container">
        <div class="chat-header">
          <span>DPIT Chatbot</span>
          <button class="new-chat-btn" id="newChat">New Chat</button>
        </div>
        <div class="chat-messages" id="messages"></div>
        <div class="chat-input-container">
          <textarea 
            class="chat-input" 
            id="input" 
            rows="1"
            placeholder="Ask about companies, products, certifications..."
          ></textarea>
          <button class="send-button" id="send">Send</button>
        </div>
      </div>
    `;
    
    this.apiUrl = apiUrl;
  }

  async fetchWelcome() {
    try {
      if (this._welcomeEnabled === false) return;
      const res = await fetch(`${this.apiUrl}/welcome`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_name: this.userName || undefined })
      });
      if (res.ok) {
        const data = await res.json();
        const msg = (data && data.message) ? String(data.message) : null;
        if (msg) {
          this.addMessage('bot', msg);
          this._welcomedOnce = true;
          return;
        }
      }
    } catch (e) {
      // ignore and try client fallback
    }
    // Fallback to client-side welcome if server call fails
    if (this._welcomeEnabled && !this._welcomedOnce && this._welcomeMessage) {
      this.addMessage('bot', this._welcomeMessage);
      this._welcomedOnce = true;
    }
  }

  setupEventListeners() {
    this.messagesContainer = this.shadowRoot.getElementById('messages');
    this.input = this.shadowRoot.getElementById('input');
    this.sendButton = this.shadowRoot.getElementById('send');
    this.newChatBtn = this.shadowRoot.getElementById('newChat');
    
    this.sendButton.addEventListener('click', () => this.sendMessage());
    this.newChatBtn.addEventListener('click', () => this.clearChat());
    
    this.input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        this.sendMessage();
      }
    });
    
    // Auto-resize textarea
    this.input.addEventListener('input', () => {
      this.input.style.height = 'auto';
      this.input.style.height = this.input.scrollHeight + 'px';
    });
  }
  
  addMessage(role, text, isError = false) {
    const msg = document.createElement('div');
    msg.className = `message ${role}`;
    
    const avatar = document.createElement('div');
    avatar.className = 'avatar';
    avatar.textContent = role === 'user' ? 'U' : 'AI';
    
    const bubble = document.createElement('div');
    bubble.className = `message-bubble ${isError ? 'error-message' : ''}`;
    bubble.textContent = text;
    
    if (role === 'user') {
      msg.appendChild(bubble);
      msg.appendChild(avatar);
    } else {
      msg.appendChild(avatar);
      msg.appendChild(bubble);
    }
    
    this.messagesContainer.appendChild(msg);
    this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
    
    return { msg, bubble };
  }
  
  addTypingIndicator() {
    const { msg, bubble } = this.addMessage('bot', '');
    bubble.innerHTML = `
      <div class="typing-indicator">
        <span class="dot"></span>
        <span class="dot"></span>
        <span class="dot"></span>
      </div>
    `;
    msg.id = 'typing-indicator';
    return msg;
  }
  
  clearChat() {
    if (this.messagesContainer) {
      this.messagesContainer.innerHTML = '';
    }
    this._welcomedOnce = false;
    this.fetchWelcome();
  }
  
  async sendMessage() {
    if (this._welcomeEnabled && !this._welcomedOnce) {
      await this.fetchWelcome();
    }
    const query = this.input.value.trim();
    if (!query || this.sendButton.disabled) return;
    
    this.input.value = '';
    this.input.style.height = 'auto';
    this.sendButton.disabled = true;
    
    this.addMessage('user', query);
    let typingMsg = this.addTypingIndicator();
    
    try {
      const response = await fetch(`${this.apiUrl}/ask_stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, k: 20, user_name: this.userName || undefined })
      });
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let answer = '';
      let answerBubble = null;
      
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        
        buffer += decoder.decode(value, { stream: true });
        
        let newlineIndex;
        while ((newlineIndex = buffer.indexOf('\n\n')) >= 0) {
          const chunk = buffer.slice(0, newlineIndex);
          buffer = buffer.slice(newlineIndex + 2);
          
          const lines = chunk.split('\n');
          let eventType = 'message';
          let data = '';
          
          for (const line of lines) {
            if (line.startsWith('event:')) {
              eventType = line.slice(6).trim();
            } else if (line.startsWith('data:')) {
              data = line.slice(5).trim();
            }
          }
          
          if (eventType === 'token') {
            if (typingMsg) {
              typingMsg.remove();
              typingMsg = null;
            }
            
            if (!answerBubble) {
              const result = this.addMessage('bot', '');
              answerBubble = result.bubble;
            }
            
            try {
              answer += JSON.parse(data);
              answerBubble.textContent = answer;
              this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
            } catch (e) {
              console.error('Error parsing token:', e);
            }
          } else if (eventType === 'done') {
            break;
          } else if (eventType === 'error') {
            throw new Error(data || 'Unknown error');
          }
        }
      }
      
      if (typingMsg) typingMsg.remove();

      if (answerBubble && answer) {
        answerBubble.innerHTML = formatForHumans(answer);
      }

    } catch (error) {
      if (typingMsg) typingMsg.remove();
      this.addMessage('bot', `Error: ${error.message}`, true);
    } finally {
      this.sendButton.disabled = false;
      this.input.focus();
    }
  }
}

/* -------------------- Compact formatter helpers -------------------- */

function formatForHumans(raw) {
  if (!raw) return '';

  // If backend returns JSON text, render compact bullets
  const asJson = tryParseJson(raw);
  if (asJson) {
    const html = renderFromJson(asJson);
    if (html) return html;
  }

  // Pattern: "Found N matching companies: - CompanyRefNo: ... | CompanyName: ... | State: ..."
  const m = raw.match(/^Found\s+(\d+)\s+matching companies:\s*(.*)$/si);
  if (m) {
    const count = Number(m[1]);
    const body = m[2].trim();
    const segments = body
      .split(/\s-\s(?=(CompanyRefNo|CompanyName)\s*:)/gi)
      .filter(Boolean);

    const items = [];
    for (const seg of segments) {
      // parse "Key: Val | Key: Val | ..." into a map
      const fields = seg.split(/\s\|\s/g);
      const map = {};
      for (const kv of fields) {
        const idx = kv.indexOf(':');
        if (idx === -1) continue;
        const k = kv.slice(0, idx).trim();
        const v = kv.slice(idx + 1).trim();
        if (k) map[k] = v;
      }

      // pick fields
      const name = map.CompanyName || map.Company || map.Name || '';
      const ref  = map.CompanyRefNo || map.CompanyRef || map.Ref || '';
      const state = map.State || map.state || '';
      const city  = map.City || map.city || '';
      const industry = map.IndustryDomain || map.IndustryDomainText || map.Domain || '';

      if (!name && !state && !ref && !city && !industry) continue;

      const line1Parts = [];
      if (name) line1Parts.push(name);
      if (state) line1Parts.push(state);
      const line1 = escapeHtml(line1Parts.join(' — ') || '(Unnamed company)');

      const meta = [];
      if (ref) meta.push(`Ref No ${escapeHtml(ref)}`);
      if (city) meta.push(escapeHtml(city));
      if (industry) meta.push(escapeHtml(industry));
      const line2 = meta.join(' • ');

      items.push(`<li><div class="l1">${line1}</div>${line2 ? `<div class="l2">${line2}</div>` : ''}</li>`);
    }

    const listHtml = items.join('') || '<li>(no items)</li>';
    return `
      <div class="compact-headline">Found ${count} matching companies</div>
      <ul class="compact-list">
        ${listHtml}
      </ul>
    `;
  }

  // Fallback: bulletize simple text, linkify, preserve newlines
  const safe = escapeHtml(raw);
  const withLinks = linkify(safe)
    .replace(/^-\s+/gm, '• ')
    .replace(/\n{2,}/g, '\n\n')
    .replace(/\n/g, '<br/>');
  return withLinks;
}

function renderFromJson(js) {
  if (!js || typeof js !== 'object') return '';

  // Single contact-style answer
  if (js.answer && typeof js.answer === 'object' && (js.answer.company_name || js.answer.companyName)) {
    const a = js.answer;
    const name = a.company_name || a.companyName || '';
    const state = a.state || '';
    const city = a.city || '';
    const ref = a.company_ref_no || a.companyRefNo || a.company_id || '';
    const industry = a.industry || a.industry_domain || '';

    const line1Parts = [];
    if (name) line1Parts.push(name);
    if (state) line1Parts.push(state);
    const line1 = escapeHtml(line1Parts.join(' — ') || '(Unnamed company)');

    const meta = [];
    if (ref) meta.push(`Ref No ${escapeHtml(ref)}`);
    if (city) meta.push(escapeHtml(city));
    if (industry) meta.push(escapeHtml(industry));

    return `
      <ul class="compact-list">
        <li>
          <div class="l1">${line1}</div>
          ${meta.length ? `<div class="l2">${meta.join(' • ')}</div>` : ''}
        </li>
      </ul>
    `;
  }

  // Array of matches
  if (Array.isArray(js.matches) && js.matches.length) {
    const items = js.matches.map(m => {
      const name = m.company_name || m.companyName || '';
      const state = m.state || '';
      const city = m.city || '';
      const ref  = m.id || m.company_ref_no || '';
      const industry = m.industry || m.industry_domain || '';

      const line1Parts = [];
      if (name) line1Parts.push(name);
      if (state) line1Parts.push(state);
      const line1 = escapeHtml(line1Parts.join(' — ') || '(Unnamed company)');

      const meta = [];
      if (ref) meta.push(`Ref No ${escapeHtml(String(ref))}`);
      if (city) meta.push(escapeHtml(city));
      if (industry) meta.push(escapeHtml(industry));

      return `<li><div class="l1">${line1}</div>${meta.length ? `<div class="l2">${meta.join(' • ')}</div>` : ''}</li>`;
    }).join('');

    return `
      <div class="compact-headline">Top matches</div>
      <ul class="compact-list">${items}</ul>
    `;
  }

  if (js.answer && typeof js.answer.text === 'string')
    return formatForHumans(js.answer.text);

  return '';
}

/* -------------------- small utilities -------------------- */

function escapeHtml(s) {
  return (s || '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function linkify(s) {
  // emails
  s = s.replace(/\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/gi,
    m => `<a href="mailto:${m}">${m}</a>`);
  // URLs (http/https)
  s = s.replace(/\bhttps?:\/\/[^\s<]+/gi,
    m => `<a href="${m}" target="_blank" rel="noopener">${m}</a>`);
  return s;
}

function tryParseJson(s) {
  try { return JSON.parse(s); } catch { return null; }
}

// Register the custom element
customElements.define('chatbot-widget', ChatbotWidget);
