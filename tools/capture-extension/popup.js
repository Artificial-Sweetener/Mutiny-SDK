const enabled = document.getElementById('enabled');
const count = document.getElementById('count');
const last = document.getElementById('last');

function updateState() {
  chrome.runtime.sendMessage({ type: 'get-state' }, (res) => {
    if (!res || !res.ok) return;
    enabled.checked = !!res.enabled;
    count.textContent = String(res.count || 0);
  });
  chrome.runtime.sendMessage({ type: 'get-logs' }, (res) => {
    if (!res || !res.ok) return;
    const logs = res.logs || [];
    const item = logs[logs.length - 1];
    last.textContent = item ? JSON.stringify(item, null, 2) : '';
  });
}

enabled.addEventListener('change', () => {
  chrome.runtime.sendMessage({ type: 'toggle', enabled: enabled.checked }, updateState);
});

document.getElementById('download').addEventListener('click', () => {
  chrome.runtime.sendMessage({ type: 'download' }, updateState);
});

document.getElementById('clear').addEventListener('click', () => {
  chrome.runtime.sendMessage({ type: 'clear' }, updateState);
});

chrome.runtime.onMessage.addListener((msg) => {
  if (msg && msg.type === 'log-appended') updateState();
});

updateState();

