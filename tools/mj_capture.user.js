// ==UserScript==
// @name         Midjourney Discord Capture (Custom Zoom & Inpaint)
// @namespace    https://github.com/user/mutiny
// @version      0.3.0
// @description  Capture Discord web client requests for MJ Custom Zoom (modal submit) and Vary (Region) / Inpaint.
// @author       you
// @match        https://discord.com/*
// @match        https://canary.discord.com/*
// @match        https://ptb.discord.com/*
// @match        https://*.discordsays.com/*
// @allframes    true
// @inject-into  page
// @run-at       document-start
// @grant        none
// ==/UserScript==

(function () {
  'use strict';

  // Inject page-context hook so we can override fetch/XMLHttpRequest
  const injected = `;(() => {
    const MJBRIDGE_EVENT = 'MJ_CAPTURE_EVENT';
    const MJBRIDGE_CTRL  = 'MJ_CAPTURE_CTRL';

    // Runtime flags controlled by overlay via postMessage
    let enabled = true;
    let filters = { interactions: true, attachments: true, messages: false, onlyMJ: true };

    function onCtrl(evt) {
      try {
        const d = evt && evt.data;
        if (!d || d.__src !== MJBRIDGE_CTRL) return;
        if (typeof d.enabled === 'boolean') enabled = d.enabled;
        if (d.filters && typeof d.filters === 'object') {
          filters = Object.assign({}, filters, d.filters);
        }
      } catch {}
    }
    window.addEventListener('message', onCtrl, false);

    // Helpers
    const redactKeys = new Set(['authorization','Authorization','token','Token','session_id','sessionId','x-super-properties','x-fingerprint','x-context-properties']);
    function redact(obj) {
      try {
        if (Array.isArray(obj)) return obj.map(redact);
        if (obj && typeof obj === 'object') {
          const out = {};
          for (const [k, v] of Object.entries(obj)) {
            out[k] = redactKeys.has(k) ? '<redacted>' : redact(v);
          }
          return out;
        }
        return obj;
      } catch { return obj; }
    }

    // Normalize URL to a comparable path (handles absolute or relative)
    function normalize(url) {
      try {
        if (!url) return '';
        // Accept Request, URL, string
        if (typeof url === 'string') {
          if (url.startsWith('http')) return new URL(url, location.origin).pathname;
          return new URL(url, location.origin).pathname; // relative
        }
        if (url && typeof url.url === 'string') return normalize(url.url);
      } catch {}
      return '';
    }
    function isInteractions(url) {
      const p = normalize(url);
      return /\/api\/(v\d+|v\d+\.\d+)\/interactions(\/?$|\?|$)/.test(p);
    }
    function isAttachments(url) {
      const p = normalize(url);
      return /\/api\/(v\d+|v\d+\.\d+)\/channels\/\d+\/attachments(\/?$|\?|$)/.test(p);
    }
    function isMessages(url) {
      const p = normalize(url);
      return /\/api\/(v\d+|v\d+\.\d+)\/channels\/\d+\/messages(\/?$|\?|$)/.test(p);
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
    function extractMetaFromInteraction(body) {
      const meta = {};
      try {
        if (!body || typeof body !== 'object') return meta;
        meta.guild_id = body.guild_id || null;
        meta.channel_id = body.channel_id || null;
        meta.session_id = body.session_id || null;
        meta.nonce = body.nonce || null;
        meta.message_id = body.message_id || null;
        meta.message_flags = body.message_flags ?? null;
        meta.custom_id = body.data && body.data.custom_id || null;
      } catch {}
      return meta;
    }

    function post(event) {
      try {
        window.postMessage({ __src: MJBRIDGE_EVENT, event }, '*');
      } catch {}
    }

    function shouldKeep(kind, url, bodyObj) {
      if (!enabled) return false;
      if (kind === 'interaction') {
        if (!filters.interactions) return false;
        if (!filters.onlyMJ) return true;
        try {
          const cid = bodyObj && bodyObj.data && bodyObj.data.custom_id || '';
          return typeof cid === 'string' && cid.startsWith('MJ::');
        } catch { return false; }
      }
      if (kind === 'attachments') return !!filters.attachments;
      if (kind === 'message') return !!filters.messages;
      return false;
    }

    // --- fetch hook ---
    const wrapFetch = (origFetch) => async function(input, init) {
      let url = '';
      let method = 'GET';
      try {
        if (typeof input === 'string') url = input; else if (input && input.url) url = input.url;
        if (init && init.method) method = String(init.method).toUpperCase();
        else if (input && input.method) method = String(input.method).toUpperCase();
      } catch {}

      const isTarget = method === 'POST' && (isInteractions(url) || isAttachments(url) || isMessages(url));
      let bodyText = null;
      let bodyObj = null;

      if (isTarget) {
        try {
          if (init && init.body && typeof init.body === 'string') {
            bodyText = init.body;
          } else if (input && typeof input.clone === 'function') {
            try { bodyText = await input.clone().text(); } catch {}
          } else if (init && init.body && typeof init.body.text === 'function') {
            bodyText = await init.body.text();
          }
        } catch {}
        try { if (bodyText) bodyObj = JSON.parse(bodyText); } catch {}
      }

      const proceed = origFetch.apply(this, arguments);

      if (!isTarget) return proceed;

      // Decide kind & build event after response (to include attachment/message response)
      try {
        const kind = isInteractions(url) ? 'interaction' : (isAttachments(url) ? 'attachments' : 'message');
        if (!shouldKeep(kind, url, bodyObj)) return proceed;

        const evt = {
          ts: new Date().toISOString(),
          kind,
          action: kind === 'interaction' ? classifyInteraction(bodyObj) : null,
          url,
          method,
          request: bodyObj ? redact(bodyObj) : (bodyText || null),
          response: null,
          meta: kind === 'interaction' ? extractMetaFromInteraction(bodyObj) : { channel_id: null }
        };

        if (kind === 'attachments' || kind === 'message') {
          proceed.then(async (resp) => {
            try {
              const clone = resp.clone();
              const ct = clone.headers && clone.headers.get ? clone.headers.get('content-type') : '';
              if (ct && ct.includes('application/json')) {
                const data = await clone.json();
                evt.response = redact(data);
                // Pull uploaded_filename for attachments
                if (kind === 'attachments') {
                  try {
                    const a = (data && data.attachments && data.attachments[0]) || null;
                    if (a && a.upload_filename) evt.meta.uploaded_filename = a.upload_filename;
                  } catch {}
                }
              }
            } catch {}
            post(evt);
          }).catch(() => post(evt));
        } else {
          post(evt);
        }
      } catch {}

      return proceed;
    };
    
    // Patch multiple fetch references for robustness
    const _origFetch = window.fetch;
    const _wrapped = wrapFetch(_origFetch);
    try { window.fetch = _wrapped; } catch {}
    try { globalThis.fetch = _wrapped; } catch {}
    try { self.fetch = _wrapped; } catch {}

    // --- XMLHttpRequest hook (fallback paths) ---
    const _open = XMLHttpRequest.prototype.open;
    const _send = XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.open = function(method, url) {
      this.__mj_url = url;
      this.__mj_method = (method || '').toString().toUpperCase();
      return _open.apply(this, arguments);
    };
    XMLHttpRequest.prototype.send = function(body) {
      const url = this.__mj_url || '';
      const method = this.__mj_method || 'GET';
      const isTarget = method === 'POST' && (isInteractions(url) || isAttachments(url) || isMessages(url));
      let bodyText = null, bodyObj = null;
      try { if (typeof body === 'string') { bodyText = body; bodyObj = JSON.parse(bodyText); } } catch {}
      if (isTarget) {
        const kind = isInteractions(url) ? 'interaction' : (isAttachments(url) ? 'attachments' : 'message');
        if (shouldKeep(kind, url, bodyObj)) {
          const evt = {
            ts: new Date().toISOString(),
            kind,
            action: kind === 'interaction' ? classifyInteraction(bodyObj) : null,
            url,
            method,
            request: bodyObj ? redact(bodyObj) : (bodyText || null),
            response: null,
            meta: kind === 'interaction' ? extractMetaFromInteraction(bodyObj) : { channel_id: null }
          };
          this.addEventListener('load', function() {
            try {
              if (kind === 'attachments' || kind === 'message') {
                const ct = this.getResponseHeader && this.getResponseHeader('content-type') || '';
                if (ct && ct.includes('application/json')) {
                  try { evt.response = redact(JSON.parse(this.responseText)); } catch {}
                }
              }
            } catch {}
            post(evt);
          });
        }
      }
      return _send.apply(this, arguments);
    };
    
    // Observe iframe modal creation (INTERACTION_IFRAME_MODAL_CREATE) for correlation
    try {
      const postUi = (target) => {
        try {
          const iframe = target.querySelector ? target.querySelector('iframe') : null;
          const evt = {
            ts: new Date().toISOString(),
            kind: 'ui',
            action: 'iframe_modal_open',
            url: location.href,
            method: null,
            request: null,
            response: null,
            meta: {
              type: target.getAttribute('type') || null,
              title: target.getAttribute('title') || null,
              channel_id: target.getAttribute('channelid') || null,
              custom_id: target.getAttribute('customid') || null,
              iframe_src: iframe ? iframe.src : null,
            }
          };
          post(evt);
        } catch {}
      };
      const look = (node) => {
        try {
          if (!(node && node.querySelector)) return;
          if (node.hasAttribute && node.getAttribute('type') === 'INTERACTION_IFRAME_MODAL_CREATE') postUi(node);
          const found = node.querySelector('[type="INTERACTION_IFRAME_MODAL_CREATE"]');
          if (found) postUi(found);
        } catch {}
      };
      const mo = new MutationObserver((muts) => {
        for (const m of muts) {
          for (const n of m.addedNodes) { if (n && n.nodeType === 1) look(n); }
        }
      });
      mo.observe(document.documentElement || document, { childList: true, subtree: true });
    } catch {}
  })();`;

  function injectHook() {
    const s = document.createElement('script');
    s.textContent = injected;
    (document.head || document.documentElement).appendChild(s);
    s.parentNode && s.parentNode.removeChild(s);
  }
  injectHook();

  // Overlay & controller in userscript (sandbox)
  const BRIDGE_EVENT = 'MJ_CAPTURE_EVENT';
  const BRIDGE_CTRL  = 'MJ_CAPTURE_CTRL';

  const state = {
    enabled: true,
    filters: { interactions: true, attachments: true, messages: false, onlyMJ: true },
    events: [],
    counters: { total: 0, interaction: 0, attachments: 0, message: 0 },
  };

  function sendCtrl() {
    window.postMessage({ __src: BRIDGE_CTRL, enabled: state.enabled, filters: state.filters }, '*');
  }

  function onEvent(evt) {
    const d = evt && evt.data;
    if (!d || d.__src !== BRIDGE_EVENT || !d.event) return;
    state.events.push(d.event);
    state.counters.total += 1;
    state.counters[d.event.kind] = (state.counters[d.event.kind] || 0) + 1;
    render();
  }
  window.addEventListener('message', onEvent, false);

  // UI
  function el(tag, attrs = {}, children = []) {
    const e = document.createElement(tag);
    Object.assign(e, attrs);
    children.forEach(c => e.appendChild(typeof c === 'string' ? document.createTextNode(c) : c));
    return e;
  }
  function css(node, styles) { Object.assign(node.style, styles); }

  let root;
  function mount() {
    if (root) return;
    root = el('div');
    root.id = 'mj-cap-overlay';
    css(root, {
      position: 'fixed', right: '12px', bottom: '12px', zIndex: 2147483647,
      background: 'rgba(20,20,24,0.95)', color: '#eee', font: '12px/1.3 system-ui, sans-serif',
      padding: '10px', borderRadius: '8px', boxShadow: '0 2px 8px rgba(0,0,0,.5)', width: '280px'
    });

    const header = el('div', { innerText: 'MJ Capture' });
    css(header, { fontWeight: '600', marginBottom: '8px' });

    const row1 = el('div');
    const chkOn = el('input', { type: 'checkbox', checked: state.enabled });
    chkOn.addEventListener('change', () => { state.enabled = chkOn.checked; sendCtrl(); });
    row1.appendChild(chkOn); row1.appendChild(el('span', { innerText: ' Capture On' }));
    css(row1, { marginBottom: '6px' });

    const row2 = el('div');
    const fInt = el('input', { type: 'checkbox', checked: state.filters.interactions });
    const fAtt = el('input', { type: 'checkbox', checked: state.filters.attachments });
    const fMsg = el('input', { type: 'checkbox', checked: state.filters.messages });
    const fMJ  = el('input', { type: 'checkbox', checked: state.filters.onlyMJ });
    fInt.addEventListener('change', () => { state.filters.interactions = fInt.checked; sendCtrl(); });
    fAtt.addEventListener('change', () => { state.filters.attachments = fAtt.checked; sendCtrl(); });
    fMsg.addEventListener('change', () => { state.filters.messages = fMsg.checked; sendCtrl(); });
    fMJ.addEventListener('change',  () => { state.filters.onlyMJ = fMJ.checked; sendCtrl(); });
    row2.appendChild(el('label', { innerText: ' Interactions ' })); row2.appendChild(fInt);
    row2.appendChild(el('label', { innerText: ' Attachments ' })); row2.appendChild(fAtt);
    row2.appendChild(el('label', { innerText: ' Messages ' })); row2.appendChild(fMsg);
    row2.appendChild(el('label', { innerText: ' Only MJ ' })); row2.appendChild(fMJ);
    css(row2, { display: 'grid', gridTemplateColumns: '1fr auto', gap: '2px 6px', marginBottom: '6px' });

    const row3 = el('div');
    const btnCopy = el('button', { innerText: 'Copy Last' });
    const btnDl   = el('button', { innerText: 'Download' });
    const btnClr  = el('button', { innerText: 'Clear' });
    [btnCopy, btnDl, btnClr].forEach(b => css(b, { background: '#3b82f6', color: '#fff', border: '0', padding: '6px 8px', borderRadius: '4px', cursor: 'pointer' }));
    css(btnDl, { background: '#10b981', marginLeft: '6px' });
    css(btnClr, { background: '#ef4444', marginLeft: '6px' });
    btnCopy.addEventListener('click', async () => {
      try {
        const last = state.events[state.events.length - 1];
        if (!last) return;
        await navigator.clipboard.writeText(JSON.stringify(last, null, 2));
      } catch {}
    });
    btnDl.addEventListener('click', () => {
      const lines = state.events.map(e => JSON.stringify(e));
      const blob = new Blob([lines.join('\n') + '\n'], { type: 'application/json' });
      const a = el('a', { href: URL.createObjectURL(blob), download: `mj_capture_${new Date().toISOString().replace(/[:.]/g,'-')}.jsonl` });
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(a.href), 1000);
    });
    btnClr.addEventListener('click', () => { state.events = []; state.counters = { total: 0, interaction: 0, attachments: 0, message: 0 }; render(); });
    row3.appendChild(btnCopy); row3.appendChild(btnDl); row3.appendChild(btnClr);
    css(row3, { marginBottom: '6px' });

    const stats = el('div', { id: 'mj-cap-stats' });
    css(stats, { opacity: 0.9 });

    root.appendChild(header);
    root.appendChild(row1);
    root.appendChild(row2);
    root.appendChild(row3);
    root.appendChild(stats);

    document.addEventListener('keydown', (e) => {
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key.toLowerCase() === 'm') {
        root.style.display = (root.style.display === 'none') ? 'block' : 'none';
      }
    });

    document.documentElement.appendChild(root);
    sendCtrl();
    render();
  }

  function render() {
    const stats = root && root.querySelector('#mj-cap-stats');
    if (!stats) return;
    stats.innerHTML = `Total: ${state.counters.total} | Interactions: ${state.counters.interaction||0} | Attachments: ${state.counters.attachments||0} | Messages: ${state.counters.message||0}`;
  }

  // Mount UI once body is available; Discord’s SPA may delay body mutations.
  function tryMount() {
    // Only render overlay in the top-level window; still capture in iframes
    if (window.self !== window.top) return;
    if (document.body) { mount(); }
    else setTimeout(tryMount, 50);
  }
  tryMount();
})();
