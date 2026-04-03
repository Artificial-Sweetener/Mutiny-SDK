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

import json
import time

import cv2

from mutiny.services.cache.artifact_cache import ArtifactCacheService
from mutiny.services.image_processor import OpenCVImageProcessor, decode_rgb


def _make_tile(color=(200, 50, 50), size=(128, 128)) -> bytes:
    width, height = size
    import numpy as np

    rgb = np.zeros((height, width, 3), dtype=np.uint8)
    rgb[:, :] = color
    ok, buffer = cv2.imencode(".png", cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
    assert ok
    return buffer.tobytes()


class _FakeDisk:
    def __init__(self):
        self.values = {}

    def put(self, ns: str, key: str, value: str):  # pragma: no cover - simple store
        self.values[(ns, key)] = value

    def get(self, ns: str, key: str) -> str | None:
        return self.values.get((ns, key))

    def delete(self, ns: str, key: str) -> None:
        self.values.pop((ns, key), None)

    def scan(self, ns: str, key_prefix: str = "") -> list[tuple[str, str]]:
        rows = []
        for (stored_ns, stored_key), value in self.values.items():
            if stored_ns != ns:
                continue
            if key_prefix and not stored_key.startswith(key_prefix):
                continue
            rows.append((stored_key, value))
        rows.sort(key=lambda item: item[0])
        return rows

    def apply_batch(self, ns: str, *, puts=None, deletes=None) -> None:
        for key in deletes or []:
            self.delete(ns, key)
        for key, value in (puts or {}).items():
            self.put(ns, key, value)


def test_job_index_exact_and_phash_fallback():
    svc = ArtifactCacheService()
    processor = OpenCVImageProcessor()
    png_bytes = _make_tile()

    digest = processor.compute_digest(png_bytes)
    phash = processor.compute_phash(png_bytes)
    svc.put_image_job_ref(
        digest,
        message_id="m1",
        message_hash="h1",
        flags=0,
        index=1,
        phash=phash,
        width=128,
        height=128,
        kind="tile",
    )

    exact = svc.find_image_by_signature(digest=digest, phash=phash, expected_kind="tile")
    assert exact is not None and exact.message_id == "m1"

    ok, jpeg = cv2.imencode(".jpg", cv2.cvtColor(decode_rgb(png_bytes), cv2.COLOR_RGB2BGR))
    assert ok
    near_phash = processor.compute_phash(jpeg.tobytes())
    near = svc.find_image_by_signature(
        digest=None,
        phash=near_phash,
        expected_kind="tile",
        width=128,
        height=128,
    )
    assert near is not None and near.message_id == "m1"


def test_job_index_hydrates_phash_from_disk():
    svc = ArtifactCacheService()
    disk = _FakeDisk()
    svc.apply_config(
        image_cache_ttl_seconds=svc.image_cache_ttl_seconds,
        image_cache_max_entries=svc.image_cache_max_entries,
        job_index_ttl_seconds=svc.job_index_ttl_seconds,
        job_index_max_entries=svc.job_index_max_entries,
        ram_max_bytes=svc.ram_max_bytes,
        disk=disk,
    )

    entry = {
        "artifact_kind": "image",
        "digest": "digest9",
        "job_ref_ts": time.time(),
        "message_id": "m9",
        "message_hash": "h9",
        "flags": 0,
        "index": 1,
        "ts": time.time(),
        "phash": "a400000000000000",
        "width": 64,
        "height": 64,
        "kind": "tile",
    }
    disk.put("artifact_cache", "image:digest9", json.dumps(entry))

    ref = svc.get_image_job_ref("digest9")
    assert ref is not None
    assert ref.message_id == "m9"
    assert ref.phash == int(entry["phash"], 16)


def test_job_index_fuzzy_lookup_uses_disk_signature_index_after_restart():
    svc = ArtifactCacheService()
    disk = _FakeDisk()
    processor = OpenCVImageProcessor()
    svc.apply_config(
        image_cache_ttl_seconds=svc.image_cache_ttl_seconds,
        image_cache_max_entries=svc.image_cache_max_entries,
        job_index_ttl_seconds=svc.job_index_ttl_seconds,
        job_index_max_entries=svc.job_index_max_entries,
        ram_max_bytes=svc.ram_max_bytes,
        disk=disk,
    )
    png_bytes = _make_tile()
    digest = processor.compute_digest(png_bytes)
    phash = processor.compute_phash(png_bytes)
    svc.put_image_job_ref(
        digest,
        message_id="m10",
        message_hash="h10",
        flags=0,
        index=2,
        phash=phash,
        width=128,
        height=128,
        kind="tile",
    )

    restarted = ArtifactCacheService()
    restarted.apply_config(
        image_cache_ttl_seconds=restarted.image_cache_ttl_seconds,
        image_cache_max_entries=restarted.image_cache_max_entries,
        job_index_ttl_seconds=restarted.job_index_ttl_seconds,
        job_index_max_entries=restarted.job_index_max_entries,
        ram_max_bytes=restarted.ram_max_bytes,
        disk=disk,
    )
    ok, jpeg = cv2.imencode(".jpg", cv2.cvtColor(decode_rgb(png_bytes), cv2.COLOR_RGB2BGR))
    assert ok
    near_phash = processor.compute_phash(jpeg.tobytes())

    ref = restarted.find_image_by_signature(
        digest=None,
        phash=near_phash,
        expected_kind="tile",
        width=128,
        height=128,
    )

    assert ref is not None
    assert ref.message_id == "m10"


def test_job_index_hydrates_video_ref_from_disk():
    svc = ArtifactCacheService()
    disk = _FakeDisk()
    svc.apply_config(
        image_cache_ttl_seconds=svc.image_cache_ttl_seconds,
        image_cache_max_entries=svc.image_cache_max_entries,
        job_index_ttl_seconds=svc.job_index_ttl_seconds,
        job_index_max_entries=svc.job_index_max_entries,
        ram_max_bytes=svc.ram_max_bytes,
        disk=disk,
    )

    entry = {
        "artifact_kind": "video",
        "digest": "video-digest",
        "job_ref_ts": time.time(),
        "message_id": "video-message",
        "message_hash": "video-hash",
        "flags": 64,
        "index": 1,
        "ts": time.time(),
        "kind": "video",
        "signature_version": 1,
    }
    disk.put("artifact_cache", "video:video-digest", json.dumps(entry))

    ref = svc.find_video_by_digest("video-digest")

    assert ref is not None
    assert ref.message_id == "video-message"
    assert ref.message_hash == "video-hash"
    assert ref.kind == "video"
    assert ref.signature_version == 1
