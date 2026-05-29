function formatTime(ts) {
  if (!ts) return '-';
  const d = new Date(ts);
  return d.toLocaleString('zh-CN', { hour12: false });
}

function getStatusLabel(status) {
  if (!status) return { text: '未知', cls: '' };
  if (status === 'success') return { text: '✅ 正常', cls: 'success' };
  return { text: '❌ 失败', cls: 'error' };
}

function getHealthLabel(status, accountStatus) {
  if (!status) return { text: '❓ 未知', cls: '' };
  if (status === 'ok') return { text: '✅ 正常', cls: 'success' };
  if (status === 'degraded') {
    const detail = accountStatus ? ` (${accountStatus})` : '';
    return { text: `⚠️ 异常${detail}`, cls: 'warning' };
  }
  return { text: `❌ ${status}`, cls: 'error' };
}

function extractShortStatus(accountStatus) {
  if (!accountStatus) return '';
  return accountStatus.split('(')[0].trim();
}

async function refreshDisplay() {
  const config = await chrome.storage.sync.get(['serverUrl', 'autoPushEnabled']);
  const status = await chrome.storage.local.get([
    'lastPushTime',
    'lastPushStatus',
    'lastAccountStatus',
    'lastError',
    'lastCookieCount',
  ]);

  document.getElementById('serverDisplay').textContent =
    config.serverUrl || '未配置';

  document.getElementById('lastPushDisplay').textContent =
    formatTime(status.lastPushTime);

  const label = getStatusLabel(status.lastPushStatus);
  const statusEl = document.getElementById('statusDisplay');
  statusEl.textContent = label.text;
  statusEl.className = `value ${label.cls}`;

  const errorEl = document.getElementById('errorMsg');
  if (status.lastPushStatus === 'error' && status.lastError) {
    errorEl.textContent = `错误: ${status.lastError}`;
  } else {
    errorEl.textContent = '';
  }

  // Toggle
  const toggle = document.getElementById('autoToggle');
  toggle.checked = config.autoPushEnabled !== false;

  // Debug info
  document.getElementById('cookieCount').textContent =
    status.lastCookieCount != null ? String(status.lastCookieCount) : '-';

  // Server health
  const healthEl = document.getElementById('healthDisplay');
  if (config.serverUrl) {
    try {
      const url = config.serverUrl.replace(/\/+$/, '') + '/health';
      const resp = await fetch(url, { signal: AbortSignal.timeout(3000) });
      if (resp.ok) {
        const data = await resp.json();
        const shortStatus = extractShortStatus(data.account_status);
        const hl = getHealthLabel(data.status, shortStatus);
        healthEl.textContent = hl.text;
        healthEl.className = `value ${hl.cls}`;
      } else {
        healthEl.textContent = `❌ HTTP ${resp.status}`;
        healthEl.className = 'value error';
      }
    } catch (err) {
      healthEl.textContent = '❌ 连接失败';
      healthEl.className = 'value error';
    }
  } else {
    healthEl.textContent = '未配置';
    healthEl.className = 'value';
  }
}

// Push button
document.getElementById('pushBtn').addEventListener('click', async () => {
  const btn = document.getElementById('pushBtn');
  btn.disabled = true;
  btn.textContent = '推送中...';

  const result = await chrome.runtime.sendMessage({ action: 'pushNow' });
  await refreshDisplay();

  btn.disabled = false;
  btn.textContent = '立即推送';
});

// Auto-push toggle
document.getElementById('autoToggle').addEventListener('change', async (e) => {
  await chrome.storage.sync.set({ autoPushEnabled: e.target.checked });
  console.log('[Popup] Auto-push:', e.target.checked ? 'enabled' : 'disabled');
});

// Copy last pushed cookies
document.getElementById('copyBtn').addEventListener('click', async () => {
  const { lastCookiesJson } = await chrome.storage.local.get(['lastCookiesJson']);
  if (!lastCookiesJson) {
    document.getElementById('copyStatus').textContent = '暂无数据';
    return;
  }
  await navigator.clipboard.writeText(lastCookiesJson);
  const el = document.getElementById('copyStatus');
  el.textContent = '✅ 已复制';
  setTimeout(() => { el.textContent = ''; }, 2000);
});

refreshDisplay();
