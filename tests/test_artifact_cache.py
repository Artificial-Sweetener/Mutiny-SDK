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

"""Behavior tests for the unified artifact cache."""

from __future__ import annotations

import json
import time

import pytest

from mutiny.domain.job import TileFollowUpMode
from mutiny.services.cache.artifact_cache import (
    ArtifactCachePersistenceError,
    ArtifactCacheRecord,
    ArtifactCacheService,
)


class _FakeDisk:
    """In-memory stand-in for PersistentKV used by cache tests."""

    def __init__(self) -> None:
        self.values: dict[tuple[str, str], str] = {}

    def put(self, namespace: str, key: str, value: str) -> None:
        self.values[(namespace, key)] = value

    def get(self, namespace: str, key: str) -> str | None:
        return self.values.get((namespace, key))

    def delete(self, namespace: str, key: str) -> None:
        self.values.pop((namespace, key), None)

    def scan(self, namespace: str, key_prefix: str = "") -> list[tuple[str, str]]:
        rows: list[tuple[str, str]] = []
        for (stored_namespace, stored_key), value in self.values.items():
            if stored_namespace != namespace:
                continue
            if key_prefix and not stored_key.startswith(key_prefix):
                continue
            rows.append((stored_key, value))
        rows.sort(key=lambda item: item[0])
        return rows

    def apply_batch(
        self,
        namespace: str,
        *,
        puts: dict[str, str] | None = None,
        deletes: list[str] | None = None,
    ) -> None:
        for key in deletes or []:
            self.delete(namespace, key)
        for key, value in (puts or {}).items():
            self.put(namespace, key, value)


def _configured_cache(*, disk: _FakeDisk | None = None, ram_max_bytes: int = 32 * 1024 * 1024):
    cache = ArtifactCacheService(ram_max_bytes=ram_max_bytes)
    cache.apply_config(
        image_cache_ttl_seconds=cache.image_cache_ttl_seconds,
        image_cache_max_entries=cache.image_cache_max_entries,
        job_index_ttl_seconds=cache.job_index_ttl_seconds,
        job_index_max_entries=cache.job_index_max_entries,
        ram_max_bytes=ram_max_bytes,
        disk=disk,
    )
    return cache


def test_record_round_trip_preserves_upload_and_job_ref_fields() -> None:
    """Serialize and deserialize one merged artifact record without data loss."""

    record = ArtifactCacheRecord(
        artifact_kind="image",
        digest="digest-1",
        ts=123.0,
        source_url="https://cdn.example/image.png",
        source_url_ts=122.0,
        message_id="message-1",
        message_hash="hash-1",
        flags=64,
        index=2,
        job_ref_ts=121.0,
        signature_version=3,
        prompt_text="castle at sunrise --ar 1:1",
        tile_follow_up_mode=TileFollowUpMode.MODERN.value,
        action_custom_ids={"upscale_subtle": "cid-subtle"},
        phash=99,
        width=1024,
        height=768,
        kind="tile",
    )

    restored = ArtifactCacheRecord.from_json(record.to_json())

    assert restored == record


def test_ram_eviction_keeps_disk_backed_image_uploads_available() -> None:
    """Evicting RAM should not lose persisted upload URLs."""

    disk = _FakeDisk()
    cache = _configured_cache(disk=disk, ram_max_bytes=256)

    cache.put_image_upload("digest-a", "https://cdn.example/a.png")
    cache.put_image_upload("digest-b", "https://cdn.example/b.png")

    assert cache._ram_bytes <= 256
    assert cache.get_image_upload_url("digest-a") == "https://cdn.example/a.png"
    assert cache.get_image_upload_url("digest-b") == "https://cdn.example/b.png"
    assert ("artifact_cache", "image:digest-a") in disk.values
    assert ("artifact_cache", "image:digest-b") in disk.values


def test_ram_eviction_keeps_disk_backed_job_refs_available() -> None:
    """Evicting RAM should not lose persisted image and video job refs."""

    disk = _FakeDisk()
    cache = _configured_cache(disk=disk, ram_max_bytes=384)

    cache.put_image_job_ref(
        "image-digest",
        message_id="image-message",
        message_hash="image-hash",
        flags=64,
        index=3,
        prompt_text="castle at sunrise",
        tile_follow_up_mode=TileFollowUpMode.LEGACY,
        action_custom_ids={"upscale_subtle": "cid-subtle"},
        phash=123,
        width=512,
        height=512,
        kind="tile",
    )
    cache.put_video_job_ref(
        "video-digest",
        message_id="video-message",
        message_hash="video-hash",
        flags=0,
        signature_version=1,
        prompt_text="idle animation --motion low",
        action_custom_ids={"animate_extend_low": "cid-extend-low"},
    )

    assert cache._ram_bytes <= 384
    image_ref = cache.get_image_job_ref("image-digest")
    video_ref = cache.find_video_by_digest("video-digest")

    assert image_ref is not None
    assert image_ref.message_id == "image-message"
    assert image_ref.kind == "tile"
    assert image_ref.prompt_text == "castle at sunrise"
    assert image_ref.tile_follow_up_mode is TileFollowUpMode.LEGACY
    assert image_ref.action_custom_ids == {"upscale_subtle": "cid-subtle"}
    assert video_ref is not None
    assert video_ref.message_id == "video-message"
    assert video_ref.kind == "video"
    assert video_ref.prompt_text == "idle animation --motion low"
    assert video_ref.action_custom_ids == {"animate_extend_low": "cid-extend-low"}


def test_one_record_can_hold_both_upload_url_and_image_job_ref() -> None:
    """Image upload URLs and recognized refs should merge into one persisted record."""

    disk = _FakeDisk()
    cache = _configured_cache(disk=disk)

    cache.put_image_upload("digest-merge", "https://cdn.example/merged.png")
    cache.put_image_job_ref(
        "digest-merge",
        message_id="message-merge",
        message_hash="hash-merge",
        flags=64,
        index=1,
        prompt_text="merged prompt",
        tile_follow_up_mode=TileFollowUpMode.MODERN,
        action_custom_ids={"upscale_creative": "cid-creative"},
        phash=77,
        width=256,
        height=256,
        kind="upscale",
    )

    payload = disk.values[("artifact_cache", "image:digest-merge")]
    stored = json.loads(payload)

    assert stored["source_url"] == "https://cdn.example/merged.png"
    assert stored["message_id"] == "message-merge"
    assert stored["prompt_text"] == "merged prompt"
    assert stored["action_custom_ids"] == {"upscale_creative": "cid-creative"}
    assert cache.get_image_upload_url("digest-merge") == "https://cdn.example/merged.png"
    assert cache.get_image_job_ref("digest-merge") is not None


def test_exact_disk_hydration_reads_unified_records_lazily() -> None:
    """Cache misses should hydrate unified records from disk on demand."""

    disk = _FakeDisk()
    payload = ArtifactCacheRecord(
        artifact_kind="video",
        digest="video-digest",
        ts=time.time(),
        message_id="video-message",
        message_hash="video-hash",
        flags=0,
        index=1,
        job_ref_ts=time.time(),
        signature_version=1,
        prompt_text="idle animation --motion low",
        action_custom_ids={"animate_extend_low": "cid-extend-low"},
        kind="video",
    ).to_json()
    disk.put("artifact_cache", "video:video-digest", payload)

    cache = _configured_cache(disk=disk)

    assert cache.find_video_by_digest("video-digest") is not None
    assert cache.find_video_context_by_digest("video-digest") is not None
    assert "video:video-digest" in cache._records


def test_image_context_lookup_returns_persisted_actionable_fields() -> None:
    """Image context lookup should surface restart-safe action metadata."""

    cache = _configured_cache()
    cache.put_image_job_ref(
        "digest-image",
        message_id="message-image",
        message_hash="hash-image",
        flags=64,
        index=4,
        prompt_text="castle at sunrise",
        tile_follow_up_mode=TileFollowUpMode.MODERN,
        action_custom_ids={"upscale_subtle": "cid-subtle"},
        kind="tile",
    )

    context = cache.find_image_context_by_signature(
        digest="digest-image",
        expected_kind="tile",
    )

    assert context is not None
    assert context.message_id == "message-image"
    assert context.index == 4
    assert context.prompt_text == "castle at sunrise"
    assert context.tile_follow_up_mode is TileFollowUpMode.MODERN
    assert context.action_custom_ids == {"upscale_subtle": "cid-subtle"}


def test_fuzzy_lookup_survives_cold_start_via_disk_signature_index() -> None:
    """Restart-safe fuzzy lookup should hydrate from the persisted signature index."""

    disk = _FakeDisk()
    writer = _configured_cache(disk=disk)
    writer.put_image_job_ref(
        "digest-fuzzy",
        message_id="message-fuzzy",
        message_hash="hash-fuzzy",
        flags=64,
        index=2,
        prompt_text="castle at sunrise",
        tile_follow_up_mode=TileFollowUpMode.MODERN,
        action_custom_ids={"upscale_subtle": "cid-subtle"},
        phash=0b101010,
        width=256,
        height=256,
        kind="tile",
    )

    reader = _configured_cache(disk=disk)
    ref = reader.find_image_by_signature(
        digest=None,
        phash=0b101011,
        expected_kind="tile",
        width=256,
        height=256,
    )

    assert ref is not None
    assert ref.message_id == "message-fuzzy"
    assert ref.message_hash == "hash-fuzzy"
    assert ref.index == 2


def test_restart_ignores_expired_job_refs_after_disk_hydration() -> None:
    """Expired persisted refs should be cleaned from disk instead of resurrecting after restart."""

    disk = _FakeDisk()
    cache = _configured_cache(disk=disk)
    cache.put_image_job_ref(
        "digest-expired",
        message_id="message-expired",
        message_hash="hash-expired",
        flags=64,
        index=1,
        prompt_text="prompt",
        tile_follow_up_mode=TileFollowUpMode.MODERN,
        action_custom_ids={},
        phash=42,
        width=128,
        height=128,
        kind="tile",
    )
    payload = json.loads(disk.values[("artifact_cache", "image:digest-expired")])
    payload["job_ref_ts"] = time.time() - (cache.job_index_ttl_seconds + 10)
    disk.values[("artifact_cache", "image:digest-expired")] = json.dumps(payload)

    restarted = _configured_cache(disk=disk)

    assert restarted.get_image_job_ref("digest-expired") is None
    assert ("artifact_cache", "image:digest-expired") not in disk.values


def test_durable_job_ref_write_failures_raise_instead_of_falling_back_to_ram() -> None:
    """Restart-critical job refs should fail loudly when durable persistence breaks."""

    class _FailingDisk(_FakeDisk):
        def apply_batch(self, namespace: str, *, puts=None, deletes=None) -> None:  # type: ignore[override]
            raise RuntimeError("disk offline")

    cache = _configured_cache(disk=_FailingDisk())

    with pytest.raises(ArtifactCachePersistenceError):
        cache.put_image_job_ref(
            "digest-fail",
            message_id="message-fail",
            message_hash="hash-fail",
            flags=64,
            index=1,
            prompt_text="prompt",
            tile_follow_up_mode=TileFollowUpMode.MODERN,
            action_custom_ids={},
            phash=7,
            width=64,
            height=64,
            kind="tile",
        )

    assert cache.get_image_job_ref("digest-fail") is None


def test_legacy_image_job_ref_without_restart_safe_metadata_is_degraded() -> None:
    """Legacy refs missing follow-up metadata should not be guessed into modern semantics."""

    disk = _FakeDisk()
    disk.put(
        "job_index",
        "legacy-digest",
        json.dumps(
            {
                "message_id": "legacy-message",
                "message_hash": "legacy-hash",
                "flags": 64,
                "index": 3,
                "ts": time.time(),
                "kind": "tile",
            }
        ),
    )

    cache = _configured_cache(disk=disk)

    assert cache.get_image_job_ref("legacy-digest") is None
