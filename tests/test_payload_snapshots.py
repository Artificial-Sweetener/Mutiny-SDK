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

from mutiny.discord.identity import DiscordIdentity
from mutiny.discord.payload_builder import DiscordPayloadBuilder


class _TokenProvider:
    def get_token(self) -> str:
        return "t"


def _identity():
    return DiscordIdentity(guild_id="g", channel_id="c", token_provider=_TokenProvider())


def test_imagine_builder_core_fields_stable():
    reg = DiscordPayloadBuilder()
    p = reg.build_imagine(_identity(), prompt="hello", nonce="n", session_id="s")
    assert p["type"] == 2
    assert p["application_id"] == "936929561302675456"
    assert p["data"]["name"] == "imagine"
    opts = p["data"]["options"]
    assert len(opts) == 1 and opts[0]["name"] == "prompt" and opts[0]["value"] == "hello"


def test_button_payload_shape_via_builder():
    reg = DiscordPayloadBuilder()
    p = reg.build_button_interaction(
        _identity(),
        "n",
        message_id="m",
        message_flags=0,
        custom_id="CID",
        session_id="s",
    )
    assert p["type"] == 3
    assert p["application_id"] == "936929561302675456"
    assert p["data"]["component_type"] == 2
    assert p["data"]["custom_id"] == "CID"


def test_custom_zoom_modal_payload_shape():
    reg = DiscordPayloadBuilder()
    p2 = reg.build_custom_zoom_modal(
        _identity(),
        "n",
        custom_id="MJ::OutpaintCustomZoomModal::abcd",
        zoom_text="zoom text",
        modal_id="$modal_id",
        session_id="s",
    )
    assert p2["type"] == 5
    assert p2["application_id"] == "936929561302675456"
    assert p2["guild_id"] == "g" and p2["channel_id"] == "c" and p2["session_id"] == "s"
    assert p2["data"]["custom_id"].startswith("MJ::OutpaintCustomZoomModal::")
    comps = p2["data"]["components"]
    assert comps and comps[0]["components"][0]["type"] == 4
    assert comps[0]["components"][0].get("value") == "zoom text"
    assert p2["data"].get("id") == "$modal_id"
