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

from mutiny.discord.custom_ids import (
    CustomIdKind,
    build_animate_custom_id,
    build_animate_extend_custom_id,
    build_cancel_by_jobid,
    build_custom_zoom_button_custom_id,
    build_custom_zoom_modal_custom_id,
    build_high_variation_custom_id,
    build_inpaint_custom_id,
    build_low_variation_custom_id,
    build_outpaint_custom_id,
    build_pan_custom_id,
    build_reroll_custom_id,
    build_upscale_custom_id,
    build_upscale_v7_custom_id,
    build_variation_custom_id,
    find_matching_solo_upscale_custom_id,
    parse_custom_id,
    validate_custom_id,
)


def test_build_upscale_custom_id_exact():
    assert build_upscale_custom_id(2, "abc123") == "MJ::JOB::upsample::2::abc123"


def test_build_variation_custom_id_exact():
    assert build_variation_custom_id(3, "xyz") == "MJ::JOB::variation::3::xyz"


def test_build_reroll_custom_id_exact():
    assert build_reroll_custom_id("hash") == "MJ::JOB::reroll::0::hash::SOLO"


def test_build_cancel_by_jobid_exact():
    assert build_cancel_by_jobid("job-42") == "MJ::CancelJob::ByJobid::job-42"


def test_build_low_variation_custom_id_exact():
    assert build_low_variation_custom_id(1, "abc") == "MJ::JOB::low_variation::1::abc::SOLO"


def test_build_high_variation_custom_id_exact():
    assert build_high_variation_custom_id(4, "hjk") == "MJ::JOB::high_variation::4::hjk::SOLO"


def test_build_upscale_v7_custom_id_modes_and_format():
    assert (
        build_upscale_v7_custom_id("subtle", 2, "h1")
        == "MJ::JOB::upsample_v7_2x_subtle::2::h1::SOLO"
    )
    assert (
        build_upscale_v7_custom_id("creative", 3, "h2")
        == "MJ::JOB::upsample_v7_2x_creative::3::h2::SOLO"
    )
    # Unrecognized mode gets normalized fallback (still returns a string)
    assert (build_upscale_v7_custom_id("", 1, "z")).startswith("MJ::JOB::upsample_v7_2x_")


def test_find_matching_solo_upscale_custom_id_accepts_v6_and_v7():
    subtle_v6 = "MJ::JOB::upsample_v6_2x_subtle::1::hash-a::SOLO"
    creative_v7 = "MJ::JOB::upsample_v7_2x_creative::1::hash-a::SOLO"
    assert (
        find_matching_solo_upscale_custom_id(
            {subtle_v6, creative_v7},
            mode="subtle",
            index=1,
            message_hash="hash-a",
        )
        == subtle_v6
    )
    assert (
        find_matching_solo_upscale_custom_id(
            {subtle_v6, creative_v7},
            mode="creative",
            index=1,
            message_hash="hash-a",
        )
        == creative_v7
    )


def test_build_outpaint_custom_id_exact():
    assert build_outpaint_custom_id(50, 1, "mh") == "MJ::Outpaint::50::1::mh::SOLO"
    assert build_outpaint_custom_id(75, 2, "abc") == "MJ::Outpaint::75::2::abc::SOLO"


def test_build_pan_custom_id_directions():
    assert build_pan_custom_id("left", 1, "h") == "MJ::JOB::pan_left::1::h::SOLO"
    assert build_pan_custom_id("right", 2, "h") == "MJ::JOB::pan_right::2::h::SOLO"
    assert build_pan_custom_id("up", 3, "h") == "MJ::JOB::pan_up::3::h::SOLO"
    assert build_pan_custom_id("down", 4, "h") == "MJ::JOB::pan_down::4::h::SOLO"


def test_build_animate_custom_id_levels():
    assert build_animate_custom_id("high", 1, "h") == "MJ::JOB::animate_high::1::h::SOLO"
    assert build_animate_custom_id("low", 2, "h") == "MJ::JOB::animate_low::2::h::SOLO"


def test_build_animate_extend_custom_id_levels():
    assert build_animate_extend_custom_id("high", 1, "h") == "MJ::JOB::animate_high_extend::1::h"
    assert build_animate_extend_custom_id("low", 1, "h") == "MJ::JOB::animate_low_extend::1::h"


def test_custom_id_builders_validate_against_registry():
    assert validate_custom_id(build_upscale_custom_id(1, "h"))
    assert validate_custom_id(build_variation_custom_id(2, "h"))
    assert validate_custom_id(build_low_variation_custom_id(3, "h"))
    assert validate_custom_id(build_high_variation_custom_id(4, "h"))
    assert validate_custom_id(build_upscale_v7_custom_id("subtle", 1, "h"))
    assert validate_custom_id(build_upscale_v7_custom_id("creative", 2, "h"))
    assert validate_custom_id(build_reroll_custom_id("h"))
    assert validate_custom_id(build_cancel_by_jobid("job-1"))
    assert validate_custom_id(build_outpaint_custom_id(50, 1, "h"))
    assert validate_custom_id(build_pan_custom_id("left", 1, "h"))
    assert validate_custom_id(build_pan_custom_id("right", 2, "h"))
    assert validate_custom_id(build_pan_custom_id("up", 3, "h"))
    assert validate_custom_id(build_pan_custom_id("down", 4, "h"))
    assert validate_custom_id(build_animate_custom_id("high", 1, "h"))
    assert validate_custom_id(build_animate_custom_id("low", 2, "h"))
    assert validate_custom_id(build_animate_extend_custom_id("high", 1, "h"))
    assert validate_custom_id(build_animate_extend_custom_id("low", 1, "h"))
    assert validate_custom_id(build_custom_zoom_button_custom_id("h"))
    assert validate_custom_id(build_custom_zoom_modal_custom_id("h"))
    assert validate_custom_id(build_inpaint_custom_id(1, "h"))
    assert validate_custom_id("MJ::JOB::upsample_v6_2x_subtle::1::h::SOLO")


def test_custom_id_parse_round_trip():
    cases = [
        (
            build_upscale_custom_id(2, "abc123"),
            CustomIdKind.UPSCALE,
            {"index": 2, "message_hash": "abc123"},
        ),
        (
            build_variation_custom_id(3, "xyz"),
            CustomIdKind.VARIATION,
            {"index": 3, "message_hash": "xyz"},
        ),
        (
            build_low_variation_custom_id(1, "abc"),
            CustomIdKind.VARIATION_LOW,
            {"index": 1, "message_hash": "abc"},
        ),
        (
            build_high_variation_custom_id(4, "hjk"),
            CustomIdKind.VARIATION_HIGH,
            {"index": 4, "message_hash": "hjk"},
        ),
        (
            build_upscale_v7_custom_id("creative", 3, "h2"),
            CustomIdKind.UPSCALE_SOLO,
            {"index": 3, "message_hash": "h2", "mode": "creative", "version": 7},
        ),
        (build_reroll_custom_id("hash"), CustomIdKind.REROLL, {"message_hash": "hash"}),
        (build_cancel_by_jobid("job-42"), CustomIdKind.CANCEL, {"job_id": "job-42"}),
        (
            build_outpaint_custom_id(75, 2, "abc"),
            CustomIdKind.OUTPAINT,
            {"scale": 75, "index": 2, "message_hash": "abc"},
        ),
        (
            build_pan_custom_id("up", 3, "h"),
            CustomIdKind.PAN,
            {"direction": "up", "index": 3, "message_hash": "h"},
        ),
        (
            build_animate_custom_id("low", 2, "h"),
            CustomIdKind.ANIMATE,
            {"level": "low", "index": 2, "message_hash": "h"},
        ),
        (
            build_animate_extend_custom_id("high", 1, "h"),
            CustomIdKind.ANIMATE_EXTEND,
            {"level": "high", "index": 1, "message_hash": "h"},
        ),
        (
            build_custom_zoom_button_custom_id("h"),
            CustomIdKind.CUSTOM_ZOOM_BUTTON,
            {"message_hash": "h"},
        ),
        (
            build_custom_zoom_modal_custom_id("h"),
            CustomIdKind.CUSTOM_ZOOM_MODAL,
            {"message_hash": "h"},
        ),
        (build_inpaint_custom_id(1, "h"), CustomIdKind.INPAINT, {"index": 1, "message_hash": "h"}),
        ("MJ::iframe::token-123", CustomIdKind.IFRAME, {"token": "token-123"}),
    ]
    for cid, expected_kind, expected_fields in cases:
        parsed = parse_custom_id(cid)
        assert parsed is not None
        assert parsed.kind is expected_kind
        for key, value in expected_fields.items():
            assert getattr(parsed, key) == value


def test_custom_id_rejects_invalid_strings():
    for cid in ["", "MJ::UNKNOWN", "MJ::JOB::upsample::x::hash", "MJ::iframe::"]:
        assert parse_custom_id(cid) is None
        assert not validate_custom_id(cid)
