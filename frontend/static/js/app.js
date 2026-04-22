/**
 * VKS AI Platform - Frontend Application
 * Handles auth, chat, API keys, usage stats
 */

// ============ STATE ============
const state = {
  adminToken: localStorage.getItem('vks_admin_token') || null,
  currentPage: 'chat',
  messages: [],
  isGenerating: false,
  models: [],
  apiKeys: [],
  settings: {
    model: '',
    temperature: 0.3,
    topP: 0.8,
    maxTokens: 4096,
    systemPrompt: 'Bạn là "Trợ lý Pháp luật VKS" - hệ thống AI hỗ trợ cán bộ Viện kiểm sát nhân dân Việt Nam. Chỉ trích dẫn điều luật cụ thể, không bịa. Sử dụng tiếng Việt pháp lý chuyên nghiệp.',
    stream: true
  }
};

// ============ API HELPERS ============
const API_BASE = window.location.origin;

async function apiCall(endpoint, options = {}) {
  const headers = { 'Content-Type': 'application/json', ...options.headers };
  if (state.adminToken) headers['Authorization'] = `Bearer ${state.adminToken}`;
  
  const res = await fetch(`${API_BASE}${endpoint}`, { ...options, headers });
  if (res.status === 401) { logout(); throw new Error('Session expired'); }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: { message: 'Request failed' } }));
    throw new Error(err.error?.message || 'Request failed');
  }
  return res;
}

// ============ AUTH ============
async function login() {
  const username = document.getElementById('login-username').value;
  const password = document.getElementById('login-password').value;
  const errorEl = document.getElementById('login-error');
  
  try {
    const res = await fetch(`${API_BASE}/api/admin/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password })
    });
    
    if (!res.ok) {
      errorEl.textContent = 'Sai tên đăng nhập hoặc mật khẩu';
      errorEl.style.display = 'block';
      return;
    }
    
    const data = await res.json();
    state.adminToken = data.access_token;
    localStorage.setItem('vks_admin_token', data.access_token);
    showApp();
    toast('Đăng nhập thành công!', 'success');
  } catch (e) {
    errorEl.textContent = 'Không thể kết nối server';
    errorEl.style.display = 'block';
  }
}

function logout() {
  state.adminToken = null;
  localStorage.removeItem('vks_admin_token');
  showLogin();
}

function showLogin() {
  document.getElementById('login-screen').style.display = 'flex';
  document.getElementById('app-screen').style.display = 'none';
}

function showApp() {
  document.getElementById('login-screen').style.display = 'none';
  document.getElementById('app-screen').style.display = 'flex';
  loadModels();
  checkHealth();
  navigateTo('chat');
}

// ============ NAVIGATION ============
function navigateTo(page) {
  state.currentPage = page;
  document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
  document.querySelector(`[data-page="${page}"]`)?.classList.add('active');
  document.querySelectorAll('.page').forEach(el => el.classList.remove('active'));
  document.getElementById(`page-${page}`)?.classList.add('active');
  
  if (page === 'keys') loadApiKeys();
  if (page === 'usage') loadUsageStats();
  if (page === 'docs') renderDocs();
}

// ============ MODELS ============
async function loadModels() {
  try {
    const res = await apiCall('/api/admin/models');
    const data = await res.json();
    state.models = data.data || [];
    
    const select = document.getElementById('model-select');
    select.innerHTML = '';
    state.models.forEach(m => {
      const opt = document.createElement('option');
      opt.value = m.id;
      opt.textContent = `${m.id} (${m.size || 'N/A'})`;
      select.appendChild(opt);
    });
    
    if (state.models.length > 0) {
      state.settings.model = state.models[0].id;
      select.value = state.settings.model;
    }
  } catch (e) {
    console.error('Failed to load models:', e);
  }
}

// ============ HEALTH ============
async function checkHealth() {
  try {
    const res = await fetch(`${API_BASE}/api/admin/health`);
    const data = await res.json();
    
    const badge = document.getElementById('status-badge');
    if (data.ollama_connected) {
      badge.className = 'status-badge online';
      badge.innerHTML = '<span class="status-dot"></span> Ollama Online';
    } else {
      badge.className = 'status-badge offline';
      badge.innerHTML = '<span class="status-dot"></span> Ollama Offline';
    }
  } catch (e) {
    const badge = document.getElementById('status-badge');
    badge.className = 'status-badge offline';
    badge.innerHTML = '<span class="status-dot"></span> Server Offline';
  }
}

// ============ CHAT ============
async function sendMessage() {
  const input = document.getElementById('chat-input');
  const text = input.value.trim();
  if (!text || state.isGenerating) return;
  
  // Add user message
  state.messages.push({ role: 'user', content: text });
  renderMessages();
  input.value = '';
  autoResize(input);
  
  state.isGenerating = true;
  updateSendButton();
  
  // Build messages array
  const messages = [];
  if (state.settings.systemPrompt) {
    messages.push({ role: 'system', content: state.settings.systemPrompt });
  }
  messages.push(...state.messages);
  
  // Get the first available API key for testing, or use admin token
  let apiKey = null;
  try {
    const keysRes = await apiCall('/api/keys');
    const keysData = await keysRes.json();
    const activeKey = keysData.keys?.find(k => k.is_active && k.key);
    if (activeKey) apiKey = activeKey.key;
  } catch (e) { /* ignore */ }
  
  const headers = { 'Content-Type': 'application/json' };
  
  // For playground, we need an API key. Create one if none exists.
  if (!apiKey) {
    try {
      const createRes = await apiCall('/api/keys', {
        method: 'POST',
        body: JSON.stringify({ name: 'Playground Key', rate_limit: 60 })
      });
      const newKey = await createRes.json();
      apiKey = newKey.key;
      localStorage.setItem('vks_playground_key', apiKey);
    } catch (e) {
      toast('Không thể tạo API key cho playground', 'error');
      state.isGenerating = false;
      updateSendButton();
      return;
    }
  }
  
  // Use stored playground key if available
  if (!apiKey) apiKey = localStorage.getItem('vks_playground_key');
  
  headers['Authorization'] = `Bearer ${apiKey}`;
  
  if (state.settings.stream) {
    await streamChat(messages, headers);
  } else {
    await normalChat(messages, headers);
  }
  
  state.isGenerating = false;
  updateSendButton();
}

async function streamChat(messages, headers) {
  const startTime = Date.now();
  
  try {
    const res = await fetch(`${API_BASE}/v1/chat/completions`, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        model: state.settings.model,
        messages,
        temperature: state.settings.temperature,
        top_p: state.settings.topP,
        max_tokens: state.settings.maxTokens,
        stream: true
      })
    });
    
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error?.message || `Error ${res.status}`);
    }
    
    // Add assistant message placeholder
    state.messages.push({ role: 'assistant', content: '', thinking: true });
    renderMessages();
    
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let fullContent = '';
    
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop();
      
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        const data = line.slice(6).trim();
        if (data === '[DONE]') continue;
        
        try {
          const parsed = JSON.parse(data);
          if (parsed.error) { throw new Error(parsed.error.message); }
          const delta = parsed.choices?.[0]?.delta?.content || '';
          fullContent += delta;
          
          // Update last message
          const lastMsg = state.messages[state.messages.length - 1];
          lastMsg.content = fullContent;
          lastMsg.thinking = false;
          renderMessages(false);
          scrollToBottom();
        } catch (e) { if (e.message !== 'Unexpected end of JSON input') console.warn(e); }
      }
    }
    
    // Set timing
    const elapsed = Date.now() - startTime;
    const lastMsg = state.messages[state.messages.length - 1];
    lastMsg.time_ms = elapsed;
    lastMsg.thinking = false;
    renderMessages(false);
    scrollToBottom();
    
  } catch (e) {
    state.messages.push({ role: 'assistant', content: `❌ Lỗi: ${e.message}` });
    renderMessages();
  }
}

async function normalChat(messages, headers) {
  try {
    const startTime = Date.now();
    const res = await fetch(`${API_BASE}/v1/chat/completions`, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        model: state.settings.model,
        messages,
        temperature: state.settings.temperature,
        top_p: state.settings.topP,
        max_tokens: state.settings.maxTokens,
        stream: false
      })
    });
    
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error?.message || `Error ${res.status}`);
    }
    
    const data = await res.json();
    const elapsed = Date.now() - startTime;
    const content = data.choices?.[0]?.message?.content || 'No response';
    
    state.messages.push({
      role: 'assistant',
      content,
      time_ms: elapsed,
      usage: data.usage
    });
    renderMessages();
    
  } catch (e) {
    state.messages.push({ role: 'assistant', content: `❌ Lỗi: ${e.message}` });
    renderMessages();
  }
}

function renderMessages(scroll = true) {
  const container = document.getElementById('chat-messages');
  const emptyState = document.getElementById('empty-state');
  
  if (state.messages.length === 0) {
    emptyState.style.display = 'flex';
    container.innerHTML = '';
    return;
  }
  
  emptyState.style.display = 'none';
  
  container.innerHTML = state.messages.map((msg, i) => {
    const avatar = msg.role === 'user' ? '👤' : '🤖';
    const roleName = msg.role === 'user' ? 'Bạn' : 'Trợ lý VKS';
    
    let metaHtml = '';
    if (msg.time_ms) {
      metaHtml += `<span>⏱️ ${(msg.time_ms / 1000).toFixed(1)}s</span>`;
    }
    if (msg.usage) {
      metaHtml += `<span>📊 ${msg.usage.total_tokens} tokens</span>`;
    }
    
    let contentHtml = msg.content;
    if (msg.thinking && !msg.content) {
      contentHtml = `<div class="thinking-indicator"><div class="thinking-dots"><span></span><span></span><span></span></div> Đang suy nghĩ...</div>`;
    } else {
      contentHtml = formatMarkdown(msg.content);
    }
    
    return `
      <div class="message ${msg.role}">
        <div class="message-avatar">${avatar}</div>
        <div class="message-content">
          <div class="role">${roleName}</div>
          <div class="text">${contentHtml}</div>
          ${metaHtml ? `<div class="message-meta">${metaHtml}</div>` : ''}
        </div>
      </div>
    `;
  }).join('');
  
  if (scroll) scrollToBottom();
}

function formatMarkdown(text) {
  if (!text) return '';
  // Basic markdown: code blocks, inline code, bold, italic
  return text
    .replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/\*([^*]+)\*/g, '<em>$1</em>')
    .replace(/\n/g, '<br>');
}

function scrollToBottom() {
  const container = document.getElementById('chat-messages');
  container.scrollTop = container.scrollHeight;
}

function clearChat() {
  state.messages = [];
  renderMessages();
}

function updateSendButton() {
  const btn = document.getElementById('send-btn');
  btn.disabled = state.isGenerating;
  btn.innerHTML = state.isGenerating ? '⏳' : '➤';
}

// ============ API KEYS ============
async function loadApiKeys() {
  try {
    const res = await apiCall('/api/keys');
    const data = await res.json();
    state.apiKeys = data.keys || [];
    renderApiKeys();
  } catch (e) {
    toast('Không thể tải danh sách API keys', 'error');
  }
}

function renderApiKeys() {
  const tbody = document.getElementById('keys-tbody');
  if (!tbody) return;
  
  if (state.apiKeys.length === 0) {
    tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:var(--text-muted);padding:40px;">Chưa có API key nào. Nhấn "Tạo Key Mới" để bắt đầu.</td></tr>';
    return;
  }
  
  tbody.innerHTML = state.apiKeys.map(key => `
    <tr>
      <td><strong>${key.name}</strong><br><span style="font-size:11px;color:var(--text-muted)">${key.description || ''}</span></td>
      <td><span class="key-preview">${key.key_preview}</span></td>
      <td><span class="badge ${key.is_active ? 'active' : 'revoked'}">${key.is_active ? 'Hoạt động' : 'Đã thu hồi'}</span></td>
      <td>${key.total_requests || 0}</td>
      <td>${key.last_used ? new Date(key.last_used).toLocaleString('vi-VN') : 'Chưa sử dụng'}</td>
      <td>
        ${key.is_active ? `<button class="btn btn-danger btn-sm" onclick="revokeKey('${key.id}')">Thu hồi</button>` : ''}
      </td>
    </tr>
  `).join('');
}

async function createApiKey() {
  const name = document.getElementById('new-key-name').value.trim();
  const desc = document.getElementById('new-key-desc').value.trim();
  const rateLimit = parseInt(document.getElementById('new-key-rate').value) || 30;
  
  if (!name) { toast('Vui lòng nhập tên API key', 'error'); return; }
  
  try {
    const res = await apiCall('/api/keys', {
      method: 'POST',
      body: JSON.stringify({ name, description: desc, rate_limit: rateLimit })
    });
    const data = await res.json();
    
    // Show the key (only shown once!)
    showNewKeyModal(data.key);
    
    document.getElementById('new-key-name').value = '';
    document.getElementById('new-key-desc').value = '';
    closeModal('create-key-modal');
    loadApiKeys();
    toast('API key đã được tạo thành công!', 'success');
  } catch (e) {
    toast(`Lỗi: ${e.message}`, 'error');
  }
}

function showNewKeyModal(key) {
  const modal = document.getElementById('show-key-modal');
  document.getElementById('new-key-value').textContent = key;
  modal.classList.remove('hidden');
}

async function revokeKey(keyId) {
  if (!confirm('Bạn có chắc muốn thu hồi API key này? Hành động này không thể hoàn tác.')) return;
  
  try {
    await apiCall(`/api/keys/${keyId}`, { method: 'DELETE' });
    toast('API key đã được thu hồi', 'success');
    loadApiKeys();
  } catch (e) {
    toast(`Lỗi: ${e.message}`, 'error');
  }
}

function copyKey(elementId) {
  const text = document.getElementById(elementId).textContent;
  navigator.clipboard.writeText(text).then(() => toast('Đã copy!', 'success'));
}

// ============ USAGE STATS ============
async function loadUsageStats() {
  try {
    const res = await apiCall('/api/admin/usage');
    const data = await res.json();
    renderUsageStats(data);
  } catch (e) {
    toast('Không thể tải thống kê', 'error');
  }
}

function renderUsageStats(data) {
  document.getElementById('stat-total-requests').textContent = data.total_requests?.toLocaleString() || '0';
  document.getElementById('stat-total-tokens').textContent = data.total_tokens?.toLocaleString() || '0';
  document.getElementById('stat-today-requests').textContent = data.requests_today?.toLocaleString() || '0';
  document.getElementById('stat-avg-response').textContent = `${Math.round(data.avg_response_time_ms || 0)}ms`;
  
  // Key stats table
  const keyStatsBody = document.getElementById('key-stats-tbody');
  if (keyStatsBody && data.key_stats) {
    keyStatsBody.innerHTML = data.key_stats.map(k => `
      <tr>
        <td>${k.key_name}</td>
        <td>${k.requests?.toLocaleString()}</td>
        <td>${k.tokens?.toLocaleString()}</td>
      </tr>
    `).join('') || '<tr><td colspan="3" style="text-align:center;color:var(--text-muted)">Chưa có dữ liệu</td></tr>';
  }
}

// ============ DOCS ============
function renderDocs() {
  const baseUrl = window.location.origin;
  const docsContainer = document.getElementById('docs-content');
  if (!docsContainer) return;
  
  docsContainer.innerHTML = `
    <div class="page-header">
      <h2>📚 API Documentation</h2>
      <p>OpenAI-compatible API. Sử dụng bất kỳ OpenAI SDK nào để kết nối.</p>
    </div>
    
    <h3 style="margin-bottom:12px;">Base URL</h3>
    <div class="code-block" style="margin-bottom:24px;border-radius:var(--radius-sm);">${baseUrl}</div>
    
    <h3 style="margin-bottom:12px;">Authentication</h3>
    <p style="color:var(--text-secondary);margin-bottom:16px;">Thêm API key vào header <code>Authorization: Bearer vks-xxx</code> hoặc <code>X-API-Key: vks-xxx</code></p>
    
    <h3 style="margin-bottom:12px;">Chat Completions</h3>
    <div class="code-tabs">
      <button class="code-tab active" onclick="showCodeTab(this, 'curl-code')">cURL</button>
      <button class="code-tab" onclick="showCodeTab(this, 'python-code')">Python</button>
      <button class="code-tab" onclick="showCodeTab(this, 'js-code')">JavaScript</button>
    </div>
    
    <div id="curl-code" class="code-block" style="display:block;">curl ${baseUrl}/v1/chat/completions \\
  -H "Authorization: Bearer vks-YOUR_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "model": "${state.settings.model || 'qwen3:30b-a3b'}",
    "messages": [
      {"role": "system", "content": "Bạn là trợ lý pháp luật VKS"},
      {"role": "user", "content": "Giải thích Điều 173 BLHS 2015"}
    ],
    "temperature": 0.3,
    "stream": false
  }'<button class="copy-btn" onclick="copyCode('curl-code')">Copy</button></div>
    
    <div id="python-code" class="code-block" style="display:none;">from openai import OpenAI

client = OpenAI(
    api_key="vks-YOUR_KEY",
    base_url="${baseUrl}/v1"
)

response = client.chat.completions.create(
    model="${state.settings.model || 'qwen3:30b-a3b'}",
    messages=[
        {"role": "system", "content": "Bạn là trợ lý pháp luật VKS"},
        {"role": "user", "content": "Giải thích Điều 173 BLHS 2015"}
    ],
    temperature=0.3
)

print(response.choices[0].message.content)<button class="copy-btn" onclick="copyCode('python-code')">Copy</button></div>
    
    <div id="js-code" class="code-block" style="display:none;">const response = await fetch("${baseUrl}/v1/chat/completions", {
  method: "POST",
  headers: {
    "Authorization": "Bearer vks-YOUR_KEY",
    "Content-Type": "application/json"
  },
  body: JSON.stringify({
    model: "${state.settings.model || 'qwen3:30b-a3b'}",
    messages: [
      { role: "system", content: "Bạn là trợ lý pháp luật VKS" },
      { role: "user", content: "Giải thích Điều 173 BLHS 2015" }
    ],
    temperature: 0.3
  })
});

const data = await response.json();
console.log(data.choices[0].message.content);<button class="copy-btn" onclick="copyCode('js-code')">Copy</button></div>

    <h3 style="margin:24px 0 12px;">Endpoints</h3>
    <table class="keys-table">
      <thead><tr><th>Method</th><th>Endpoint</th><th>Mô tả</th><th>Auth</th></tr></thead>
      <tbody>
        <tr><td><span class="badge active">POST</span></td><td><code>/v1/chat/completions</code></td><td>Chat completion (streaming + non-streaming)</td><td>API Key</td></tr>
        <tr><td><span class="badge active">GET</span></td><td><code>/v1/models</code></td><td>Danh sách models</td><td>Không</td></tr>
        <tr><td><span class="badge" style="background:rgba(99,102,241,0.1);color:var(--accent)">POST</span></td><td><code>/api/admin/login</code></td><td>Đăng nhập admin</td><td>Không</td></tr>
        <tr><td><span class="badge" style="background:rgba(99,102,241,0.1);color:var(--accent)">GET</span></td><td><code>/api/keys</code></td><td>Danh sách API keys</td><td>Admin</td></tr>
        <tr><td><span class="badge" style="background:rgba(99,102,241,0.1);color:var(--accent)">POST</span></td><td><code>/api/keys</code></td><td>Tạo API key mới</td><td>Admin</td></tr>
        <tr><td><span class="badge revoked">DELETE</span></td><td><code>/api/keys/:id</code></td><td>Thu hồi API key</td><td>Admin</td></tr>
        <tr><td><span class="badge" style="background:rgba(99,102,241,0.1);color:var(--accent)">GET</span></td><td><code>/api/admin/usage</code></td><td>Thống kê sử dụng</td><td>Admin</td></tr>
        <tr><td><span class="badge" style="background:rgba(99,102,241,0.1);color:var(--accent)">GET</span></td><td><code>/api/admin/health</code></td><td>Health check</td><td>Không</td></tr>
      </tbody>
    </table>
  `;
}

function showCodeTab(btn, codeId) {
  btn.parentElement.querySelectorAll('.code-tab').forEach(t => t.classList.remove('active'));
  btn.classList.add('active');
  ['curl-code', 'python-code', 'js-code'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.style.display = id === codeId ? 'block' : 'none';
  });
}

function copyCode(elementId) {
  const el = document.getElementById(elementId);
  const text = el.textContent.replace('Copy', '').trim();
  navigator.clipboard.writeText(text).then(() => toast('Đã copy!', 'success'));
}

// ============ MODALS ============
function openModal(id) { document.getElementById(id).classList.remove('hidden'); }
function closeModal(id) { document.getElementById(id).classList.add('hidden'); }

// ============ TOAST ============
function toast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  const icons = { success: '✅', error: '❌', info: 'ℹ️' };
  el.innerHTML = `${icons[type] || ''} ${message}`;
  container.appendChild(el);
  setTimeout(() => { el.style.opacity = '0'; setTimeout(() => el.remove(), 300); }, 3000);
}

// ============ UTILS ============
function autoResize(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 150) + 'px';
}

function useSuggestion(text) {
  document.getElementById('chat-input').value = text;
  sendMessage();
}

function updateSetting(key, value) {
  if (key === 'temperature' || key === 'topP') value = parseFloat(value);
  if (key === 'maxTokens') value = parseInt(value);
  state.settings[key] = value;
  
  const display = document.getElementById(`${key}-value`);
  if (display) display.textContent = value;
}

// ============ INIT ============
document.addEventListener('DOMContentLoaded', () => {
  // Check if logged in
  if (state.adminToken) {
    showApp();
  } else {
    showLogin();
  }
  
  // Chat input handlers
  const chatInput = document.getElementById('chat-input');
  if (chatInput) {
    chatInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });
    chatInput.addEventListener('input', () => autoResize(chatInput));
  }
  
  // Login form handler
  const loginForm = document.getElementById('login-form');
  if (loginForm) {
    loginForm.addEventListener('submit', (e) => { e.preventDefault(); login(); });
  }
  
  // Health check interval
  setInterval(checkHealth, 30000);
});
