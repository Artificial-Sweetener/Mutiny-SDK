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
import base64
import os
import time

import cv2
import pytest
from dotenv import load_dotenv

from mutiny import JobStatus, Mutiny
from mutiny.domain.job import JobAction
from mutiny.types import (
    CharacterReferenceImages,
    ImagineImageInputs,
    OmniReferenceImage,
    StyleReferenceImages,
)
from tests.image_helpers import decode_rgb, make_mask_data_url, make_png_data_url
from tests.output_utils import save_task_output

_make_png_data_url = make_png_data_url


def _load_test_env() -> bool:
    # Load env from tests/.env to provide Discord credentials
    load_dotenv(dotenv_path=os.path.join(".env"), override=True)
    os.environ.setdefault("MUTINY_ENV", "development")
    return all(os.getenv(k) for k in ("MJ_USER_TOKEN", "MJ_GUILD_ID", "MJ_CHANNEL_ID"))


async def _wait_for_status_client(client: Mutiny, task_id: str, timeout_s: int = 600):
    deadline = time.time() + timeout_s
    last = None
    while time.time() < deadline:
        last = await client.get_job(task_id)
        if last.status in (JobStatus.SUCCEEDED, JobStatus.FAILED):
            return last
        await asyncio.sleep(2)
    return last


pytestmark = pytest.mark.network

requires_env = pytest.mark.skipif(
    not _load_test_env(),
    reason="Missing MJ_* credentials in tests/.env or environment",
)


@requires_env
@pytest.mark.asyncio
async def test_client_imagine_and_changes():
    c = Mutiny()
    await c.start()
    try:
        assert await c.wait_ready(), "WebSocket client did not become ready in time"
        t1 = await c.imagine(
            "starlight over a desert monolith, long-exposure astrophotography", state="test"
        )
        res = await _wait_for_status_client(c, t1)
        assert res and res.status == JobStatus.SUCCEEDED, res
        save_task_output(res.model_dump(), label="client_imagine_grid")

        v1 = await c.change(t1, JobAction.VARIATION, index=1, state="test")
        v1_res = await _wait_for_status_client(c, v1)
        assert v1_res and v1_res.status == JobStatus.SUCCEEDED, v1_res
        save_task_output(v1_res.model_dump(), label="client_variation")

        u1 = await c.change(t1, JobAction.UPSCALE, index=1, state="test")
        u1_res = await _wait_for_status_client(c, u1)
        assert u1_res and u1_res.status == JobStatus.SUCCEEDED, u1_res
        save_task_output(u1_res.model_dump(), label="client_upscale")

        rr = await c.change(t1, JobAction.REROLL, state="test")
        rr_res = await _wait_for_status_client(c, rr)
        assert rr_res and rr_res.status == JobStatus.SUCCEEDED, rr_res
        save_task_output(rr_res.model_dump(), label="client_reroll")
    finally:
        await c.close()


@requires_env
@pytest.mark.asyncio
async def test_client_upscale_v7_subtle():
    c = Mutiny()
    await c.start()
    try:
        assert await c.wait_ready(), "WebSocket client did not become ready in time"
        base = await c.imagine(
            "v7-test: stone lighthouse at dawn, long exposure, misty sea", state="v7"
        )
        base_res = await _wait_for_status_client(c, base)
        assert base_res and base_res.status == JobStatus.SUCCEEDED, base_res

        # First do a standard Upscale of tile 1 to produce the upscaled message
        up = await c.change(base, JobAction.UPSCALE, index=1, state="v7")
        up_res = await _wait_for_status_client(c, up)
        assert up_res and up_res.status == JobStatus.SUCCEEDED, up_res

        # Now invoke v7 2x (Subtle) on the upscaled message; reuse original index
        v7 = await c.change(up, JobAction.UPSCALE_V7_2X_SUBTLE, index=1, state="v7")
        v7_res = await _wait_for_status_client(c, v7)
        assert v7_res and v7_res.status == JobStatus.SUCCEEDED, v7_res
        save_task_output(v7_res.model_dump(), label="client_upscale_v7_subtle")
    finally:
        await c.close()


@requires_env
@pytest.mark.asyncio
async def test_client_vary_subtle():
    c = Mutiny()
    await c.start()
    try:
        assert await c.wait_ready(), "WebSocket client did not become ready in time"
        base = await c.imagine("vary-subtle test: weathered brass compass on map", state="vary")
        base_res = await _wait_for_status_client(c, base)
        assert base_res and base_res.status == JobStatus.SUCCEEDED, base_res

        up = await c.change(base, JobAction.UPSCALE, index=1, state="vary")
        up_res = await _wait_for_status_client(c, up)
        assert up_res and up_res.status == JobStatus.SUCCEEDED, up_res

        v = await c.change(up, JobAction.VARY_SUBTLE, index=1, state="vary")
        v_res = await _wait_for_status_client(c, v)
        assert v_res and v_res.status == JobStatus.SUCCEEDED, v_res
        save_task_output(v_res.model_dump(), label="client_vary_subtle")
    finally:
        await c.close()


@requires_env
@pytest.mark.asyncio
async def test_client_zoom_out_2x():
    c = Mutiny()
    await c.start()
    try:
        assert await c.wait_ready(), "WebSocket client did not become ready in time"
        base = await c.imagine("zoom-out test: misty mountain cabin at dawn", state="zoom")
        base_res = await _wait_for_status_client(c, base)
        assert base_res and base_res.status == JobStatus.SUCCEEDED, base_res

        up = await c.change(base, JobAction.UPSCALE, index=1, state="zoom")
        up_res = await _wait_for_status_client(c, up)
        assert up_res and up_res.status == JobStatus.SUCCEEDED, up_res

        z = await c.change(up, JobAction.ZOOM_OUT_2X, index=1, state="zoom")
        z_res = await _wait_for_status_client(c, z)
        assert z_res and z_res.status == JobStatus.SUCCEEDED, z_res
        save_task_output(z_res.model_dump(), label="client_zoom_out_2x")
    finally:
        await c.close()


@requires_env
@pytest.mark.asyncio
async def test_client_pan_left():
    c = Mutiny()
    await c.start()
    try:
        assert await c.wait_ready(), "WebSocket client did not become ready in time"
        base = await c.imagine("pan-left test: antique telescope on a desk", state="pan")
        base_res = await _wait_for_status_client(c, base)
        assert base_res and base_res.status == JobStatus.SUCCEEDED, base_res

        up = await c.change(base, JobAction.UPSCALE, index=1, state="pan")
        up_res = await _wait_for_status_client(c, up)
        assert up_res and up_res.status == JobStatus.SUCCEEDED, up_res

        p = await c.change(up, JobAction.PAN_LEFT, index=1, state="pan")
        p_res = await _wait_for_status_client(c, p)
        assert p_res and p_res.status == JobStatus.SUCCEEDED, p_res
        save_task_output(p_res.model_dump(), label="client_pan_left")
    finally:
        await c.close()


@requires_env
@pytest.mark.asyncio
async def test_client_animate_high():
    c = Mutiny()
    await c.start()
    try:
        assert await c.wait_ready(), "WebSocket client did not become ready in time"
        base = await c.imagine("animate-high test: neon sign flickering in rain", state="anim")
        base_res = await _wait_for_status_client(c, base)
        assert base_res and base_res.status == JobStatus.SUCCEEDED, base_res

        up = await c.change(base, JobAction.UPSCALE, index=1, state="anim")
        up_res = await _wait_for_status_client(c, up)
        assert up_res and up_res.status == JobStatus.SUCCEEDED, up_res

        a = await c.change(up, JobAction.ANIMATE_HIGH, index=1, state="anim")
        a_res = await _wait_for_status_client(c, a)
        assert a_res and a_res.status == JobStatus.SUCCEEDED, a_res
        save_task_output(a_res.model_dump(), label="client_animate_high")
    finally:
        await c.close()


@requires_env
@pytest.mark.asyncio
async def test_client_custom_zoom():
    c = Mutiny()
    await c.start()
    try:
        assert await c.wait_ready(), "WebSocket client did not become ready in time"
        base = await c.imagine("client custom-zoom test: stone archway on cliff", state="cz")
        base_res = await _wait_for_status_client(c, base)
        assert base_res and base_res.status == JobStatus.SUCCEEDED, base_res

        up = await c.change(base, JobAction.UPSCALE, index=1, state="cz")
        up_res = await _wait_for_status_client(c, up)
        assert up_res and up_res.status == JobStatus.SUCCEEDED, up_res

        cz = await c.custom_zoom(
            job_id=up, zoom_text="tight crop on arch details --zoom 1.24", state="cz"
        )
        cz_res = await _wait_for_status_client(c, cz)
        assert cz_res and cz_res.status == JobStatus.SUCCEEDED, cz_res
        save_task_output(cz_res.model_dump(), label="client_custom_zoom")
    finally:
        await c.close()


@requires_env
@pytest.mark.asyncio
async def test_client_inpaint_mvp():
    c = Mutiny()
    await c.start()
    try:
        assert await c.wait_ready(), "WebSocket client did not become ready in time"
        base = await c.imagine(
            "client inpaint test: stone archway spanning a stream", state="inpaint"
        )
        base_res = await _wait_for_status_client(c, base)
        assert base_res and base_res.status == JobStatus.SUCCEEDED, base_res

        up = await c.change(base, JobAction.UPSCALE, index=1, state="inpaint")
        up_res = await _wait_for_status_client(c, up)
        assert up_res and up_res.status == JobStatus.SUCCEEDED, up_res

        mask = make_mask_data_url()
        ip = await c.inpaint(
            job_id=up, mask_data_url=mask, prompt="carve vines into the arch", state="inpaint"
        )
        ip_res = await _wait_for_status_client(c, ip)
        assert ip_res and ip_res.status == JobStatus.SUCCEEDED, ip_res
        save_task_output(ip_res.model_dump(), label="client_inpaint_mvp")
    finally:
        await c.close()


@requires_env
@pytest.mark.asyncio
async def test_client_describe_and_blend():
    c = Mutiny()
    await c.start()
    try:
        assert await c.wait_ready(), "WebSocket client did not become ready in time"
        d = await c.describe(_make_png_data_url(), state="test")
        d_res = await _wait_for_status_client(c, d)
        assert d_res and d_res.status == JobStatus.SUCCEEDED, d_res
        save_task_output(d_res.model_dump(), label="client_describe")

        imgs = [
            _make_png_data_url(color=(255, 0, 0)),
            _make_png_data_url(color=(0, 0, 255)),
        ]
        b = await c.blend(imgs, dimensions="1:1", state="test")
        b_res = await _wait_for_status_client(c, b)
        assert b_res and b_res.status == JobStatus.SUCCEEDED, b_res
        save_task_output(b_res.model_dump(), label="client_blend")
    finally:
        await c.close()


@requires_env
@pytest.mark.asyncio
async def test_client_blend_duplicate_rejected():
    c = Mutiny()
    await c.start()
    try:
        assert await c.wait_ready(), "WebSocket client did not become ready in time"
        img = _make_png_data_url()
        with pytest.raises(RuntimeError):
            await c.blend([img, img], dimensions="1:1", state="test")
    finally:
        await c.close()


@requires_env
@pytest.mark.asyncio
async def test_client_imagine_with_images_and_cache():
    c = Mutiny()
    await c.start()
    try:
        assert await c.wait_ready(), "WebSocket client did not become ready in time"

        img = _make_png_data_url(color=(128, 128, 255))
        t1 = await c.imagine(
            "clockwork hummingbird made of brass and glass, steampunk, macro",
            images=[img],
            state="test",
        )
        res1 = await _wait_for_status_client(c, t1)
        assert res1 and res1.status == JobStatus.SUCCEEDED, res1

        t2 = await c.imagine(
            "ancient library grown inside a giant tree, warm light shafts",
            images=[img],
            state="test",
        )
        res2 = await _wait_for_status_client(c, t2)
        assert res2 and res2.status == JobStatus.SUCCEEDED, res2

        img2 = _make_png_data_url(color=(255, 128, 128))
        t3 = await c.imagine(
            "neon-lit cyberpunk alley in the rain, reflective puddles and fog",
            images=[img, img2],
            state="test",
        )
        res3 = await _wait_for_status_client(c, t3)
        assert res3 and res3.status == JobStatus.SUCCEEDED, res3
    finally:
        await c.close()


@requires_env
@pytest.mark.asyncio
async def test_client_imagine_with_style_reference_images():
    c = Mutiny()
    await c.start()
    try:
        assert await c.wait_ready(), "WebSocket client did not become ready in time"

        style = _make_png_data_url(color=(32, 96, 192))
        task_id = await c.imagine(
            "editorial portrait with dramatic backlight --v 7 --sw 300",
            image_inputs=ImagineImageInputs(
                style_reference=StyleReferenceImages(
                    images=(style,),
                    multipliers=(2.0,),
                )
            ),
            state="test-style-image",
        )
        result = await _wait_for_status_client(c, task_id)
        assert result and result.status == JobStatus.SUCCEEDED, result
        save_task_output(result.model_dump(), label="client_style_reference_image")
    finally:
        await c.close()


@requires_env
@pytest.mark.asyncio
async def test_client_imagine_with_character_reference_images():
    c = Mutiny()
    await c.start()
    try:
        assert await c.wait_ready(), "WebSocket client did not become ready in time"

        character = _make_png_data_url(color=(196, 144, 80))
        task_id = await c.imagine(
            "fantasy hero on a cliff at sunrise --v 6.1 --cw 80",
            image_inputs=ImagineImageInputs(
                character_reference=CharacterReferenceImages(images=(character,))
            ),
            state="test-character-image",
        )
        result = await _wait_for_status_client(c, task_id)
        assert result and result.status == JobStatus.SUCCEEDED, result
        save_task_output(result.model_dump(), label="client_character_reference_image")
    finally:
        await c.close()


@requires_env
@pytest.mark.asyncio
async def test_client_imagine_with_combined_prompt_style_and_omni_images():
    c = Mutiny()
    await c.start()
    try:
        assert await c.wait_ready(), "WebSocket client did not become ready in time"

        composition = _make_png_data_url(color=(64, 64, 160))
        style = _make_png_data_url(color=(192, 64, 160))
        omni = _make_png_data_url(color=(160, 160, 64))
        task_id = await c.imagine(
            "cinematic full-body portrait in the rain --v 7 --iw 1.5 --sw 250 --ow 180 --ar 2:3",
            image_inputs=ImagineImageInputs(
                prompt_images=(composition,),
                style_reference=StyleReferenceImages(images=(style,)),
                omni_reference=OmniReferenceImage(omni),
            ),
            state="test-combined-images",
        )
        result = await _wait_for_status_client(c, task_id)
        assert result and result.status == JobStatus.SUCCEEDED, result
        save_task_output(result.model_dump(), label="client_combined_image_inputs")
    finally:
        await c.close()


@requires_env
@pytest.mark.asyncio
async def test_client_image_change_via_tile():
    import httpx

    c = Mutiny()
    await c.start()
    try:
        assert await c.wait_ready(), "WebSocket client did not become ready in time"
        base = await c.imagine("ornate compass rose on aged parchment, top-down", state="test")
        base_res = await _wait_for_status_client(c, base)
        assert base_res and base_res.status == JobStatus.SUCCEEDED, base_res

        # Fetch base image and crop tile 1 locally (avoid hitting HTTP route)
        assert base_res.image_url
        async with httpx.AsyncClient() as ac:
            img_bytes = (await ac.get(base_res.image_url, timeout=60)).content
        # crop tile 1
        rgb = decode_rgb(img_bytes)
        height, width = rgb.shape[:2]
        tile = rgb[0 : height // 2, 0 : width // 2]
        ok, buffer = cv2.imencode(".png", cv2.cvtColor(tile, cv2.COLOR_RGB2BGR))
        assert ok
        tile_bytes = buffer.tobytes()

        # Wait for background indexing to map this tile hash to job ref (parity with HTTP test)
        proc = c._state.require_context().image_processor  # use same processor as indexer
        digest = proc.compute_digest(tile_bytes)

        found = False
        for _ in range(200):  # up to ~20s
            state = getattr(c, "_state", None)
            ctx = state.require_context() if state else None
            idx = ctx.artifact_cache if ctx else None
            if idx and idx.get_image_job_ref(digest):
                found = True
                break
            await asyncio.sleep(0.1)
        assert found, "Tile hash was not indexed in time"

        data_url = f"data:image/png;base64,{base64.b64encode(tile_bytes).decode('ascii')}"

        t2 = await c.image_change(data_url, action=JobAction.VARIATION, state="test")
        res2 = await _wait_for_status_client(c, t2)
        assert res2 and res2.status == "SUCCEEDED", res2
        save_task_output(res2.model_dump(), label="client_image_change_variation")
    finally:
        await c.close()


@requires_env
@pytest.mark.asyncio
async def test_client_cancel_flows():
    # Consolidated cancel test that tries VARIATION then UPSCALE, similar to HTTP tests
    c = Mutiny()
    await c.start()
    try:
        assert await c.wait_ready(), "WebSocket client did not become ready in time"

        base = await c.imagine(
            "network-cancel run: blue lighthouse on cliff", state="network-cancel"
        )
        # wait for base to finish
        _ = await _wait_for_status_client(c, base)

        # Trigger a variation and then attempt cancel repeatedly until it succeeds or finishes
        change_id = await c.change(base, JobAction.VARIATION, index=1, state="network-cancel")
        deadline = time.time() + 240
        cancel_ok = False
        last_err = None
        while time.time() < deadline:
            try:
                await c.cancel(change_id)
                cancel_ok = True
                break
            except RuntimeError as e:
                last_err = str(e)
                await asyncio.sleep(1)
        if not cancel_ok:
            # If already finished, treat as inconclusive
            cur = await c.get_job(change_id)
            if cur.status == JobStatus.SUCCEEDED:
                save_task_output(cur.model_dump(), label="client_upscale_finished_before_cancel")
                pytest.skip("Task finished before cancel could be applied")
            assert cancel_ok, f"Cancel did not succeed in time: {last_err}"

        # The local task should transition to FAILURE quickly
        deadline = time.time() + 60
        status = None
        while time.time() < deadline:
            cur = await c.get_job(change_id)
            status = cur.status
            if status in (JobStatus.FAILED,):
                break
            await asyncio.sleep(1)
        assert status == JobStatus.FAILED, f"Expected FAILURE after cancel, got {status}"
        save_task_output(cur.model_dump(), label="client_cancel_variation")

        # Repeat for UPSCALE
        change_id = await c.change(base, JobAction.UPSCALE, index=1, state="network-cancel")
        deadline = time.time() + 240
        cancel_ok = False
        last_err = None
        while time.time() < deadline:
            try:
                await c.cancel(change_id)
                cancel_ok = True
                break
            except RuntimeError as e:
                last_err = str(e)
                await asyncio.sleep(1)
        assert cancel_ok, f"Cancel did not succeed in time: {last_err}"

        deadline = time.time() + 60
        status = None
        while time.time() < deadline:
            cur = await c.get_job(change_id)
            status = cur.status
            if status in (JobStatus.FAILED,):
                break
            await asyncio.sleep(1)
        assert status == JobStatus.FAILED, f"Expected FAILURE after cancel, got {status}"
        save_task_output(cur.model_dump(), label="client_cancel_upscale")
    finally:
        await c.close()
