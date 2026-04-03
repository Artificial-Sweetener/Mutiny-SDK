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

import base64
import hashlib
import logging

import pytest

from mutiny.domain.job import Job, JobAction, JobStatus
from mutiny.engine.action_dispatcher import ActionContext, _exec_imagine
from mutiny.engine.runtime.artifact_prep import prepare_image_input
from mutiny.services.cache.artifact_cache import ArtifactCacheService
from mutiny.services.interaction_cache import InteractionCache


def _data_url(payload: bytes) -> str:
    encoded = base64.b64encode(payload).decode("ascii")
    return f"data:image/png;base64,{encoded}"


class _FakeProvider:
    def __init__(
        self,
        upload_result: str | None = None,
        cdn_result: str | None = None,
        imagine_result: str | None = None,
    ):
        self.upload_result = upload_result
        self.cdn_result = cdn_result
        self.imagine_result = imagine_result or "Success"
        self.upload_calls: list[tuple[str, bytes, str]] = []
        self.send_calls: list[str] = []
        self.imagine_calls: list[tuple[str, str]] = []

    async def upload(self, filename: str, data: bytes, mime: str):  # type: ignore[no-untyped-def]
        self.upload_calls.append((filename, data, mime))
        return self.upload_result or f"uploads/{filename}"

    async def send_image_message(self, _: str, uploaded_name: str):  # type: ignore[no-untyped-def]
        self.send_calls.append(uploaded_name)
        return self.cdn_result

    async def imagine(self, prompt: str, nonce: str):  # type: ignore[no-untyped-def]
        self.imagine_calls.append((prompt, nonce))
        return self.imagine_result


@pytest.mark.asyncio
async def test_prepare_image_input_uses_cache_without_upload():
    payload = b"A"
    data_url = _data_url(payload)
    digest = hashlib.sha256(payload).hexdigest()
    cache = ArtifactCacheService()
    cached_url = "https://cdn.example/hit.png"
    cache.put_image_upload(digest, cached_url)
    provider = _FakeProvider()
    ctx = ActionContext(
        commands=provider,
        artifact_cache=cache,
        interaction_cache=InteractionCache(),
        channel_id="c",
    )
    job = Job(id="j1", action=JobAction.IMAGINE)

    res = await prepare_image_input(
        ctx,
        job,
        data_url,
        index_label="index 0",
        filename_factory=lambda ext: f"{job.id}{ext}",
        use_cache=True,
        fetch_cdn=True,
        cdn_required=True,
    )

    assert res.cache_hit is True
    assert res.cdn_url == cached_url
    assert res.error is None
    assert not provider.upload_calls
    assert not provider.send_calls


@pytest.mark.asyncio
async def test_prepare_image_input_cdn_required_failure_sets_job_fail_reason():
    payload = b"B"
    data_url = _data_url(payload)
    cache = ArtifactCacheService()
    provider = _FakeProvider(cdn_result=None)
    ctx = ActionContext(
        commands=provider,
        artifact_cache=cache,
        interaction_cache=InteractionCache(),
        channel_id="c",
    )
    job = Job(id="j2", action=JobAction.IMAGINE)

    res = await prepare_image_input(
        ctx,
        job,
        data_url,
        index_label="index 0",
        filename_factory=lambda ext: f"{job.id}{ext}",
        use_cache=True,
        fetch_cdn=True,
        cdn_required=True,
    )

    assert res.error == "Failed to get CDN URL for file at index 0"
    assert job.status is JobStatus.FAILED
    assert job.fail_reason == "Failed to get CDN URL for file at index 0"
    assert provider.upload_calls
    assert provider.send_calls


@pytest.mark.asyncio
async def test_prepare_image_input_caches_cdn_url_on_success():
    payload = b"C"
    data_url = _data_url(payload)
    digest = hashlib.sha256(payload).hexdigest()
    cache = ArtifactCacheService()
    cdn_url = "https://cdn.example/new.png"
    provider = _FakeProvider(cdn_result=cdn_url)
    ctx = ActionContext(
        commands=provider,
        artifact_cache=cache,
        interaction_cache=InteractionCache(),
        channel_id="c",
    )
    job = Job(id="j3", action=JobAction.IMAGINE)

    res = await prepare_image_input(
        ctx,
        job,
        data_url,
        index_label="index 0",
        filename_factory=lambda ext: f"{job.id}{ext}",
        use_cache=True,
        fetch_cdn=True,
        cdn_required=True,
    )

    assert res.error is None
    assert res.cdn_url == cdn_url
    assert res.uploaded_name is not None
    assert cache.get_image_upload_url(digest) == cdn_url
    assert provider.upload_calls
    assert provider.send_calls


@pytest.mark.asyncio
async def test_exec_imagine_logs_and_fails_on_prepare_error(caplog):
    caplog.set_level(logging.WARNING, logger="mutiny.engine.action_dispatcher")
    cache = ArtifactCacheService()
    provider = _FakeProvider()
    ctx = ActionContext(
        commands=provider,
        artifact_cache=cache,
        interaction_cache=InteractionCache(),
        channel_id="c",
    )
    job = Job(id="j4", action=JobAction.IMAGINE)
    job.inputs.base64_array = ["not-a-data-url"]

    res = await _exec_imagine(ctx, job, "n1")

    assert res is None
    assert job.status is JobStatus.FAILED
    assert job.fail_reason == "Invalid Base64 Data URL at index 0"
    assert not provider.upload_calls
    assert not provider.send_calls
    assert not provider.imagine_calls

    records = [r for r in caplog.records if r.message == "Imagine image preparation failed"]
    assert records, "expected imagine failure warning to be logged"
    record = records[0]
    assert record.job_id == "j4"
    assert record.job_action == JobAction.IMAGINE
    assert record.index == 0
    assert record.reason == "Invalid Base64 Data URL at index 0"


@pytest.mark.asyncio
async def test_exec_imagine_appends_style_character_and_omni_reference_urls():
    provider = _FakeProvider(cdn_result="https://cdn.example/shared.png")
    ctx = ActionContext(
        commands=provider,
        artifact_cache=ArtifactCacheService(),
        interaction_cache=InteractionCache(),
        channel_id="c",
    )
    job = Job(
        id="j5",
        action=JobAction.IMAGINE,
        prompt="editorial portrait --sw 300 --cw 80 --ow 250",
    )
    job.inputs.base64_array = [_data_url(b"A")]
    job.inputs.style_reference_images = [_data_url(b"B"), _data_url(b"C")]
    job.inputs.style_reference_multipliers = [2.0, 1.0]
    job.inputs.character_reference_images = [_data_url(b"D")]
    job.inputs.omni_reference_image = _data_url(b"E")

    result = await _exec_imagine(ctx, job, "n5")

    assert result == "Success"
    assert provider.imagine_calls == [
        (
            "https://cdn.example/shared.png editorial portrait --sw 300 --cw 80 --ow 250 "
            "--sref https://cdn.example/shared.png::2 https://cdn.example/shared.png::1 "
            "--cref https://cdn.example/shared.png --oref https://cdn.example/shared.png",
            "n5",
        )
    ]
    assert job.context.final_prompt == provider.imagine_calls[0][0]
