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

// Load config + status
async function refreshDisplay() {
  const config = await chrome.storage.sync.get(['serverUrl']);
  const status = await chrome.storage.local.get([
    'lastPushTime',
    'lastPushStatus',
    'lastAccountStatus',
    'lastError',
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
    errorEl.textContent = `上次错误: ${status.lastError}`;
  } else {
    errorEl.textContent = '';
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

// Initial load
refreshDisplay();
