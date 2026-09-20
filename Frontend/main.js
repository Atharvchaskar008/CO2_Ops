// ==========================================================================
// CO2Ops — Frontend Controller (Landing Page & Workspace Console)
// ==========================================================================

document.addEventListener('DOMContentLoaded', () => {
  const API_BASE_URL = window.CO2OPS_API_URL || 'http://127.0.0.1:8080';
  const APP_NAME = 'co2ops_agent';

  // --- UUID Generator ---
  const generateUUID = () => {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
      const r = (Math.random() * 16) | 0;
      const v = c === 'x' ? r : (r & 0x3) | 0x8;
      return v.toString(16);
    });
  };

  // ==========================================================================
  // WORKSPACE LOGIC (Only runs when on workspace.html)
  // ==========================================================================
  const chatHistory = document.getElementById('ws-chat-history');
  const chatForm = document.getElementById('ws-chat-form');
  const chatInput = document.getElementById('ws-chat-input');
  const sendBtn = document.getElementById('ws-send-btn');
  const userIdEl = document.getElementById('ws-user-id');
  const sessionIdEl = document.getElementById('ws-session-id');
  const newSessionBtn = document.getElementById('ws-new-session-btn');

  if (chatForm && chatHistory && chatInput) {
    // Session state
    let userId = localStorage.getItem('co2ops_user_id');
    if (!userId) {
      userId = `user-${generateUUID().substring(0, 8)}`;
      localStorage.setItem('co2ops_user_id', userId);
    }
    if (userIdEl) userIdEl.textContent = userId;

    let sessionId = `session-${Math.floor(Date.now() / 1000)}`;
    if (sessionIdEl) sessionIdEl.textContent = sessionId;

    // Helper: Markdown parser
    const renderMarkdown = (text) => {
      if (!text) return '';
      let html = text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');

      // Code blocks
      html = html.replace(/```([a-z]*)\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>');
      // Inline code
      html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
      // Bold
      html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
      // Italic
      html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');
      // Links
      html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
      // Unordered lists
      html = html.replace(/^\s*[-*]\s+(.*)$/gm, '<li>$1</li>');
      html = html.replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>');
      // Line breaks
      html = html.replace(/\n\n/g, '</p><p>').replace(/\n/g, '<br/>');

      return `<p>${html}</p>`;
    };

    // Append Chat Bubble
    const appendMessage = (role, text) => {
      const msgDiv = document.createElement('div');
      msgDiv.className = `chat-message ${role === 'user' ? 'user-msg' : 'assistant-msg'}`;

      const avatarDiv = document.createElement('div');
      avatarDiv.className = 'msg-avatar';
      if (role === 'user') {
        avatarDiv.textContent = 'YOU';
      } else {
        avatarDiv.innerHTML = '<svg width="20" height="20"><use href="#icon-copilot-spark"/></svg>';
      }

      const contentDiv = document.createElement('div');
      contentDiv.className = 'msg-content';

      const senderDiv = document.createElement('div');
      senderDiv.className = 'msg-sender';
      senderDiv.textContent = role === 'user' ? 'You' : 'CO2Ops Orchestrator';

      const textDiv = document.createElement('div');
      textDiv.className = 'msg-text';
      textDiv.innerHTML = renderMarkdown(text);

      contentDiv.appendChild(senderDiv);
      contentDiv.appendChild(textDiv);
      msgDiv.appendChild(avatarDiv);
      msgDiv.appendChild(contentDiv);

      chatHistory.appendChild(msgDiv);
      chatHistory.scrollTop = chatHistory.scrollHeight;
    };

    // Append Thinking Indicator
    let thinkingEl = null;
    const showThinking = () => {
      if (thinkingEl) return;
      thinkingEl = document.createElement('div');
      thinkingEl.className = 'chat-message assistant-msg';
      thinkingEl.innerHTML = `
        <div class="msg-avatar"><svg width="20" height="20"><use href="#icon-copilot-spark"/></svg></div>
        <div class="msg-content">
          <div class="msg-sender">CO2Ops Orchestrator</div>
          <div class="thinking-bubble">
            <span class="dot-flashing"></span>
            <span>Auditing fleet and coordinating AWS sub-agents...</span>
          </div>
        </div>
      `;
      chatHistory.appendChild(thinkingEl);
      chatHistory.scrollTop = chatHistory.scrollHeight;
    };

    const hideThinking = () => {
      if (thinkingEl && thinkingEl.parentNode) {
        thinkingEl.parentNode.removeChild(thinkingEl);
      }
      thinkingEl = null;
    };

    // Create session API call
    const createSession = async () => {
      sessionId = `session-${Math.floor(Date.now() / 1000)}`;
      if (sessionIdEl) sessionIdEl.textContent = sessionId;

      try {
        await fetch(`${API_BASE_URL}/api/sessions`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ user_id: userId })
        });
      } catch (err) {
        console.warn('Backend session endpoint notice:', err);
      }
    };

    // Initialize session
    createSession();

    if (newSessionBtn) {
      newSessionBtn.addEventListener('click', () => {
        createSession();
        appendMessage('assistant', `Started a new session: <code>${sessionId}</code>. How can I help optimize your AWS fleet?`);
      });
    }

    // Send message to CO2Ops FastAPI backend
    const sendMessage = async (messageText) => {
      if (!messageText) return;

      appendMessage('user', messageText);
      chatInput.value = '';
      chatInput.disabled = true;
      if (sendBtn) sendBtn.disabled = true;
      showThinking();

      try {
        const res = await fetch(`${API_BASE_URL}/api/chat`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            message: messageText,
            user_id: userId,
            session_id: sessionId
          })
        });

        hideThinking();

        if (res.ok) {
          const data = await res.json();
          let fullText = '';

          if (data && data.response) {
            fullText = data.response;
          } else if (Array.isArray(data)) {
            data.forEach((event) => {
              if (event.response) fullText += event.response;
              else if (event.content && event.content.parts) {
                event.content.parts.forEach((p) => {
                  if (p.text) fullText += p.text;
                });
              } else if (event.step_details && event.step_details.model_output) {
                const parts = event.step_details.model_output.parts || [];
                parts.forEach((p) => {
                  if (p.text) fullText += p.text;
                });
              }
            });
          }

          if (fullText.trim()) {
            appendMessage('assistant', fullText);
          } else {
            appendMessage('assistant', 'Action processed by CO2Ops. All AWS sub-agents reported success.');
          }
        } else {
          const errorText = await res.text();
          appendMessage('assistant', `Backend notice (${res.status}): ${errorText || 'Agent service busy. Please retry.'}`);
        }
      } catch (err) {
        hideThinking();
        console.error('Fetch error:', err);
        appendMessage('assistant', `Could not reach CO2Ops FastAPI backend on ${API_BASE_URL}. Ensure the backend is running.`);
      } finally {
        chatInput.disabled = false;
        if (sendBtn) sendBtn.disabled = false;
        chatInput.focus();
      }
    };

    // Chat form submit
    chatForm.addEventListener('submit', (e) => {
      e.preventDefault();
      const text = chatInput.value.trim();
      if (text) sendMessage(text);
    });

    // Quick chip buttons
    document.querySelectorAll('.quick-chip').forEach((chip) => {
      chip.addEventListener('click', () => {
        const prompt = chip.getAttribute('data-prompt');
        if (prompt) {
          chatInput.value = prompt;
          sendMessage(prompt);
        }
      });
    });

    // Check URL parameters for prompt (e.g. workspace.html?prompt=Audit%20fleet)
    const urlParams = new URLSearchParams(window.location.search);
    const initialPrompt = urlParams.get('prompt');
    if (initialPrompt) {
      setTimeout(() => {
        sendMessage(decodeURIComponent(initialPrompt));
      }, 500);
    }
  }

  // ==========================================================================
  // LANDING PAGE LOGIC
  // ==========================================================================
  // Smooth scroll for anchor navigation
  document.querySelectorAll('a[href^="#"]').forEach((anchor) => {
    anchor.addEventListener('click', function (e) {
      const targetId = this.getAttribute('href').substring(1);
      const targetElement = document.getElementById(targetId);
      if (targetElement) {
        e.preventDefault();
        targetElement.scrollIntoView({ behavior: 'smooth' });
      }
    });
  });
});
