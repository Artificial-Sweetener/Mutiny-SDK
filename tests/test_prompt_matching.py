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

from mutiny.engine.prompt_matching import normalize_prompt_for_matching


def test_normalize_prompt_for_matching_strips_trailing_image_reference_flags():
    original = "pink twintails tsundere girl --no evil --ar 3:4 --seed 7 --niji 7"
    rewritten = (
        "pink twintails tsundere girl --no evil --ar 3:4 --seed 7 --niji 7 "
        "--sref <https://s.mj.run/a> <https://s.mj.run/b> "
        "--cref <https://s.mj.run/c> --oref <https://s.mj.run/d>"
    )

    assert normalize_prompt_for_matching(original) == normalize_prompt_for_matching(rewritten)


def test_normalize_prompt_for_matching_preserves_non_reference_flags():
    prompt = "pink twintails tsundere girl --no evil --ar 3:4 --seed 7 --niji 7"

    assert normalize_prompt_for_matching(prompt) == prompt


def test_normalize_prompt_for_matching_treats_video_one_as_video():
    original = "<https://s.mj.run/abcd> magic spell --motion low --bs 1 --video --aspect 199:256"
    rewritten = "<https://s.mj.run/abcd> magic spell --motion low --bs 1 --video 1 --aspect 199:256"

    assert normalize_prompt_for_matching(original) == normalize_prompt_for_matching(rewritten)


def test_normalize_prompt_for_matching_canonicalizes_prompt_video_flag_order():
    original = "<https://s.mj.run/abcd> blink once --video --motion low --bs 1"
    rewritten = "<https://s.mj.run/abcd> blink once --motion low --bs 1 --video 1"

    assert normalize_prompt_for_matching(original) == normalize_prompt_for_matching(rewritten)


def test_normalize_prompt_for_matching_ignores_prompt_video_aspect_injection():
    original = "<https://s.mj.run/abcd> magic spell --video --motion low --bs 1"
    rewritten = "<https://s.mj.run/abcd> magic spell --motion low --bs 1 --video 1 --aspect 199:256"

    assert normalize_prompt_for_matching(original) == normalize_prompt_for_matching(rewritten)


def test_normalize_prompt_for_matching_canonicalizes_prompt_video_end_frame_order():
    original = (
        "<https://s.mj.run/start> magic spell --video --motion high "
        "--end <https://s.mj.run/end> --bs 2"
    )
    rewritten = (
        "<https://s.mj.run/start> magic spell --bs 2 --motion high "
        "--video 1 --end <https://s.mj.run/end> --aspect 16:9"
    )

    assert normalize_prompt_for_matching(original) == normalize_prompt_for_matching(rewritten)
