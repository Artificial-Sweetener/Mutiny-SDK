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

"""Unified artifact cache for image uploads and restart-safe artifact contexts.

This service is the single artifact-recognition cache used by Mutiny runtime
flows. It stores one canonical record shape in memory and on disk, supports
lazy hydration, and keeps RAM as a working set while disk remains the durable
backing layer when enabled.
"""

from __future__ import annotations

import json
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, Optional, TypedDict, cast

from mutiny.services.image_utils import phash_to_int
from mutiny.services.persistence.persistent_kv import PersistentKV

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from mutiny.types import TileFollowUpMode

ArtifactKind = Literal["image", "video"]

_ARTIFACT_NAMESPACE = "artifact_cache"
_LEGACY_IMAGE_URL_NAMESPACE = "image_cache"
_LEGACY_IMAGE_REF_NAMESPACE = "job_index"
_LEGACY_VIDEO_REF_NAMESPACE = "video_job_index"
_MEMORY_ENTRY_OVERHEAD_BYTES = 128
_SIGNATURE_INDEX_PREFIX = "sig:image"
_SIGNATURE_POINTER_PREFIX = "sigptr:image"


class ImageSignature(TypedDict, total=False):
    """Canonical image identity used by artifact recognition.

    Fields:
        digest: SHA256 hex string of raw RGB pixel bytes.
        phash: Optional perceptual hash integer for fuzzy matching.
        width: Optional image width in pixels.
        height: Optional image height in pixels.
        kind: Optional result-kind hint such as ``tile`` or ``upscale``.
    """

    digest: str
    phash: int
    width: int
    height: int
    kind: str


class ArtifactCachePersistenceError(RuntimeError):
    """Raise when a restart-critical artifact record cannot be durably persisted."""


@dataclass(frozen=True)
class JobRef:
    """Store actionable Midjourney message context for one recognized artifact."""

    message_id: str
    message_hash: str
    flags: int
    index: int
    ts: float
    prompt_text: str | None = None
    tile_follow_up_mode: "TileFollowUpMode | str" = "modern"
    action_custom_ids: dict[str, str] | None = None
    phash: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    kind: Optional[str] = None
    signature_version: Optional[int] = None


@dataclass(frozen=True)
class RecognizedImageContext:
    """Describe one recognized image using persisted artifact-cache state only."""

    message_id: str
    message_hash: str
    flags: int
    index: int
    kind: str | None
    prompt_text: str | None
    tile_follow_up_mode: "TileFollowUpMode"
    action_custom_ids: dict[str, str]


@dataclass(frozen=True)
class RecognizedVideoContext:
    """Describe one recognized video using persisted artifact-cache state only."""

    message_id: str
    message_hash: str
    flags: int
    index: int
    prompt_text: str | None
    action_custom_ids: dict[str, str]
    signature_version: int | None = None


@dataclass
class ArtifactCacheRecord:
    """Persist one artifact's cached upload URL and/or actionable job ref."""

    artifact_kind: ArtifactKind
    digest: str
    ts: float
    source_url: str | None = None
    source_url_ts: float | None = None
    message_id: str | None = None
    message_hash: str | None = None
    flags: int = 0
    index: int = 0
    job_ref_ts: float | None = None
    signature_version: int | None = None
    prompt_text: str | None = None
    tile_follow_up_mode: str | None = None
    action_custom_ids: dict[str, str] | None = None
    phash: int | None = None
    width: int | None = None
    height: int | None = None
    kind: str | None = None

    def image_job_ref(self) -> JobRef | None:
        """Return the image/video job ref projection when one is present."""
        if not self.message_id or not self.message_hash or self.job_ref_ts is None:
            return None
        return JobRef(
            message_id=self.message_id,
            message_hash=self.message_hash,
            flags=int(self.flags or 0),
            index=int(self.index or 0),
            ts=float(self.job_ref_ts),
            prompt_text=self.prompt_text,
            tile_follow_up_mode=_normalize_tile_follow_up_mode(self.tile_follow_up_mode),
            action_custom_ids=dict(self.action_custom_ids or {}),
            phash=self.phash,
            width=self.width,
            height=self.height,
            kind=self.kind,
            signature_version=self.signature_version,
        )

    def image_context(self) -> RecognizedImageContext | None:
        """Return one persisted image context when this record represents an image."""
        ref = self.image_job_ref()
        if ref is None or self.artifact_kind != "image":
            return None
        return RecognizedImageContext(
            message_id=ref.message_id,
            message_hash=ref.message_hash,
            flags=ref.flags,
            index=ref.index,
            kind=ref.kind,
            prompt_text=ref.prompt_text,
            tile_follow_up_mode=_normalize_tile_follow_up_mode(ref.tile_follow_up_mode),
            action_custom_ids=dict(ref.action_custom_ids or {}),
        )

    def video_context(self) -> RecognizedVideoContext | None:
        """Return one persisted video context when this record represents a video."""
        ref = self.image_job_ref()
        if ref is None or self.artifact_kind != "video":
            return None
        return RecognizedVideoContext(
            message_id=ref.message_id,
            message_hash=ref.message_hash,
            flags=ref.flags,
            index=ref.index or 1,
            prompt_text=ref.prompt_text,
            action_custom_ids=dict(ref.action_custom_ids or {}),
            signature_version=ref.signature_version,
        )

    def to_json(self) -> str:
        """Serialize the record for disk persistence."""
        return json.dumps(
            {
                "artifact_kind": self.artifact_kind,
                "digest": self.digest,
                "ts": self.ts,
                "source_url": self.source_url,
                "source_url_ts": self.source_url_ts,
                "message_id": self.message_id,
                "message_hash": self.message_hash,
                "flags": int(self.flags or 0),
                "index": int(self.index or 0),
                "job_ref_ts": self.job_ref_ts,
                "signature_version": self.signature_version,
                "prompt_text": self.prompt_text,
                "tile_follow_up_mode": self.tile_follow_up_mode,
                "action_custom_ids": self.action_custom_ids or {},
                "phash": self.phash,
                "width": self.width,
                "height": self.height,
                "kind": self.kind,
            }
        )

    @classmethod
    def from_json(cls, payload: str) -> ArtifactCacheRecord:
        """Deserialize one persisted record."""
        obj = json.loads(payload)
        phash_value = obj.get("phash")
        if phash_value is not None:
            phash_value = phash_to_int(phash_value)
        return cls(
            artifact_kind=cast(ArtifactKind, str(obj["artifact_kind"])),
            digest=str(obj["digest"]),
            ts=float(obj.get("ts") or time.time()),
            source_url=obj.get("source_url"),
            source_url_ts=(
                float(obj["source_url_ts"]) if obj.get("source_url_ts") is not None else None
            ),
            message_id=obj.get("message_id"),
            message_hash=obj.get("message_hash"),
            flags=int(obj.get("flags") or 0),
            index=int(obj.get("index") or 0),
            job_ref_ts=(float(obj["job_ref_ts"]) if obj.get("job_ref_ts") is not None else None),
            signature_version=(
                int(obj["signature_version"]) if obj.get("signature_version") is not None else None
            ),
            prompt_text=obj.get("prompt_text"),
            tile_follow_up_mode=obj.get("tile_follow_up_mode"),
            action_custom_ids=_normalize_action_custom_ids(obj.get("action_custom_ids")),
            phash=phash_value,
            width=(int(obj["width"]) if obj.get("width") is not None else None),
            height=(int(obj["height"]) if obj.get("height") is not None else None),
            kind=obj.get("kind"),
        )


class ArtifactCacheService:
    """Manage RAM and disk-backed artifact records for image/video recognition."""

    def __init__(
        self,
        *,
        image_cache_ttl_seconds: int = 24 * 3600,
        image_cache_max_entries: int = 5000,
        job_index_ttl_seconds: int = 7 * 24 * 3600,
        job_index_max_entries: int = 10000,
        ram_max_bytes: int = 32 * 1024 * 1024,
    ) -> None:
        self.image_cache_ttl_seconds = image_cache_ttl_seconds
        self.image_cache_max_entries = image_cache_max_entries
        self.job_index_ttl_seconds = job_index_ttl_seconds
        self.job_index_max_entries = job_index_max_entries
        self.ram_max_bytes = ram_max_bytes
        self._records: OrderedDict[str, ArtifactCacheRecord] = OrderedDict()
        self._record_sizes: dict[str, int] = {}
        self._ram_bytes = 0
        self._disk: Optional[PersistentKV] = None

    def apply_config(
        self,
        *,
        image_cache_ttl_seconds: int,
        image_cache_max_entries: int,
        job_index_ttl_seconds: int,
        job_index_max_entries: int,
        ram_max_bytes: int,
        disk: Optional[PersistentKV],
    ) -> None:
        """Hot-apply cache limits and disk attachment."""
        self.image_cache_ttl_seconds = image_cache_ttl_seconds
        self.image_cache_max_entries = image_cache_max_entries
        self.job_index_ttl_seconds = job_index_ttl_seconds
        self.job_index_max_entries = job_index_max_entries
        self.ram_max_bytes = ram_max_bytes
        self._disk = disk
        self._prune_expired_memory()
        self._evict_if_needed()

    def put_image_upload(self, digest: str, source_url: str) -> None:
        """Persist one image upload/CDN URL keyed by artifact digest."""
        now = time.time()
        record = self._load_record("image", digest) or ArtifactCacheRecord(
            artifact_kind="image",
            digest=digest,
            ts=now,
        )
        record.source_url = source_url
        record.source_url_ts = now
        record.ts = now
        self._store_record(record)

    def get_image_upload_url(self, digest: str) -> str | None:
        """Return a cached image upload/CDN URL when still fresh."""
        record = self._get_record("image", digest)
        if not record or not record.source_url or record.source_url_ts is None:
            return None
        if self._is_source_url_expired(record):
            record.source_url = None
            record.source_url_ts = None
            self._persist_cleanup(record)
            return None
        return record.source_url

    def put_image_job_ref(
        self,
        digest: str,
        *,
        message_id: str,
        message_hash: str,
        flags: int,
        index: int,
        prompt_text: str | None = None,
        tile_follow_up_mode: "TileFollowUpMode | str" = "modern",
        action_custom_ids: dict[str, str] | None = None,
        phash: Optional[int] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
        kind: Optional[str] = None,
        signature_version: Optional[int] = None,
    ) -> None:
        """Persist one image artifact job ref keyed by digest."""
        now = time.time()
        record = self._load_record("image", digest) or ArtifactCacheRecord(
            artifact_kind="image",
            digest=digest,
            ts=now,
        )
        record.message_id = message_id
        record.message_hash = message_hash
        record.flags = int(flags or 0)
        record.index = int(index or 0)
        record.job_ref_ts = now
        record.signature_version = signature_version
        record.prompt_text = prompt_text
        record.tile_follow_up_mode = _normalize_tile_follow_up_mode(tile_follow_up_mode).value
        record.action_custom_ids = dict(action_custom_ids or {})
        record.phash = phash
        record.width = width
        record.height = height
        record.kind = kind
        record.ts = now
        self._store_record(record, require_durable=True)

    def find_image_by_signature(
        self,
        *,
        digest: str | None,
        phash: Optional[int] = None,
        expected_kind: Optional[str] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
        phash_threshold: int = 6,
    ) -> JobRef | None:
        """Resolve one image artifact using exact digest or durable phash fallback."""
        if digest:
            ref = self.get_image_job_ref(digest)
            if ref and (expected_kind is None or ref.kind == expected_kind):
                return ref

        if phash is None:
            return None

        best: JobRef | None = None
        best_dist = 1 << 30
        for record in self._records.values():
            if record.artifact_kind != "image":
                continue
            ref = self._record_job_ref(record)
            if ref is None:
                continue
            if expected_kind and ref.kind != expected_kind:
                continue
            if ref.phash is None:
                continue
            distance = (int(ref.phash) ^ int(phash)).bit_count()
            if distance < best_dist:
                best_dist = distance
                best = ref

        if best and best_dist <= phash_threshold:
            return best

        for candidate in self._iter_disk_signature_candidates(
            expected_kind=expected_kind,
            width=width,
            height=height,
        ):
            if expected_kind and candidate["kind"] != expected_kind:
                continue
            distance = (int(candidate["phash"]) ^ int(phash)).bit_count()
            if distance > phash_threshold or distance >= best_dist:
                continue
            candidate_record: ArtifactCacheRecord | None = self._get_record(
                "image", candidate["digest"]
            )
            ref = self._record_job_ref(candidate_record)
            if ref is None:
                continue
            if expected_kind and ref.kind != expected_kind:
                continue
            best_dist = distance
            best = ref

        if best and best_dist <= phash_threshold:
            return best
        return None

    def get_image_job_ref(self, digest: str) -> JobRef | None:
        """Return the exact image job ref for one digest when still fresh."""
        record = self._get_record("image", digest)
        return self._record_job_ref(record)

    def find_image_context_by_signature(
        self,
        *,
        digest: str | None,
        phash: Optional[int] = None,
        expected_kind: Optional[str] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
        phash_threshold: int = 6,
    ) -> RecognizedImageContext | None:
        """Resolve one image to its persisted actionable context."""

        ref = self.find_image_by_signature(
            digest=digest,
            phash=phash,
            expected_kind=expected_kind,
            width=width,
            height=height,
            phash_threshold=phash_threshold,
        )
        if ref is None:
            return None
        record = self._get_record("image", digest or "")
        if digest and record is not None:
            context = record.image_context()
            if context is not None and (expected_kind is None or context.kind == expected_kind):
                return context
        return RecognizedImageContext(
            message_id=ref.message_id,
            message_hash=ref.message_hash,
            flags=ref.flags,
            index=ref.index,
            kind=ref.kind,
            prompt_text=ref.prompt_text,
            tile_follow_up_mode=_normalize_tile_follow_up_mode(ref.tile_follow_up_mode),
            action_custom_ids=dict(ref.action_custom_ids or {}),
        )

    def put_video_job_ref(
        self,
        digest: str,
        *,
        message_id: str,
        message_hash: str,
        flags: int,
        signature_version: int,
        prompt_text: str | None = None,
        action_custom_ids: dict[str, str] | None = None,
        kind: str = "video",
        index: int = 1,
    ) -> None:
        """Persist one normalized video job ref keyed by digest."""
        now = time.time()
        record = self._load_record("video", digest) or ArtifactCacheRecord(
            artifact_kind="video",
            digest=digest,
            ts=now,
        )
        record.message_id = message_id
        record.message_hash = message_hash
        record.flags = int(flags or 0)
        record.index = int(index or 0)
        record.job_ref_ts = now
        record.signature_version = int(signature_version)
        record.prompt_text = prompt_text
        record.tile_follow_up_mode = None
        record.action_custom_ids = dict(action_custom_ids or {})
        record.kind = kind
        record.ts = now
        self._store_record(record, require_durable=True)

    def find_video_by_digest(self, digest: str | None) -> JobRef | None:
        """Resolve one exact recognized video digest to its job ref."""
        if not digest:
            return None
        record = self._get_record("video", digest)
        ref = self._record_job_ref(record)
        if ref and ref.kind == "video":
            return ref
        return None

    def find_video_context_by_digest(self, digest: str | None) -> RecognizedVideoContext | None:
        """Resolve one recognized video digest to its persisted actionable context."""

        if not digest:
            return None
        record = self._get_record("video", digest)
        if record is None:
            return None
        return record.video_context()

    def _record_job_ref(self, record: ArtifactCacheRecord | None) -> JobRef | None:
        if not record:
            return None
        ref = record.image_job_ref()
        if ref is None:
            return None
        if self._is_job_ref_expired(record):
            record.message_id = None
            record.message_hash = None
            record.flags = 0
            record.index = 0
            record.job_ref_ts = None
            if record.artifact_kind == "video":
                record.signature_version = None
                record.prompt_text = None
                record.action_custom_ids = None
            if record.artifact_kind == "image":
                record.prompt_text = None
                record.tile_follow_up_mode = None
                record.action_custom_ids = None
                record.phash = None
                record.width = None
                record.height = None
                record.kind = None if record.source_url else record.kind
            self._persist_cleanup(record)
            return None
        return ref

    def _is_source_url_expired(self, record: ArtifactCacheRecord) -> bool:
        return (
            record.source_url_ts is None
            or (time.time() - float(record.source_url_ts)) > self.image_cache_ttl_seconds
        )

    def _is_job_ref_expired(self, record: ArtifactCacheRecord) -> bool:
        return (
            record.job_ref_ts is None
            or (time.time() - float(record.job_ref_ts)) > self.job_index_ttl_seconds
        )

    def _get_record(self, artifact_kind: ArtifactKind, digest: str) -> ArtifactCacheRecord | None:
        key = self._record_key(artifact_kind, digest)
        record = self._records.get(key)
        if record is None:
            record = self._load_record(artifact_kind, digest)
            if record is not None:
                self._remember_record(record)
        else:
            self._touch_record(record)
        return record

    def _load_record(self, artifact_kind: ArtifactKind, digest: str) -> ArtifactCacheRecord | None:
        key = self._record_key(artifact_kind, digest)
        record = self._load_from_unified_disk(key)
        if record is not None:
            return record
        return self._load_from_legacy_disk(artifact_kind, digest)

    def _load_from_unified_disk(self, key: str) -> ArtifactCacheRecord | None:
        if not self._disk:
            return None
        try:
            raw = self._disk.get(_ARTIFACT_NAMESPACE, key)
        except Exception:
            logger.warning("Artifact cache disk read failed", exc_info=True, extra={"key": key})
            return None
        if not raw:
            return None
        try:
            return ArtifactCacheRecord.from_json(raw)
        except Exception:
            logger.warning(
                "Artifact cache record decode failed",
                exc_info=True,
                extra={"key": key},
            )
            return None

    def _load_from_legacy_disk(
        self, artifact_kind: ArtifactKind, digest: str
    ) -> ArtifactCacheRecord | None:
        if not self._disk:
            return None
        if artifact_kind == "video":
            return self._load_legacy_video_record(digest)
        return self._load_legacy_image_record(digest)

    def _load_legacy_image_record(self, digest: str) -> ArtifactCacheRecord | None:
        source_url = None
        source_url_ts = None
        message_ref: JobRef | None = None

        disk = self._disk
        if disk is None:
            return None

        try:
            raw_url = disk.get(_LEGACY_IMAGE_URL_NAMESPACE, digest)
        except Exception:
            raw_url = None
        if raw_url:
            try:
                obj = json.loads(raw_url)
                source_url = obj["url"]
                source_url_ts = float(obj["ts"])
            except Exception:
                logger.warning(
                    "Legacy image-cache record decode failed",
                    exc_info=True,
                    extra={"digest": digest},
                )

        try:
            raw_ref = disk.get(_LEGACY_IMAGE_REF_NAMESPACE, digest)
        except Exception:
            raw_ref = None
        if raw_ref:
            try:
                legacy = json.loads(raw_ref)
                if (
                    legacy.get("prompt_text") in (None, "")
                    or legacy.get("tile_follow_up_mode") is None
                    or not isinstance(legacy.get("action_custom_ids"), dict)
                ):
                    logger.warning(
                        "Legacy image-job-index record lacks restart-safe metadata; "
                        "skipping job-ref recovery",
                        extra={"digest": digest},
                    )
                else:
                    message_ref = JobRef(
                        message_id=legacy["message_id"],
                        message_hash=legacy["message_hash"],
                        flags=int(legacy.get("flags", 0)),
                        index=int(legacy.get("index", 0)),
                        ts=float(legacy["ts"]),
                        prompt_text=str(legacy.get("prompt_text") or "") or None,
                        tile_follow_up_mode=_normalize_tile_follow_up_mode(
                            legacy.get("tile_follow_up_mode")
                        ),
                        action_custom_ids=_normalize_action_custom_ids(
                            legacy.get("action_custom_ids")
                        ),
                        phash=(
                            phash_to_int(legacy["phash"])
                            if legacy.get("phash") is not None
                            else None
                        ),
                        width=(int(legacy["width"]) if legacy.get("width") is not None else None),
                        height=(
                            int(legacy["height"]) if legacy.get("height") is not None else None
                        ),
                        kind=legacy.get("kind"),
                        signature_version=(
                            int(legacy["signature_version"])
                            if legacy.get("signature_version") is not None
                            else None
                        ),
                    )
            except Exception:
                logger.warning(
                    "Legacy image-job-index record decode failed",
                    exc_info=True,
                    extra={"digest": digest},
                )

        if source_url is None and message_ref is None:
            return None

        now = time.time()
        record = ArtifactCacheRecord(
            artifact_kind="image",
            digest=digest,
            ts=now,
            source_url=source_url,
            source_url_ts=source_url_ts,
            message_id=message_ref.message_id if message_ref else None,
            message_hash=message_ref.message_hash if message_ref else None,
            flags=message_ref.flags if message_ref else 0,
            index=message_ref.index if message_ref else 0,
            job_ref_ts=message_ref.ts if message_ref else None,
            signature_version=message_ref.signature_version if message_ref else None,
            prompt_text=message_ref.prompt_text if message_ref else None,
            tile_follow_up_mode=(
                _normalize_tile_follow_up_mode(message_ref.tile_follow_up_mode).value
                if message_ref
                else None
            ),
            action_custom_ids=dict(message_ref.action_custom_ids or {}) if message_ref else None,
            phash=message_ref.phash if message_ref else None,
            width=message_ref.width if message_ref else None,
            height=message_ref.height if message_ref else None,
            kind=message_ref.kind if message_ref else None,
        )
        self._persist_record(record)
        return record

    def _load_legacy_video_record(self, digest: str) -> ArtifactCacheRecord | None:
        disk = self._disk
        if disk is None:
            return None

        try:
            raw_ref = disk.get(_LEGACY_VIDEO_REF_NAMESPACE, digest)
        except Exception:
            raw_ref = None
        if not raw_ref:
            return None
        try:
            legacy = json.loads(raw_ref)
            record = ArtifactCacheRecord(
                artifact_kind="video",
                digest=digest,
                ts=time.time(),
                message_id=legacy["message_id"],
                message_hash=legacy["message_hash"],
                flags=int(legacy.get("flags", 0)),
                index=int(legacy.get("index", 1)),
                job_ref_ts=float(legacy["ts"]),
                signature_version=(
                    int(legacy["signature_version"])
                    if legacy.get("signature_version") is not None
                    else None
                ),
                prompt_text=legacy.get("prompt_text"),
                action_custom_ids=_normalize_action_custom_ids(legacy.get("action_custom_ids")),
                kind=legacy.get("kind") or "video",
            )
        except Exception:
            logger.warning(
                "Legacy video-job-index record decode failed",
                exc_info=True,
                extra={"digest": digest},
            )
            return None
        self._persist_record(record)
        return record

    def _store_record(self, record: ArtifactCacheRecord, *, require_durable: bool = False) -> None:
        persisted = self._persist_record(record, require_durable=require_durable)
        self._remember_record(record)
        skip_keys = set() if persisted else {self._record_key(record.artifact_kind, record.digest)}
        self._evict_if_needed(skip_keys=skip_keys)

    def _persist_record(
        self, record: ArtifactCacheRecord, *, require_durable: bool = False
    ) -> bool:
        if not self._disk:
            return True
        key = self._record_key(record.artifact_kind, record.digest)
        try:
            puts = {key: record.to_json()}
            deletes: list[str] = []
            if record.artifact_kind == "image":
                pointer_key = _signature_pointer_key(record.digest)
                previous_signature_key = self._disk.get(_ARTIFACT_NAMESPACE, pointer_key)
                signature_key, signature_payload = _build_signature_entry(record)
                if previous_signature_key and previous_signature_key != signature_key:
                    deletes.append(previous_signature_key)
                if previous_signature_key and signature_key is None:
                    deletes.append(previous_signature_key)
                if previous_signature_key and previous_signature_key != signature_key:
                    deletes.append(pointer_key)
                elif previous_signature_key and signature_key is None:
                    deletes.append(pointer_key)
                if signature_key is not None and signature_payload is not None:
                    puts[signature_key] = signature_payload
                    puts[pointer_key] = signature_key
            self._disk.apply_batch(_ARTIFACT_NAMESPACE, puts=puts, deletes=deletes)
            return True
        except Exception:
            logger.warning(
                "Artifact cache disk write failed",
                exc_info=True,
                extra={"key": key},
            )
            if require_durable:
                raise ArtifactCachePersistenceError(
                    f"Failed to durably persist artifact cache record for {key}"
                ) from None
            return False

    def _persist_cleanup(self, record: ArtifactCacheRecord) -> None:
        key = self._record_key(record.artifact_kind, record.digest)
        if record.source_url is None and record.job_ref_ts is None:
            self._delete_persisted_record(record)
            self._drop_record(key)
            return
        persisted = self._persist_record(record)
        self._remember_record(record)
        skip_keys = set() if persisted else {key}
        self._evict_if_needed(skip_keys=skip_keys)

    def _delete_persisted_record(self, record: ArtifactCacheRecord) -> None:
        if not self._disk:
            return
        deletes = [self._record_key(record.artifact_kind, record.digest)]
        if record.artifact_kind == "image":
            pointer_key = _signature_pointer_key(record.digest)
            signature_key = self._disk.get(_ARTIFACT_NAMESPACE, pointer_key)
            if signature_key:
                deletes.append(signature_key)
                deletes.append(pointer_key)
        try:
            self._disk.apply_batch(_ARTIFACT_NAMESPACE, deletes=deletes)
        except Exception:
            logger.warning(
                "Artifact cache disk delete failed",
                exc_info=True,
                extra={"digest": record.digest, "artifact_kind": record.artifact_kind},
            )

    def _iter_disk_signature_candidates(
        self,
        *,
        expected_kind: Optional[str],
        width: Optional[int],
        height: Optional[int],
    ) -> list[ImageSignature]:
        if not self._disk:
            return []

        prefixes: list[str] = []
        if expected_kind is not None and width is not None and height is not None:
            prefixes.append(_signature_bucket_prefix(expected_kind, width, height))
        elif expected_kind is not None:
            prefixes.append(_signature_kind_prefix(expected_kind))
        else:
            prefixes.append(f"{_SIGNATURE_INDEX_PREFIX}:")

        seen_digests: set[str] = set()
        candidates: list[ImageSignature] = []
        for prefix in prefixes:
            try:
                rows = self._disk.scan(_ARTIFACT_NAMESPACE, prefix)
            except Exception:
                logger.warning(
                    "Artifact cache signature scan failed",
                    exc_info=True,
                    extra={"prefix": prefix},
                )
                continue
            for _key, payload in rows:
                try:
                    decoded = json.loads(payload)
                    digest = str(decoded["digest"])
                    if digest in seen_digests:
                        continue
                    candidate: ImageSignature = {
                        "digest": digest,
                        "phash": phash_to_int(decoded["phash"]),
                        "width": int(decoded["width"]),
                        "height": int(decoded["height"]),
                        "kind": str(decoded["kind"]),
                    }
                except Exception:
                    logger.warning(
                        "Artifact cache signature decode failed",
                        exc_info=True,
                    )
                    continue
                seen_digests.add(digest)
                candidates.append(candidate)
        return candidates

    def _remember_record(self, record: ArtifactCacheRecord) -> None:
        key = self._record_key(record.artifact_kind, record.digest)
        previous_size = self._record_sizes.pop(key, 0)
        self._ram_bytes -= previous_size
        self._records.pop(key, None)
        record.ts = time.time()
        self._records[key] = record
        self._records.move_to_end(key)
        size = self._estimate_record_size(key, record)
        self._record_sizes[key] = size
        self._ram_bytes += size

    def _touch_record(self, record: ArtifactCacheRecord) -> None:
        key = self._record_key(record.artifact_kind, record.digest)
        if key not in self._records:
            self._remember_record(record)
            return
        record.ts = time.time()
        self._records.move_to_end(key)
        new_size = self._estimate_record_size(key, record)
        old_size = self._record_sizes.get(key, 0)
        self._record_sizes[key] = new_size
        self._ram_bytes += new_size - old_size

    def _prune_expired_memory(self) -> None:
        for key, record in list(self._records.items()):
            changed = False
            if record.source_url and self._is_source_url_expired(record):
                record.source_url = None
                record.source_url_ts = None
                changed = True
            if record.job_ref_ts is not None and self._is_job_ref_expired(record):
                record.message_id = None
                record.message_hash = None
                record.flags = 0
                record.index = 0
                record.job_ref_ts = None
                changed = True
                if record.artifact_kind == "video":
                    record.signature_version = None
                if record.artifact_kind == "image":
                    record.phash = None
                    record.width = None
                    record.height = None
                    record.kind = None if record.source_url is None else record.kind
            if changed:
                self._persist_cleanup(record)
            else:
                self._touch_record(record)

    def _evict_if_needed(self, skip_keys: set[str] | None = None) -> None:
        skip_keys = skip_keys or set()
        self._enforce_entry_caps(skip_keys)
        while self._ram_bytes > self.ram_max_bytes and self._records:
            evicted = False
            for key in list(self._records.keys()):
                if key in skip_keys:
                    continue
                self._drop_record(key)
                evicted = True
                break
            if not evicted:
                break

    def _enforce_entry_caps(self, skip_keys: set[str]) -> None:
        image_upload_keys = [
            key
            for key, record in self._records.items()
            if record.artifact_kind == "image" and record.source_url is not None
        ]
        while len(image_upload_keys) > self.image_cache_max_entries:
            drop_key = next((key for key in image_upload_keys if key not in skip_keys), None)
            if drop_key is None:
                break
            self._drop_record(drop_key, drop_source_url_only=True)
            image_upload_keys = [
                key
                for key, record in self._records.items()
                if record.artifact_kind == "image" and record.source_url is not None
            ]

        job_ref_keys = [
            key for key, record in self._records.items() if record.job_ref_ts is not None
        ]
        while len(job_ref_keys) > self.job_index_max_entries:
            drop_key = next((key for key in job_ref_keys if key not in skip_keys), None)
            if drop_key is None:
                break
            self._drop_record(drop_key, drop_job_ref_only=True)
            job_ref_keys = [
                key for key, record in self._records.items() if record.job_ref_ts is not None
            ]

    def _drop_record(
        self,
        key: str,
        *,
        drop_source_url_only: bool = False,
        drop_job_ref_only: bool = False,
    ) -> None:
        record = self._records.get(key)
        if record is None:
            return
        if drop_source_url_only:
            record.source_url = None
            record.source_url_ts = None
            if record.job_ref_ts is not None:
                self._touch_record(record)
                return
        elif drop_job_ref_only:
            record.message_id = None
            record.message_hash = None
            record.flags = 0
            record.index = 0
            record.job_ref_ts = None
            if record.artifact_kind == "video":
                record.signature_version = None
                record.prompt_text = None
                record.action_custom_ids = None
            if record.artifact_kind == "image":
                record.prompt_text = None
                record.tile_follow_up_mode = None
                record.action_custom_ids = None
                record.phash = None
                record.width = None
                record.height = None
                if record.source_url is None:
                    record.kind = None
            if record.source_url is not None:
                self._touch_record(record)
                return

        self._records.pop(key, None)
        self._ram_bytes -= self._record_sizes.pop(key, 0)

    @staticmethod
    def _record_key(artifact_kind: ArtifactKind, digest: str) -> str:
        return f"{artifact_kind}:{digest}"

    @staticmethod
    def _estimate_record_size(key: str, record: ArtifactCacheRecord) -> int:
        return (
            len(key.encode("utf-8"))
            + len(record.to_json().encode("utf-8"))
            + _MEMORY_ENTRY_OVERHEAD_BYTES
        )


__all__ = [
    "ArtifactCachePersistenceError",
    "ArtifactCacheRecord",
    "ArtifactCacheService",
    "ImageSignature",
    "JobRef",
    "RecognizedImageContext",
    "RecognizedVideoContext",
    "phash_to_int",
]


def _normalize_tile_follow_up_mode(value: object) -> "TileFollowUpMode":
    """Return one safe tile-follow-up mode from persisted cache state."""

    from mutiny.types import TileFollowUpMode

    if isinstance(value, TileFollowUpMode):
        return value
    if value == TileFollowUpMode.LEGACY.value:
        return TileFollowUpMode.LEGACY
    return TileFollowUpMode.MODERN


def _normalize_action_custom_ids(value: object) -> dict[str, str]:
    """Return a normalized string-to-string custom-id mapping."""

    if not isinstance(value, dict):
        return {}
    normalized: dict[str, str] = {}
    for key, item in value.items():
        if key is None or item in (None, ""):
            continue
        normalized[str(key)] = str(item)
    return normalized


def _signature_kind_prefix(kind: str) -> str:
    return f"{_SIGNATURE_INDEX_PREFIX}:{kind}:"


def _signature_bucket_prefix(kind: str, width: int, height: int) -> str:
    return f"{_SIGNATURE_INDEX_PREFIX}:{kind}:{width}:{height}:"


def _signature_pointer_key(digest: str) -> str:
    return f"{_SIGNATURE_POINTER_PREFIX}:{digest}"


def _build_signature_entry(record: ArtifactCacheRecord) -> tuple[str | None, str | None]:
    if (
        record.artifact_kind != "image"
        or record.job_ref_ts is None
        or record.phash is None
        or record.width is None
        or record.height is None
        or record.kind is None
    ):
        return None, None
    key = (
        f"{_SIGNATURE_INDEX_PREFIX}:{record.kind}:{int(record.width)}:{int(record.height)}:"
        f"{record.digest}"
    )
    payload = json.dumps(
        {
            "digest": record.digest,
            "phash": int(record.phash),
            "width": int(record.width),
            "height": int(record.height),
            "kind": record.kind,
        }
    )
    return key, payload
