// Captures POST bodies to Discord API endpoints and stores a rolling JSONL log in chrome.storage.local

const CAPTURE_URLS = [
  "https://discord.com/api/*",
  "https://*.discord.com/api/*",
  "https://*.discordapp.com/api/*",
  "https://*.discordsays.com/api/*"
];

let enabled = true;

function classify(url, body) {
  if (url.includes("/interactions")) return "interaction";
  if (url.includes("/attachments")) return "attachments";
  if (url.includes("/messages")) return "message";
  return null;
}

function redact(obj) {
  const S = new Set(["authorization","Authorization","token","Token","session_id","sessionId","x-super-properties","x-fingerprint","x-context-properties"]);
  try {
    if (Array.isArray(obj)) return obj.map(redact);
    if (obj && typeof obj === 'object') {
      const out = {};
      for (const [k,v] of Object.entries(obj)) out[k] = S.has(k) ? '<redacted>' : redact(v);
      return out;
    }
    return obj;
  } catch { return obj; }
}

function extractMeta(kind, body) {
  const meta = {};
  try {
    if (kind === 'interaction' && body && typeof body === 'object') {
      meta.guild_id = body.guild_id || null;
      meta.channel_id = body.channel_id || null;
      meta.session_id = body.session_id || null;
      meta.nonce = body.nonce || null;
      meta.message_id = body.message_id || null;
      meta.message_flags = body.message_flags ?? null;
      meta.custom_id = body.data && body.data.custom_id || null;
    }
  } catch {}
  return meta;
}

function classifyInteraction(body) {
  try {
    const t = body && body.type;
    const cid = body && body.data && body.data.custom_id || '';
    if (t === 3) {
      if (cid.startsWith('MJ::CustomZoom::')) return 'custom_zoom_button';
      if (cid.startsWith('MJ::Inpaint::')) return 'inpaint_button';
      if (cid.startsWith('MJ::')) return 'mj_button';
      return 'interaction_button';
    }
    if (t === 5) {
      if (cid.includes('CustomZoom')) return 'custom_zoom_submit';
      if (cid.includes('Inpaint')) return 'inpaint_submit';
      return 'modal_submit';
    }
  } catch {}
  return null;
}

async function pushEvent(evt) {
  try {
    const { logs = [] } = await chrome.storage.local.get({ logs: [] });
    logs.push(evt);
    // Cap logs to avoid unbounded growth
    if (logs.length > 5000) logs.splice(0, logs.length - 5000);
    await chrome.storage.local.set({ logs });
    chrome.runtime.sendMessage({ type: 'log-appended', evt });
  } catch (e) {
    // ignore
  }
}

function decodeBody(details) {
  try {
    const rb = details.requestBody;
    if (!rb) return null;
    if (rb.formData) return rb.formData; // not expected for our endpoints
    if (rb.raw && rb.raw[0] && rb.raw[0].bytes) {
      const bytes = new Uint8Array(rb.raw[0].bytes);
      const text = new TextDecoder('utf-8').decode(bytes);
      try { return JSON.parse(text); } catch { return text; }
    }
  } catch {}
  return null;
}

chrome.webRequest.onBeforeRequest.addListener(async (details) => {
  if (!enabled) return;
  const url = details.url || '';
  const method = details.method || 'GET';
  if (method !== 'POST') return;
  const kind = classify(url);
  if (!kind) return;

  const body = decodeBody(details);
  const evt = {
    ts: new Date().toISOString(),
    kind,
    action: null,
    url,
    method,
    request: null,
    response: null,
    meta: {},
  };
  if (kind === 'interaction' && body && typeof body === 'object') {
    evt.action = classifyInteraction(body);
    evt.meta = extractMeta(kind, body);
  }
  evt.request = (body && typeof body === 'object') ? redact(body) : body;
  pushEvent(evt);
}, { urls: CAPTURE_URLS }, ["requestBody"]);

chrome.runtime.onMessage.addListener(async (msg, sender, sendResponse) => {
  try {
    if (msg && msg.type === 'toggle') {
      enabled = !!msg.enabled;
      sendResponse({ ok: true, enabled });
      return true;
    }
    if (msg && msg.type === 'get-state') {
      const { logs = [] } = await chrome.storage.local.get({ logs: [] });
      sendResponse({ ok: true, enabled, count: logs.length });
      return true;
    }
    if (msg && msg.type === 'get-logs') {
      const { logs = [] } = await chrome.storage.local.get({ logs: [] });
      sendResponse({ ok: true, logs });
      return true;
    }
    if (msg && msg.type === 'clear') {
      await chrome.storage.local.set({ logs: [] });
      sendResponse({ ok: true });
      return true;
    }
    if (msg && msg.type === 'download') {
      const { logs = [] } = await chrome.storage.local.get({ logs: [] });
      const jsonl = logs.map(l => JSON.stringify(l)).join('\n') + '\n';
      const blob = new Blob([jsonl], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      await chrome.downloads.download({ url, filename: `mj_capture_${Date.now()}.jsonl`, saveAs: true });
      setTimeout(() => URL.revokeObjectURL(url), 2000);
      sendResponse({ ok: true });
      return true;
    }
  } catch (e) {
    sendResponse({ ok: false, error: String(e) });
    return true;
  }
});

