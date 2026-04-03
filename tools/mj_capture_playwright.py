#    Mutiny - Unofficial Midjourney integration SDK
#    Copyright (C) 2026  Artificial Sweetener and contributors
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <https://www.gnu.org/licenses/>.

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


def _redact(obj: Any) -> Any:
    sensitive = {
        "authorization",
        "Authorization",
        "token",
        "Token",
        "session_id",
        "sessionId",
        "x-super-properties",
        "x-fingerprint",
        "x-context-properties",
    }
    try:
        if isinstance(obj, dict):
            out = {}
            for k, v in obj.items():
                out[k] = "<redacted>" if k in sensitive else _redact(v)
            return out
        if isinstance(obj, list):
            return [_redact(v) for v in obj]
        return obj
    except Exception:
        return obj


def _is_target_url(url: str) -> bool:
    # Matches Discord API endpoints across common domains and subdomains
    if not url or "/api/" not in url:
        return False
    import re

    patterns = [
        r"://(?:[^/]*\.)?discord\.com/api/",  # discord.com, canary.discord.com, ptb.discord.com
        r"://(?:[^/]*\.)?discordapp\.com/api/",  # legacy domains if any
        r"://(?:[^/]*\.)?discordsays\.com/api/",  # app iframes (e.g., 9369....discordsays.com)
    ]
    return any(re.search(p, url) for p in patterns)


def _classify(url: str) -> Optional[str]:
    if "/interactions" in url:
        return "interaction"
    if "/attachments" in url:
        return "attachments"
    if "/messages" in url:
        return "message"
    return None


async def main():
    try:
        from playwright.async_api import async_playwright
    except Exception:
        print(
            "Playwright not installed. Install with: pip install playwright && playwright "
            "install firefox",
            file=sys.stderr,
        )
        return 1

    parser = argparse.ArgumentParser("mj-capture-playwright")
    parser.add_argument("--guild-id", dest="guild_id", default=os.getenv("MJ_GUILD_ID"))
    parser.add_argument("--channel-id", dest="channel_id", default=os.getenv("MJ_CHANNEL_ID"))
    parser.add_argument(
        "--out",
        dest="out",
        default=None,
        help="Output JSONL path (defaults under .cache/mutiny/dev_captures)",
    )
    parser.add_argument("--persist-dir", dest="persist_dir", default=None)
    parser.add_argument(
        "--browser",
        dest="browser",
        choices=["chromium", "firefox"],
        default="chromium",
        help="Browser engine (default: chromium)",
    )
    parser.add_argument(
        "--headless", dest="headless", action="store_true", help="Run headless (default: headed)"
    )
    parser.add_argument(
        "--all",
        dest="all_events",
        action="store_true",
        help="Capture all API v9 requests, not only interactions/attachments/messages",
    )
    parser.add_argument(
        "--quiet",
        dest="quiet",
        action="store_true",
        help="Do not print events to console (still writes JSONL)",
    )
    args = parser.parse_args()

    out_dir = Path(args.out).parent if args.out else Path(".cache/mutiny/dev_captures")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = (
        Path(args.out)
        if args.out
        else out_dir / f"mj_capture_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.jsonl"
    )

    print(f"[capture] Writing JSONL to: {out_file}")

    async with async_playwright() as p:
        browser_type = p.chromium if args.browser == "chromium" else p.firefox
        # Choose default profile directory per browser if not provided
        default_dir = (
            Path(".cache/mutiny/.pw-chromium-profile")
            if args.browser == "chromium"
            else Path(".cache/mutiny/.pw-firefox-profile")
        )
        user_dir = Path(args.persist_dir) if args.persist_dir else default_dir
        user_dir.mkdir(parents=True, exist_ok=True)
        print(f"[capture] Launching {args.browser} (persistent profile at {user_dir})...")
        try:
            launch_kwargs = {"headless": bool(args.headless)}
            if args.browser == "chromium":
                # Loosen third-party cookie blocking to allow MJ iframe to function
                launch_kwargs["args"] = [
                    "--disable-features=BlockThirdPartyCookies,SameSiteByDefaultCookies,CookiesWithoutSameSiteMustBeSecure,PrivacySandboxAdsAPIs",
                    "--allow-third-party-cookies",
                    "--disable-site-isolation-trials",
                ]
            context = await browser_type.launch_persistent_context(
                user_dir.as_posix(), **launch_kwargs
            )
        except Exception as e:
            print(f"[error] Failed to launch {args.browser} via Playwright:", e, file=sys.stderr)
            hint = "chromium" if args.browser == "chromium" else "firefox"
            print(
                f"[hint] Try: venv\\Scripts\\python -m playwright install {hint}", file=sys.stderr
            )
            return 1

        page = context.pages[0] if context.pages else await context.new_page()
        target_url = None
        if args.guild_id and args.channel_id:
            target_url = f"https://discord.com/channels/{args.guild_id}/{args.channel_id}"
        else:
            target_url = "https://discord.com/channels/@me"

        try:
            print(f"[capture] Navigating to: {target_url}")
            await page.goto(target_url)
        except Exception as e:
            print("[warn] Navigation failed:", e, file=sys.stderr)
        print(
            "[capture] Ready. Navigate/login if needed. Perform Custom Zoom and Inpaint, then "
            "press Enter here to stop."
        )

        # Attach diagnostic listeners (helps diagnose blank iframe / blocked requests)
        def _on_req_failed(req):
            try:
                print(f"[req-failed] {req.method} {req.url} error={req.failure}\n")
            except Exception:
                pass

        context.on("requestfailed", _on_req_failed)

        def _wire_page(pg):
            try:
                pg.on("console", lambda msg: print(f"[console] {msg.type()} {msg.text()}"))
                pg.on("pageerror", lambda err: print(f"[pageerror] {err}"))
                pg.on("filechooser", lambda *_: print("[filechooser] opened (likely mask upload)"))
            except Exception:
                pass

        _wire_page(page)
        context.on("page", _wire_page)

        # JSONL writer
        f = open(out_file, "a", encoding="utf-8")

        def write_event(d: Dict[str, Any]):
            try:
                f.write(json.dumps(d, ensure_ascii=False) + "\n")
                f.flush()
            except Exception:
                pass
            # Console echo (co-op mode)
            if not args.quiet:
                try:
                    kind = d.get("kind")
                    action = d.get("action")
                    meta = d.get("meta") or {}
                    cid = meta.get("custom_id")
                    upf = meta.get("uploaded_filename") if isinstance(meta, dict) else None
                    if kind == "attachments" and upf:
                        print(f"[{kind}] uploaded_filename={upf}")
                    elif kind == "interaction":
                        print(f"[{kind}] action={action} custom_id={cid}")
                    else:
                        print(f"[{kind}] url={d.get('url')}")
                except Exception:
                    pass

        def on_request(request):
            try:
                url = request.url
                if not _is_target_url(url):
                    return
                kind = _classify(url) or ("other" if args.all_events else None)
                if not kind:
                    return
                # Build base event
                evt: Dict[str, Any] = {
                    "ts": datetime.utcnow().isoformat() + "Z",
                    "kind": kind,
                    "action": None,
                    "url": url,
                    "method": request.method,
                    "request": None,
                    "response": None,
                    "meta": {},
                }
                # Request body
                body_text = request.post_data or None
                body_obj = None
                if (
                    body_text
                    and isinstance(body_text, str)
                    and "application/json" in (request.headers or {}).get("content-type", "")
                ):
                    try:
                        body_obj = json.loads(body_text)
                    except Exception:
                        pass
                evt["request"] = _redact(body_obj) if body_obj else body_text
                # Extract meta/action for interactions
                if kind == "interaction" and isinstance(body_obj, dict):
                    meta = {}
                    meta["guild_id"] = body_obj.get("guild_id")
                    meta["channel_id"] = body_obj.get("channel_id")
                    meta["session_id"] = body_obj.get("session_id")
                    meta["nonce"] = body_obj.get("nonce")
                    meta["message_id"] = body_obj.get("message_id")
                    meta["message_flags"] = body_obj.get("message_flags")
                    cid = (body_obj.get("data") or {}).get("custom_id")
                    meta["custom_id"] = cid
                    evt["meta"] = meta
                    t = body_obj.get("type")
                    if t == 3:
                        if isinstance(cid, str) and cid.startswith("MJ::CustomZoom::"):
                            evt["action"] = "custom_zoom_button"
                        elif isinstance(cid, str) and cid.startswith("MJ::Inpaint::"):
                            evt["action"] = "inpaint_button"
                        elif isinstance(cid, str) and cid.startswith("MJ::"):
                            evt["action"] = "mj_button"
                        else:
                            evt["action"] = "interaction_button"
                    elif t == 5:
                        if isinstance(cid, str) and "CustomZoom" in cid:
                            evt["action"] = "custom_zoom_submit"
                        elif isinstance(cid, str) and "Inpaint" in cid:
                            evt["action"] = "inpaint_submit"
                        else:
                            evt["action"] = "modal_submit"
                write_event(evt)
            except Exception:
                pass

        async def on_response(response):
            try:
                req = response.request
                url = req.url
                if not _is_target_url(url):
                    return
                kind = _classify(url)
                if kind not in {"attachments", "message"} and not args.all_events:
                    return
                # Build response event with minimal join back to request
                evt: Dict[str, Any] = {
                    "ts": datetime.utcnow().isoformat() + "Z",
                    "kind": kind,
                    "action": None,
                    "url": url,
                    "method": req.method,
                    "request": None,
                    "response": None,
                    "meta": {},
                }
                # We only include response JSON when available
                ctype = response.headers.get("content-type", "")
                if "application/json" in ctype:
                    try:
                        body = await response.body()
                        data = json.loads(body.decode("utf-8", errors="ignore"))
                        evt["response"] = _redact(data)
                        if kind == "attachments":
                            try:
                                att = (data.get("attachments") or [None])[0]
                                if att and att.get("upload_filename"):
                                    evt["meta"]["uploaded_filename"] = att.get("upload_filename")
                            except Exception:
                                pass
                    except Exception:
                        pass
                write_event(evt)
            except Exception:
                pass

        context.on("request", on_request)
        context.on("response", lambda r: asyncio.create_task(on_response(r)))

        # Wait until user presses Enter
        try:
            input()
        except EOFError:
            await asyncio.sleep(2)

        f.close()
        try:
            await context.close()
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
