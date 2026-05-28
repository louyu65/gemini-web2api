const serverUrlInput = document.getElementById('serverUrl');
const authTokenInput = document.getElementById('authToken');
const saveBtn = document.getElementById('saveBtn');
const statusDiv = document.getElementById('status');

// Load saved config
chrome.storage.sync.get(['serverUrl', 'authToken'], (items) => {
  if (items.serverUrl) serverUrlInput.value = items.serverUrl;
  if (items.authToken) authTokenInput.value = items.authToken;
});

// Save config
saveBtn.addEventListener('click', () => {
  const serverUrl = serverUrlInput.value.trim();
  const authToken = authTokenInput.value.trim();

  if (!serverUrl) {
    statusDiv.textContent = '⚠️ 请输入服务器地址';
    statusDiv.style.color = '#d93025';
    return;
  }

  chrome.storage.sync.set({ serverUrl, authToken }, () => {
    statusDiv.textContent = '✅ 已保存';
    statusDiv.style.color = '#188038';
    setTimeout(() => { statusDiv.textContent = ''; }, 2000);
  });
});
