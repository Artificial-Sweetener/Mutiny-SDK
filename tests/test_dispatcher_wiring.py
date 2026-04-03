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

import logging
from typing import cast

import pytest

from mutiny.domain.job import Job, JobAction
from mutiny.engine.action_dispatcher import ActionContext, execute_action
from mutiny.services.cache.artifact_cache import ArtifactCacheService
from mutiny.services.interaction_cache import InteractionCache


class DummyProvider:
    def __init__(self):
        self.calls: list[tuple[str, tuple]] = []

    async def send_button_interaction(self, *args):  # type: ignore[no-redef]
        self.calls.append(("send_button_interaction", args))
        return "Success"

    async def imagine(self, *args):  # type: ignore[no-redef]
        self.calls.append(("imagine", args))
        return "Success"

    async def upload(self, *args):  # type: ignore[no-redef]
        self.calls.append(("upload", args))
        return "uploaded-file.png"

    async def send_image_message(self, *args):  # type: ignore[no-redef]
        self.calls.append(("send_image_message", args))
        filename = args[1]
        return f"https://cdn.example/{filename}"

    async def upscale(self, *args):  # type: ignore[no-redef]
        self.calls.append(("upscale", args))
        return "Success"

    async def vary_subtle(self, *args):  # type: ignore[no-redef]
        self.calls.append(("vary_subtle", args))
        return "Success"

    async def vary_strong(self, *args):  # type: ignore[no-redef]
        self.calls.append(("vary_strong", args))
        return "Success"

    async def upscale_v7_subtle(self, *args):  # type: ignore[no-redef]
        self.calls.append(("upscale_v7_subtle", args))
        return "Success"

    async def upscale_v7_creative(self, *args):  # type: ignore[no-redef]
        self.calls.append(("upscale_v7_creative", args))
        return "Success"

    async def outpaint_50(self, *args):  # type: ignore[no-redef]
        self.calls.append(("outpaint_50", args))
        return "Success"

    async def outpaint_75(self, *args):  # type: ignore[no-redef]
        self.calls.append(("outpaint_75", args))
        return "Success"

    async def pan_left(self, *args):  # type: ignore[no-redef]
        self.calls.append(("pan_left", args))
        return "Success"

    async def pan_right(self, *args):  # type: ignore[no-redef]
        self.calls.append(("pan_right", args))
        return "Success"

    async def pan_up(self, *args):  # type: ignore[no-redef]
        self.calls.append(("pan_up", args))
        return "Success"

    async def pan_down(self, *args):  # type: ignore[no-redef]
        self.calls.append(("pan_down", args))
        return "Success"

    async def animate_high(self, *args):  # type: ignore[no-redef]
        self.calls.append(("animate_high", args))
        return "Success"

    async def animate_low(self, *args):  # type: ignore[no-redef]
        self.calls.append(("animate_low", args))
        return "Success"

    async def animate_extend_high(self, *args):  # type: ignore[no-redef]
        self.calls.append(("animate_extend_high", args))
        return "Success"

    async def animate_extend_low(self, *args):  # type: ignore[no-redef]
        self.calls.append(("animate_extend_low", args))
        return "Success"

    async def custom_zoom(self, *args):  # type: ignore[no-redef]
        self.calls.append(("custom_zoom", args))
        return "Success"

    async def inpaint_button(self, *args):  # type: ignore[no-redef]
        self.calls.append(("inpaint_button", args))
        return "Success"

    async def inpaint_submit_job(self, *args, **kwargs):  # type: ignore[no-redef]
        self.calls.append(("inpaint_submit_job", args))
        return "Success"


class DummyInstance:
    def __init__(self):
        self.provider = DummyProvider()
        self.commands = self.provider
        self.interaction_cache = InteractionCache()
        self.artifact_cache = ArtifactCacheService()
        self.channel_id = "c"


class _FailingInteractionCache(InteractionCache):
    def get_message_components(self, *_: str):
        raise RuntimeError("boom")


def _job(action: JobAction, *, idx: int | None = 1) -> Job:
    job = Job(id="t1", action=action)
    job.context.message_id = "m"
    job.context.message_hash = "h"
    job.context.flags = 0
    if idx is not None:
        job.context.index = idx
    return job


@pytest.mark.asyncio
async def test_dispatcher_vary_subtle_calls_service():
    inst = DummyInstance()
    t = _job(JobAction.VARY_SUBTLE, idx=2)
    ctx = ActionContext(
        commands=inst.provider,
        artifact_cache=inst.artifact_cache,
        interaction_cache=inst.interaction_cache,
        channel_id=inst.channel_id,
    )
    res = await execute_action(ctx, t, nonce="n")
    assert res == "Success"
    assert any(name == "vary_subtle" for name, _ in inst.provider.calls)


@pytest.mark.asyncio
async def test_dispatcher_vary_strong_calls_service():
    inst = DummyInstance()
    t = _job(JobAction.VARY_STRONG, idx=3)
    ctx = ActionContext(
        commands=inst.provider,
        artifact_cache=inst.artifact_cache,
        interaction_cache=inst.interaction_cache,
        channel_id=inst.channel_id,
    )
    res = await execute_action(ctx, t, nonce="n")
    assert res == "Success"
    assert any(name == "vary_strong" for name, _ in inst.provider.calls)


@pytest.mark.asyncio
async def test_dispatcher_upscale_v7_subtle_uses_observed_component_when_available():
    inst = DummyInstance()
    t = _job(JobAction.UPSCALE_V7_2X_SUBTLE, idx=1)
    inst.interaction_cache.set_message_components(
        "m",
        {"MJ::JOB::upsample_v6_2x_subtle::1::h::SOLO"},
    )
    ctx = ActionContext(
        commands=inst.provider,
        artifact_cache=inst.artifact_cache,
        interaction_cache=inst.interaction_cache,
        channel_id=inst.channel_id,
    )
    res = await execute_action(ctx, t, nonce="n")
    assert res == "Success"
    assert inst.provider.calls == [
        (
            "send_button_interaction",
            ("m", "MJ::JOB::upsample_v6_2x_subtle::1::h::SOLO", 0, "n"),
        )
    ]


@pytest.mark.asyncio
async def test_dispatcher_upscale_v7_creative_falls_back_to_synthesized_service():
    inst = DummyInstance()
    t = _job(JobAction.UPSCALE_V7_2X_CREATIVE, idx=4)
    ctx = ActionContext(
        commands=inst.provider,
        artifact_cache=inst.artifact_cache,
        interaction_cache=inst.interaction_cache,
        channel_id=inst.channel_id,
    )
    res = await execute_action(ctx, t, nonce="n")
    assert res == "Success"
    assert any(name == "upscale_v7_creative" for name, _ in inst.provider.calls)


@pytest.mark.asyncio
async def test_dispatcher_zoom_out_and_pan_call_services():
    inst = DummyInstance()
    ctx = ActionContext(
        commands=inst.provider,
        artifact_cache=inst.artifact_cache,
        interaction_cache=inst.interaction_cache,
        channel_id=inst.channel_id,
    )
    for action, expected in [
        (JobAction.ZOOM_OUT_2X, "outpaint_50"),
        (JobAction.ZOOM_OUT_1_5X, "outpaint_75"),
        (JobAction.PAN_LEFT, "pan_left"),
        (JobAction.PAN_RIGHT, "pan_right"),
        (JobAction.PAN_UP, "pan_up"),
        (JobAction.PAN_DOWN, "pan_down"),
        (JobAction.ANIMATE_HIGH, "animate_high"),
        (JobAction.ANIMATE_LOW, "animate_low"),
        (JobAction.ANIMATE_EXTEND_HIGH, "animate_extend_high"),
        (JobAction.ANIMATE_EXTEND_LOW, "animate_extend_low"),
    ]:
        inst.provider.calls.clear()
        t = _job(action, idx=1)
        res = await execute_action(ctx, t, nonce="n")
        assert res == "Success"
        assert any(name == expected for name, _ in inst.provider.calls)


@pytest.mark.asyncio
async def test_dispatcher_routes_pending_tile_promotion_through_upscale():
    inst = DummyInstance()
    t = _job(JobAction.PAN_LEFT, idx=2)
    t.context.implicit_tile_promotion_pending = True
    t.context.implicit_tile_promotion_index = 2
    ctx = ActionContext(
        commands=inst.provider,
        artifact_cache=inst.artifact_cache,
        interaction_cache=inst.interaction_cache,
        channel_id=inst.channel_id,
    )

    res = await execute_action(ctx, t, nonce="n")

    assert res == "Success"
    assert inst.provider.calls == [("upscale", ("m", 2, "h", 0, "n"))]


@pytest.mark.asyncio
async def test_dispatcher_prompt_video_animate_uses_imagine_submission():
    inst = DummyInstance()
    t = Job(id="anim-prompt", action=JobAction.ANIMATE_HIGH)
    t.inputs.base64 = "data:image/png;base64,AA=="
    t.inputs.end_frame_base64 = "data:image/png;base64,BB=="
    t.inputs.prompt = "camera push through fog"
    t.inputs.batch_size = 2
    ctx = ActionContext(
        commands=inst.provider,
        artifact_cache=inst.artifact_cache,
        interaction_cache=inst.interaction_cache,
        channel_id=inst.channel_id,
    )

    res = await execute_action(ctx, t, nonce="n")

    assert res == "Success"
    names = [name for name, _args in inst.provider.calls]
    assert names == [
        "upload",
        "send_image_message",
        "upload",
        "send_image_message",
        "imagine",
    ]
    assert (
        t.context.final_prompt
        == "https://cdn.example/uploaded-file.png camera push through fog --video --motion high "
        "--end https://cdn.example/uploaded-file.png --bs 2"
    )


@pytest.mark.asyncio
async def test_dispatcher_missing_index_errors():
    inst = DummyInstance()
    t = _job(JobAction.VARY_SUBTLE, idx=None)
    ctx = ActionContext(
        commands=inst.provider,
        artifact_cache=inst.artifact_cache,
        interaction_cache=inst.interaction_cache,
        channel_id=inst.channel_id,
    )
    res = await execute_action(ctx, t, nonce="n")
    assert isinstance(res, str) and "index" in res


@pytest.mark.asyncio
async def test_dispatcher_custom_zoom_calls_service():
    inst = DummyInstance()
    t = Job(
        id="cz1",
        action=JobAction.CUSTOM_ZOOM,
    )
    t.context.message_id = "m"
    t.context.message_hash = "h"
    t.context.flags = 0
    t.context.zoom_text = "tight crop"
    ctx = ActionContext(
        commands=inst.provider,
        artifact_cache=inst.artifact_cache,
        interaction_cache=inst.interaction_cache,
        channel_id=inst.channel_id,
    )
    res = await execute_action(ctx, t, nonce="n")
    assert res == "Success"
    assert any(name == "custom_zoom" for name, _ in inst.provider.calls)


@pytest.mark.asyncio
async def test_dispatcher_logs_missing_executor(caplog):
    inst = DummyInstance()
    t = _job(JobAction.IMAGINE, idx=1)
    t.action = cast(JobAction, "UNREGISTERED")
    ctx = ActionContext(
        commands=inst.provider,
        artifact_cache=inst.artifact_cache,
        interaction_cache=inst.interaction_cache,
        channel_id=inst.channel_id,
    )
    with caplog.at_level(logging.WARNING):
        res = await execute_action(ctx, t, nonce="n")
    assert res == "No executor registered for action UNREGISTERED"
    assert any("No executor registered for action" in record.message for record in caplog.records)


@pytest.mark.asyncio
async def test_dispatcher_inpaint_calls_button_then_submit():
    inst = DummyInstance()
    t = Job(
        id="ip1",
        action=JobAction.INPAINT,
    )
    t.context.message_id = "upscaled-message"
    t.context.message_hash = "upscaled-hash"
    t.context.flags = 0
    t.context.index = 1
    t.context.custom_id = "CID"
    t.inputs.mask_webp_base64 = "UklGdummy"
    t.inputs.prompt = "p"
    t.inputs.full_prompt = None
    ctx = ActionContext(
        commands=inst.provider,
        artifact_cache=inst.artifact_cache,
        interaction_cache=inst.interaction_cache,
        channel_id=inst.channel_id,
    )
    res = await execute_action(ctx, t, nonce="n")
    assert res == "Success"
    names = [n for n, _ in inst.provider.calls]
    assert names[:2] == ["inpaint_button", "inpaint_submit_job"]
    assert inst.provider.calls[0] == (
        "inpaint_button",
        ("upscaled-message", 1, "upscaled-hash", 0, "n"),
    )


@pytest.mark.asyncio
async def test_dispatcher_inpaint_logs_component_polling_failure(caplog):
    inst = DummyInstance()
    inst.interaction_cache = _FailingInteractionCache()
    t = Job(
        id="ip2",
        action=JobAction.INPAINT,
    )
    t.context.message_id = "m"
    t.context.message_hash = "h"
    t.context.flags = 0
    t.context.index = 1
    t.context.custom_id = "CID"
    t.inputs.mask_webp_base64 = "UklGdummy"
    t.inputs.prompt = "p"
    t.inputs.full_prompt = None
    ctx = ActionContext(
        commands=inst.provider,
        artifact_cache=inst.artifact_cache,
        interaction_cache=inst.interaction_cache,
        channel_id=inst.channel_id,
    )
    with caplog.at_level(logging.WARNING):
        res = await execute_action(ctx, t, nonce="n")
    assert res == "Success"
    names = [n for n, _ in inst.provider.calls]
    assert names[:2] == ["inpaint_button", "inpaint_submit_job"]
    assert any("Inpaint component polling failed" in r.message for r in caplog.records)
