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

import asyncio
from typing import Any, List

import pytest

from mutiny.discord.identity import DiscordIdentity
from mutiny.domain.job import Job, JobAction, JobStatus
from mutiny.domain.state_machine import JobStateMachine, JobTransition
from mutiny.engine.discord_engine import DiscordEngine
from mutiny.engine.execution_policy import EnginePolicy
from mutiny.services.cache.artifact_cache import ArtifactCacheService
from mutiny.services.image_processor import OpenCVImageProcessor
from mutiny.services.interaction_cache import InteractionCache
from mutiny.services.job_store import InMemoryJobStoreService
from mutiny.services.metrics.service import MetricsService
from mutiny.services.notify.event_bus import JobUpdateBus
from mutiny.services.response_dump import ResponseDumpService
from mutiny.services.video_signature import VideoSignatureService


class FakeNotifyBus(JobUpdateBus):
    def __init__(self) -> None:
        self.events: List[Job] = []
        self.progress_events = []

    def publish_job(self, job: Job):
        self.events.append(job)

    def publish_progress(self, event):  # pragma: no cover - not used
        self.progress_events.append(event)

    def subscribe(self, job_id: str):  # pragma: no cover - not used
        raise NotImplementedError

    def subscribe_progress(self, job_id: str):  # pragma: no cover - not used
        raise NotImplementedError

    async def close(self) -> None:
        return None


class FakeProvider:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

    async def start(self) -> None:
        return None

    async def close(self) -> None:
        return None

    def is_ready(self) -> bool:
        return True

    async def imagine(self, final_prompt: str, nonce: str):
        self.calls.append(("imagine", (final_prompt, nonce), {}))
        return "Success"

    async def upload(self, filename: str, file_content: bytes, mime_type: str):
        self.calls.append(("upload", (filename, len(file_content), mime_type), {}))
        # simulate Discord returning an uploaded filename token
        return f"https://uploads.example/{filename}"

    async def send_image_message(self, text: str, uploaded_filename: str):
        self.calls.append(("send_image_message", (text, uploaded_filename), {}))
        # return a CDN URL that instance.worker concatenates
        return f"https://cdn.example/{uploaded_filename.split('/')[-1]}"

    async def upscale(self, message_id: str, index: int, message_hash: str, flags: int, nonce: str):
        self.calls.append(("upscale", (message_id, index, message_hash, flags, nonce), {}))
        return "Success"

    async def variation(
        self, message_id: str, index: int, message_hash: str, flags: int, nonce: str
    ):
        self.calls.append(("variation", (message_id, index, message_hash, flags, nonce), {}))
        return "Success"

    async def reroll(self, message_id: str, message_hash: str, flags: int, nonce: str):
        self.calls.append(("reroll", (message_id, message_hash, flags, nonce), {}))
        return "Success"

    async def describe(self, uploaded_filename: str, nonce: str):
        self.calls.append(("describe", (uploaded_filename, nonce), {}))
        return "Success"

    async def blend(self, uploaded_filenames: list[str], dimensions: str, nonce: str):
        self.calls.append(("blend", (tuple(uploaded_filenames), dimensions, nonce), {}))
        return "Success"

    async def cancel_job(self, message_id: str, job_id: str, message_flags: int, nonce: str):
        self.calls.append(("cancel_job", (message_id, job_id, message_flags, nonce), {}))
        return "Success"

    async def fetch_cdn_bytes(self, url: str) -> bytes | None:
        return None


class FakeTransport:
    def __init__(self, commands: FakeProvider) -> None:
        self.commands = commands

    async def start(self) -> None:
        return None

    async def close(self) -> None:
        return None

    def is_ready(self) -> bool:
        return True


class _TokenProvider:
    def get_token(self) -> str:
        return "t"


def make_instance(
    fake_provider: FakeProvider,
    config,
) -> tuple[DiscordEngine, InMemoryJobStoreService, FakeNotifyBus]:
    store = InMemoryJobStoreService()
    notify = FakeNotifyBus()
    identity = DiscordIdentity(guild_id="g", channel_id="c", token_provider=_TokenProvider())
    policy = EnginePolicy(config.engine.execution)
    inst = DiscordEngine(
        identity=identity,
        job_store=store,
        notify_bus=notify,
        config=config,
        policy=policy,
        artifact_cache=ArtifactCacheService(),
        video_signature_service=VideoSignatureService(),
        image_processor=OpenCVImageProcessor(),
        interaction_cache=InteractionCache(),
        response_dump=ResponseDumpService(enabled=False),
        metrics=MetricsService(),
    )
    inst.provider = FakeTransport(fake_provider)
    inst.commands = fake_provider
    return inst, store, notify


async def run_and_complete(
    inst: DiscordEngine, job: Job, store: InMemoryJobStoreService, notify: FakeNotifyBus
):
    # start worker
    worker = asyncio.create_task(inst.worker())
    try:
        JobStateMachine.apply(job, JobTransition.SUBMIT)
        assert await inst.submit_job(job)

        # Wait until the service call happens, then simulate handler completion
        # by marking the task as success and saving it.
        async def finisher():
            # Poll until the task is marked in_progress by the worker
            for _ in range(100):
                if job.status == JobStatus.IN_PROGRESS:
                    break
                await asyncio.sleep(0.01)
            JobStateMachine.apply(job, JobTransition.SUCCEED)
            inst.save_and_notify(job)

        await asyncio.wait_for(finisher(), timeout=2)

        # Wait until worker processes it and removes from active set
        for _ in range(200):
            if not inst.job_lookup.find_running_by_condition(lambda j: j.id == job.id):
                break
            await asyncio.sleep(0.01)
        # Ensure saved status
        saved = store.get(job.id)
        assert saved is not None and saved.status == JobStatus.SUCCEEDED
        return saved
    finally:
        await inst.shutdown()
        worker.cancel()
        with pytest.raises(asyncio.CancelledError):
            await worker


@pytest.mark.asyncio
async def test_imagine_simple(test_config):
    provider = FakeProvider()
    inst, store, notify = make_instance(provider, test_config)
    t = Job(id="t1", action=JobAction.IMAGINE, prompt="hello world")
    saved = await run_and_complete(inst, t, store, notify)
    assert saved.status == JobStatus.SUCCEEDED
    # Verify service call
    calls = [c for c in provider.calls if c[0] == "imagine"]
    assert calls and "hello world" in calls[0][1][0]


@pytest.mark.asyncio
async def test_upscale_variation_reroll(test_config):
    provider = FakeProvider()
    inst, store, notify = make_instance(provider, test_config)

    base_props = {"message_id": "mid", "message_hash": "abc123", "flags": 0, "index": 2}
    t_up = Job(id="u1", action=JobAction.UPSCALE)
    t_up.context.message_id = base_props["message_id"]
    t_up.context.message_hash = base_props["message_hash"]
    t_up.context.flags = base_props["flags"]
    t_up.context.index = base_props["index"]
    await run_and_complete(inst, t_up, store, notify)

    t_var = Job(id="v1", action=JobAction.VARIATION)
    t_var.context.message_id = base_props["message_id"]
    t_var.context.message_hash = base_props["message_hash"]
    t_var.context.flags = base_props["flags"]
    t_var.context.index = base_props["index"]
    await run_and_complete(inst, t_var, store, notify)

    t_re = Job(id="r1", action=JobAction.REROLL)
    t_re.context.message_id = base_props["message_id"]
    t_re.context.message_hash = base_props["message_hash"]
    t_re.context.flags = base_props["flags"]
    await run_and_complete(inst, t_re, store, notify)

    kinds = [c[0] for c in provider.calls]
    # Ensure each pathway was exercised
    assert "upscale" in kinds and "variation" in kinds and "reroll" in kinds


@pytest.mark.asyncio
async def test_describe_and_blend(test_config):
    provider = FakeProvider()
    inst, store, notify = make_instance(provider, test_config)

    # describe with a valid data URL
    data_url = "data:image/png;base64,aGVsbG8="
    t_desc = Job(id="d1", action=JobAction.DESCRIBE)
    t_desc.inputs.base64 = data_url
    await run_and_complete(inst, t_desc, store, notify)

    # blend with two images
    imgs = [
        "data:image/png;base64,aGVsbG8=",
        "data:image/png;base64,aGVsbG8=",
    ]
    t_blend = Job(id="b1", action=JobAction.BLEND)
    t_blend.inputs.base64_array = imgs
    t_blend.inputs.dimensions = "1:1"
    await run_and_complete(inst, t_blend, store, notify)

    kinds = [c[0] for c in provider.calls]
    assert "describe" in kinds
    assert "blend" in kinds
    # uploads should be called for describe (1) + blend (2) = 3 times
    assert len([k for k in kinds if k == "upload"]) == 3
