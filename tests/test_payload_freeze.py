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

from pathlib import Path

from mutiny.discord.identity import DiscordIdentity
from mutiny.discord.payload_builder import DiscordPayloadBuilder

from .snapshot_utils import assert_snapshot, canonical_hash, snapshot_hash

SNAPSHOT_DIR = Path(__file__).resolve().parent / "snapshots" / "discord_payloads"


class _TokenProvider:
    def get_token(self) -> str:
        return "t"


def _identity() -> DiscordIdentity:
    return DiscordIdentity(guild_id="g", channel_id="c", token_provider=_TokenProvider())


def test_imagine_payload_frozen() -> None:
    reg = DiscordPayloadBuilder()
    payload = reg.build_imagine(_identity(), "a prompt", "n", session_id="s")
    snap = SNAPSHOT_DIR / "built_imagine.json"
    assert_snapshot(payload, snap)
    assert canonical_hash(payload) == snapshot_hash(snap)


def test_button_payload_frozen() -> None:
    reg = DiscordPayloadBuilder()
    payload = reg.build_button_interaction(
        _identity(), "n", message_id="m", message_flags=64, custom_id="CID", session_id="s"
    )
    snap = SNAPSHOT_DIR / "built_button_upscale.json"
    assert_snapshot(payload, snap)
    assert canonical_hash(payload) == snapshot_hash(snap)


def test_custom_zoom_modal_payload_frozen() -> None:
    reg = DiscordPayloadBuilder()
    payload = reg.build_custom_zoom_modal(
        _identity(),
        "n",
        custom_id="MJ::OutpaintCustomZoomModal::abcd",
        zoom_text="zoom text",
        modal_id="$modal_id",
        session_id="s",
    )
    snap = SNAPSHOT_DIR / "built_custom_zoom_modal.json"
    assert_snapshot(payload, snap)
    assert canonical_hash(payload) == snapshot_hash(snap)


def test_describe_payload_frozen() -> None:
    reg = DiscordPayloadBuilder()
    payload = reg.build_describe_upload(_identity(), "uploads/abc/file.png", "n", session_id="s")
    snap = SNAPSHOT_DIR / "built_describe.json"
    assert_snapshot(payload, snap)
    assert canonical_hash(payload) == snapshot_hash(snap)


def test_describe_by_url_payload_frozen() -> None:
    reg = DiscordPayloadBuilder()
    payload = reg.build_describe_url(
        _identity(), "https://example.com/img.png", "n", session_id="s"
    )
    snap = SNAPSHOT_DIR / "built_describe_by_url.json"
    assert_snapshot(payload, snap)
    assert canonical_hash(payload) == snapshot_hash(snap)


def test_blend_payload_frozen() -> None:
    reg = DiscordPayloadBuilder()
    payload = reg.build_blend(
        _identity(), ["uploads/a.png", "uploads/b.png"], "16:9", "n", session_id="s"
    )
    snap = SNAPSHOT_DIR / "built_blend.json"
    assert_snapshot(payload, snap)
    assert canonical_hash(payload) == snapshot_hash(snap)
