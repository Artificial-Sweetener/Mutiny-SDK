const el = (id) => document.getElementById(id);
const enabled = el('enabled');
const count = el('count');
const last = el('last');

function updateState() {
  browser.runtime.sendMessage({ type: 'get-state' }).then(res => {
    if (!res || !res.ok) return;
    enabled.checked = !!res.enabled;
    count.textContent = String(res.count || 0);
  });
  browser.runtime.sendMessage({ type: 'get-logs' }).then(res => {
    if (!res || !res.ok) return;
    const logs = res.logs || [];
    const item = logs[logs.length - 1];
    last.textContent = item ? JSON.stringify(item, null, 2) : '';
  });
}

enabled.addEventListener('change', () => {
  browser.runtime.sendMessage({ type: 'toggle', enabled: enabled.checked }).then(updateState);
});

el('download').addEventListener('click', () => {
  browser.runtime.sendMessage({ type: 'download' });
});

el('clear').addEventListener('click', () => {
  browser.runtime.sendMessage({ type: 'clear' }).then(updateState);
});

browser.runtime.onMessage.addListener((msg) => {
  if (msg && msg.type === 'log-appended') updateState();
});

updateState();

