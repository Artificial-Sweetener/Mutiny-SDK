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
import json
from pathlib import Path

import pytest
import websockets

from mutiny.discord.gateway_client import DiscordGatewayClient, _compute_backoff_state
from mutiny.discord.identity import DiscordIdentity, DiscordSessionState
from mutiny.services.interaction_cache import InteractionCache
from mutiny.services.metrics.service import MetricsService
from mutiny.services.response_dump import ResponseDumpService

from .snapshot_utils import assert_snapshot, canonical_hash, snapshot_hash

SNAPSHOT_DIR = Path(__file__).resolve().parent / "snapshots" / "discord_gateway"


class _CaptureWS:
    def __init__(self):
        self.sent: list[dict] = []
        self.raw: list[str] = []

    async def send(self, payload: str):
        self.raw.append(payload)
        self.sent.append(json.loads(payload))


class _TokenProvider:
    def get_token(self) -> str:
        return "t"


def _identity() -> DiscordIdentity:
    return DiscordIdentity(guild_id="g", channel_id="c", token_provider=_TokenProvider())


def _session(session_id: str | None = None) -> DiscordSessionState:
    s = DiscordSessionState()
    s.session_id = session_id
    return s


@pytest.mark.asyncio
async def test_gateway_ready_snapshot(test_config):
    ws = DiscordGatewayClient(
        identity=_identity(),
        session=_session(),
        config=test_config,
        interaction_cache=InteractionCache(),
        metrics=MetricsService(),
        response_dump=ResponseDumpService(enabled=False),
        message_handler=lambda *_: None,
    )
    payload = {
        "op": 0,
        "t": "READY",
        "s": 1,
        "d": {"session_id": "sess-1", "resume_gateway_url": "wss://resume"},
    }
    await ws.handle_message(json.dumps(payload))
    snap = SNAPSHOT_DIR / "ready.json"
    assert_snapshot(
        {
            "session_id": ws.session.session_id,
            "resume_gateway_url": ws.session.resume_gateway_url,
        },
        snap,
    )
    assert canonical_hash(
        {
            "session_id": ws.session.session_id,
            "resume_gateway_url": ws.session.resume_gateway_url,
        }
    ) == snapshot_hash(snap)


@pytest.mark.asyncio
async def test_gateway_identify_payload_snapshot(test_config):
    ws = DiscordGatewayClient(
        identity=_identity(),
        session=_session(),
        config=test_config,
        interaction_cache=InteractionCache(),
        metrics=MetricsService(),
        response_dump=ResponseDumpService(enabled=False),
        message_handler=lambda *_: None,
    )
    cap = _CaptureWS()
    ws.ws = cap  # type: ignore[assignment]

    await ws.identify()
    assert cap.sent
    snap = SNAPSHOT_DIR / "identify_payload.json"
    assert_snapshot(cap.sent[-1], snap)
    assert canonical_hash(cap.sent[-1]) == snapshot_hash(snap)


@pytest.mark.asyncio
async def test_gateway_resume_payload_snapshot(test_config):
    sess = _session()
    ws = DiscordGatewayClient(
        identity=_identity(),
        session=sess,
        config=test_config,
        interaction_cache=InteractionCache(),
        metrics=MetricsService(),
        response_dump=ResponseDumpService(enabled=False),
        message_handler=lambda *_: None,
    )
    cap = _CaptureWS()
    ws.ws = cap  # type: ignore[assignment]
    sess.session_id = "sess-1"
    ws.sequence = 42

    await ws._do_resume_or_identify()
    assert cap.sent
    snap = SNAPSHOT_DIR / "resume_payload.json"
    assert_snapshot(cap.sent[-1], snap)
    assert canonical_hash(cap.sent[-1]) == snapshot_hash(snap)


def test_gateway_url_snapshot(test_config):
    ws = DiscordGatewayClient(
        identity=_identity(),
        session=_session(),
        config=test_config,
        interaction_cache=InteractionCache(),
        metrics=MetricsService(),
        response_dump=ResponseDumpService(enabled=False),
        message_handler=lambda *_: None,
    )
    ws.session.resume_gateway_url = "wss://resume"
    snap = SNAPSHOT_DIR / "gateway_urls.json"
    payload = {
        "initial": ws._gateway_url(reconnect=False),
        "resume": ws._gateway_url(reconnect=True),
    }
    assert_snapshot(payload, snap)
    assert canonical_hash(payload) == snapshot_hash(snap)


def test_gateway_backoff_helper_sequence():
    base = 1.0
    cap = 4.0
    jitter = 0.3
    backoff = base
    delays: list[float] = []

    for jitter_seed in (0.0, 1.0, 0.5):
        delay, backoff = _compute_backoff_state(
            backoff,
            base,
            cap,
            jitter,
            rand=lambda jitter_seed=jitter_seed: jitter_seed,
        )
        delays.append(delay)

    assert delays[0] == pytest.approx(1.15)
    assert delays[1] == pytest.approx(1.85)
    assert delays[2] == pytest.approx(4.0)
    assert backoff == cap


@pytest.mark.asyncio
async def test_gateway_connect_backoff_flow(monkeypatch, test_config):
    cfg = test_config.copy()
    gw = DiscordGatewayClient(
        identity=_identity(),
        session=_session(),
        config=cfg,
        interaction_cache=InteractionCache(),
        metrics=MetricsService(),
        response_dump=ResponseDumpService(enabled=False),
        message_handler=lambda *_: None,
    )

    errors: list[str] = []
    delays: list[float] = []
    monkeypatch.setattr(gw.metrics, "increment_discord_error", lambda label: errors.append(label))

    attempt = 0

    async def _fake_run_websocket_once(*_: object, **__: object):
        nonlocal attempt
        attempt += 1
        if attempt == 1:
            raise websockets.exceptions.ConnectionClosedError(None, None)
        if attempt == 2:
            raise Exception("boom")
        raise asyncio.CancelledError()

    backoff_returns = [(0.25, 2.0), (0.5, 2.0)]
    compute_calls = -1

    def _fake_compute_backoff(current, base, cap, jitter, rand=None):
        nonlocal compute_calls
        compute_calls += 1
        return backoff_returns[compute_calls]

    async def _fake_sleep(delay: float):
        delays.append(delay)
        if len(delays) >= len(backoff_returns):
            raise asyncio.CancelledError()

    monkeypatch.setattr(gw, "_run_websocket_once", _fake_run_websocket_once)
    monkeypatch.setattr(gw, "_sleep_with_backoff", _fake_sleep)
    monkeypatch.setattr(
        "mutiny.discord.gateway_client._compute_backoff_state", _fake_compute_backoff
    )

    with pytest.raises(asyncio.CancelledError):
        await gw.connect()

    assert errors == ["gateway", "gateway"]
    assert delays == [pytest.approx(0.25), pytest.approx(0.5)]
    assert compute_calls == 1


@pytest.mark.asyncio
async def test_gateway_resumed_snapshot(test_config):
    sess = _session("sess-1")
    ws = DiscordGatewayClient(
        identity=_identity(),
        session=sess,
        config=test_config,
        interaction_cache=InteractionCache(),
        metrics=MetricsService(),
        response_dump=ResponseDumpService(enabled=False),
        message_handler=lambda *_: None,
    )
    payload = {"op": 0, "t": "RESUMED", "s": 2, "d": {}}
    await ws.handle_message(json.dumps(payload))
    snap = SNAPSHOT_DIR / "resumed.json"
    payload = {
        "session_id": ws.session.session_id,
    }
    assert_snapshot(payload, snap)
    assert canonical_hash(payload) == snapshot_hash(snap)


@pytest.mark.asyncio
@pytest.mark.parametrize("event_type", ["MESSAGE_CREATE", "MESSAGE_UPDATE"])
async def test_gateway_message_components_snapshot(event_type: str, test_config):
    cache = InteractionCache()
    ws = DiscordGatewayClient(
        identity=_identity(),
        session=_session(),
        config=test_config,
        interaction_cache=cache,
        metrics=MetricsService(),
        response_dump=ResponseDumpService(enabled=False),
        message_handler=lambda *_: None,
    )
    payload = {
        "op": 0,
        "t": event_type,
        "s": 3,
        "d": {
            "id": "m1",
            "components": [{"components": [{"custom_id": "CID_A"}, {"custom_id": "CID_B"}]}],
        },
    }
    await ws.handle_message(json.dumps(payload))
    comp = cache.get_message_components("m1")
    snap = SNAPSHOT_DIR / f"message_components_{event_type.lower()}.json"
    payload = {"message_id": "m1", "custom_ids": sorted(comp)}
    assert_snapshot(payload, snap)
    assert canonical_hash(payload) == snapshot_hash(snap)


@pytest.mark.asyncio
async def test_gateway_custom_zoom_modal_snapshot(test_config):
    cache = InteractionCache()
    ws = DiscordGatewayClient(
        identity=_identity(),
        session=_session(),
        config=test_config,
        interaction_cache=cache,
        metrics=MetricsService(),
        response_dump=ResponseDumpService(enabled=False),
        message_handler=lambda *_: None,
    )
    payload = {
        "op": 0,
        "t": "INTERACTION_CREATE",
        "s": 4,
        "d": {
            "id": "modal-1",
            "channel_id": "c",
            "data": {"custom_id": "MJ::OutpaintCustomZoomModal::hash-1"},
        },
    }
    await ws.handle_message(json.dumps(payload))
    snap = SNAPSHOT_DIR / "custom_zoom_modal.json"
    assert_snapshot(cache.custom_zoom_modals, snap)
    assert canonical_hash(cache.custom_zoom_modals) == snapshot_hash(snap)


@pytest.mark.asyncio
async def test_gateway_inpaint_iframe_snapshot(test_config):
    cache = InteractionCache()
    ws = DiscordGatewayClient(
        identity=_identity(),
        session=_session(),
        config=test_config,
        interaction_cache=cache,
        metrics=MetricsService(),
        response_dump=ResponseDumpService(enabled=False),
        message_handler=lambda *_: None,
    )
    payload = {
        "op": 0,
        "t": "INTERACTION_CREATE",
        "s": 5,
        "d": {
            "channel_id": "c",
            "data": {"custom_id": "MJ::iframe::token-123"},
        },
    }
    await ws.handle_message(json.dumps(payload))
    snap = SNAPSHOT_DIR / "inpaint_iframe_tokens.json"
    assert_snapshot(cache.inpaint_iframe_tokens, snap)
    assert canonical_hash(cache.inpaint_iframe_tokens) == snapshot_hash(snap)
