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

from mutiny.discord.constants import APPLICATION_ID, ComponentType
from mutiny.discord.identity import DiscordIdentity
from mutiny.discord.payload_builder import DiscordPayloadBuilder


class _TokenProvider:
    def get_token(self) -> str:
        return "t"


def _identity() -> DiscordIdentity:
    return DiscordIdentity(guild_id="g", channel_id="c", token_provider=_TokenProvider())


def test_build_imagine_sets_expected_keys():
    reg = DiscordPayloadBuilder()
    p = reg.build_imagine(_identity(), prompt="hi", nonce="n", session_id="s")
    assert p["guild_id"] == "g"
    assert p["channel_id"] == "c"
    assert p["session_id"] == "s"
    assert p["nonce"] == "n"
    assert p["application_id"] == APPLICATION_ID
    assert p["data"]["options"][0]["value"] == "hi"


def test_build_button_sets_button_context():
    reg = DiscordPayloadBuilder()
    p = reg.build_button_interaction(
        _identity(),
        nonce="n",
        message_id="m",
        message_flags=64,
        custom_id="CID",
        session_id="s",
    )
    assert p["guild_id"] == "g"
    assert p["message_id"] == "m"
    assert p["message_flags"] == 64
    assert p["application_id"] == APPLICATION_ID
    assert p["data"]["custom_id"] == "CID"
    assert p["data"]["component_type"] == ComponentType.BUTTON


def test_build_button_tolerates_missing_session():
    reg = DiscordPayloadBuilder()
    p = reg.build_button_interaction(
        _identity(),
        nonce="n",
        message_id="m",
        message_flags=64,
        custom_id="CID",
        session_id=None,
    )
    assert "session_id" not in p


def test_build_describe_payload_attachments_shape():
    reg = DiscordPayloadBuilder()
    payload = reg.build_describe_upload(
        _identity(), "uploads/abc/file.png", nonce="n", session_id="s"
    )
    atts = payload["data"]["attachments"]
    assert atts and atts[0]["filename"] == "file.png"
    assert atts[0]["uploaded_filename"] == "uploads/abc/file.png"


def test_build_describe_by_url_sets_options_and_clears_attachments():
    reg = DiscordPayloadBuilder()
    payload = reg.build_describe_url(_identity(), "https://x/y.png", nonce="n", session_id="s")
    opts = payload["data"]["options"]
    assert opts and opts[0]["name"] == "image" and opts[0]["value"] == "https://x/y.png"
    assert payload["data"]["attachments"] == []


def test_build_blend_payload_options_and_attachments():
    reg = DiscordPayloadBuilder()
    payload = reg.build_blend(
        _identity(), ["u/f1.png", "u/f2.png"], dimensions="16:9", nonce="n", session_id="s"
    )
    options = payload["data"]["options"]
    attachments = payload["data"]["attachments"]
    # There should be 2 image options + 1 dimensions option
    assert len(options) == 3
    assert options[0]["name"] == "image1" and options[0]["value"] == 0
    assert options[1]["name"] == "image2" and options[1]["value"] == 1
    assert options[2]["name"] == "dimensions" and options[2]["value"] == "--ar 16:9"
    # Attachments mirror the images
    assert len(attachments) == 2
    assert attachments[0]["filename"] == "f1.png" and attachments[1]["filename"] == "f2.png"
