/*
 Firefox WebExtension to capture Discord API POST bodies across tabs/frames.
 Stores a rolling log in storage and exposes a popup to toggle and download JSONL.
*/

const FILTER_URLS = [
  // Discord API endpoints
  "https://discord.com/api/*",
  "https://*.discord.com/api/*",
  "https://*.discordapp.com/api/*",
  "https://*.discordsays.com/api/*",
  // MJ iframe/app endpoints (non-API posts)
  "https://*.discordsays.com/*"
];

let enabled = true;
const MAX_LOGS = 5000;

// Map requestId -> content-type (from onBeforeSendHeaders)
const contentTypes = new Map();
// Map requestId -> safe request headers snapshot (lowercased keys)
const requestHeadersMap = new Map();

function setContentType(details) {
  try {
    const hdrs = details.requestHeaders || [];
    const ct = hdrs.find(h => (h.name || '').toLowerCase() === 'content-type');
    if (ct && details.requestId) contentTypes.set(details.requestId, (ct.value || '').toLowerCase());
    // Save a minimal, redacted header snapshot for iframe posts
    const headers = {};
    for (const h of hdrs) {
      const k = (h.name || '').toLowerCase();
      if (!k) continue;
      if (["content-type","origin","referer","user-agent"].includes(k)) headers[k] = h.value || '';
      if (["authorization","cookie","x-super-properties","x-fingerprint","x-context-properties"].includes(k)) headers[k] = '<redacted>';
    }
    requestHeadersMap.set(details.requestId, headers);
  } catch {}
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

function kindFromUrl(url) {
  if (!url) return null;
  if (url.includes('/interactions')) return 'interaction';
  if (url.includes('/attachments')) return 'attachments';
  if (url.includes('/messages')) return 'message';
  // Heuristic for iframe/app submits (e.g., /.proxy/inpaint/)
  if (/\.discordsays\.com\//.test(url)) return 'iframe';
  return null;
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

async function pushEvent(evt) {
  try {
    const { logs = [] } = await browser.storage.local.get({ logs: [] });
    logs.push(evt);
    if (logs.length > MAX_LOGS) logs.splice(0, logs.length - MAX_LOGS);
    await browser.storage.local.set({ logs });
    try { browser.runtime.sendMessage({ type: 'log-appended', evt }); } catch {}
  } catch (e) {
    // ignore
  }
}

// Initialize enabled flag from storage (so the popup state persists across reloads)
(async () => {
  try {
    const v = await browser.storage.local.get({ enabled: true });
    enabled = !!v.enabled;
  } catch {}
})();

function sanitizeLarge(value) {
  try {
    if (typeof value === 'string' && value.length > 100000) {
      return `<large-string ${value.length} bytes redacted>`;
    }
    if (Array.isArray(value)) return value.map(sanitizeLarge);
  if (value && typeof value === 'object') {
      const out = {};
      for (const [k, v] of Object.entries(value)) {
        // Do not truncate mask; we need full payload to replicate server-side encoding
        if (k && k.toLowerCase() === 'mask') out[k] = v;
        else out[k] = sanitizeLarge(v);
      }
      return out;
    }
    return value;
  } catch { return value; }
}

function inferMimeFromBase64(s) {
  try {
    const str = String(s || '').replace(/^data:[^,]+,/, '');
    if (str.startsWith('UklG')) return 'image/webp';
    if (str.startsWith('iVBOR')) return 'image/png';
    if (str.startsWith('/9j/')) return 'image/jpeg';
    return null;
  } catch { return null; }
}

function decodeBody(details) {
  try {
    const rb = details.requestBody;
    if (!rb) return null;
    if (rb.formData) return rb.formData; // not expected for these endpoints
    const raw = rb.raw && rb.raw[0] && rb.raw[0].bytes;
    if (!raw) return null;
    const text = new TextDecoder('utf-8').decode(raw);
    // Try parse as JSON when content-type indicates JSON, else best-effort
    const ct = (contentTypes.get(details.requestId) || '').toLowerCase();
    if (ct.includes('application/json')) {
      try { return JSON.parse(text); } catch { return text; }
    }
    try { return JSON.parse(text); } catch { return text; }
  } catch {}
  return null;
}

browser.webRequest.onBeforeSendHeaders.addListener(setContentType, { urls: FILTER_URLS }, ["requestHeaders"]);

browser.webRequest.onBeforeRequest.addListener(async (details) => {
  if (!enabled) return;
  const method = details.method || 'GET';
  if (method !== 'POST') return;
  const url = details.url || '';
  const kind = kindFromUrl(url);
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
  let reqPayload = body;
  if (reqPayload && typeof reqPayload === 'object') reqPayload = redact(sanitizeLarge(reqPayload));
  evt.request = reqPayload;
  if (kind === 'iframe') {
    const lower = url.toLowerCase();
    if (lower.includes('inpaint')) evt.action = 'inpaint_iframe_submit';
    else if (lower.includes('outpaint') || lower.includes('custom')) evt.action = 'outpaint_iframe_submit';
    else evt.action = 'iframe_post';
    try {
      // Attach minimal headers and derived mask info for convenience
      evt.meta.headers = requestHeadersMap.get(details.requestId) || {};
      if (body && typeof body === 'object') {
        if (body.customId) evt.meta.customId = body.customId;
        if (typeof body.prompt === 'string') evt.meta.prompt = body.prompt;
        if (typeof body.full_prompt === 'string' || body.full_prompt === null) evt.meta.full_prompt = body.full_prompt;
        if (typeof body.mask === 'string') {
          evt.meta.maskMime = inferMimeFromBase64(body.mask);
          evt.meta.maskLength = body.mask.length;
        }
      }
    } catch {}
  }
  pushEvent(evt);
}, { urls: FILTER_URLS }, ["requestBody"]);

browser.runtime.onMessage.addListener(async (msg) => {
  if (!msg || typeof msg !== 'object') return;
  if (msg.type === 'toggle') {
    enabled = !!msg.enabled;
    try { await browser.storage.local.set({ enabled }); } catch {}
    return { ok: true, enabled };
  }
  if (msg.type === 'get-state') {
    const { logs = [] } = await browser.storage.local.get({ logs: [] });
    return { ok: true, enabled, count: logs.length };
  }
  if (msg.type === 'get-logs') {
    const { logs = [] } = await browser.storage.local.get({ logs: [] });
    return { ok: true, logs };
  }
  if (msg.type === 'clear') {
    await browser.storage.local.set({ logs: [] });
    return { ok: true };
  }
  if (msg.type === 'download') {
    const { logs = [] } = await browser.storage.local.get({ logs: [] });
    const jsonl = (logs || []).map(l => JSON.stringify(l)).join('\n') + '\n';
    const blob = new Blob([jsonl], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    try {
      await browser.downloads.download({ url, filename: `mj_capture_${Date.now()}.jsonl`, saveAs: true });
    } finally {
      setTimeout(() => URL.revokeObjectURL(url), 2000);
    }
    return { ok: true };
  }
});
