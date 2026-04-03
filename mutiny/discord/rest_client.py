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

import asyncio
import logging
import random
from typing import Callable, Optional
from urllib.parse import quote

import httpx

from ..config import Config
from ..services.interaction_cache import InteractionCache
from ..services.metrics.service import MetricsService
from .constants import APPLICATION_ID
from .custom_ids import (
    build_animate_custom_id,
    build_animate_extend_custom_id,
    build_cancel_by_jobid,
    build_custom_zoom_button_custom_id,
    build_custom_zoom_modal_custom_id,
    build_high_variation_custom_id,
    build_inpaint_custom_id,
    build_low_variation_custom_id,
    build_outpaint_custom_id,
    build_pan_custom_id,
    build_reroll_custom_id,
    build_upscale_custom_id,
    build_upscale_v7_custom_id,
    build_variation_custom_id,
)
from .identity import DiscordIdentity, DiscordSessionState
from .payload_builder import DiscordPayloadBuilder

logger = logging.getLogger(__name__)


class DiscordAPIError(Exception):
    pass


class DiscordRestClient:
    def __init__(
        self,
        identity: DiscordIdentity,
        *,
        session: DiscordSessionState,
        config: Config,
        interaction_cache: InteractionCache,
        metrics: MetricsService,
    ):
        self.identity = identity
        self.session = session
        self.config = config
        self.interaction_cache = interaction_cache
        self.metrics = metrics
        token = self.identity.token_provider.get_token()
        self.base_headers = {
            "Authorization": token,
            "User-Agent": self.identity.user_agent,
            "Origin": "https://discord.com",
            "Referer": f"https://discord.com/channels/{self.identity.guild_id}/{self.identity.channel_id}",
        }
        http_cfg = self.config.http
        timeout = httpx.Timeout(
            connect=http_cfg.connect_timeout,
            read=http_cfg.read_timeout,
            write=http_cfg.write_timeout,
            pool=http_cfg.pool_timeout,
        )
        self.client = httpx.AsyncClient(headers=self.base_headers, timeout=timeout)
        cdn_cfg = self.config.cdn
        cdn_timeout = httpx.Timeout(
            connect=cdn_cfg.connect_timeout,
            read=cdn_cfg.read_timeout,
            write=cdn_cfg.write_timeout,
            pool=cdn_cfg.pool_timeout,
        )
        # No default auth headers for CDN/S3 URLs
        self.cdn_client = httpx.AsyncClient(timeout=cdn_timeout)
        self.api_base = self.config.discord.api_endpoint.rstrip("/")
        # Centralized payload builders
        self.payloads = DiscordPayloadBuilder()

    async def apply_config(self, config: Config) -> None:
        """Rebuild HTTP and CDN clients using updated config settings."""

        # Build new clients first, then swap and close old to avoid gaps.
        http_cfg = config.http
        new_http = httpx.AsyncClient(
            headers=self.base_headers,
            timeout=httpx.Timeout(
                connect=http_cfg.connect_timeout,
                read=http_cfg.read_timeout,
                write=http_cfg.write_timeout,
                pool=http_cfg.pool_timeout,
            ),
        )

        cdn_cfg = config.cdn
        new_cdn = httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=cdn_cfg.connect_timeout,
                read=cdn_cfg.read_timeout,
                write=cdn_cfg.write_timeout,
                pool=cdn_cfg.pool_timeout,
            )
        )

        old_http, old_cdn = self.client, self.cdn_client
        self.config = config
        self.client = new_http
        self.cdn_client = new_cdn
        self.api_base = self.config.discord.api_endpoint.rstrip("/")

        try:
            await old_http.aclose()
        except Exception:
            pass
        try:
            await old_cdn.aclose()
        except Exception:
            pass

    def _session_id(self) -> Optional[str]:
        return self.session.session_id

    def _require_session(self) -> str | None:
        if not self.session.has_session():
            return "Account not connected to WebSocket"
        return None

    async def _do_button_action(
        self,
        *,
        message_id: str,
        message_flags: int,
        nonce: str,
        build_custom_id: Callable[[], str],
    ) -> str:
        """Build a custom_id then send the button interaction."""

        try:
            custom_id = build_custom_id()
        except Exception as exc:  # defensive: builder should not raise
            logger.error("Failed to build custom_id: %s", exc)
            return str(exc)

        return await self.send_button_interaction(
            message_id=message_id,
            custom_id=custom_id,
            message_flags=message_flags,
            nonce=nonce,
        )

    async def send_button_interaction(
        self, message_id: str, custom_id: str, message_flags: int, nonce: str
    ) -> str:
        """
        Send a generic button interaction by custom_id.

        This centralizes the common POST /interactions flow for button-based actions.
        Callers provide the exact Discord component custom_id string and message context.
        """
        missing = self._require_session()
        if missing:
            return missing

        payload = self.payloads.build_button_interaction(
            self.identity,
            nonce,
            message_id=message_id,
            message_flags=message_flags,
            custom_id=custom_id,
            session_id=self._session_id(),
        )

        url = f"{self.api_base}/interactions"
        try:
            response = await self._request("POST", url, json=payload)
        except Exception as e:
            self.metrics.increment_discord_error("rest")
            logger.error(f"Error sending button interaction: {e}")
            return str(e)

        if response.status_code == 204:
            return "Success"

        return response.text

    async def imagine(self, prompt: str, nonce: str):
        missing = self._require_session()
        if missing:
            return missing

        payload = self.payloads.build_imagine(
            self.identity, prompt, nonce, session_id=self._session_id()
        )

        url = f"{self.api_base}/interactions"
        try:
            response = await self._request("POST", url, json=payload)
        except Exception as e:
            self.metrics.increment_discord_error("rest")
            logger.error(f"Error sending imagine command: {e}")
            return str(e)

        if response.status_code == 204:
            return "Success"

        return response.text

    async def cancel_job(self, message_id: str, job_id: str, message_flags: int, nonce: str):
        custom_id = build_cancel_by_jobid(job_id)
        return await self.send_button_interaction(
            message_id=message_id,
            custom_id=custom_id,
            message_flags=message_flags,
            nonce=nonce,
        )

    async def upscale(
        self, message_id: str, index: int, message_hash: str, message_flags: int, nonce: str
    ):
        return await self._do_button_action(
            message_id=message_id,
            message_flags=message_flags,
            nonce=nonce,
            build_custom_id=lambda: build_upscale_custom_id(index, message_hash),
        )

    async def variation(
        self, message_id: str, index: int, message_hash: str, message_flags: int, nonce: str
    ):
        return await self._do_button_action(
            message_id=message_id,
            message_flags=message_flags,
            nonce=nonce,
            build_custom_id=lambda: build_variation_custom_id(index, message_hash),
        )

    async def vary_subtle(
        self, message_id: str, index: int, message_hash: str, message_flags: int, nonce: str
    ):
        return await self._do_button_action(
            message_id=message_id,
            message_flags=message_flags,
            nonce=nonce,
            build_custom_id=lambda: build_low_variation_custom_id(index, message_hash),
        )

    async def vary_strong(
        self, message_id: str, index: int, message_hash: str, message_flags: int, nonce: str
    ):
        return await self._do_button_action(
            message_id=message_id,
            message_flags=message_flags,
            nonce=nonce,
            build_custom_id=lambda: build_high_variation_custom_id(index, message_hash),
        )

    async def reroll(self, message_id: str, message_hash: str, message_flags: int, nonce: str):
        return await self._do_button_action(
            message_id=message_id,
            message_flags=message_flags,
            nonce=nonce,
            build_custom_id=lambda: build_reroll_custom_id(message_hash),
        )

    async def upscale_v7_subtle(
        self, message_id: str, index: int, message_hash: str, message_flags: int, nonce: str
    ):
        return await self._do_button_action(
            message_id=message_id,
            message_flags=message_flags,
            nonce=nonce,
            build_custom_id=lambda: build_upscale_v7_custom_id("subtle", index, message_hash),
        )

    async def upscale_v7_creative(
        self, message_id: str, index: int, message_hash: str, message_flags: int, nonce: str
    ):
        return await self._do_button_action(
            message_id=message_id,
            message_flags=message_flags,
            nonce=nonce,
            build_custom_id=lambda: build_upscale_v7_custom_id("creative", index, message_hash),
        )

    # --- Outpaint (Zoom Out) ---

    async def outpaint_50(
        self, message_id: str, index: int, message_hash: str, message_flags: int, nonce: str
    ):
        return await self._do_button_action(
            message_id=message_id,
            message_flags=message_flags,
            nonce=nonce,
            build_custom_id=lambda: build_outpaint_custom_id(50, index, message_hash),
        )

    async def outpaint_75(
        self, message_id: str, index: int, message_hash: str, message_flags: int, nonce: str
    ):
        return await self._do_button_action(
            message_id=message_id,
            message_flags=message_flags,
            nonce=nonce,
            build_custom_id=lambda: build_outpaint_custom_id(75, index, message_hash),
        )

    # --- Pan (arrows) ---

    async def pan_left(
        self, message_id: str, index: int, message_hash: str, message_flags: int, nonce: str
    ):
        return await self._do_button_action(
            message_id=message_id,
            message_flags=message_flags,
            nonce=nonce,
            build_custom_id=lambda: build_pan_custom_id("left", index, message_hash),
        )

    async def pan_right(
        self, message_id: str, index: int, message_hash: str, message_flags: int, nonce: str
    ):
        return await self._do_button_action(
            message_id=message_id,
            message_flags=message_flags,
            nonce=nonce,
            build_custom_id=lambda: build_pan_custom_id("right", index, message_hash),
        )

    async def pan_up(
        self, message_id: str, index: int, message_hash: str, message_flags: int, nonce: str
    ):
        return await self._do_button_action(
            message_id=message_id,
            message_flags=message_flags,
            nonce=nonce,
            build_custom_id=lambda: build_pan_custom_id("up", index, message_hash),
        )

    async def pan_down(
        self, message_id: str, index: int, message_hash: str, message_flags: int, nonce: str
    ):
        return await self._do_button_action(
            message_id=message_id,
            message_flags=message_flags,
            nonce=nonce,
            build_custom_id=lambda: build_pan_custom_id("down", index, message_hash),
        )

    # --- Animate (High/Low motion) ---

    async def animate_high(
        self, message_id: str, index: int, message_hash: str, message_flags: int, nonce: str
    ):
        return await self._do_button_action(
            message_id=message_id,
            message_flags=message_flags,
            nonce=nonce,
            build_custom_id=lambda: build_animate_custom_id("high", index, message_hash),
        )

    async def animate_low(
        self, message_id: str, index: int, message_hash: str, message_flags: int, nonce: str
    ):
        return await self._do_button_action(
            message_id=message_id,
            message_flags=message_flags,
            nonce=nonce,
            build_custom_id=lambda: build_animate_custom_id("low", index, message_hash),
        )

    async def animate_extend_high(
        self, message_id: str, index: int, message_hash: str, message_flags: int, nonce: str
    ):
        return await self._do_button_action(
            message_id=message_id,
            message_flags=message_flags,
            nonce=nonce,
            build_custom_id=lambda: build_animate_extend_custom_id("high", index, message_hash),
        )

    async def animate_extend_low(
        self, message_id: str, index: int, message_hash: str, message_flags: int, nonce: str
    ):
        return await self._do_button_action(
            message_id=message_id,
            message_flags=message_flags,
            nonce=nonce,
            build_custom_id=lambda: build_animate_extend_custom_id("low", index, message_hash),
        )

    async def custom_zoom(
        self, message_id: str, message_hash: str, message_flags: int, nonce: str, zoom_text: str
    ) -> str:
        """Perform Custom Zoom by sending the button then the modal submit with text."""
        missing = self._require_session()
        if missing:
            return missing

        # Step 1: button interaction
        btn_id = build_custom_zoom_button_custom_id(message_hash)
        btn_res = await self.send_button_interaction(
            message_id=message_id,
            custom_id=btn_id,
            message_flags=message_flags,
            nonce=nonce,
        )
        if btn_res != "Success":
            return btn_res

        # Give MJ a brief moment to surface the modal server-side
        try:
            await asyncio.sleep(3.0)
        except Exception:
            pass

        # Step 2: wait for modal id from gateway, then submit
        modal_id_value: str | None = None
        try:
            for _ in range(20):
                entry = self.interaction_cache.get_custom_zoom_modal(message_hash) or {}
                if entry.get("id"):
                    modal_id_value = str(entry.get("id"))
                    break
                await asyncio.sleep(0.5)
        except Exception:
            modal_id_value = None

        # Validate zoom text; do not auto-format. Ensure we don't send invalid input to Discord.
        ztxt = (zoom_text or "").strip()
        if "--zoom" not in ztxt:
            return "Invalid zoomText: requires --zoom <value>"

        # Build modal payload
        modal_id = build_custom_zoom_modal_custom_id(message_hash)
        # Use a fresh nonce for the modal submission as observed in captures
        try:
            from mutiny.domain.time import get_current_timestamp_ms as _now_ms

            modal_nonce = str(_now_ms())
        except Exception:
            modal_nonce = nonce
        payload = self.payloads.build_custom_zoom_modal(
            self.identity,
            modal_nonce,
            custom_id=modal_id,
            zoom_text=ztxt,
            modal_id=modal_id_value or modal_nonce,
            session_id=self._session_id(),
        )

        url = f"{self.api_base}/interactions"
        # Retry modal submission a couple of times to allow modal to initialize
        for attempt in range(3):
            try:
                response = await self._request("POST", url, json=payload)
                if response.status_code == 204:
                    return "Success"
                # Non-204 but no exception: treat as error text
                msg = response.text
            except Exception as e:
                msg = str(e)
            # If not last attempt, wait and retry
            if attempt < 2:
                delay = 1.5 * (attempt + 1)
                logger.warning(
                    f"Custom Zoom modal not accepted (attempt {attempt + 1}); "
                    f"retrying in {delay:.1f}s: {msg}"
                )
                await asyncio.sleep(delay)
                continue
            logger.error(f"Error sending custom-zoom modal: {msg}")
            self.metrics.increment_discord_error("rest")
            return msg

    async def inpaint_button(
        self, message_id: str, index: int, message_hash: str, message_flags: int, nonce: str
    ) -> str:
        custom_id = build_inpaint_custom_id(index, message_hash)
        return await self.send_button_interaction(
            message_id=message_id, custom_id=custom_id, message_flags=message_flags, nonce=nonce
        )

    async def inpaint_submit_job(
        self,
        *,
        iframe_token: str,
        mask_webp_base64: str,
        prompt: str | None,
    ) -> str:
        """Submit an inpaint edit through the current Midjourney iframe app contract."""

        app_origin = f"https://{APPLICATION_ID}.discordsays.com"
        iframe_custom_id = f"MJ::iframe::{iframe_token}"
        referer = (
            f"{app_origin}/.proxy/inpaint/index.html?"
            "instance_id="
            f"{self.identity.channel_id}:{APPLICATION_ID}:"
            f"{quote(iframe_custom_id, safe='')}"
            f"&custom_id={quote(iframe_custom_id, safe='')}"
            f"&channel_id={self.identity.channel_id}"
            f"&guild_id={self.identity.guild_id}"
            "&platform=desktop"
        )
        url = f"{app_origin}/.proxy/inpaint/api/submit-job/{iframe_token}"
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Origin": app_origin,
            "Referer": referer,
        }
        body = self.payloads.build_inpaint_submit_body(
            mask_webp_base64=mask_webp_base64,
            prompt=prompt,
        )
        try:
            resp = await self.cdn_client.post(url, json=body, headers=headers)
            # Consider any 2xx a success
            if 200 <= resp.status_code < 300:
                return "Success"
            self.metrics.increment_discord_error("rest")
            return f"Inpaint submit failed: {resp.status_code} {resp.text[:200]}"
        except Exception as e:
            self.metrics.increment_discord_error("rest")
            return f"Inpaint submit error: {e}"

    async def upload(self, filename: str, file_content: bytes, mime_type: str) -> str | None:
        url = f"{self.api_base}/channels/{self.identity.channel_id}/attachments"
        file_info = {"filename": filename, "file_size": len(file_content), "id": "0"}
        payload = {"files": [file_info]}
        try:
            response = await self._request("POST", url, json=payload)
            upload_data = response.json()["attachments"][0]
            upload_url = upload_data["upload_url"]
            upload_filename = upload_data["upload_filename"]
        except (DiscordAPIError, KeyError, IndexError) as e:
            self.metrics.increment_discord_error("rest")
            logger.error(f"Error getting upload URL: {e}")
            return None

        headers = {"Content-Type": mime_type}
        try:
            # Uploads go to CDN/S3; use CDN client with explicit timeouts, no retry/backoff.
            upload_response = await self.cdn_client.put(
                upload_url, content=file_content, headers=headers
            )
            upload_response.raise_for_status()
        except httpx.HTTPError as e:
            self.metrics.increment_discord_error("rest")
            logger.error(f"Error uploading file: {e}")
            return None

        return upload_filename

    async def send_image_message(self, content: str | None, uploaded_filename: str) -> str | None:
        url = f"{self.api_base}/channels/{self.identity.channel_id}/messages"
        file_name_only = uploaded_filename.split("/")[-1]
        body = {
            "content": content or "",
            "flags": 0,
            "attachments": [
                {
                    "id": "0",
                    "filename": file_name_only,
                    "uploaded_filename": uploaded_filename,
                }
            ],
        }
        try:
            response = await self._request("POST", url, json=body)
            data = response.json()
            atts = data.get("attachments") or []
            if atts:
                return atts[0].get("url")
            return None
        except Exception as e:
            self.metrics.increment_discord_error("rest")
            logger.error(f"Error sending image message: {e}")
            return None

    async def fetch_cdn_bytes(self, url: str) -> bytes | None:
        """Fetch bytes from a Discord CDN/S3 URL using the CDN client."""

        try:
            resp = await self.cdn_client.get(url)
            resp.raise_for_status()
            return resp.content
        except Exception as e:
            self.metrics.increment_discord_error("rest")
            logger.error("Error fetching CDN bytes: %s", e)
            return None

    async def describe(self, uploaded_filename: str, nonce: str):
        missing = self._require_session()
        if missing:
            return missing

        payload = self.payloads.build_describe_upload(
            self.identity, uploaded_filename, nonce, session_id=self._session_id()
        )

        url = f"{self.api_base}/interactions"
        try:
            await self._request("POST", url, json=payload)
            return "Success"
        except Exception as e:
            self.metrics.increment_discord_error("rest")
            logger.error(f"Error sending describe command: {e}")
            return str(e)

    async def describe_by_url(self, image_url: str, nonce: str):
        missing = self._require_session()
        if missing:
            return missing

        payload = self.payloads.build_describe_url(
            self.identity, image_url, nonce, session_id=self._session_id()
        )

        url = f"{self.api_base}/interactions"
        try:
            await self._request("POST", url, json=payload)
            return "Success"
        except Exception as e:
            self.metrics.increment_discord_error("rest")
            logger.error(f"Error sending describe-by-url command: {e}")
            return str(e)

    async def blend(self, uploaded_filenames: list[str], dimensions: str, nonce: str):
        missing = self._require_session()
        if missing:
            return missing

        payload = self.payloads.build_blend(
            self.identity, uploaded_filenames, dimensions, nonce, session_id=self._session_id()
        )

        url = f"{self.api_base}/interactions"
        try:
            await self._request("POST", url, json=payload)
            return "Success"
        except Exception as e:
            self.metrics.increment_discord_error("rest")
            logger.error(f"Error sending blend command: {e}")
            return str(e)

    async def close(self):
        await self.client.aclose()
        await self.cdn_client.aclose()

    async def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        http_cfg = self.config.http
        max_retries = max(0, int(http_cfg.max_retries))
        base = max(0.0, float(http_cfg.backoff_initial))
        cap = max(base, float(http_cfg.backoff_max))
        jitter = max(0.0, float(http_cfg.backoff_jitter))
        max_retry_after = max(0.0, float(http_cfg.max_retry_after))

        last_error: Optional[Exception] = None

        for attempt in range(0, max_retries + 1):
            try:
                resp = await self.client.request(method, url, **kwargs)
                if resp.status_code == 429:
                    self.metrics.increment_discord_error("rest")
                    # Respect rate limit headers
                    retry_after = self._parse_retry_after(resp, default=None)
                    if attempt >= max_retries:
                        text = self._safe_text(resp)
                        raise DiscordAPIError(
                            f"Rate limited by Discord (429). Retry-After="
                            f"{retry_after or 'n/a'}s. Attempts exhausted. Body: {text}"
                        )
                    delay = min(retry_after or base, max_retry_after or cap)
                    delay = max(0.0, delay) + (jitter * (0.5 - random.random()))
                    logger.warning(
                        f"HTTP 429; retrying in {delay:.2f}s (attempt {attempt + 1}/{max_retries})"
                    )
                    await asyncio.sleep(max(0.0, delay))
                    continue
                # Non-429 statuses
                resp.raise_for_status()
                return resp
            except httpx.TimeoutException as e:
                last_error = e
                self.metrics.increment_discord_error("rest")
                if attempt >= max_retries:
                    break
                delay = min(cap, base * (2**attempt)) + (jitter * (0.5 - random.random()))
                logger.warning(
                    f"HTTP timeout; retrying in {delay:.2f}s (attempt {attempt + 1}/{max_retries})"
                )
                await asyncio.sleep(max(0.0, delay))
            except httpx.TransportError as e:
                last_error = e
                self.metrics.increment_discord_error("rest")
                if attempt >= max_retries:
                    break
                delay = min(cap, base * (2**attempt)) + (jitter * (0.5 - random.random()))
                logger.warning(
                    f"HTTP transport error; retrying in {delay:.2f}s "
                    f"(attempt {attempt + 1}/{max_retries})"
                )
                await asyncio.sleep(max(0.0, delay))
            except httpx.HTTPStatusError as e:
                # Don't retry for 4xx except 429 which is handled above
                last_error = e
                self.metrics.increment_discord_error("rest")
                if 500 <= e.response.status_code < 600 and attempt < max_retries:
                    delay = min(cap, base * (2**attempt)) + (jitter * (0.5 - random.random()))
                    logger.warning(
                        f"HTTP {e.response.status_code}; retrying in {delay:.2f}s "
                        f"(attempt {attempt + 1}/{max_retries})"
                    )
                    await asyncio.sleep(max(0.0, delay))
                    continue
                # Non-retriable
                text = self._safe_text(e.response)
                raise DiscordAPIError(f"Discord API error {e.response.status_code}: {text}")

        # Exhausted retries on timeout/transport
        raise DiscordAPIError(
            f"Discord API request failed after {max_retries + 1} attempts: {last_error}"
        )

    @staticmethod
    def _parse_retry_after(
        resp: httpx.Response, default: Optional[float] = None
    ) -> Optional[float]:
        try:
            h = resp.headers
            if "Retry-After" in h:
                return float(h["Retry-After"])  # seconds
            if "X-RateLimit-Reset-After" in h:
                return float(h["X-RateLimit-Reset-After"])  # seconds
        except Exception:
            return default
        return default

    @staticmethod
    def _safe_text(resp: httpx.Response, limit: int = 200) -> str:
        try:
            t = resp.text
            return t[:limit]
        except Exception:
            return "<no body>"


__all__ = ["DiscordAPIError", "DiscordRestClient"]
