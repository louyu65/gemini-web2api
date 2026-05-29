/**
 * Gemini Cookie Sync — Background Service Worker
 *
 * Push triggers:
 *   1. __Secure-1PSID 发生变化 (onChanged 事件) → 立即推 (防抖 2s)
 *   2. 健康检查 degraded + cookie 变了 → 推
 *   3. 每 30 分钟兜底 → cookie 变了才推
 *
 * 节流逻辑:
 *   - 如果 cookie 内容和上次成功推送完全一致 → 跳过 (不浪费请求)
 *   - 健康检查 degraded 但 cookie 没变 → 等用户重新登录
 */

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------
const PUSH_ALARM = 'gemini-cookie-push';
const PUSH_INTERVAL_MINUTES = 30;

const HEALTH_ALARM = 'gemini-health-check';
const HEALTH_INTERVAL_MINUTES = 1;

const DEBOUNCE_MS = 2000;

// ---------------------------------------------------------------------------
// State (in-memory only, not persisted)
// ---------------------------------------------------------------------------
let lastPushedCookieHash = '';      // hash of last SUCCESSFULLY pushed cookies
let lastPushAttemptTime = 0;        // timestamp of last pushCookies() call
const MIN_PUSH_INTERVAL_MS = 30000; // 30s minimum between pushes with same cookies

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Build a stable hash string from a cookie dict (sorted keys). */
function cookieHash(cookies) {
  return Object.keys(cookies)
    .sort()
    .map(k => `${k}=${cookies[k]}`)
    .join('&');
}

/** Summarize cookies for debug logging (partial values). */
function summarizeCookies(cookies) {
  const names = Object.keys(cookies).sort();
  const psid = cookies['__Secure-1PSID'] || '';
  const psidts = cookies['__Secure-1PSIDTS'] || '';
  return {
    names,
    psidPrefix: psid.slice(0, 10) + '...' + psid.slice(-4),
    psidtsPrefix: psidts ? psidts.slice(0, 10) + '...' + psidts.slice(-4) : '(none)',
    count: names.length,
  };
}

// ---------------------------------------------------------------------------
// Push logic
// ---------------------------------------------------------------------------

async function pushCookies(options = {}) {
  const { force = false } = options;

  // Check pause state (manual push with force bypasses pause)
  if (!force) {
    const { autoPushEnabled } = await chrome.storage.sync.get(['autoPushEnabled']);
    if (autoPushEnabled === false) {
      console.log('[Push] Auto-push is paused — skipping');
      return { success: true, skipped: true, reason: 'paused' };
    }
  }

  const { serverUrl, authToken } = await chrome.storage.sync.get([
    'serverUrl',
    'authToken',
  ]);

  if (!serverUrl || !authToken) {
    console.log('[GeminiCookieSync] Server URL or token not configured');
    return { success: false, error: 'not configured' };
  }

  const url = serverUrl.replace(/\/+$/, '') + '/v1/extension/refresh-cookie';

  // Read ALL google.com cookies
  const allCookies = await chrome.cookies.getAll({ domain: 'google.com' });
  const cookies = {};
  for (const c of allCookies) {
    if (!c.value) continue;
    cookies[c.name] = c.value;
  }

  if (!cookies['__Secure-1PSID']) {
    console.log('[Push] __Secure-1PSID not found — not logged in');
    return { success: false, error: '__Secure-1PSID not found — not logged in?' };
  }

  // Dedup: skip if cookies haven't changed since last successful push
  const hash = cookieHash(cookies);
  const now = Date.now();
  if (!force && hash === lastPushedCookieHash) {
    console.log('[Push] Skipped: cookies unchanged since last successful push');
    return { success: true, skipped: true, reason: 'unchanged' };
  }

  // Throttle: don't push too frequently with same cookies
  if (!force && hash !== lastPushedCookieHash && (now - lastPushAttemptTime) < MIN_PUSH_INTERVAL_MS) {
    console.log('[Push] Throttled: too soon since last attempt');
    return { success: true, skipped: true, reason: 'throttled' };
  }

  // Debug log
  const summary = summarizeCookies(cookies);
  console.log('[Push] Sending cookies:', JSON.stringify(summary, null, 2));

  lastPushAttemptTime = now;

  try {
    const resp = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${authToken}`,
      },
      body: JSON.stringify({ cookies }),
    });

    const text = await resp.text();

    if (!resp.ok) {
      console.error('[Push] Server returned', resp.status, text);
      return { success: false, error: `HTTP ${resp.status}: ${text}` };
    }

    let data;
    try { data = JSON.parse(text); } catch { data = {}; }

    // Mark success — only update hash on successful push
    lastPushedCookieHash = hash;

    await chrome.storage.local.set({
      lastPushTime: now,
      lastPushStatus: 'success',
      lastAccountStatus: data.account_status || 'unknown',
      lastCookieCount: summary.count,
      lastCookieNames: summary.names.join(', '),
      lastCookiesJson: JSON.stringify(cookies, null, 2),
    });

    console.log('[Push] Succeeded, account_status:', data.account_status, '| cookies pushed:', summary.count);
    return { success: true, account_status: data.account_status };
  } catch (err) {
    await chrome.storage.local.set({
      lastPushTime: Date.now(),
      lastPushStatus: 'error',
      lastError: err.message,
    });
    console.error('[Push] Failed:', err.message);
    return { success: false, error: err.message };
  }
}

// ---------------------------------------------------------------------------
// Health check — only push if degraded AND cookies have changed
// ---------------------------------------------------------------------------

async function checkHealthAndPush() {
  const { serverUrl, autoPushEnabled } = await chrome.storage.sync.get(['serverUrl', 'autoPushEnabled']);
  if (!serverUrl) return;
  if (autoPushEnabled === false) return;

  const url = serverUrl.replace(/\/+$/, '') + '/health';

  try {
    const resp = await fetch(url, { signal: AbortSignal.timeout(5000) });
    if (!resp.ok) return;

    const data = await resp.json();
    const status = (data.status || '').toLowerCase();
    const accountStatus = (data.account_status || '').toLowerCase();

    if (status !== 'degraded' && !accountStatus.includes('unauthenticated')) {
      return; // all good
    }

    // Degraded — check if browser cookies have changed
    const allCookies = await chrome.cookies.getAll({ domain: 'google.com' });
    const cookies = {};
    for (const c of allCookies) {
      if (!c.value) continue;
      cookies[c.name] = c.value;
    }

    const hash = cookieHash(cookies);
    if (hash === lastPushedCookieHash) {
      console.log('[Health] Degraded (' + accountStatus + ') but cookies unchanged — waiting for user re-login');
      return;
    }

    // Cookies changed since last successful push — try pushing
    console.log('[Health] Degraded but cookies differ — pushing');
    await pushCookies();
  } catch (err) {
    console.log('[Health] Check failed:', err.message);
  }
}

// ---------------------------------------------------------------------------
// Debounce helper for onChanged events
// ---------------------------------------------------------------------------

let debounceTimer = null;

function debouncedPush() {
  if (debounceTimer) clearTimeout(debounceTimer);
  debounceTimer = setTimeout(async () => {
    debounceTimer = null;
    const { autoPushEnabled } = await chrome.storage.sync.get(['autoPushEnabled']);
    if (autoPushEnabled === false) {
      console.log('[Event] Auto-push is paused — ignoring cookie change');
      return;
    }
    pushCookies();
  }, DEBOUNCE_MS);
}

// ---------------------------------------------------------------------------
// Cookie change listener — instant sync after login
// ---------------------------------------------------------------------------

chrome.cookies.onChanged.addListener((changeInfo) => {
  if (changeInfo.removed) return;

  const name = changeInfo.cookie.name;
  const domain = changeInfo.cookie.domain;

  if (name === '__Secure-1PSID' && domain && domain.includes('google')) {
    console.log('[Event] __Secure-1PSID changed, scheduling push');
    debouncedPush();
  }
});

// ---------------------------------------------------------------------------
// Alarm handlers
// ---------------------------------------------------------------------------

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === PUSH_ALARM) {
    console.log('[Alarm] Periodic push (30min)');
    pushCookies();
  } else if (alarm.name === HEALTH_ALARM) {
    checkHealthAndPush();
  }
});

// ---------------------------------------------------------------------------
// Installation
// ---------------------------------------------------------------------------

chrome.runtime.onInstalled.addListener((details) => {
  chrome.alarms.create(PUSH_ALARM, { periodInMinutes: PUSH_INTERVAL_MINUTES });
  chrome.alarms.create(HEALTH_ALARM, { periodInMinutes: HEALTH_INTERVAL_MINUTES });

  if (details.reason === 'install') {
    chrome.runtime.openOptionsPage();
  }
});

// ---------------------------------------------------------------------------
// Message handler (popup calls this)
// ---------------------------------------------------------------------------

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === 'pushNow') {
    pushCookies({ force: true }).then(sendResponse);
    return true;
  }
  if (message.action === 'getStatus') {
    chrome.storage.local.get([
      'lastPushTime',
      'lastPushStatus',
      'lastAccountStatus',
      'lastError',
      'lastCookieCount',
      'lastCookieNames',
      'lastCookiesJson',
    ]).then(sendResponse);
    return true;
  }
});
