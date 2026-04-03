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

from __future__ import annotations

from mutiny.engine.reactors.animate_reactor import AnimateReactor
from mutiny.engine.reactors.blend_reactor import BlendReactor
from mutiny.engine.reactors.describe_reactor import DescribeReactor
from mutiny.engine.reactors.error_reactor import ErrorReactor
from mutiny.engine.reactors.imagine_reactor import ImagineReactor
from mutiny.engine.reactors.progress_reactor import ProgressReactor
from mutiny.engine.reactors.reroll_reactor import RerollReactor
from mutiny.engine.reactors.upscale_reactor import UpscaleReactor
from mutiny.engine.reactors.variation_reactor import VariationReactor


def build_reactors():
    return [
        ErrorReactor(),
        ProgressReactor(),
        DescribeReactor(),
        ImagineReactor(),
        UpscaleReactor(),
        VariationReactor(),
        RerollReactor(),
        BlendReactor(),
        AnimateReactor(),
    ]


__all__ = ["build_reactors"]
