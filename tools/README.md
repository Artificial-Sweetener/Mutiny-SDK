# Tools

This directory contains local development tooling for two jobs:

- capturing Discord and Midjourney behavior when you need raw evidence
- checking that Mutiny's public surface, demos, and docs have not drifted apart

If you are just looking for "what should I run first?", start there.

## Quick Picks

### I Need To Check The Docs Contract

Run:

```powershell
python tools\check_consistency.py --section docs
```

What it checks:

- symbol coverage in `docs\*.md`
- ghost symbols that do not match the public `.pyi` contract

What it does **not** currently check:

- `README.md`
- `tools\README.md`
- prose quality, tone, or examples beyond symbol-level contract coverage

In other words: it is a good contract checker, not a substitute for reading the docs like a human.

### I Need To Inspect Mutiny-Side Dumps

Run:

```powershell
python tools\inspect_mj_dumps.py
```

This reads `.cache\mutiny\mj_responses\index.jsonl` and summarizes:

- button labels
- `custom_id` prefix patterns

Use this when you want to understand what Midjourney surfaced without opening every raw dump file yourself.

### I Need To Tail A Browser Capture Live

Run:

```powershell
python tools\tail_capture.py --file .cache\mutiny\dev_captures\live_capture.jsonl
```

Useful optional filter:

```powershell
python tools\tail_capture.py --only interaction,attachments
```

Use this while running one of the browser capture tools below.

## Browser Capture Tooling

These tools capture Discord-side request activity. They are for browser/request debugging, not for Mutiny's own response-dump path.

### `mj_capture.user.js`

Use this when:

- you prefer a userscript manager
- you want an in-page overlay and quick export flow

What it does:

- hooks `fetch` and XHR on Discord pages
- captures interaction, attachment, and message POST payloads
- provides an on-page overlay to toggle capture, filter events, and export JSONL

### `extension\`

Firefox browser extension version.

Use this when:

- you want browser-native capture without a userscript manager

What it does:

- captures POST request bodies through `browser.webRequest`
- includes a popup for toggle, clear, download, and last-event status

### `capture-extension\`

Chrome browser extension version.

Use this when:

- you want the same capture idea in Chrome

What it does:

- captures POST request bodies through `chrome.webRequest`
- includes popup controls for toggle, clear, download, and last-event status

### `mj_capture_playwright.py`

Use this when:

- extension or userscript capture is inconvenient
- you want a persistent automated browser profile

Prerequisites:

```powershell
pip install playwright
python -m playwright install chromium
```

Or for Firefox:

```powershell
pip install playwright
python -m playwright install firefox
```

Basic usage:

```powershell
python tools\mj_capture_playwright.py --guild-id <guild> --channel-id <channel>
```

What it does:

- launches Chromium or Firefox with a persistent profile
- captures relevant Discord API requests
- writes JSONL output under `.cache\mutiny\dev_captures` by default

## Mutiny-Side Response Dump Utilities

These work with Mutiny's own dump files, not browser request capture.

### `inspect_mj_dumps.py`

Use this when:

- you already have response dumps under `.cache\mutiny\mj_responses`
- you want fast summary output instead of reading every file manually

Input:

- `.cache\mutiny\mj_responses\index.jsonl`

### Response dump context

The config knobs that matter most are:

- `websocket.capture_enabled`
- `cache.response_dump_dir`

Remember the nuance:

- gateway dumps honor `capture_enabled`
- reactor-driven message dumps use the same dump service but are not gated by that flag the same way

## Consistency Tooling

### `check_consistency.py`

This script checks four areas:

- implementation surface vs `.pyi` contract
- demo compliance with the public facade
- docs symbol coverage in `docs\*.md`
- demo method coverage

Run everything:

```powershell
python tools\check_consistency.py
```

Run one section:

```powershell
python tools\check_consistency.py --section docs
python tools\check_consistency.py --section impl
python tools\check_consistency.py --section demo
python tools\check_consistency.py --section coverage
```

Strict mode:

```powershell
python tools\check_consistency.py --strict
```

JSON report:

```powershell
python tools\check_consistency.py --json-out .cache\mutiny\consistency.json
```

## License Header Tooling

### `add_license_headers.py`

Use this when:

- you need to normalize or add Mutiny's AGPL header across `.py` and `.pyi` files

What it does:

- scans tracked `.py` and `.pyi` files
- adds Mutiny's canonical AGPL header when missing
- normalizes malformed known Mutiny headers in place
- preserves shebang and encoding lines
- skips unknown existing GPL/AGPL headers instead of overwriting them blindly

## Suggested Workflow

If you are debugging behavior:

1. enable response dumps
2. reproduce the problem
3. inspect `.cache\mutiny\mj_responses`
4. use `inspect_mj_dumps.py` for summaries

If you are editing docs:

1. run `python tools\check_consistency.py --section docs`
2. fix contract drift first
3. then read the docs like a human anyway, because symbol coverage is not the same thing as good documentation
