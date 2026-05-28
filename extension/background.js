/**
 * Gemini Cookie Sync — Background Service Worker
 *
 * 1. Listens for Google cookie changes → pushes immediately (debounced 2s)
 * 2. Checks /health every 1 minute → pushes if account is degraded
 * 3. Full cookie push every 30 minutes (safety net)
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
// Push logic
// ---------------------------------------------------------------------------

async function pushCookies() {
  const { serverUrl, authToken } = await chrome.storage.sync.get([
    'serverUrl',
    'authToken',
  ]);

  if (!serverUrl || !authToken) {
    console.log('[GeminiCookieSync] Server URL or token not configured');
    return { success: false, error: 'not configured' };
  }

  const url = serverUrl.replace(/\/+$/, '') + '/v1/extension/refresh-cookie';

  // Read ALL non-expired google.com cookies
  const allCookies = await chrome.cookies.getAll({ domain: 'google.com' });
  const cookies = {};
  for (const c of allCookies) {
    if (!c.value) continue;
    cookies[c.name] = c.value;
  }

  if (!cookies['__Secure-1PSID']) {
    return { success: false, error: '__Secure-1PSID not found — not logged in?' };
  }

  try {
    const resp = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${authToken}`,
      },
      body: JSON.stringify({ cookies }),
    });

    if (!resp.ok) {
      const text = await resp.text();
      return { success: false, error: `HTTP ${resp.status}: ${text}` };
    }

    const data = await resp.json();
    const now = Date.now();
    await chrome.storage.local.set({
      lastPushTime: now,
      lastPushStatus: 'success',
      lastAccountStatus: data.account_status || 'unknown',
    });

    console.log('[GeminiCookieSync] Push succeeded:', data.account_status);
    return { success: true, account_status: data.account_status };
  } catch (err) {
    await chrome.storage.local.set({
      lastPushTime: Date.now(),
      lastPushStatus: 'error',
      lastError: err.message,
    });
    console.error('[GeminiCookieSync] Push failed:', err);
    return { success: false, error: err.message };
  }
}

// ---------------------------------------------------------------------------
// Health check — if degraded, trigger push immediately
// ---------------------------------------------------------------------------

async function checkHealthAndPush() {
  const { serverUrl, authToken } = await chrome.storage.sync.get([
    'serverUrl',
    'authToken',
  ]);
  if (!serverUrl) return;

  const url = serverUrl.replace(/\/+$/, '') + '/health';

  try {
    const resp = await fetch(url, { signal: AbortSignal.timeout(5000) });
    if (!resp.ok) return;

    const data = await resp.json();
    const status = (data.status || '').toLowerCase();
    const accountStatus = (data.account_status || '').toLowerCase();

    // Only push when account is degraded / unauthenticated
    if (status === 'degraded' || accountStatus.includes('unauthenticated')) {
      console.log('[GeminiCookieSync] Health check: degraded, pushing cookies');
      await pushCookies();
    }
  } catch (err) {
    // Network error — silently ignore, will retry next interval
    console.log('[GeminiCookieSync] Health check failed:', err.message);
  }
}

// ---------------------------------------------------------------------------
// Debounce helper
// ---------------------------------------------------------------------------

let debounceTimer = null;

function debouncedPush() {
  if (debounceTimer) clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => {
    debounceTimer = null;
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
    console.log('[GeminiCookieSync] __Secure-1PSID changed, scheduling push');
    debouncedPush();
  }
});

// ---------------------------------------------------------------------------
// Alarm handlers
// ---------------------------------------------------------------------------

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === PUSH_ALARM) {
    console.log('[GeminiCookieSync] Periodic push alarm fired');
    pushCookies();
  } else if (alarm.name === HEALTH_ALARM) {
    checkHealthAndPush();
  }
});

// ---------------------------------------------------------------------------
// Installation
// ---------------------------------------------------------------------------

chrome.runtime.onInstalled.addListener((details) => {
  chrome.alarms.create(PUSH_ALARM, {
    periodInMinutes: PUSH_INTERVAL_MINUTES,
  });

  chrome.alarms.create(HEALTH_ALARM, {
    periodInMinutes: HEALTH_INTERVAL_MINUTES,
  });

  if (details.reason === 'install') {
    chrome.runtime.openOptionsPage();
  }
});

// ---------------------------------------------------------------------------
// Message handler (popup calls this)
// ---------------------------------------------------------------------------

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === 'pushNow') {
    pushCookies().then(sendResponse);
    return true;
  }
  if (message.action === 'getStatus') {
    chrome.storage.local.get([
      'lastPushTime',
      'lastPushStatus',
      'lastAccountStatus',
      'lastError',
    ]).then(sendResponse);
    return true;
  }
});
