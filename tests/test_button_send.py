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

import pytest

from mutiny.discord.identity import DiscordIdentity, DiscordSessionState
from mutiny.discord.rest_client import DiscordRestClient
from mutiny.services.interaction_cache import InteractionCache
from mutiny.services.metrics.service import MetricsService


class DummyResponse:
    def __init__(self, status_code: int = 204, text: str = ""):
        self.status_code = status_code
        self.text = text


class _TokenProvider:
    def get_token(self) -> str:
        return "t"


def _svc(
    test_config, session_id: str | None = "s", *, guild_id: str = "g", channel_id: str = "c"
) -> DiscordRestClient:
    identity = DiscordIdentity(
        guild_id=guild_id, channel_id=channel_id, token_provider=_TokenProvider()
    )
    session = DiscordSessionState()
    session.session_id = session_id
    return DiscordRestClient(
        identity=identity,
        session=session,
        config=test_config,
        interaction_cache=InteractionCache(),
        metrics=MetricsService(),
    )


@pytest.mark.asyncio
async def test_send_button_interaction_builds_payload(monkeypatch, test_config):
    # Arrange a DiscordService with a ready session
    svc = _svc(test_config, session_id="sess", guild_id="g1", channel_id="c1")
    captured: dict = {}

    async def _fake_request(method: str, url: str, **kwargs):  # type: ignore[override]
        captured["method"] = method
        captured["url"] = url
        captured["json"] = kwargs.get("json")
        return DummyResponse(status_code=204)

    monkeypatch.setattr(svc, "_request", _fake_request)

    # Act
    result = await svc.send_button_interaction(
        message_id="m123",
        custom_id="X::Y::Z",
        message_flags=64,
        nonce="n1",
    )

    # Assert outcome and payload shape
    assert result == "Success"
    body = captured.get("json") or {}
    assert body.get("type") == 3
    assert body.get("guild_id") == "g1"
    assert body.get("channel_id") == "c1"
    assert body.get("message_id") == "m123"
    assert body.get("message_flags") == 64
    assert body.get("session_id") == "sess"
    assert body.get("nonce") == "n1"
    assert body.get("data", {}).get("custom_id") == "X::Y::Z"


@pytest.mark.asyncio
async def test_button_methods_delegate_to_generic(monkeypatch, test_config):
    svc = _svc(test_config, session_id="s")
    calls: list[dict] = []

    async def _fake_send(message_id: str, custom_id: str, message_flags: int, nonce: str):  # type: ignore[override]
        calls.append(
            {
                "message_id": message_id,
                "custom_id": custom_id,
                "flags": message_flags,
                "nonce": nonce,
            }
        )
        return "Success"

    monkeypatch.setattr(svc, "send_button_interaction", _fake_send)

    # Act: invoke each button-style method
    await svc.upscale("mid", 2, "hash", 0, "n")
    await svc.variation("mid", 3, "hash", 0, "n")
    await svc.reroll("mid", "hash", 0, "n")
    await svc.cancel_job("mid", "job-123", 64, "n")

    # Assert: computed custom_id strings and flag passthrough
    assert len(calls) == 4
    ids = [c["custom_id"] for c in calls]
    assert "MJ::JOB::upsample::2::hash" in ids
    assert "MJ::JOB::variation::3::hash" in ids
    assert "MJ::JOB::reroll::0::hash::SOLO" in ids
    assert "MJ::CancelJob::ByJobid::job-123" in ids
    # Flags should match provided values per call
    assert any(c["flags"] == 64 for c in calls)
    assert all(c["nonce"] == "n" for c in calls)


@pytest.mark.asyncio
async def test_new_wrappers_delegate_and_build_expected_custom_ids(monkeypatch, test_config):
    svc = _svc(test_config, session_id="s")
    calls: list[dict] = []

    async def _fake_send(message_id: str, custom_id: str, message_flags: int, nonce: str):  # type: ignore[override]
        calls.append(
            {
                "message_id": message_id,
                "custom_id": custom_id,
                "flags": message_flags,
                "nonce": nonce,
            }
        )
        return "Success"

    monkeypatch.setattr(svc, "send_button_interaction", _fake_send)

    # Act: call new feature wrappers
    await svc.vary_subtle("mid", 3, "hash", 0, "n")
    await svc.vary_strong("mid", 4, "hash", 0, "n")
    await svc.upscale_v7_subtle("mid", 1, "hash", 0, "n")
    await svc.upscale_v7_creative("mid", 2, "hash", 0, "n")
    await svc.outpaint_50("mid", 1, "hash", 0, "n")
    await svc.outpaint_75("mid", 1, "hash", 0, "n")
    await svc.pan_left("mid", 1, "hash", 0, "n")
    await svc.pan_right("mid", 1, "hash", 0, "n")
    await svc.pan_up("mid", 1, "hash", 0, "n")
    await svc.pan_down("mid", 1, "hash", 0, "n")
    await svc.animate_high("mid", 1, "hash", 0, "n")
    await svc.animate_low("mid", 1, "hash", 0, "n")

    # Assert: correct custom_id strings built
    ids = [c["custom_id"] for c in calls]
    assert "MJ::JOB::low_variation::3::hash::SOLO" in ids
    assert "MJ::JOB::high_variation::4::hash::SOLO" in ids
    assert "MJ::JOB::upsample_v7_2x_subtle::1::hash::SOLO" in ids
    assert "MJ::JOB::upsample_v7_2x_creative::2::hash::SOLO" in ids
    assert "MJ::Outpaint::50::1::hash::SOLO" in ids
    assert "MJ::Outpaint::75::1::hash::SOLO" in ids
    assert "MJ::JOB::pan_left::1::hash::SOLO" in ids
    assert "MJ::JOB::pan_right::1::hash::SOLO" in ids
    assert "MJ::JOB::pan_up::1::hash::SOLO" in ids
    assert "MJ::JOB::pan_down::1::hash::SOLO" in ids
    assert "MJ::JOB::animate_high::1::hash::SOLO" in ids
    assert "MJ::JOB::animate_low::1::hash::SOLO" in ids
