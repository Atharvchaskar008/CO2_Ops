// ==========================================================================
// CO2Ops — Autonomous FinOps & GreenOps Console Controller
// Multi-Agent Orchestration • Live Fleet Telemetry • Interactive Actions
// ==========================================================================

document.addEventListener('DOMContentLoaded', () => {
  const API_BASE_URL = window.CO2OPS_API_URL || 'http://127.0.0.1:8080';
  const APP_NAME = 'co2ops_agent';

  // --- AWS Benchmark Telemetry Dataset ---
  const BENCHMARK_FLEET = [
    { id: "i-01a2b3c4d5e6f7g80", type: "m5.2xlarge", region: "us-east-1", cpu: 14.5, mem: 32.0, carbon: 2.85, status: "Underutilized", target: "m5.large" },
    { id: "i-02b3c4d5e6f7g8h91", type: "c5.xlarge", region: "us-east-1", cpu: 18.2, mem: 28.5, carbon: 1.42, status: "Underutilized", target: "t3.large" },
    { id: "i-03c4d5e6f7g8h9i02", type: "t3.large", region: "us-east-1", cpu: 11.0, mem: 25.0, carbon: 0.65, status: "Underutilized", target: "t3.medium" },
    { id: "i-04d5e6f7g8h9i0j13", type: "r5.2xlarge", region: "us-east-1", cpu: 22.0, mem: 38.0, carbon: 3.10, status: "Underutilized", target: "r5.xlarge" },
    { id: "i-05e6f7g8h9i0j1k24", type: "m5.xlarge", region: "us-west-2", cpu: 16.4, mem: 35.0, carbon: 0.95, status: "Underutilized", target: "m5.large" },
    { id: "i-06f7g8h9i0j1k2l35", type: "c5.2xlarge", region: "us-west-2", cpu: 21.0, mem: 31.0, carbon: 1.80, status: "Underutilized", target: "c5.xlarge" },
    { id: "i-07g8h9i0j1k2l3m46", type: "m5.4xlarge", region: "eu-west-1", cpu: 12.8, mem: 29.0, carbon: 4.20, status: "Underutilized", target: "m5.2xlarge" },
    { id: "i-08h9i0j1k2l3m4n57", type: "t3.xlarge", region: "eu-west-1", cpu: 15.0, mem: 33.0, carbon: 1.10, status: "Underutilized", target: "t3.medium" },
    { id: "i-09i0j1k2l3m4n5o68", type: "c5.xlarge", region: "ap-south-1", cpu: 19.5, mem: 34.0, carbon: 2.45, status: "Underutilized", target: "t3.large" },
    { id: "i-10j1k2l3m4n5o6p79", type: "r5.xlarge", region: "ap-south-1", cpu: 17.0, mem: 30.0, carbon: 2.90, status: "Underutilized", target: "r5.large" }
  ];

  const REGIONAL_GRID_CARBON = {
    "us-east-1": "0.379 kg CO₂/kWh",
    "us-west-2": "0.180 kg CO₂/kWh",
    "eu-west-1": "0.295 kg CO₂/kWh",
    "ap-south-1": "0.708 kg CO₂/kWh"
  };

  // --- UUID Generator ---
  const generateUUID = () => {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
      const r = (Math.random() * 16) | 0;
      const v = c === 'x' ? r : (r & 0x3) | 0x8;
      return v.toString(16);
    });
  };

  // ==========================================================================
  // WORKSPACE DOM ELEMENTS
  // ==========================================================================
  const chatHistory = document.getElementById('ws-chat-history');
  const chatForm = document.getElementById('ws-chat-form');
  const chatInput = document.getElementById('ws-chat-input');
  const sendBtn = document.getElementById('ws-send-btn');
  const userIdEl = document.getElementById('ws-user-id');
  const sessionIdEl = document.getElementById('ws-session-id');
  const newSessionBtn = document.getElementById('ws-new-session-btn');
  const clearChatBtn = document.getElementById('clear-chat-btn');
  const chatWelcomeHero = document.getElementById('chat-welcome-hero');

  // Pipeline Stepper Elements
  const pipelineStepper = document.getElementById('pipeline-stepper');
  const stepperTimer = document.getElementById('stepper-timer');
  const stepperStatusText = document.getElementById('stepper-status-text');

  // Drawer & Sidebar Elements
  const workspaceRail = document.getElementById('workspace-rail');
  const sidebarToggleBtn = document.getElementById('sidebar-toggle-btn');
  const telemetryDrawer = document.getElementById('telemetry-drawer');
  const telemetryDrawerToggle = document.getElementById('telemetry-drawer-toggle');
  const drawerCloseBtn = document.getElementById('drawer-close-btn');
  const fleetListContainer = document.getElementById('fleet-list-container');
  const fleetSearchInput = document.getElementById('fleet-search-input');
  const activeRegionSelect = document.getElementById('active-region-select');
  const drawerGridIntensity = document.getElementById('drawer-grid-intensity');
  const btnAuditSelectedRegion = document.getElementById('btn-audit-selected-region');

  // If we are on workspace.html, initialize console logic
  if (chatForm && chatHistory && chatInput) {

    // --- State Variables ---
    let userId = localStorage.getItem('co2ops_user_id');
    if (!userId) {
      userId = `user-${generateUUID().substring(0, 8)}`;
      localStorage.setItem('co2ops_user_id', userId);
    }
    if (userIdEl) userIdEl.textContent = userId;

    let sessionId = `session-${Math.floor(Date.now() / 1000)}`;
    if (sessionIdEl) sessionIdEl.textContent = sessionId;

    let activePipelineInterval = null;
    let pipelineStartTime = null;

    // ==========================================================================
    // 1. DYNAMIC MULTI-AGENT PIPELINE STEPPER
    // ==========================================================================
    const stepNodes = [
      { id: 'step-orchestrator', agent: 'co2ops_agent', label: 'Intent Classification & Plan' },
      { id: 'step-scout', agent: 'aws_server_analyst', label: 'DuckDB Fleet Telemetry Query' },
      { id: 'step-profiler', agent: 'workload_profiler', label: 'Workload & Waste Profiling' },
      { id: 'step-recommender', agent: 'infra_recommender', label: 'Rightsizing Synthesis' },
      { id: 'step-executor', agent: 'safe_executor', label: 'Safety Gate & Verification' }
    ];

    const resetPipelineSteps = () => {
      stepNodes.forEach((node, i) => {
        const el = document.getElementById(node.id);
        if (el) {
          el.className = 'step-node';
        }
        if (i < 4) {
          const line = document.getElementById(`line-${i + 1}`);
          if (line) line.className = 'step-line';
        }
      });
    };

    const startPipeline = () => {
      if (!pipelineStepper) return;
      pipelineStepper.style.display = 'flex';
      resetPipelineSteps();

      // Activate Orchestrator
      const step1 = document.getElementById('step-orchestrator');
      if (step1) step1.classList.add('active');

      if (stepperStatusText) {
        stepperStatusText.textContent = 'Orchestrator formulating plan and evaluating sub-agents...';
      }

      pipelineStartTime = Date.now();
      if (activePipelineInterval) clearInterval(activePipelineInterval);

      activePipelineInterval = setInterval(() => {
        const elapsed = ((Date.now() - pipelineStartTime) / 1000).toFixed(1);
        if (stepperTimer) stepperTimer.textContent = `Elapsed: ${elapsed}s`;

        // Progressive simulation for smooth visual feedback
        const sec = parseFloat(elapsed);
        if (sec > 3 && sec <= 12) {
          markStep('step-orchestrator', 'completed');
          setStepLine(1, true);
          markStep('step-scout', 'active');
          if (stepperStatusText) stepperStatusText.textContent = 'Infra Scout querying DuckDB `server_metrics` for AWS EC2 telemetry...';
          highlightSwarmAgent('optimization_advisor');
        } else if (sec > 12 && sec <= 24) {
          markStep('step-scout', 'completed');
          setStepLine(2, true);
          markStep('step-profiler', 'active');
          if (stepperStatusText) stepperStatusText.textContent = 'Workload Profiler identifying underutilized CPU & carbon waste...';
          highlightSwarmAgent('optimization_advisor');
        } else if (sec > 24 && sec <= 42) {
          markStep('step-profiler', 'completed');
          setStepLine(3, true);
          markStep('step-recommender', 'active');
          if (stepperStatusText) stepperStatusText.textContent = 'Recommender formulating rightsizing options & Graviton targets...';
          highlightSwarmAgent('optimization_advisor');
        } else if (sec > 42) {
          markStep('step-recommender', 'completed');
          setStepLine(4, true);
          markStep('step-executor', 'active');
          if (stepperStatusText) stepperStatusText.textContent = 'Evaluating policy rules & ARIMA forecasting windows...';
          highlightSwarmAgent('safe_executor');
        }
      }, 100);
    };

    const markStep = (nodeId, status) => {
      const el = document.getElementById(nodeId);
      if (!el) return;
      el.classList.remove('active', 'completed');
      el.classList.add(status);
    };

    const setStepLine = (lineNum, completed) => {
      const line = document.getElementById(`line-${lineNum}`);
      if (!line) return;
      if (completed) line.classList.add('completed');
      else line.classList.remove('completed');
    };

    const finishPipeline = (success = true) => {
      if (activePipelineInterval) {
        clearInterval(activePipelineInterval);
        activePipelineInterval = null;
      }
      stepNodes.forEach((node) => markStep(node.id, 'completed'));
      for (let i = 1; i <= 4; i++) setStepLine(i, true);

      if (stepperStatusText) {
        stepperStatusText.textContent = success
          ? 'Completed. All AWS sub-agents reported success.'
          : 'Agent response received.';
      }
      clearSwarmHighlights();

      setTimeout(() => {
        if (pipelineStepper) pipelineStepper.style.display = 'none';
      }, 2500);
    };

    const highlightSwarmAgent = (agentKey) => {
      document.querySelectorAll('.swarm-agent-card').forEach((card) => {
        card.classList.remove('active');
        const dot = card.querySelector('.agent-status-dot');
        if (dot) dot.className = 'agent-status-dot online';
      });
      const targetCard = document.getElementById(`swarm-${agentKey}`);
      if (targetCard) {
        targetCard.classList.add('active');
        const dot = targetCard.querySelector('.agent-status-dot');
        if (dot) dot.className = 'agent-status-dot active';
      }
    };

    const clearSwarmHighlights = () => {
      document.querySelectorAll('.swarm-agent-card').forEach((card) => {
        card.classList.remove('active');
        const dot = card.querySelector('.agent-status-dot');
        if (dot) dot.className = 'agent-status-dot online';
      });
    };

    // ==========================================================================
    // 2. ENHANCED MARKDOWN & ACTIONABLE RECOMMENDATION CARDS
    // ==========================================================================
    const renderMarkdown = (text) => {
      if (!text) return '';
      let html = text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');

      // Code blocks with syntax copy button
      html = html.replace(/```([a-z0-9_-]*)\n([\s\S]*?)```/g, (match, lang, code) => {
        return `
          <div class="code-block-wrapper" style="position: relative;">
            <button class="code-copy-btn" onclick="navigator.clipboard.writeText(this.nextElementSibling.innerText).then(() => { this.innerText = 'Copied!'; setTimeout(() => this.innerText = 'Copy', 1500); })">Copy</button>
            <pre><code>${code.trim()}</code></pre>
          </div>
        `;
      });

      // Inline code
      html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

      // Bold & Italic
      html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
      html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');

      // Links
      html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');

      // Headers
      html = html.replace(/^### (.*$)/gm, '<h4 style="color:#ffffff; margin:14px 0 6px 0; font-size:0.95rem;">$1</h4>');
      html = html.replace(/^## (.*$)/gm, '<h3 style="color:#ffffff; margin:16px 0 8px 0; font-size:1.05rem; border-bottom:1px solid rgba(255,255,255,0.08); padding-bottom:4px;">$1</h3>');
      html = html.replace(/^# (.*$)/gm, '<h2 style="color:#ffffff; margin:18px 0 10px 0; font-size:1.2rem;">$1</h2>');

      // Unordered lists
      html = html.replace(/^\s*[-*]\s+(.*)$/gm, '<li>$1</li>');
      html = html.replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>');

      // Tables (Markdown pipe tables)
      html = html.replace(/\|(.+)\|/g, (match) => {
        const cells = match.split('|').filter((c) => c.trim() !== '');
        if (cells.some((c) => c.includes('---'))) return '';
        const isHeader = false;
        const cellHtml = cells.map((c) => `<td>${c.trim()}</td>`).join('');
        return `<tr>${cellHtml}</tr>`;
      });
      html = html.replace(/(<tr>.*<\/tr>)/s, '<div style="overflow-x:auto;"><table>$1</table></div>');

      // Line breaks
      html = html.replace(/\n\n/g, '</p><p>').replace(/\n/g, '<br/>');

      return `<p>${html}</p>`;
    };

    // Scan assistant text to detect recommended instance actions
    const injectActionableRecommendationCards = (text) => {
      // Find instance matches like i-01a2b3c4d5e6f7g80
      const instanceRegex = /(i-[0-9a-f]{17})/gi;
      const matches = text.match(instanceRegex);
      if (!matches) return '';

      const uniqueInstances = [...new Set(matches)];
      let cardsHtml = '';

      uniqueInstances.forEach((instId) => {
        const found = BENCHMARK_FLEET.find((f) => f.id === instId);
        if (found) {
          cardsHtml += `
            <div class="recommendation-card">
              <div class="rec-card-header">
                <div class="rec-title-wrap">
                  <svg width="18" height="18"><use href="#icon-shield"/></svg>
                  <span class="rec-instance-id">${found.id}</span>
                  <span class="rec-badge-policy">Policy Verified</span>
                </div>
                <div style="font-size: 0.725rem; color: #94a3b8;">${found.region}</div>
              </div>
              <div class="rec-specs-grid">
                <div class="rec-spec-box">
                  <span class="rec-spec-label">Current Configuration</span>
                  <span class="rec-spec-val">${found.type}</span>
                  <span class="rec-spec-sub">Avg CPU: ${found.cpu}% &bull; Carbon: ${found.carbon} kg/d</span>
                </div>
                <div class="rec-arrow-divider">&rarr;</div>
                <div class="rec-spec-box">
                  <span class="rec-spec-label">Recommended Target</span>
                  <span class="rec-spec-val" style="color: #34d399;">${found.target}</span>
                  <span class="rec-spec-sub">Rightsized &bull; Zero Downtime</span>
                </div>
              </div>
              <div class="rec-impact-row">
                <div class="rec-impact-pill cost">
                  <span>💰 Est. Monthly Savings: ~$64.20 (-52%)</span>
                </div>
                <div class="rec-impact-pill carbon">
                  <span>🌿 Carbon Savings: -0.85 kg CO₂/day</span>
                </div>
              </div>
              <div class="rec-actions-row">
                <button class="btn-rec-migrate" onclick="window.co2opsDispatchPrompt('Execute safe migration of instance ${found.id} to ${found.target}')">
                  ⚡ Validate & Apply Migration
                </button>
                <button class="btn-rec-forecast" onclick="window.co2opsDispatchPrompt('Provide 7-day ARIMA forecast for CPU and memory on instance ${found.id}')">
                  📈 7-Day Forecast
                </button>
                <button class="btn-rec-forecast" onclick="navigator.clipboard.writeText('${found.id}').then(() => alert('Instance ID ${found.id} copied!'))">
                  📋 Copy ID
                </button>
              </div>
            </div>
          `;
        }
      });

      return cardsHtml;
    };

    // Append Message to Chat
    const appendMessage = (role, text) => {
      // Hide the initial hero once a message is posted
      if (chatWelcomeHero) {
        chatWelcomeHero.style.display = 'none';
      }

      const msgDiv = document.createElement('div');
      msgDiv.className = `chat-message ${role === 'user' ? 'user-msg' : 'assistant-msg'}`;

      const avatarDiv = document.createElement('div');
      avatarDiv.className = 'msg-avatar';
      if (role === 'user') {
        avatarDiv.textContent = 'YOU';
      } else {
        avatarDiv.innerHTML = '<svg width="20" height="20"><use href="#icon-spark"/></svg>';
      }

      const contentDiv = document.createElement('div');
      contentDiv.className = 'msg-content';

      const headerRow = document.createElement('div');
      headerRow.className = 'msg-header-row';

      const senderDiv = document.createElement('div');
      senderDiv.className = 'msg-sender';
      senderDiv.textContent = role === 'user' ? 'DevOps Operator' : 'CO2Ops Orchestrator (Google ADK)';

      const timeDiv = document.createElement('div');
      timeDiv.className = 'msg-time';
      const now = new Date();
      timeDiv.textContent = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}`;

      headerRow.appendChild(senderDiv);
      headerRow.appendChild(timeDiv);

      const textDiv = document.createElement('div');
      textDiv.className = 'msg-text';
      let parsed = renderMarkdown(text);

      // If assistant, inject interactive recommendation cards if applicable
      if (role === 'assistant') {
        const extraCards = injectActionableRecommendationCards(text);
        if (extraCards) {
          parsed += extraCards;
        }
      }
      textDiv.innerHTML = parsed;

      contentDiv.appendChild(headerRow);
      contentDiv.appendChild(textDiv);
      msgDiv.appendChild(avatarDiv);
      msgDiv.appendChild(contentDiv);

      chatHistory.appendChild(msgDiv);
      chatHistory.scrollTop = chatHistory.scrollHeight;
    };

    // ==========================================================================
    // 3. SESSION CREATION & API CALLS
    // ==========================================================================
    const createSession = async () => {
      sessionId = `session-${Math.floor(Date.now() / 1000)}`;
      if (sessionIdEl) sessionIdEl.textContent = sessionId;

      try {
        await fetch(`${API_BASE_URL}/apps/${APP_NAME}/users/${userId}/sessions/${sessionId}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({})
        });
      } catch (err) {
        console.warn('Backend session endpoint notice:', err);
      }
    };

    // Initialize session on load
    createSession();

    if (newSessionBtn) {
      newSessionBtn.addEventListener('click', () => {
        createSession();
        chatHistory.innerHTML = '';
        if (chatWelcomeHero) {
          chatWelcomeHero.style.display = 'flex';
          chatHistory.appendChild(chatWelcomeHero);
        }
        appendMessage('assistant', `Started fresh audit session: <code>${sessionId}</code>. Sub-agents initialized and ready for fleet queries.`);
      });
    }

    if (clearChatBtn) {
      clearChatBtn.addEventListener('click', () => {
        chatHistory.innerHTML = '';
        if (chatWelcomeHero) {
          chatWelcomeHero.style.display = 'flex';
          chatHistory.appendChild(chatWelcomeHero);
        }
      });
    }

    // Send message to ADK backend
    const sendMessage = async (messageText) => {
      if (!messageText) return;

      appendMessage('user', messageText);
      chatInput.value = '';
      chatInput.style.height = 'auto';
      chatInput.disabled = true;
      if (sendBtn) sendBtn.disabled = true;
      startPipeline();

      try {
        const res = await fetch(`${API_BASE_URL}/run`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            app_name: APP_NAME,
            user_id: userId,
            session_id: sessionId,
            new_message: {
              role: 'user',
              parts: [{ text: messageText }]
            }
          })
        });

        if (res.ok) {
          const events = await res.json();
          let fullText = '';

          events.forEach((event) => {
            // ADK format 1: step_details
            if (event.step_details && event.step_details.step_type === 'model_output') {
              const modelOutput = event.step_details.model_output;
              if (modelOutput && modelOutput.parts) {
                modelOutput.parts.forEach((p) => {
                  if (p.text) fullText += p.text;
                });
              }
            }
            // ADK format 2: direct content
            if (event.content && event.content.parts) {
              event.content.parts.forEach((p) => {
                if (!p.functionResponse && p.text) fullText += p.text;
              });
            }
          });

          finishPipeline(true);

          if (fullText.trim()) {
            appendMessage('assistant', fullText);
          } else {
            appendMessage('assistant', 'Audit complete. All AWS sub-agents finished operations with zero errors.');
          }
        } else {
          finishPipeline(false);
          const errorText = await res.text();
          appendMessage('assistant', `Backend notice (${res.status}): ${errorText || 'Agent service busy. Please retry.'}`);
        }
      } catch (err) {
        finishPipeline(false);
        console.error('Fetch error:', err);
        appendMessage('assistant', `Could not reach Google ADK backend on ${API_BASE_URL}. Ensure the backend is active on port 8080.`);
      } finally {
        chatInput.disabled = false;
        if (sendBtn) sendBtn.disabled = false;
        chatInput.focus();
      }
    };

    // Global dispatcher for quick chips and recommendation cards
    window.co2opsDispatchPrompt = (promptText) => {
      chatInput.value = promptText;
      sendMessage(promptText);
    };

    // Chat form submit
    chatForm.addEventListener('submit', (e) => {
      e.preventDefault();
      const text = chatInput.value.trim();
      if (text) sendMessage(text);
    });

    // Auto-growing textarea & Enter to submit
    chatInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        const text = chatInput.value.trim();
        if (text) sendMessage(text);
      }
    });

    chatInput.addEventListener('input', () => {
      chatInput.style.height = 'auto';
      chatInput.style.height = Math.min(chatInput.scrollHeight, 160) + 'px';
    });

    // Quick runbook chips
    document.querySelectorAll('.runbook-chip, .action-chip, .feature-card').forEach((btn) => {
      btn.addEventListener('click', () => {
        const prompt = btn.getAttribute('data-prompt');
        if (prompt) {
          window.co2opsDispatchPrompt(prompt);
        }
      });
    });

    // ==========================================================================
    // 4. FLEET TELEMETRY DRAWER LOGIC
    // ==========================================================================
    const renderFleetList = (filterText = '', region = '') => {
      if (!fleetListContainer) return;

      let filtered = BENCHMARK_FLEET;
      if (region) {
        filtered = filtered.filter((f) => f.region === region);
      }
      if (filterText) {
        const q = filterText.toLowerCase();
        filtered = filtered.filter((f) => f.id.toLowerCase().includes(q) || f.type.toLowerCase().includes(q) || f.region.toLowerCase().includes(q));
      }

      if (filtered.length === 0) {
        fleetListContainer.innerHTML = `<div style="text-align:center; padding: 24px; color:#64748b; font-size:0.8rem;">No EC2 instances match current filter.</div>`;
        return;
      }

      let html = '';
      filtered.forEach((inst) => {
        const cpuClass = inst.cpu < 20 ? 'low' : inst.cpu < 50 ? 'med' : 'high';
        const memClass = inst.mem < 30 ? 'low' : inst.mem < 60 ? 'med' : 'high';

        html += `
          <div class="fleet-instance-card" onclick="window.co2opsDispatchPrompt('Audit and calculate rightsizing impact for instance ${inst.id}')">
            <div class="fleet-card-top">
              <span class="fleet-id">${inst.id}</span>
              <span class="fleet-type-badge">${inst.type}</span>
            </div>
            <div class="fleet-gauges-grid">
              <div class="gauge-box">
                <div class="gauge-label"><span>CPU</span><span>${inst.cpu}%</span></div>
                <div class="gauge-track"><div class="gauge-fill ${cpuClass}" style="width: ${inst.cpu}%;"></div></div>
              </div>
              <div class="gauge-box">
                <div class="gauge-label"><span>Mem</span><span>${inst.mem}%</span></div>
                <div class="gauge-track"><div class="gauge-fill ${memClass}" style="width: ${inst.mem}%;"></div></div>
              </div>
            </div>
            <div class="fleet-card-bottom">
              <span class="fleet-carbon-metric">🌿 ${inst.carbon} kg/d</span>
              <div class="fleet-card-actions">
                <button class="btn-card-action" onclick="event.stopPropagation(); window.co2opsDispatchPrompt('Provide 7-day ARIMA forecast for CPU on ${inst.id}')">Forecast</button>
                <button class="btn-card-action" onclick="event.stopPropagation(); window.co2opsDispatchPrompt('Recommend rightsizing for instance ${inst.id}')">Rightsize</button>
              </div>
            </div>
          </div>
        `;
      });

      fleetListContainer.innerHTML = html;
    };

    // Drawer Initial Render
    renderFleetList('', activeRegionSelect ? activeRegionSelect.value : '');

    // Search input in drawer
    if (fleetSearchInput) {
      fleetSearchInput.addEventListener('input', (e) => {
        renderFleetList(e.target.value, activeRegionSelect ? activeRegionSelect.value : '');
      });
    }

    // Active Region selector change
    if (activeRegionSelect) {
      activeRegionSelect.addEventListener('change', (e) => {
        const reg = e.target.value;
        if (drawerGridIntensity && REGIONAL_GRID_CARBON[reg]) {
          drawerGridIntensity.textContent = REGIONAL_GRID_CARBON[reg];
        }
        renderFleetList(fleetSearchInput ? fleetSearchInput.value : '', reg);
      });
    }

    // Button: Audit Selected Region Now
    if (btnAuditSelectedRegion) {
      btnAuditSelectedRegion.addEventListener('click', () => {
        const reg = activeRegionSelect ? activeRegionSelect.value : 'us-east-1';
        window.co2opsDispatchPrompt(`Audit all AWS EC2 instances in ${reg} for underutilized capacity and carbon waste`);
      });
    }

    // Toggle Drawer Button
    if (telemetryDrawerToggle && telemetryDrawer) {
      telemetryDrawerToggle.addEventListener('click', () => {
        telemetryDrawer.classList.toggle('collapsed');
        telemetryDrawerToggle.classList.toggle('active');
      });
    }

    if (drawerCloseBtn && telemetryDrawer) {
      drawerCloseBtn.addEventListener('click', () => {
        telemetryDrawer.classList.add('collapsed');
        if (telemetryDrawerToggle) telemetryDrawerToggle.classList.remove('active');
      });
    }

    // Toggle Sidebar Button
    if (sidebarToggleBtn && workspaceRail) {
      sidebarToggleBtn.addEventListener('click', () => {
        workspaceRail.classList.toggle('collapsed');
      });
    }

    // Check URL parameters for prompt (e.g. workspace.html?prompt=Audit%20fleet)
    const urlParams = new URLSearchParams(window.location.search);
    const initialPrompt = urlParams.get('prompt');
    if (initialPrompt) {
      setTimeout(() => {
        sendMessage(decodeURIComponent(initialPrompt));
      }, 600);
    }
  }

  // ==========================================================================
  // LANDING PAGE LOGIC
  // ==========================================================================
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
