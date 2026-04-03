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
from pathlib import Path

import httpx
import pytest

from mutiny.discord.identity import DiscordIdentity, DiscordSessionState
from mutiny.discord.rest_client import DiscordRestClient
from mutiny.services.interaction_cache import InteractionCache
from mutiny.services.metrics.service import MetricsService

SNAPSHOT_DIR = Path(__file__).resolve().parent / "snapshots" / "discord_contracts"


def _canonical(obj: object) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _snapshot_text(name: str) -> str:
    path = SNAPSHOT_DIR / f"{name}.json"
    assert path.exists(), f"Missing snapshot: {path}"
    return path.read_text(encoding="utf-8").rstrip("\r\n")


def _assert_snapshot(name: str, obj: object) -> None:
    assert _canonical(obj) == _snapshot_text(name)


class _TokenProvider:
    def get_token(self) -> str:
        return "t"


def _svc(config, session_id: str | None = "s") -> DiscordRestClient:
    identity = DiscordIdentity(guild_id="g", channel_id="c", token_provider=_TokenProvider())
    session = DiscordSessionState()
    session.session_id = session_id
    return DiscordRestClient(
        identity=identity,
        session=session,
        config=config,
        interaction_cache=InteractionCache(),
        metrics=MetricsService(),
    )


@pytest.mark.asyncio
async def test_upload_payload_snapshot(test_config):
    svc = _svc(test_config)
    captured: dict[str, object] = {}

    async def _fake_request(method: str, url: str, **kwargs):
        captured["payload"] = kwargs.get("json")
        req = httpx.Request(method, url)
        return httpx.Response(
            200,
            json={
                "attachments": [
                    {"upload_url": "https://upload", "upload_filename": "uploads/f.png"}
                ]
            },
            request=req,
        )

    async def _fake_put(url, **kwargs):
        req = httpx.Request("PUT", url)
        return httpx.Response(200, request=req)

    svc._request = _fake_request  # type: ignore[assignment]
    svc.cdn_client.put = _fake_put  # type: ignore[assignment]

    await svc.upload("file.png", b"abc", "image/png")
    _assert_snapshot("upload_payload", captured.get("payload"))


@pytest.mark.asyncio
async def test_send_image_message_payload_snapshot(test_config):
    svc = _svc(test_config)
    captured: dict[str, object] = {}

    async def _fake_request(method: str, url: str, **kwargs):
        captured["payload"] = kwargs.get("json")
        req = httpx.Request(method, url)
        return httpx.Response(200, json={"attachments": [{"url": "u"}]}, request=req)

    svc._request = _fake_request  # type: ignore[assignment]

    await svc.send_image_message("hello", "uploads/abc/file.png")
    _assert_snapshot("send_image_message_payload", captured.get("payload"))


@pytest.mark.asyncio
async def test_inpaint_submit_job_body_snapshot(test_config):
    svc = _svc(test_config)
    captured: dict[str, object] = {}

    async def _fake_post(url, **kwargs):
        captured["payload"] = kwargs.get("json")
        req = httpx.Request("POST", url)
        return httpx.Response(200, request=req)

    svc.cdn_client.post = _fake_post  # type: ignore[assignment]

    await svc.inpaint_submit_job(
        iframe_token="cid",
        mask_webp_base64="mask",
        prompt="p",
    )
    _assert_snapshot("inpaint_submit_job_body", captured.get("payload"))


@pytest.mark.asyncio
async def test_custom_zoom_modal_submit_payload_snapshot(monkeypatch, test_config):
    cache = InteractionCache()
    svc = _svc(test_config)
    svc.interaction_cache = cache
    captured: dict[str, object] = {}
    message_hash = "mh"

    async def _fake_request(method: str, url: str, **kwargs):
        captured["payload"] = kwargs.get("json")
        req = httpx.Request(method, url)
        return httpx.Response(204, request=req)

    async def _no_sleep(_):
        return None

    async def _send_button(**_):
        return "Success"

    monkeypatch.setattr("mutiny.discord.rest_client.asyncio.sleep", _no_sleep)
    monkeypatch.setattr(
        "mutiny.discord.rest_client.build_custom_zoom_modal_custom_id",
        lambda _: "MJ::OutpaintCustomZoomModal::mh",
    )
    monkeypatch.setattr("mutiny.domain.time.get_current_timestamp_ms", lambda: 1700000000000)

    cache.set_custom_zoom_modal(message_hash, {"id": "modal-123"})
    svc._request = _fake_request  # type: ignore[assignment]
    svc.send_button_interaction = _send_button  # type: ignore[assignment]

    await svc.custom_zoom(
        message_id="mid",
        message_hash=message_hash,
        message_flags=64,
        nonce="n",
        zoom_text="tight crop --zoom 1.23",
    )
    _assert_snapshot("custom_zoom_modal_submit_payload", captured.get("payload"))
