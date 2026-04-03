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

from mutiny.discord.message_interpreter import DiscordMessageParser, MessageKind
from mutiny.services.image_utils import parse_data_url


def test_parse_data_url_good_and_bad():
    good = "data:image/png;base64,aGVsbG8="  # b"hello"
    parsed = parse_data_url(good)
    assert parsed is not None
    assert parsed.mime_type == "image/png"
    assert parsed.data == b"hello"

    assert parse_data_url("") is None
    assert parse_data_url("not-a-data-url") is None


def test_parse_progress_extracts_prompt_and_status():
    content = "some pre **A fancy prompt** and more <@12345> (RELAX) trailing"
    parser = DiscordMessageParser()
    interpreted = parser.interpret("MESSAGE_CREATE", {"content": content})
    assert interpreted is not None
    assert interpreted.has_kind(MessageKind.PROGRESS)
    data = interpreted.as_progress()
    assert data is not None
    assert data.prompt == "A fancy prompt"
    assert data.status == "RELAX"


def test_parse_referenced_midjourney_error_without_color():
    """Classify known Midjourney decline embeds as errors even without color."""
    parser = DiscordMessageParser()
    interpreted = parser.interpret(
        "MESSAGE_CREATE",
        {
            "embeds": [
                {
                    "title": "Sorry, something went wrong",
                    "description": "The job encountered an error. Our team has been notified.",
                    "footer": {"text": "decline-revise-frolic"},
                }
            ],
            "message_reference": {"message_id": "job-msg-1"},
        },
    )

    assert interpreted is not None
    assert interpreted.has_kind(MessageKind.ERROR)
    assert interpreted.error_title == "Sorry, something went wrong"
    assert (
        interpreted.error_description == "The job encountered an error. Our team has been notified."
    )
    assert interpreted.error_footer == "decline-revise-frolic"


def test_parse_color_based_error_still_works():
    """Preserve legacy color-based Midjourney error classification."""
    parser = DiscordMessageParser()
    interpreted = parser.interpret(
        "MESSAGE_CREATE",
        {
            "embeds": [{"color": 15548997, "title": "Error", "description": "bad"}],
            "message_reference": {"message_id": "job-msg-2"},
        },
    )

    assert interpreted is not None
    assert interpreted.has_kind(MessageKind.ERROR)
    assert interpreted.error_title == "Error"
    assert interpreted.error_description == "bad"


def test_parse_slow_down_embed_as_midjourney_error():
    """Classify Midjourney cooldown embeds as referenced job errors."""
    parser = DiscordMessageParser()
    interpreted = parser.interpret(
        "MESSAGE_CREATE",
        {
            "embeds": [
                {
                    "title": "Slow Down!",
                    "description": (
                        "You can request another upscale for this image <t:1774990054:R>"
                    ),
                }
            ],
            "message_reference": {"message_id": "job-msg-4"},
        },
    )

    assert interpreted is not None
    assert interpreted.has_kind(MessageKind.ERROR)
    assert interpreted.error_title == "Slow Down!"
    assert (
        interpreted.error_description
        == "You can request another upscale for this image <t:1774990054:R>"
    )


def test_parse_unrelated_referenced_embed_is_not_error():
    """Avoid over-classifying arbitrary referenced embeds as Midjourney errors."""
    parser = DiscordMessageParser()
    interpreted = parser.interpret(
        "MESSAGE_CREATE",
        {
            "embeds": [
                {
                    "title": "Helpful info",
                    "description": "This is just a normal embed.",
                    "footer": {"text": "not-a-decline"},
                }
            ],
            "message_reference": {"message_id": "job-msg-3"},
        },
    )

    assert interpreted is not None
    assert not interpreted.has_kind(MessageKind.ERROR)


def test_parse_referenced_unrecognized_parameter_content_as_error():
    """Classify referenced Midjourney parameter-validation replies as errors."""
    parser = DiscordMessageParser()
    interpreted = parser.interpret(
        "MESSAGE_CREATE",
        {
            "content": (
                "Invalid parameter\n"
                "Unrecognized parameter(s): use_raw\n"
                "/imagine test prompt --seed 1 True --niji 7"
            ),
            "message_reference": {"message_id": "job-msg-5"},
        },
    )

    assert interpreted is not None
    assert interpreted.has_kind(MessageKind.ERROR)
    assert interpreted.error_title == "Invalid parameter"
    assert interpreted.error_description == "Unrecognized parameter(s): use_raw"
