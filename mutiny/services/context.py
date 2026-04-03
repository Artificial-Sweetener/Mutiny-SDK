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

"""Application context objects used to wire one Mutiny runtime session."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from ..config import Config
from ..interfaces.image import ImageProcessor
from .cache.artifact_cache import ArtifactCacheService
from .image_processor import OpenCVImageProcessor
from .interaction_cache import InteractionCache
from .job_store import JobStore
from .metrics.service import MetricsService
from .notify.event_bus import JobUpdateBus
from .response_dump import ResponseDumpService
from .video_signature import VideoSignatureService

if TYPE_CHECKING:
    from mutiny.engine.discord_engine import DiscordEngine


@dataclass
class AppContext:
    """Runtime service container for one Mutiny session."""

    config: Config
    job_store: JobStore
    notify_bus: JobUpdateBus
    artifact_cache: ArtifactCacheService
    response_dump: ResponseDumpService
    interaction_cache: InteractionCache
    metrics: MetricsService
    image_processor: ImageProcessor = field(default_factory=OpenCVImageProcessor)
    engine: Optional["DiscordEngine"] = None
    video_signature_service: VideoSignatureService = field(default_factory=VideoSignatureService)


@dataclass(frozen=True)
class ContextOverrides:
    """Optional service overrides used when building application state."""

    job_store: Optional[JobStore] = None
    notify_bus: Optional[JobUpdateBus] = None
    artifact_cache: Optional[ArtifactCacheService] = None
    video_signature_service: Optional[VideoSignatureService] = None
    response_dump: Optional[ResponseDumpService] = None
    interaction_cache: Optional[InteractionCache] = None
    metrics: Optional[MetricsService] = None
    engine: Optional["DiscordEngine"] = None


__all__ = ["AppContext", "ContextOverrides"]
