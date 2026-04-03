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

from mutiny.discord.event_scanner import scan_gateway_event
from mutiny.discord.identity import DiscordIdentity
from mutiny.services.interaction_cache import InteractionCache


class _TokenProvider:
    def get_token(self) -> str:
        return "t"


def _identity() -> DiscordIdentity:
    return DiscordIdentity(guild_id="g", channel_id="c", token_provider=_TokenProvider())


def test_scanner_caches_custom_zoom_modal():
    cache = InteractionCache()
    data = {
        "t": "INTERACTION_CREATE",
        "d": {
            "id": "modal-1",
            "channel_id": "c",
            "data": {"custom_id": "MJ::OutpaintCustomZoomModal::hash-1"},
        },
    }

    result = scan_gateway_event(data, cache, _identity())

    assert result.modal_cached
    assert cache.custom_zoom_modals["hash-1"] == {
        "id": "modal-1",
        "custom_id": "MJ::OutpaintCustomZoomModal::hash-1",
    }


def test_scanner_caches_inpaint_iframe_token():
    cache = InteractionCache()
    data = {
        "t": "INTERACTION_CREATE",
        "d": {"channel_id": "c", "data": {"custom_id": "MJ::iframe::token-123"}},
    }

    result = scan_gateway_event(data, cache, _identity())

    assert result.iframe_token_cached
    assert cache.inpaint_iframe_tokens["c"] == "token-123"


def test_scanner_caches_message_components():
    cache = InteractionCache()
    data = {
        "t": "MESSAGE_CREATE",
        "d": {
            "id": "m1",
            "components": [
                {"components": [{"custom_id": "CID_A"}, {"custom_id": "CID_B"}]},
            ],
        },
    }

    result = scan_gateway_event(data, cache, _identity())

    assert result.message_components_cached
    assert cache.get_message_components("m1") == {"CID_A", "CID_B"}


def test_scanner_reports_errors_without_raising():
    class BrokenCache(InteractionCache):
        def set_custom_zoom_modal(self, message_hash, data):  # type: ignore[override]
            raise RuntimeError("boom")

    cache = BrokenCache()
    data = {
        "t": "INTERACTION_CREATE",
        "d": {"id": "modal-err", "data": {"custom_id": "MJ::OutpaintCustomZoomModal::hash"}},
    }

    result = scan_gateway_event(data, cache, _identity())

    assert not result.modal_cached
    assert result.errors
    assert result.errors[0].event_type == "INTERACTION_CREATE"
