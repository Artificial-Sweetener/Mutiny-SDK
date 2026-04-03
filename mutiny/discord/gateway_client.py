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

"""Discord gateway client handling Midjourney session lifecycles and dispatch."""

import asyncio
import json
import logging
import random
import zlib
from typing import Any, Awaitable, Callable, Optional

import websockets

from ..config import Config
from ..services.interaction_cache import InteractionCache
from ..services.metrics.service import MetricsService
from ..services.response_dump import ResponseDumpService
from .event_scanner import EventScanResult, scan_gateway_event
from .identity import DiscordIdentity, DiscordSessionState

logger = logging.getLogger(__name__)

GATEWAY_BASE = "wss://gateway.discord.gg"
FLUSH_MARKER = b"\x00\x00\xff\xff"


MessageHandler = Callable[[str, dict], Awaitable[None] | None]


def _compute_backoff_state(
    current: float,
    base: float,
    cap: float,
    jitter: float,
    *,
    rand: Callable[[], float] = random.random,
) -> tuple[float, float]:
    """Return (delay, next_backoff) using capped exponential backoff with jitter."""

    delay = min(cap, current) + (jitter * (0.5 - rand()))
    clamped_delay = max(0.0, delay)
    next_backoff = min(cap, max(base, current * 2))
    return clamped_delay, next_backoff


class DiscordGatewayClient:
    """Manage the persistent Discord websocket, heartbeats, and dispatch handling."""

    def __init__(
        self,
        *,
        identity: DiscordIdentity,
        session: DiscordSessionState,
        config: Config,
        interaction_cache: InteractionCache,
        metrics: MetricsService,
        response_dump: ResponseDumpService,
        message_handler: MessageHandler,
    ):
        """Initialize gateway state, connection config, and handlers for a Discord identity."""
        self.identity = identity
        self.session = session
        self.config = config
        self.interaction_cache = interaction_cache
        self.metrics = metrics
        self.response_dump = response_dump
        self.message_handler = message_handler
        self.ws: Optional[websockets.WebSocketClientProtocol] = None

        self.heartbeat_interval: float = 0.0
        self.sequence = None

        self._token = self.identity.token_provider.get_token()

        self.heartbeat_ack: bool = False

        self._zobj = zlib.decompressobj()
        self._zb = bytearray()

        self._hb_task: Optional[asyncio.Task] = None
        self._hb_timeout_task: Optional[asyncio.Task] = None

    def _reset_stream_state(self) -> None:
        """Reset zlib stream buffers before a new websocket attempt."""
        self._zobj = zlib.decompressobj()
        self._zb.clear()

    def _gateway_url(self, reconnect: bool) -> str:
        """Build the gateway URL, preferring the resume endpoint when reconnecting."""
        base = (
            self.session.resume_gateway_url
            if reconnect and self.session.resume_gateway_url
            else GATEWAY_BASE
        )
        return f"{base}/?encoding=json&v=9&compress=zlib-stream"

    async def reconnect_with_config(self, config: Config) -> None:
        """Swap config/backoff settings and trigger a reconnect cycle."""

        self.config = config
        if self.ws:
            try:
                await self.ws.close(code=2002, reason="config update")
            except Exception:
                logger.warning(
                    "WS - Failed to close websocket on config update for %s",
                    self.identity.channel_id,
                    exc_info=True,
                )
        # Ensure token is refreshed if the provider swapped
        try:
            self._token = self.identity.token_provider.get_token()
        except Exception:
            logger.warning(
                "WS - Failed to refresh token provider for %s",
                self.identity.channel_id,
                exc_info=True,
            )

    async def _start_hb_timeout(self):
        """Schedule a heartbeat timeout that will force-close if acks stall."""
        self._cancel_hb_timeout()

        async def _wait():
            try:
                await asyncio.sleep(self.heartbeat_interval)
                if not self.heartbeat_ack and self.ws:
                    await self.ws.close(code=2001, reason="heartbeat has not ack")
            except asyncio.CancelledError:
                pass

        self._hb_timeout_task = asyncio.create_task(_wait())

    def _cancel_hb_timeout(self):
        """Cancel any pending heartbeat timeout task."""
        if self._hb_timeout_task and not self._hb_timeout_task.done():
            self._hb_timeout_task.cancel()
        self._hb_timeout_task = None

    def is_ready(self) -> bool:
        """Report whether a websocket is active and the session is resumable."""
        return (self.ws is not None) and self.session.has_session()

    def _zfeed(self, chunk: bytes):
        """Incrementally decompress zlib-stream frames and return JSON when flushed."""
        self._zb.extend(chunk)
        if len(chunk) >= 4 and chunk[-4:] == FLUSH_MARKER:
            text = self._zobj.decompress(bytes(self._zb)).decode("utf-8")
            self._zb.clear()
            return json.loads(text)
        return None

    async def _do_resume_or_identify(self):
        """Resume a known session when possible, otherwise perform IDENTIFY."""
        if self.session.session_id:
            payload = {
                "op": 6,
                "d": {
                    "token": self._token,
                    "session_id": self.session.session_id,
                    "seq": self.sequence,
                },
            }
            await self.send_json(payload)
            logger.info(f"WS - RESUME sent for {self.identity.channel_id}")
        else:
            await self.identify()

    async def send_json(self, payload: dict):
        """Send a JSON payload over the active websocket if connected."""
        if self.ws:
            await self.ws.send(json.dumps(payload))

    async def connect(self):
        """Maintain the gateway connection with backoff, resume, and message dispatch."""
        logger.info(f"WS - Connecting for account {self.identity.channel_id}.")

        headers = [
            ("Accept-Encoding", "gzip, deflate, br"),
            ("Accept-Language", "en-US,en;q=0.9"),
            ("Cache-Control", "no-cache"),
            ("Pragma", "no-cache"),
            ("Sec-Websocket-Extensions", "permessage-deflate; client_max_window_bits"),
            ("User-Agent", self.identity.user_agent),
            ("Origin", "https://discord.com"),
            ("Referer", "https://discord.com/channels/@me"),
        ]

        reconnect = False
        ws_cfg = self.config.websocket
        base = max(0.0, float(ws_cfg.backoff_initial))
        cap = max(base, float(ws_cfg.backoff_max))
        jitter = max(0.0, float(ws_cfg.backoff_jitter))
        backoff = base
        while True:
            url = self._gateway_url(reconnect)

            def _mark_connected() -> None:
                nonlocal backoff
                backoff = base

            try:
                await self._run_websocket_once(
                    url=url,
                    headers=headers,
                    on_connected=_mark_connected,
                )
            except asyncio.CancelledError:
                raise
            except websockets.ConnectionClosed as e:
                self.metrics.increment_discord_error("gateway")
                logger.warning(
                    f"WS - Connection closed for {self.identity.channel_id}: {e.code} {e.reason}"
                )
                reconnect = True
                delay, backoff = _compute_backoff_state(backoff, base, cap, jitter)
                logger.info(f"WS - Reconnecting in {delay:.2f}s for {self.identity.channel_id}")
                await self._sleep_with_backoff(delay)
            except Exception as e:
                self.metrics.increment_discord_error("gateway")
                logger.exception(f"WS - Error for {self.identity.channel_id}: {e}")
                reconnect = True
                delay, backoff = _compute_backoff_state(backoff, base, cap, jitter)
                logger.info(f"WS - Reconnecting in {delay:.2f}s for {self.identity.channel_id}")
                await self._sleep_with_backoff(delay)

    async def _run_websocket_once(
        self, *, url: str, headers: list[tuple[str, str]], on_connected: Callable[[], None]
    ) -> None:
        """Open a websocket, stream messages, and invoke the connected hook."""

        self._reset_stream_state()
        async with websockets.connect(
            url,
            ping_interval=None,
            extra_headers=headers,
        ) as ws:
            self.ws = ws
            on_connected()
            await asyncio.sleep(1.0)
            async for message in ws:
                await self.handle_message(message)

    async def _sleep_with_backoff(self, delay: float) -> None:
        """Sleep for a backoff interval (non-negative)."""

        await asyncio.sleep(max(0.0, delay))

    async def handle_message(self, message):
        """Process gateway frames, manage heartbeats, and dispatch events downstream."""
        if isinstance(message, (bytes, bytearray)):
            data = self._zfeed(bytes(message))
            if data is None:
                return
        else:
            data = json.loads(message)

        op = data.get("op")
        self.sequence = data.get("s") or self.sequence

        # Opportunistic gateway event dumping for capture sessions
        try:
            if op == 0:
                t = data.get("t")
                if self.response_dump.is_enabled():
                    self.response_dump.dump_gateway_event(op=int(op), t=t, payload=data)
        except Exception:
            logger.warning(
                "WS - Failed to dump gateway event op=%s t=%s for %s",
                op,
                data.get("t"),
                self.identity.channel_id,
                exc_info=True,
            )

        if op == 10:
            self.heartbeat_interval = data["d"]["heartbeat_interval"] / 1000.0
            self.heartbeat_ack = True
            logger.info(
                f"WS - HELLO received. Heartbeat interval: {self.heartbeat_interval}s "
                f"for {self.identity.channel_id}"
            )
            if self._hb_task and not self._hb_task.done():
                self._hb_task.cancel()
            self._hb_task = asyncio.create_task(self.send_heartbeats())
            await self._do_resume_or_identify()

        elif op == 11:
            self.heartbeat_ack = True
            self._cancel_hb_timeout()
            logger.debug(f"WS - Heartbeat acknowledged for {self.identity.channel_id}")

        elif op == 1:
            await self.send_json({"op": 1, "d": self.sequence})
            await self._start_hb_timeout()
            logger.debug(
                f"WS - Responded to server HEARTBEAT request for {self.identity.channel_id}"
            )

        elif op == 0:
            t = data.get("t")
            logger.debug(f"WS - DISPATCH {t} for {self.identity.channel_id}")

            if t == "READY":
                d = data.get("d", {})
                self.session.set_ready(d.get("session_id"), d.get("resume_gateway_url"))
                logger.info(f"WS - READY received; session_id set for {self.identity.channel_id}")
            elif t == "RESUMED":
                logger.info(f"WS - RESUMED received for {self.identity.channel_id}")
            else:
                scan_result = self._scan_event(data)
                if scan_result.errors:
                    self.metrics.increment_discord_error("gateway_scan")
                    for error in scan_result.errors:
                        logger.warning(
                            "WS - %s for %s (event=%s)",
                            error.message,
                            self.identity.channel_id,
                            error.event_type,
                            exc_info=error.exception,
                        )

            if t in ("MESSAGE_CREATE", "MESSAGE_UPDATE"):
                event_data = data["d"]
                res = self.message_handler(t, event_data)
                if asyncio.iscoroutine(res):
                    await res

        elif op == 7:
            logger.warning(f"WS - RECONNECT requested by server for {self.identity.channel_id}")
            if self.ws:
                await self.ws.close(code=2001, reason="server asked to reconnect")

        elif op == 9:
            resumable = bool(data.get("d"))
            logger.warning(
                f"WS - INVALID_SESSION (resumable={resumable}) for {self.identity.channel_id}"
            )
            if not resumable:
                self.session.clear()
                self.sequence = None
            if self.ws:
                await self.ws.close(code=4000, reason="receive session invalid")

        else:
            logger.debug(f"WS - Unhandled op={op} for {self.identity.channel_id}: {data}")

    async def send_heartbeats(self):
        """Continuously send heartbeats and reconnect when acks are missed."""
        initial_delay = random.random() * self.heartbeat_interval
        await asyncio.sleep(initial_delay)

        while True:
            if not self.ws:
                return
            if not self.heartbeat_ack:
                logger.warning("WS - Heartbeat not acknowledged (interval). Reconnecting...")
                await self.ws.close(code=2001, reason="heartbeat has not ack interval")
                return

            self.heartbeat_ack = False
            await self.send_json({"op": 1, "d": self.sequence})
            logger.debug(f"WS - Heartbeat sent for {self.identity.channel_id}")

            await asyncio.sleep(self.heartbeat_interval)

    async def identify(self):
        """Send the IDENTIFY payload with the frozen Discord client fingerprint and token.

        Uses the Midjourney-aligned Chrome/Windows fingerprint (build 222963), disables
        compression, and keeps presence empty/online. The payload must remain byte-stable to
        preserve gateway compatibility and impersonation behaviour.
        """
        ua = self.identity.user_agent
        payload = {
            "op": 2,
            "d": {
                "token": self._token,
                "capabilities": 16381,
                "properties": {
                    "browser": "Chrome",
                    "browser_user_agent": ua,
                    "browser_version": "",
                    "client_build_number": 222963,
                    "client_event_source": None,
                    "device": "",
                    "os": "Windows",
                    "referer": "https://www.midjourney.com",
                    "referrer_current": "",
                    "referring_domain": "www.midjourney.com",
                    "referring_domain_current": "",
                    "release_channel": "stable",
                    "system_locale": "en-US",
                },
                "compress": False,
                "client_state": {
                    "api_code_version": 0,
                    "guild_versions": {},
                    "highest_last_message_id": "0",
                    "private_channels_version": "0",
                    "read_state_version": 0,
                    "user_guild_settings_version": -1,
                    "user_settings_version": -1,
                },
                "presence": {
                    "activities": [],
                    "afk": False,
                    "since": 0,
                    "status": "online",
                },
            },
        }
        await self.send_json(payload)
        logger.info(f"WS - IDENTIFY sent for {self.identity.channel_id}")

    async def close(self):
        """Close the websocket and cancel heartbeat tasks."""
        ws, self.ws = self.ws, None
        if self._hb_task and not self._hb_task.done():
            self._hb_task.cancel()
        self._cancel_hb_timeout()
        if ws:
            try:
                await ws.close()
            except Exception:
                pass

    def _scan_event(self, data: dict[str, Any]) -> EventScanResult:
        """Delegate gateway event scanning to the dedicated scanner."""

        return scan_gateway_event(data, self.interaction_cache, self.identity)


__all__ = ["DiscordGatewayClient", "MessageHandler"]
