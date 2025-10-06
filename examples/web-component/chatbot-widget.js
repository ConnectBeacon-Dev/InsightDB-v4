/**
 * Chatbot Widget - Web Component
 * A standalone custom element that integrates with the DPIT Chatbot API
 * 
 * Usage:
 * <chatbot-widget 
 *   api-url="http://127.0.0.1:8000"
 *   theme="#12a150"
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
    const theme = this.getAttribute('theme') || '#12a150';
    const height = this.getAttribute('height') || '600px';
    
    this.render(apiUrl, theme, height);
    this.setupEventListeners();
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
    this.messagesContainer.innerHTML = '';
  }
  
  async sendMessage() {
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
        body: JSON.stringify({ query, k: 20 })
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
      
    } catch (error) {
      if (typingMsg) typingMsg.remove();
      this.addMessage('bot', `Error: ${error.message}`, true);
    } finally {
      this.sendButton.disabled = false;
      this.input.focus();
    }
  }
}

// Register the custom element
customElements.define('chatbot-widget', ChatbotWidget);
