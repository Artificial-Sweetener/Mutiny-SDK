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

import pytest

from mutiny.discord.identity import DiscordIdentity, DiscordSessionState
from mutiny.discord.rest_client import DiscordRestClient
from mutiny.services.interaction_cache import InteractionCache
from mutiny.services.metrics.service import MetricsService

SNAPSHOT_DIR = Path(__file__).resolve().parent / "snapshots" / "discord_payloads"


def _canonical(obj: object) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _snapshot_text(name: str) -> str:
    path = SNAPSHOT_DIR / f"{name}.json"
    assert path.exists(), f"Missing snapshot: {path}"
    return path.read_text(encoding="utf-8").rstrip("\r\n")


def _assert_snapshot(name: str, obj: object) -> None:
    assert _canonical(obj) == _snapshot_text(name)


class DummyResponse:
    def __init__(self, status_code: int = 200, text: str = "ok"):
        self.status_code = status_code
        self.text = text


@pytest.mark.asyncio
async def test_inpaint_submit_payload_frozen(monkeypatch: pytest.MonkeyPatch, test_config) -> None:
    class _TokenProvider:
        def get_token(self) -> str:
            return "t"

    identity = DiscordIdentity(
        guild_id="g", channel_id="c", token_provider=_TokenProvider(), user_agent="ua"
    )
    session = DiscordSessionState()
    session.session_id = "s"
    svc = DiscordRestClient(
        identity=identity,
        session=session,
        config=test_config,
        interaction_cache=InteractionCache(),
        metrics=MetricsService(),
    )
    captured: dict = {}

    async def _fake_post(url: str, *, json: dict, headers: dict):  # type: ignore[override]
        captured["json"] = json
        captured["headers"] = headers
        return DummyResponse(status_code=200)

    monkeypatch.setattr(svc.cdn_client, "post", _fake_post)

    result = await svc.inpaint_submit_job(
        iframe_token="CID",
        mask_webp_base64="MASK",
        prompt="prompt",
    )

    assert result == "Success"
    _assert_snapshot("built_inpaint_submit", captured.get("json"))
