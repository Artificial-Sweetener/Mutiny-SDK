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

from mutiny.discord.message_interpreter import DiscordMessageParser
from mutiny.domain.job import Job, JobAction, JobStatus
from mutiny.domain.state_machine import JobStateMachine, JobTransition
from mutiny.engine.reactors.animate_reactor import AnimateReactor
from mutiny.engine.reactors.blend_reactor import BlendReactor
from mutiny.engine.reactors.describe_reactor import DescribeReactor
from mutiny.engine.reactors.error_reactor import ErrorReactor
from mutiny.engine.reactors.imagine_reactor import ImagineReactor
from mutiny.engine.reactors.progress_reactor import ProgressReactor
from mutiny.engine.reactors.reroll_reactor import RerollReactor
from mutiny.engine.reactors.upscale_reactor import UpscaleReactor
from mutiny.engine.reactors.variation_reactor import VariationReactor

_VIDEO_UPSCALE_CUSTOM_ID = "MJ::JOB::video_virtual_upscale::1::ba5620ce-521c-4b8e-a5da-e5512725d429"


class _FakeInstance:
    def __init__(self, jobs: list[Job]):
        self.jobs = jobs
        self.saved: list[Job] = []
        self.image_indexed: list[str] = []
        self.image_index_actions: list[tuple[JobAction, str | None]] = []
        self.prompt_video_follow_ups: list[dict[str, object]] = []
        self.internal_follow_ups: list[str] = []
        self.notify_bus = _FakeNotifyBus()

    def get_running_job_by_condition(self, predicate):
        return next((j for j in self.jobs if predicate(j)), None)

    def get_running_job_by_nonce(self, nonce: str):
        return next((j for j in self.jobs if j.context.nonce == nonce), None)

    def save_and_notify(self, job: Job):
        self.saved.append(job)

    def apply_transition(
        self, job: Job, transition: JobTransition, reason: str | None = None
    ) -> bool:
        return JobStateMachine.apply(job, transition, reason)

    def schedule_image_indexing(self, action: JobAction, message: dict, job: Job):
        self.image_indexed.append(message.get("id"))
        self.image_index_actions.append((action, message.get("id")))

    def schedule_video_indexing(self, message: dict, job: Job):
        self.image_indexed.append(message.get("id"))

    def schedule_prompt_video_follow_up(
        self,
        job: Job,
        *,
        message_id: str,
        custom_id: str,
        message_flags: int,
    ) -> None:
        self.prompt_video_follow_ups.append(
            {
                "job_id": job.id,
                "message_id": message_id,
                "custom_id": custom_id,
                "message_flags": message_flags,
            }
        )

    def schedule_internal_follow_up_action(self, job: Job) -> None:
        self.internal_follow_ups.append(job.id)


class _FakeNotifyBus:
    def __init__(self) -> None:
        self.progress_events = []

    def publish_progress(self, event):
        self.progress_events.append(event)


_PARSER = DiscordMessageParser()


def _interpret(message: dict):
    interpreted = _PARSER.interpret("MESSAGE_CREATE", message)
    assert interpreted is not None
    return interpreted


def _attachment(url: str) -> list[dict]:
    return [{"url": url}]


def _start_job(job: Job) -> None:
    JobStateMachine.apply(job, JobTransition.SUBMIT)
    JobStateMachine.apply(job, JobTransition.START)


def test_imagine_success_handler_freeze():
    prompt = "Ocean lighthouse"
    t = Job(id="t1", action=JobAction.IMAGINE)
    t.context.final_prompt = prompt
    _start_job(t)
    inst = _FakeInstance([t])

    msg = {
        "id": "m1",
        "content": f"**{prompt}** - <@123> (fast)",
        "attachments": _attachment("https://cdn/x/file_abcd1234.png"),
    }
    handled = ImagineReactor().handle_message(inst, "MESSAGE_CREATE", _interpret(msg))

    assert handled is True
    assert t.status == JobStatus.SUCCEEDED
    assert t.context.message_id == "m1"
    assert t.context.message_hash == "abcd1234"
    assert inst.image_index_actions == [(JobAction.IMAGINE, "m1")]


def test_variation_success_handler_freeze():
    prompt = "Marble bust"
    t = Job(id="t2", action=JobAction.VARIATION)
    t.context.final_prompt = prompt
    _start_job(t)
    inst = _FakeInstance([t])

    msg = {
        "id": "m2",
        "content": f"**{prompt}** - Variations by <@123> (fast)",
        "attachments": _attachment("https://cdn/x/var_zz99.png"),
    }
    handled = VariationReactor().handle_message(inst, "MESSAGE_CREATE", _interpret(msg))

    assert handled is True
    assert t.status == JobStatus.SUCCEEDED
    assert t.context.message_hash == "zz99"
    assert inst.image_index_actions == [(JobAction.VARIATION, "m2")]


def test_inpaint_success_handler_freeze():
    prompt = "carve vines into the arch --v 7.0"
    t = Job(id="t2a", action=JobAction.INPAINT)
    t.context.final_prompt = prompt
    _start_job(t)
    inst = _FakeInstance([t])

    msg = {
        "id": "m2a",
        "content": f"**{prompt}** - Variations (Region) by <@123> (fast)",
        "attachments": _attachment("https://cdn/x/inpaint_1a2b.png"),
    }
    handled = VariationReactor().handle_message(inst, "MESSAGE_CREATE", _interpret(msg))

    assert handled is True
    assert t.status == JobStatus.SUCCEEDED
    assert t.context.message_hash == "1a2b"
    assert inst.image_index_actions == [(JobAction.INPAINT, "m2a")]


def test_vary_subtle_success_handler_freeze():
    prompt = "weathered bronze statue"
    t = Job(id="t2b", action=JobAction.VARY_SUBTLE)
    t.context.final_prompt = prompt
    _start_job(t)
    inst = _FakeInstance([t])

    msg = {
        "id": "m2b",
        "content": f"**{prompt}** - Variations (Subtle) by <@123> (fast)",
        "attachments": _attachment("https://cdn/x/vary_subtle_22aa.png"),
    }
    handled = VariationReactor().handle_message(inst, "MESSAGE_CREATE", _interpret(msg))

    assert handled is True
    assert t.status == JobStatus.SUCCEEDED
    assert t.context.message_hash == "22aa"
    assert inst.image_index_actions == [(JobAction.VARY_SUBTLE, "m2b")]


def test_vary_strong_success_handler_freeze():
    prompt = "weathered bronze statue"
    t = Job(id="t2c", action=JobAction.VARY_STRONG)
    t.context.final_prompt = prompt
    _start_job(t)
    inst = _FakeInstance([t])

    msg = {
        "id": "m2c",
        "content": f"**{prompt}** - Variations (Strong) by <@123> (fast)",
        "attachments": _attachment("https://cdn/x/vary_strong_33bb.png"),
    }
    handled = VariationReactor().handle_message(inst, "MESSAGE_CREATE", _interpret(msg))

    assert handled is True
    assert t.status == JobStatus.SUCCEEDED
    assert t.context.message_hash == "33bb"
    assert inst.image_index_actions == [(JobAction.VARY_STRONG, "m2c")]


def test_reroll_success_handler_freeze():
    prompt = "Old town street"
    t = Job(id="t3", action=JobAction.REROLL)
    t.context.final_prompt = prompt
    _start_job(t)
    inst = _FakeInstance([t])

    msg = {
        "id": "m3",
        "content": f"**{prompt}** - <@123> (relax)",
        "attachments": _attachment("https://cdn/x/reroll_h123.png"),
    }
    handled = RerollReactor().handle_message(inst, "MESSAGE_CREATE", _interpret(msg))

    assert handled is True
    assert t.status == JobStatus.SUCCEEDED
    assert t.context.message_hash == "h123"
    assert inst.image_index_actions == [(JobAction.REROLL, "m3")]


def test_blend_success_handler_freeze():
    prompt = "<https://s.mj.run/abcd>"
    t = Job(id="t4", action=JobAction.BLEND)
    t.context.final_prompt = prompt
    _start_job(t)
    inst = _FakeInstance([t])

    msg = {
        "id": "m4",
        "content": f"**{prompt}** - <@123> (fast)",
        "attachments": _attachment("https://cdn/x/blend_1a2b.png"),
    }
    handled = BlendReactor().handle_message(inst, "MESSAGE_CREATE", _interpret(msg))

    assert handled is True
    assert t.status == JobStatus.SUCCEEDED
    assert t.context.message_hash == "1a2b"
    assert inst.image_index_actions == [(JobAction.BLEND, "m4")]


def test_describe_success_handler_freeze():
    t = Job(id="t5", action=JobAction.DESCRIBE)
    _start_job(t)
    t.context.nonce = "n1"
    inst = _FakeInstance([t])

    msg_start = {"id": "pm1", "interaction": {"name": "describe"}, "nonce": "n1"}
    handled_start = DescribeReactor().handle_message(inst, "MESSAGE_CREATE", _interpret(msg_start))
    assert handled_start is True
    assert t.context.progress_message_id == "pm1"

    msg_done = {
        "id": "pm1",
        "embeds": [{"description": "desc text", "image": {"url": "https://cdn/x.png"}}],
    }
    handled_done = DescribeReactor().handle_message(inst, "MESSAGE_CREATE", _interpret(msg_done))

    assert handled_done is True
    assert t.status == JobStatus.SUCCEEDED
    assert t.prompt == "desc text"
    assert t.prompt_en == "desc text"
    assert t.context.final_prompt == "desc text"
    assert t.image_url == "https://cdn/x.png"


def test_error_handler_freeze():
    t = Job(id="t6", action=JobAction.IMAGINE)
    _start_job(t)
    t.context.progress_message_id = "pm2"
    inst = _FakeInstance([t])

    msg = {
        "embeds": [{"color": 15548997, "title": "Error", "description": "bad"}],
        "message_reference": {"message_id": "pm2"},
    }
    handled = ErrorReactor().handle_message(inst, "MESSAGE_CREATE", _interpret(msg))

    assert handled is True
    assert t.status == JobStatus.FAILED
    assert t.fail_reason == "[Error] bad"


def test_error_handler_matches_message_id_without_progress_message():
    t = Job(id="t6b", action=JobAction.IMAGINE)
    _start_job(t)
    t.context.message_id = "base-msg-1"
    inst = _FakeInstance([t])

    msg = {
        "embeds": [
            {
                "title": "Sorry, something went wrong",
                "description": "The job encountered an error. Our team has been notified.",
                "footer": {"text": "decline-revise-frolic"},
            }
        ],
        "message_reference": {"message_id": "base-msg-1"},
    }
    handled = ErrorReactor().handle_message(inst, "MESSAGE_CREATE", _interpret(msg))

    assert handled is True
    assert t.status == JobStatus.FAILED
    assert (
        t.fail_reason == "Prompt was rejected by Midjourney moderation. Try revising the prompt. "
        "(Midjourney code: decline-revise-frolic)"
    )


def test_error_handler_translates_slow_down_rate_limit():
    t = Job(id="t6d", action=JobAction.UPSCALE)
    _start_job(t)
    t.context.message_id = "base-msg-rate-limit"
    inst = _FakeInstance([t])

    msg = {
        "embeds": [
            {
                "title": "Slow Down!",
                "description": "You can request another upscale for this image <t:1774990054:R>",
            }
        ],
        "message_reference": {"message_id": "base-msg-rate-limit"},
    }
    handled = ErrorReactor().handle_message(inst, "MESSAGE_CREATE", _interpret(msg))

    assert handled is True
    assert t.status == JobStatus.FAILED
    assert (
        t.fail_reason
        == "Midjourney rate-limited this follow-up. You can try again <t:1774990054:R>."
    )


def test_error_handler_translates_unrecognized_parameter_validation():
    t = Job(id="t6e", action=JobAction.IMAGINE)
    _start_job(t)
    t.context.progress_message_id = "pm-invalid-parameter"
    inst = _FakeInstance([t])

    msg = {
        "content": (
            "Invalid parameter\n"
            "Unrecognized parameter(s): use_raw\n"
            "/imagine prompt text --seed 1 True --niji 7"
        ),
        "message_reference": {"message_id": "pm-invalid-parameter"},
    }
    handled = ErrorReactor().handle_message(inst, "MESSAGE_CREATE", _interpret(msg))

    assert handled is True
    assert t.status == JobStatus.FAILED
    assert t.fail_reason == "Midjourney rejected the prompt: Unrecognized parameter(s): use_raw."


def test_error_handler_does_not_refail_succeeded_job():
    t = Job(id="t6c", action=JobAction.IMAGINE)
    _start_job(t)
    JobStateMachine.apply(t, JobTransition.SUCCEED)
    t.context.progress_message_id = "pm-succeeded"
    inst = _FakeInstance([t])

    msg = {
        "embeds": [{"color": 15548997, "title": "Error", "description": "bad"}],
        "message_reference": {"message_id": "pm-succeeded"},
    }
    handled = ErrorReactor().handle_message(inst, "MESSAGE_CREATE", _interpret(msg))

    assert handled is False
    assert t.status == JobStatus.SUCCEEDED


def test_start_and_progress_handler_nonce_match_freeze():
    t = Job(id="t7", action=JobAction.IMAGINE, prompt="Prompt")
    _start_job(t)
    inst = _FakeInstance([t])

    msg = {
        "id": "pm3",
        "content": "**Prompt** - <@123> (Waiting to start)",
        "interaction": {"id": "ix-1", "name": "imagine"},
    }
    handled = ProgressReactor().handle_message(inst, "MESSAGE_CREATE", _interpret(msg))

    assert handled is True
    assert t.status == JobStatus.IN_PROGRESS
    assert t.context.progress_message_id == "pm3"
    assert t.context.final_prompt == "Prompt"
    assert t.context.not_fast is True
    assert t.context.interaction_id == "ix-1"


def test_start_and_progress_handler_progress_update_freeze():
    t = Job(id="t8", action=JobAction.IMAGINE)
    _start_job(t)
    t.context.progress_message_id = "pm4"
    t.context.interaction_id = "ix-2"
    inst = _FakeInstance([t])

    msg = {
        "id": "pm4",
        "content": "**Prompt** - <@123> (fast 25%)",
        "flags": 64,
        "interaction": {"id": "ix-2", "name": "imagine"},
        "attachments": _attachment("https://cdn/x/grid_abc_12345_grid_0.webp"),
        "components": [
            {
                "components": [
                    {"custom_id": "MJ::CancelJob::ByJobid::job-1"},
                ]
            }
        ],
    }
    handled = ProgressReactor().handle_message(inst, "MESSAGE_CREATE", _interpret(msg))

    assert handled is True
    assert t.progress == "fast 25%"
    assert t.context.flags == 64
    assert t.context.message_hash == "grid_abc_12345"
    assert t.context.cancel_message_id == "pm4"
    assert t.context.cancel_job_id == "job-1"


def test_start_and_progress_handler_reference_match_freeze():
    t = Job(id="t9", action=JobAction.INPAINT)
    _start_job(t)
    t.context.message_id = "base1"
    inst = _FakeInstance([t])

    msg = {
        "id": "pm5",
        "content": "**Prompt** - <@123> (Waiting to start)",
        "message_reference": {"message_id": "base1"},
    }
    handled = ProgressReactor().handle_message(inst, "MESSAGE_CREATE", _interpret(msg))

    assert handled is True
    assert t.status == JobStatus.IN_PROGRESS
    assert t.context.progress_message_id == "pm5"


def test_start_and_progress_handler_matches_rewritten_prompt_with_injected_sref():
    original_prompt = (
        "cute pink twintails hair tsundere girl with smug pink eyes "
        "--no evil, villain, teeth, vampire --ar 3:4 --seed 2227065045 --niji 7"
    )
    rewritten_prompt = (
        f"{original_prompt} --sref <https://s.mj.run/jzApQeBLQLk> <https://s.mj.run/i36gARL0e94>"
    )
    t = Job(id="t9b", action=JobAction.IMAGINE, prompt=original_prompt)
    _start_job(t)
    inst = _FakeInstance([t])

    msg = {
        "id": "pm6",
        "content": f"**{rewritten_prompt}** - <@123> (Waiting to start)",
    }
    handled = ProgressReactor().handle_message(inst, "MESSAGE_CREATE", _interpret(msg))

    assert handled is True
    assert t.status == JobStatus.IN_PROGRESS
    assert t.context.progress_message_id == "pm6"
    assert t.context.final_prompt == rewritten_prompt


def test_upscale_success_reference_match_freeze():
    t = Job(id="t10", action=JobAction.ZOOM_OUT_2X)
    t.context.final_prompt = "zoom/pan test: alpine lake sunrise"
    t.context.message_id = "base1"
    _start_job(t)
    inst = _FakeInstance([t])

    msg = {
        "id": "m10",
        "content": "**zoom/pan test: alpine lake sunrise --ar 3:2** - Zoom Out by <@123> (fast)",
        "attachments": _attachment("https://cdn/x/zoom_9abc.png"),
        "message_reference": {"message_id": "base1"},
    }
    handled = UpscaleReactor().handle_message(inst, "MESSAGE_CREATE", _interpret(msg))

    assert handled is True
    assert t.status == JobStatus.SUCCEEDED
    assert t.context.message_id == "m10"
    assert inst.image_index_actions == [(JobAction.ZOOM_OUT_2X, "m10")]


def test_pan_success_indexes_with_pan_action_not_upscale():
    t = Job(id="t10b", action=JobAction.PAN_LEFT)
    t.context.final_prompt = "pan-left test: alpine lake sunrise"
    t.context.message_id = "base-pan"
    _start_job(t)
    inst = _FakeInstance([t])

    msg = {
        "id": "m10b",
        "content": "**pan-left test: alpine lake sunrise --ar 3:2** - Pan Left by <@123> (fast)",
        "attachments": _attachment("https://cdn/x/pan_9abc.png"),
        "message_reference": {"message_id": "base-pan"},
    }
    handled = UpscaleReactor().handle_message(inst, "MESSAGE_CREATE", _interpret(msg))

    assert handled is True
    assert t.status == JobStatus.SUCCEEDED
    assert t.context.message_id == "m10b"
    assert inst.image_index_actions == [(JobAction.PAN_LEFT, "m10b")]


def test_modern_tile_promotion_intermediate_schedules_internal_follow_up():
    t = Job(id="tp1", action=JobAction.PAN_LEFT)
    t.context.final_prompt = "modern tile alpine lake"
    t.context.message_id = "grid-msg"
    t.context.message_hash = "grid-hash"
    t.context.index = 2
    t.context.implicit_tile_promotion_pending = True
    t.context.implicit_tile_promotion_index = 2
    _start_job(t)
    inst = _FakeInstance([t])

    msg = {
        "id": "promoted-msg",
        "content": "**modern tile alpine lake** - Image #2 <@123>",
        "attachments": _attachment("https://cdn/x/promoted_aa11.png"),
        "message_reference": {"message_id": "grid-msg"},
    }
    handled = UpscaleReactor().handle_message(inst, "MESSAGE_CREATE", _interpret(msg))

    assert handled is True
    assert t.status == JobStatus.IN_PROGRESS
    assert t.context.message_id == "promoted-msg"
    assert t.context.message_hash == "aa11"
    assert t.context.index == 1
    assert t.context.implicit_tile_promotion_pending is False
    assert len(inst.notify_bus.progress_events) == 1
    event = inst.notify_bus.progress_events[0]
    assert event.job_id == "tp1"
    assert event.kind == "promotion"
    assert event.status_text == "Preparing tile follow-up"
    assert event.prompt == "modern tile alpine lake"
    assert event.progress_message_id is None
    assert event.message_id == "promoted-msg"
    assert event.image_url == "https://cdn/x/promoted_aa11.png"
    assert event.message_hash == "aa11"
    assert inst.internal_follow_ups == ["tp1"]


def test_subtle_upscale_ignores_source_message_echo_before_real_result_arrives():
    t = Job(id="tp2", action=JobAction.UPSCALE_V7_2X_SUBTLE)
    t.context.final_prompt = (
        "Key image illustration, digital crayon painting magical girl mage --niji 7"
    )
    t.context.message_id = "source-solo-message"
    t.context.message_hash = "339e8aa5-bac2-42c8-ab69-af3920988ed4"
    _start_job(t)
    inst = _FakeInstance([t])

    source_update = {
        "id": "source-solo-message",
        "content": (
            "**Key image illustration, digital crayon painting magical girl mage --niji 7** "
            "- Image #4 <@123>"
        ),
        "attachments": _attachment(
            "https://cdn/x/"
            "artificialsweetener_Key_image_illustration_digital_crayon_paint_"
            "339e8aa5-bac2-42c8-ab69-af3920988ed4.png"
        ),
    }

    interpreted_source = _PARSER.interpret("MESSAGE_UPDATE", source_update)
    assert interpreted_source is not None

    handled_source = UpscaleReactor().handle_message(inst, "MESSAGE_UPDATE", interpreted_source)

    assert handled_source is False
    assert t.status == JobStatus.IN_PROGRESS
    assert t.image_url is None
    assert inst.image_indexed == []


def test_animate_success_reference_match_freeze():
    t = Job(id="t11", action=JobAction.ANIMATE_HIGH)
    t.context.final_prompt = "animate-high test: neon sign flickering in rain"
    t.context.message_id = "base2"
    _start_job(t)
    inst = _FakeInstance([t])

    msg = {
        "id": "m11",
        "content": (
            "**animate-high test: neon sign flickering in rain --motion high --video 1 "
            "--aspect 1:1** - <@123> [(Open on website for full quality)]"
            "(https://midjourney.com/jobs/abc) (fast)"
        ),
        "attachments": _attachment("https://cdn/x/anim_9abc.mp4"),
        "message_reference": {"message_id": "base2"},
    }
    handled = AnimateReactor().handle_message(inst, "MESSAGE_CREATE", _interpret(msg))

    assert handled is True
    assert t.status == JobStatus.SUCCEEDED
    assert t.artifacts.video_url == "https://cdn/x/anim_9abc.mp4"
    assert t.artifacts.website_url == "https://midjourney.com/jobs/abc"


def test_animate_prompt_video_intermediate_freeze():
    t = Job(id="t12", action=JobAction.ANIMATE_LOW)
    t.context.final_prompt = "<https://s.mj.run/abcd> blink once --video --motion low --bs 1"
    _start_job(t)
    inst = _FakeInstance([t])

    msg = {
        "id": "m12",
        "content": (
            "**<https://s.mj.run/abcd> blink once --motion low --bs 1 --video 1** - <@123> "
            "[(Open on website for full quality)](https://midjourney.com/jobs/abc) (fast)"
        ),
        "attachments": _attachment("https://cdn/x/video_stage_88ff.webp"),
        "components": [{"components": [{"custom_id": _VIDEO_UPSCALE_CUSTOM_ID}]}],
    }
    handled = AnimateReactor().handle_message(inst, "MESSAGE_CREATE", _interpret(msg))

    assert handled is True
    assert t.status == JobStatus.IN_PROGRESS
    assert t.image_url == "https://cdn/x/video_stage_88ff.webp"
    assert t.artifacts.website_url == "https://midjourney.com/jobs/abc"
    assert t.context.message_id == "m12"
    assert t.context.message_hash == "88ff"
    assert t.context.prompt_video_follow_up_requested is True
    assert inst.prompt_video_follow_ups == [
        {
            "job_id": "t12",
            "message_id": "m12",
            "custom_id": _VIDEO_UPSCALE_CUSTOM_ID,
            "message_flags": 0,
        }
    ]


def test_animate_progress_terminal_freeze():
    """Keep terminal prompt-video progress updates as progress-only state changes."""

    t = Job(id="t12b", action=JobAction.ANIMATE_LOW)
    t.context.final_prompt = "<https://s.mj.run/abcd> blink once --video --motion low --bs 1"
    _start_job(t)
    t.context.progress_message_id = "pm-animate"
    inst = _FakeInstance([t])

    msg = {
        "id": "pm-animate",
        "content": (
            "**<https://s.mj.run/abcd> blink once --motion low --bs 1 --video 1** - <@123> (100%)"
        ),
    }
    handled = ProgressReactor().handle_message(inst, "MESSAGE_CREATE", _interpret(msg))

    assert handled is True
    assert t.progress == "100%"
    assert t.status == JobStatus.IN_PROGRESS


def test_animate_extend_progress_start_matches_inherited_prompt():
    t = Job(
        id="t12c",
        action=JobAction.ANIMATE_EXTEND_LOW,
        prompt="idle animation --motion low --bs 1 --video 1 --aspect 1:1",
    )
    t.context.message_id = "source-video-message"
    t.context.message_hash = "582e1700-e7b6-48e6-a0cd-6f91c36d0712"
    _start_job(t)
    inst = _FakeInstance([t])

    msg = {
        "id": "pm-extend",
        "content": (
            "**idle animation --motion low --bs 1 --video 1 --aspect 1:1** "
            "- <@123> (Waiting to start)"
        ),
        "flags": 64,
    }
    handled = ProgressReactor().handle_message(inst, "MESSAGE_UPDATE", _interpret(msg))

    assert handled is True
    assert t.status == JobStatus.IN_PROGRESS
    assert t.context.progress_message_id == "pm-extend"
    assert t.context.final_prompt == "idle animation --motion low --bs 1 --video 1 --aspect 1:1"
