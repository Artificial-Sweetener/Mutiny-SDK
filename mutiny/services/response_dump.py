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

import json
import os
import time
from typing import Any, Dict, List, Optional


class ResponseDumpService:
    """Dumps raw MJ Discord/Gateway payloads and concise summaries to disk.

    - When enabled, persists:
      - Per-message dumps for MJ replies (upscale/variation/etc.)
      - Gateway DISPATCH events (for capture sessions)
      - A rolling index.jsonl with compact summaries
    - Secrets are best-effort redacted from dumps
    """

    def __init__(self, root_dir: str = ".cache/mutiny/mj_responses", enabled: bool = False):
        self.root_dir = root_dir
        self.enabled = bool(enabled)
        os.makedirs(self.root_dir, exist_ok=True)

    def apply_config(self, *, root_dir: str, enabled: bool) -> None:
        """Hot-apply response dump settings without swapping instances."""

        if root_dir != self.root_dir:
            self.root_dir = root_dir
            os.makedirs(self.root_dir, exist_ok=True)
        self.enabled = bool(enabled)
        if self.enabled:
            os.makedirs(self.root_dir, exist_ok=True)

    def _components_summary(self, message: Dict[str, Any]) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        rows = message.get("components") or []
        for row in rows:
            comps = row.get("components") or []
            for c in comps:
                if not isinstance(c, dict):
                    continue
                label = c.get("label")
                custom_id = c.get("custom_id")
                ctype = c.get("type")  # 2=button, etc.
                style = c.get("style")
                emoji = None
                if c.get("emoji"):
                    emoji = c["emoji"].get("name") or c["emoji"].get("id")
                items.append(
                    {
                        "label": label,
                        "custom_id": custom_id,
                        "type": ctype,
                        "style": style,
                        "emoji": emoji,
                    }
                )
        return items

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = bool(enabled)

    def is_enabled(self) -> bool:
        return bool(self.enabled)

    def _redact(self, obj: Any) -> Any:
        # Recursively redact sensitive tokens/ids (best-effort)
        SENSITIVE_KEYS = {"token", "authorization", "Authorization", "session_id", "sessionId"}
        try:
            if isinstance(obj, dict):
                out = {}
                for k, v in obj.items():
                    if k in SENSITIVE_KEYS:
                        out[k] = "<redacted>"
                    else:
                        out[k] = self._redact(v)
                return out
            if isinstance(obj, list):
                return [self._redact(v) for v in obj]
            return obj
        except Exception:
            # Fallback to raw object on any redact failure
            return obj

    def _dump(
        self,
        *,
        kind: str,
        message: Dict[str, Any],
        prompt: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        now = time.time()
        msg_id = message.get("id") or f"unknown-{int(now)}"
        content = message.get("content") or ""
        attachments = message.get("attachments") or []
        image_url = attachments[0].get("url") if attachments else None
        flags = int(message.get("flags") or 0)
        summary = {
            "ts": now,
            "kind": kind,
            "message_id": msg_id,
            "flags": flags,
            "prompt": prompt or content,
            "image_url": image_url,
            "components": self._components_summary(message),
        }
        if extra:
            summary.update(extra)

        # Write full payload
        with open(os.path.join(self.root_dir, f"{msg_id}.json"), "w", encoding="utf-8") as f:
            json.dump(
                {"summary": summary, "raw": self._redact(message)}, f, ensure_ascii=False, indent=2
            )

        # Append to index
        with open(os.path.join(self.root_dir, "index.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(summary, ensure_ascii=False) + "\n")

    def dump_imagine(self, *, message: Dict[str, Any], prompt: Optional[str] = None) -> None:
        self._dump(kind="IMAGINE", message=message, prompt=prompt)

    def dump_variation(self, *, message: Dict[str, Any], prompt: Optional[str] = None) -> None:
        self._dump(kind="VARIATION", message=message, prompt=prompt)

    def dump_reroll(self, *, message: Dict[str, Any], prompt: Optional[str] = None) -> None:
        self._dump(kind="REROLL", message=message, prompt=prompt)

    def dump_upscale(self, *, message: Dict[str, Any], prompt: Optional[str] = None) -> None:
        self._dump(kind="UPSCALE", message=message, prompt=prompt)

    def dump_blend(self, *, message: Dict[str, Any], prompt: Optional[str] = None) -> None:
        self._dump(kind="BLEND", message=message, prompt=prompt)

    def dump_describe(self, *, message: Dict[str, Any], prompt: Optional[str] = None) -> None:
        self._dump(kind="DESCRIBE", message=message, prompt=prompt)

    def dump_progress(self, *, message: Dict[str, Any], prompt: Optional[str] = None) -> None:
        self._dump(kind="PROGRESS", message=message, prompt=prompt)

    def dump_error(
        self,
        *,
        message: Dict[str, Any],
        prompt: Optional[str] = None,
        error_title: Optional[str] = None,
        error_description: Optional[str] = None,
        error_footer: Optional[str] = None,
    ) -> None:
        self._dump(
            kind="ERROR",
            message=message,
            prompt=prompt,
            extra={
                "referenced_message_id": (message.get("message_reference") or {}).get("message_id"),
                "error_title": error_title,
                "error_description": error_description,
                "error_footer": error_footer,
            },
        )

    # --- Gateway event capture (listener) ---

    def dump_gateway_event(self, *, op: int, t: Optional[str], payload: Dict[str, Any]) -> None:
        if not self.enabled:
            return
        try:
            now = time.time()
            kind = f"DISPATCH:{t}" if (op == 0 and t) else f"OP:{op}"
            # Prefer message id if present in d
            msg_id = None
            try:
                d = payload.get("d") or {}
                msg_id = d.get("id") or d.get("message", {}).get("id")
            except Exception:
                msg_id = None
            fname = f"gw_{int(now * 1000)}_{op}_{t or 'NA'}_{msg_id or 'noid'}.json"
            data = {"op": op, "t": t, "raw": self._redact(payload)}
            with open(os.path.join(self.root_dir, fname), "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            # Append to index with minimal summary
            summary = {"ts": now, "kind": kind, "t": t, "message_id": msg_id}
            with open(os.path.join(self.root_dir, "index.jsonl"), "a", encoding="utf-8") as f:
                f.write(json.dumps(summary, ensure_ascii=False) + "\n")
        except Exception:
            # Never throw from dumper
            pass
