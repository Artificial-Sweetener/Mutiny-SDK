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

import logging
import re
from contextvars import ContextVar
from typing import Iterable, Optional

SENSITIVE_PATTERNS: Iterable[tuple[re.Pattern[str], int]] = [
    # Authorization headers
    (re.compile(r"(authorization\s*[:=]\s*)((?:bearer\s+)?)\S+", re.IGNORECASE), 1),
    # Query params like token=, auth=, api_key=
    (re.compile(r"([?&])(token|auth|authorization|api[_-]?key)=([^&#\s]+)", re.IGNORECASE), 2),
    # JSON-like or key-value fields containing sensitive keys
    (
        re.compile(
            r"(?P<prefix>^|[\s,{])(?P<key>token|user[_-]?token|api[_-]?secret|secret|session[_-]?id)\s*[:=]\s*(?:'[^']*'|\"[^\"]*\"|\S+)",
            re.IGNORECASE,
        ),
        3,
    ),
]


def _scrub(text: str) -> str:
    if not text:
        return text

    def _repl(m: re.Match[str], kind: int) -> str:
        if kind == 1:  # Authorization header
            return f"{m.group(1)}{m.group(2)}[REDACTED]"
        if kind == 2:  # query param
            return f"{m.group(1)}{m.group(2)}=[REDACTED]"
        # key-value with sensitive key
        prefix = m.group("prefix") if "prefix" in m.groupdict() else ""
        key = m.group("key") if "key" in m.groupdict() else m.group(1)
        return f"{prefix}{key}: [REDACTED]"

    for pat, kind in SENSITIVE_PATTERNS:
        text = pat.sub(lambda m, k=kind: _repl(m, k), text)
    return text


class SensitiveDataFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:  # type: ignore[override]
        try:
            rendered = (
                record.msg % record.args
                if (isinstance(record.msg, str) and record.args)
                else str(record.msg)
            )
            # Apply correlation prefix if available
            prefix = _correlation_prefix()
            rendered = f"{prefix}{rendered}" if prefix else rendered
            scrubbed = _scrub(rendered)
            record.msg = scrubbed
            record.args = ()
        except Exception:
            # Never block logging; fail open without modification
            pass
        return True


def install_logging_scrubber():
    filt = SensitiveDataFilter()
    # Root logger
    logging.getLogger().addFilter(filt)
    # Common third-party loggers used here
    for name in ("httpx",):
        logging.getLogger(name).addFilter(filt)


# --- Correlation context ---
_JOB_CONTEXT: ContextVar[dict] = ContextVar("JOB_CONTEXT", default={})


def set_job_context(
    job_id: Optional[str] = None,
    action: Optional[str] = None,
    status: Optional[str] = None,
    latency_ms: Optional[float] = None,
):
    ctx = _JOB_CONTEXT.get({}).copy()
    if job_id is not None:
        ctx["job_id"] = job_id
    if action is not None:
        ctx["action"] = action
    if status is not None:
        ctx["status"] = status
    if latency_ms is not None:
        ctx["latency_ms"] = latency_ms
    _JOB_CONTEXT.set(ctx)


def clear_job_context():
    _JOB_CONTEXT.set({})


def _correlation_prefix() -> str:
    try:
        ctx = _JOB_CONTEXT.get({})
        parts = []
        job_id = ctx.get("job_id")
        action = ctx.get("action")
        status = ctx.get("status")
        latency_ms = ctx.get("latency_ms")
        if job_id:
            parts.append(f"job_id={job_id}")
        if action:
            parts.append(f"action={action}")
        if status:
            parts.append(f"status={status}")
        if latency_ms is not None:
            parts.append(f"latency_ms={int(latency_ms)}")
        if parts:
            return f"[{' '.join(parts)}] "
    except Exception:
        return ""
    return ""


__all__ = [
    "SensitiveDataFilter",
    "install_logging_scrubber",
    "set_job_context",
    "clear_job_context",
]
