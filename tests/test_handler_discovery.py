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

from mutiny.engine.reactors.registry import build_reactors


def _index_map(names: list[str]) -> dict[str, int]:
    return {n: i for i, n in enumerate(names)}


def test_pipeline_listener_order():
    hs = build_reactors()
    names = [type(h).__name__ for h in hs]
    expected = [
        "ErrorReactor",
        "ProgressReactor",
        "DescribeReactor",
        "ImagineReactor",
        "UpscaleReactor",
        "VariationReactor",
        "RerollReactor",
        "BlendReactor",
        "AnimateReactor",
    ]
    idx = _index_map(names)
    for e in expected:
        assert e in idx, f"Missing listener {e} in pipeline: {names}"
    for a, b in zip(expected, expected[1:]):
        assert idx[a] < idx[b], f"Order violation: {a} should come before {b}"
