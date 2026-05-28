/**
 * Gemini Cookie Sync — Background Service Worker
 *
 * Listens for Google cookie changes and periodically pushes
 * __Secure-1PSID / __Secure-1PSIDTS to the configured server.
 */

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------
const ALARM_NAME = 'gemini-cookie-push';
const ALARM_PERIOD_MINUTES = 30;
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

  // Read both cookies in parallel
  const [psid, psidts] = await Promise.all([
    chrome.cookies.get({ url: 'https://www.google.com', name: '__Secure-1PSID' }),
    chrome.cookies.get({ url: 'https://www.google.com', name: '__Secure-1PSIDTS' }),
  ]);

  if (!psid || !psid.value) {
    return { success: false, error: '__Secure-1PSID not found — not logged in?' };
  }

  const cookies = {};
  cookies['__Secure-1PSID'] = psid.value;
  if (psidts && psidts.value) {
    cookies['__Secure-1PSIDTS'] = psidts.value;
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

  // Only care about Google auth cookies
  if (name === '__Secure-1PSID' && domain && domain.includes('google')) {
    console.log('[GeminiCookieSync] __Secure-1PSID changed, scheduling push');
    debouncedPush();
  }
});

// ---------------------------------------------------------------------------
// Periodic alarm — safety net
// ---------------------------------------------------------------------------

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === ALARM_NAME) {
    console.log('[GeminiCookieSync] Alarm fired, pushing cookies');
    pushCookies();
  }
});

// ---------------------------------------------------------------------------
// Installation
// ---------------------------------------------------------------------------

chrome.runtime.onInstalled.addListener((details) => {
  // Create periodic alarm
  chrome.alarms.create(ALARM_NAME, {
    periodInMinutes: ALARM_PERIOD_MINUTES,
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
    return true; // keep channel open for async response
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
