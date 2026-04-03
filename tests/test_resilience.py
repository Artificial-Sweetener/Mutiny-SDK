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

import httpx
import pytest

from mutiny.discord.identity import DiscordIdentity, DiscordSessionState
from mutiny.discord.rest_client import DiscordAPIError, DiscordRestClient
from mutiny.services.interaction_cache import InteractionCache
from mutiny.services.metrics.service import MetricsService


class _SeqClient:
    def __init__(self, results):
        self.results = list(results)
        self.calls = 0

    async def request(self, method, url, **kwargs):  # type: ignore[no-untyped-def]
        self.calls += 1
        nxt = self.results.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt


def _resp(status: int, headers: dict | None = None) -> httpx.Response:
    req = httpx.Request("POST", "https://discord.test/interactions")
    return httpx.Response(status, headers=headers or {}, request=req)


class _TokenProvider:
    def get_token(self) -> str:
        return "t"


def _svc(test_config) -> DiscordRestClient:
    identity = DiscordIdentity(
        guild_id="g", channel_id="c", token_provider=_TokenProvider(), user_agent="ua"
    )
    session = DiscordSessionState()
    return DiscordRestClient(
        identity=identity,
        session=session,
        config=test_config,
        interaction_cache=InteractionCache(),
        metrics=MetricsService(),
    )


@pytest.mark.asyncio
async def test_request_retries_on_429_and_respects_retry_after(monkeypatch, test_config):
    # Arrange: 429 twice with Retry-After=0 (to avoid real sleeping), then 204 success
    r1 = _resp(429, {"Retry-After": "0"})
    r2 = _resp(429, {"Retry-After": "0"})
    r3 = _resp(204)

    svc = _svc(test_config)
    fake = _SeqClient([r1, r2, r3])
    svc.client = fake  # type: ignore[assignment]

    # Speed up sleeps
    async def _fast_sleep(_):
        return None

    monkeypatch.setattr(asyncio, "sleep", _fast_sleep)

    # Act
    resp = await svc._request("POST", "https://discord.test/interactions", json={})

    # Assert
    assert resp.status_code == 204
    assert fake.calls == 3


@pytest.mark.asyncio
async def test_request_retries_on_timeouts_then_succeeds(monkeypatch, test_config):
    t1 = httpx.ConnectTimeout("connect timeout")
    t2 = httpx.ReadTimeout("read timeout")
    r = _resp(204)

    svc = _svc(test_config)
    fake = _SeqClient([t1, t2, r])
    svc.client = fake  # type: ignore[assignment]

    async def _fast_sleep(_):
        return None

    monkeypatch.setattr(asyncio, "sleep", _fast_sleep)

    resp = await svc._request("POST", "https://discord.test/interactions", json={})
    assert resp.status_code == 204
    assert fake.calls == 3


@pytest.mark.asyncio
async def test_request_non_retriable_4xx_raises_immediately(test_config):
    r = _resp(400)

    svc = _svc(test_config)
    svc.client = _SeqClient([r])  # type: ignore[assignment]

    with pytest.raises(DiscordAPIError) as ei:
        await svc._request("POST", "https://discord.test/interactions", json={})
    assert "Discord API error 400" in str(ei.value)
