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

import pytest

from mutiny.discord.message_interpreter import DiscordMessageParser
from mutiny.domain.job import Job, JobAction, JobStatus
from mutiny.domain.state_machine import JobStateMachine, JobTransition
from mutiny.engine.reactors.animate_reactor import AnimateReactor

_VIDEO_UPSCALE_CUSTOM_ID = "MJ::JOB::video_virtual_upscale::1::ba5620ce-521c-4b8e-a5da-e5512725d429"


class FakeInstance:
    def __init__(self, tasks):
        self._tasks = tasks
        self.saved = []
        self.scheduled_prompt_video_follow_ups = []
        self.scheduled_video_indexing = []

    def get_running_job_by_condition(self, predicate):
        return next((tk for tk in self._tasks if predicate(tk)), None)

    def save_and_notify(self, job):  # pragma: no cover - not asserted
        self.saved.append(job)

    def schedule_prompt_video_follow_up(
        self,
        job: Job,
        *,
        message_id: str,
        custom_id: str,
        message_flags: int,
    ) -> None:
        self.scheduled_prompt_video_follow_ups.append(
            {
                "job_id": job.id,
                "message_id": message_id,
                "custom_id": custom_id,
                "message_flags": message_flags,
            }
        )

    def _apply_transition(
        self, job: Job, transition: JobTransition, reason: str | None = None
    ) -> bool:
        return JobStateMachine.apply(job, transition, reason)

    def apply_transition(
        self, job: Job, transition: JobTransition, reason: str | None = None
    ) -> bool:
        return JobStateMachine.apply(job, transition, reason)

    def schedule_video_indexing(self, message, job):
        self.scheduled_video_indexing.append({"job_id": job.id, "message_id": message.get("id")})


@pytest.mark.asyncio
async def test_animate_success_handler_finishes_on_video_reply():
    # Prepare running animate tasks
    t = Job(id="a1", action=JobAction.ANIMATE_HIGH)
    t.context.message_id = "orig-upscaled-1"
    JobStateMachine.apply(t, JobTransition.SUBMIT)
    JobStateMachine.apply(t, JobTransition.START)

    inst = FakeInstance([t])

    # Incoming reply with a video attachment
    message = {
        "id": "msg-2",
        "flags": 0,
        "message_reference": {"message_id": "orig-upscaled-1"},
        "attachments": [
            {
                "url": (
                    "https://cdn.discordapp.com/attachments/123/456/"
                    "3dabc83d-4d24-4f89-aea8-c1c8c112a3ca_1_720_N.mp4?ex=123&is=456"
                ),
                "filename": "3dabc83d-4d24-4f89-aea8-c1c8c112a3ca_1_720_N.mp4",
                "content_type": "video/mp4",
            }
        ],
    }

    parser = DiscordMessageParser()
    interpreted = parser.interpret("MESSAGE_CREATE", message)
    assert interpreted is not None
    handled = AnimateReactor().handle_message(inst, "MESSAGE_CREATE", interpreted)
    assert handled is True
    assert t.status == JobStatus.SUCCEEDED
    assert (t.artifacts.video_url or "").endswith(
        "3dabc83d-4d24-4f89-aea8-c1c8c112a3ca_1_720_N.mp4?ex=123&is=456"
    )
    assert t.context.message_id == "msg-2"
    assert t.context.message_hash == "3dabc83d-4d24-4f89-aea8-c1c8c112a3ca"


@pytest.mark.asyncio
async def test_animate_success_handler_matches_prompt_video_replies_by_prompt():
    t = Job(id="a2", action=JobAction.ANIMATE_LOW, prompt="camera push through fog")
    t.context.final_prompt = (
        "https://cdn.example/start.png camera push through fog --video --motion low"
    )
    JobStateMachine.apply(t, JobTransition.SUBMIT)
    JobStateMachine.apply(t, JobTransition.START)

    inst = FakeInstance([t])
    message = {
        "id": "msg-3",
        "flags": 0,
        "content": (
            "**https://cdn.example/start.png camera push through fog --video --motion low** - "
            "<@123> [(Open on website for full quality)](https://midjourney.com/jobs/abc) (fast)"
        ),
        "attachments": [
            {
                "url": "https://cdn.example.com/video.mp4",
                "filename": "video.mp4",
                "content_type": "video/mp4",
            }
        ],
    }

    parser = DiscordMessageParser()
    interpreted = parser.interpret("MESSAGE_CREATE", message)
    assert interpreted is not None
    handled = AnimateReactor().handle_message(inst, "MESSAGE_CREATE", interpreted)

    assert handled is True
    assert t.status == JobStatus.SUCCEEDED
    assert t.artifacts.video_url == "https://cdn.example.com/video.mp4"
    assert t.artifacts.website_url == "https://midjourney.com/jobs/abc"


@pytest.mark.asyncio
async def test_animate_prompt_video_intermediate_schedules_follow_up_button():
    t = Job(id="a3", action=JobAction.ANIMATE_LOW, prompt="camera push through fog")
    t.context.final_prompt = (
        "https://cdn.example/start.png camera push through fog --video --motion low --bs 1"
    )
    JobStateMachine.apply(t, JobTransition.SUBMIT)
    JobStateMachine.apply(t, JobTransition.START)

    inst = FakeInstance([t])
    message = {
        "id": "msg-4",
        "flags": 0,
        "content": (
            "**https://cdn.example/start.png camera push through fog --video 1 --motion low "
            "--bs 1** - <@123> "
            "[(Open on website for full quality)](https://midjourney.com/jobs/abc) (fast)"
        ),
        "attachments": [
            {
                "url": "https://cdn.example.com/anim_frame_9abc.webp",
                "filename": "anim_frame_9abc.webp",
                "content_type": "image/webp",
            }
        ],
        "components": [{"components": [{"custom_id": _VIDEO_UPSCALE_CUSTOM_ID}]}],
    }

    parser = DiscordMessageParser()
    interpreted = parser.interpret("MESSAGE_CREATE", message)
    assert interpreted is not None

    handled = AnimateReactor().handle_message(inst, "MESSAGE_CREATE", interpreted)

    assert handled is True
    assert t.status == JobStatus.IN_PROGRESS
    assert t.image_url == "https://cdn.example.com/anim_frame_9abc.webp"
    assert t.artifacts.website_url == "https://midjourney.com/jobs/abc"
    assert t.context.message_id == "msg-4"
    assert t.context.message_hash == "9abc"
    assert t.context.prompt_video_follow_up_requested is True
    assert inst.scheduled_prompt_video_follow_ups == [
        {
            "job_id": "a3",
            "message_id": "msg-4",
            "custom_id": _VIDEO_UPSCALE_CUSTOM_ID,
            "message_flags": 0,
        }
    ]


@pytest.mark.asyncio
async def test_animate_prompt_video_intermediate_only_schedules_once():
    t = Job(id="a4", action=JobAction.ANIMATE_LOW, prompt="camera push through fog")
    t.context.final_prompt = (
        "https://cdn.example/start.png camera push through fog --video --motion low"
    )
    t.context.prompt_video_follow_up_requested = True
    JobStateMachine.apply(t, JobTransition.SUBMIT)
    JobStateMachine.apply(t, JobTransition.START)

    inst = FakeInstance([t])
    message = {
        "id": "msg-5",
        "flags": 0,
        "content": (
            "**https://cdn.example/start.png camera push through fog --video --motion low** - "
            "<@123> [(Open on website for full quality)](https://midjourney.com/jobs/abc) (fast)"
        ),
        "attachments": [
            {
                "url": "https://cdn.example.com/anim_frame_9abc.webp",
                "filename": "anim_frame_9abc.webp",
                "content_type": "image/webp",
            }
        ],
        "components": [{"components": [{"custom_id": _VIDEO_UPSCALE_CUSTOM_ID}]}],
    }

    parser = DiscordMessageParser()
    interpreted = parser.interpret("MESSAGE_CREATE", message)
    assert interpreted is not None

    handled = AnimateReactor().handle_message(inst, "MESSAGE_CREATE", interpreted)

    assert handled is True
    assert inst.scheduled_prompt_video_follow_ups == []


@pytest.mark.asyncio
async def test_animate_terminal_prompt_video_result_without_attachment_stays_in_progress():
    """Keep waiting when one prompt-video result still has no direct Discord video reply."""

    t = Job(id="a5", action=JobAction.ANIMATE_LOW, prompt="magic spell")
    t.context.final_prompt = "https://cdn.example/start.png magic spell --video --motion low"
    t.progress = "100%"
    JobStateMachine.apply(t, JobTransition.SUBMIT)
    JobStateMachine.apply(t, JobTransition.START)

    inst = FakeInstance([t])
    message = {
        "id": "msg-6",
        "flags": 0,
        "content": (
            "**https://cdn.example/start.png magic spell --motion low --video 1 --aspect 1:1** - "
            "<@123> [(Open on website for full quality)](https://midjourney.com/jobs/final) (fast)"
        ),
        "attachments": [
            {
                "url": "https://cdn.example.com/final_frame_77aa.webp",
                "filename": "final_frame_77aa.webp",
                "content_type": "image/webp",
            }
        ],
    }

    parser = DiscordMessageParser()
    interpreted = parser.interpret("MESSAGE_CREATE", message)
    assert interpreted is not None

    handled = AnimateReactor().handle_message(inst, "MESSAGE_CREATE", interpreted)

    assert handled is True
    assert t.status == JobStatus.IN_PROGRESS
    assert t.image_url == "https://cdn.example.com/final_frame_77aa.webp"
    assert t.artifacts.website_url == "https://midjourney.com/jobs/final"


@pytest.mark.asyncio
async def test_animate_extend_success_handler_finishes_on_video_reply():
    t = Job(id="a6", action=JobAction.ANIMATE_EXTEND_HIGH)
    t.context.message_id = "prior-video-message"
    t.context.message_hash = "extend-hash"
    JobStateMachine.apply(t, JobTransition.SUBMIT)
    JobStateMachine.apply(t, JobTransition.START)

    inst = FakeInstance([t])
    message = {
        "id": "msg-extend",
        "flags": 0,
        "message_reference": {"message_id": "prior-video-message"},
        "attachments": [
            {
                "url": "https://cdn.example.com/extend.mp4",
                "filename": "extend.mp4",
                "content_type": "video/mp4",
            }
        ],
    }

    parser = DiscordMessageParser()
    interpreted = parser.interpret("MESSAGE_CREATE", message)
    assert interpreted is not None

    handled = AnimateReactor().handle_message(inst, "MESSAGE_CREATE", interpreted)

    assert handled is True
    assert t.status == JobStatus.SUCCEEDED
    assert t.context.index == 1
    assert inst.scheduled_video_indexing == [{"job_id": "a6", "message_id": "msg-extend"}]


@pytest.mark.asyncio
async def test_animate_extend_ignores_source_video_echo_before_new_preview_arrives():
    t = Job(id="a7", action=JobAction.ANIMATE_EXTEND_LOW)
    t.context.message_id = "source-video-message"
    t.context.message_hash = "source-video-hash"
    JobStateMachine.apply(t, JobTransition.SUBMIT)
    JobStateMachine.apply(t, JobTransition.START)

    inst = FakeInstance([t])
    source_video_update = {
        "id": "source-video-message",
        "flags": 0,
        "attachments": [
            {
                "url": "https://cdn.example.com/source-video-hash_1_720_N.mp4",
                "filename": "source-video-hash_1_720_N.mp4",
                "content_type": "video/mp4",
            }
        ],
    }

    parser = DiscordMessageParser()
    interpreted_source = parser.interpret("MESSAGE_UPDATE", source_video_update)
    assert interpreted_source is not None

    handled_source = AnimateReactor().handle_message(inst, "MESSAGE_UPDATE", interpreted_source)

    assert handled_source is False
    assert t.status == JobStatus.IN_PROGRESS
    assert t.artifacts.video_url is None
    assert inst.scheduled_video_indexing == []

    extend_preview = {
        "id": "extend-preview-message",
        "flags": 0,
        "message_reference": {"message_id": "source-video-message"},
        "content": (
            "**idle animation --motion low --bs 1 --video 1 --aspect 1:1** - <@123> "
            "[(Open on website for full quality)]("
            "https://midjourney.com/jobs/bb0707fe-c79f-4f10-85ee-b8edb4300477"
            ") "
            "(fast)"
        ),
        "attachments": [
            {
                "url": "https://cdn.example.com/bb0707fe-c79f-4f10-85ee-b8edb4300477.webp",
                "filename": (
                    "artificialsweetener_idle_animation_bb0707fe-c79f-4f10-85ee-b8edb4300477.webp"
                ),
                "content_type": "image/webp",
            }
        ],
        "components": [{"components": [{"custom_id": _VIDEO_UPSCALE_CUSTOM_ID}]}],
    }

    interpreted_preview = parser.interpret("MESSAGE_CREATE", extend_preview)
    assert interpreted_preview is not None

    handled_preview = AnimateReactor().handle_message(inst, "MESSAGE_CREATE", interpreted_preview)

    assert handled_preview is True
    assert t.status == JobStatus.IN_PROGRESS
    assert t.context.message_id == "extend-preview-message"
    assert t.context.message_hash == "bb0707fe-c79f-4f10-85ee-b8edb4300477"
    assert t.context.prompt_video_follow_up_requested is True
    assert inst.scheduled_prompt_video_follow_ups == [
        {
            "job_id": "a7",
            "message_id": "extend-preview-message",
            "custom_id": _VIDEO_UPSCALE_CUSTOM_ID,
            "message_flags": 0,
        }
    ]


@pytest.mark.asyncio
async def test_animate_extend_ignores_source_hash_video_reply_messages():
    t = Job(id="a8", action=JobAction.ANIMATE_EXTEND_LOW)
    t.context.message_id = "source-video-message"
    t.context.message_hash = "aa4d98b8-fe43-4219-aecf-60945bbd850c"
    JobStateMachine.apply(t, JobTransition.SUBMIT)
    JobStateMachine.apply(t, JobTransition.START)

    inst = FakeInstance([t])
    source_hash_reply = {
        "id": "source-hash-reply",
        "flags": 0,
        "message_reference": {"message_id": "source-preview-message"},
        "attachments": [
            {
                "url": (
                    "https://cdn.discordapp.com/attachments/1390872786410405981/"
                    "1488356025571737713/aa4d98b8-fe43-4219-aecf-60945bbd850c_1_720_N.mp4"
                ),
                "filename": "aa4d98b8-fe43-4219-aecf-60945bbd850c_1_720_N.mp4",
                "content_type": "video/mp4",
            }
        ],
    }

    parser = DiscordMessageParser()
    interpreted_source = parser.interpret("MESSAGE_CREATE", source_hash_reply)
    assert interpreted_source is not None

    handled_source = AnimateReactor().handle_message(inst, "MESSAGE_CREATE", interpreted_source)

    assert handled_source is False
    assert t.status == JobStatus.IN_PROGRESS
    assert t.artifacts.video_url is None

    extend_preview = {
        "id": "extend-preview-message",
        "flags": 0,
        "message_reference": {"message_id": "source-video-message"},
        "content": (
            "**idle animation --motion low --bs 1 --video 1 --aspect 1:1** - <@123> "
            "[(Open on website for full quality)]("
            "https://midjourney.com/jobs/1b977da5-c46c-41c0-a850-54692f41adbe"
            ") (fast)"
        ),
        "attachments": [
            {
                "url": (
                    "https://cdn.example.com/"
                    "artificialsweetener_A_pink-haired_anime_witch_stands_beneath_"
                    "1b977da5-c46c-41c0-a850-54692f41adbe.webp"
                ),
                "filename": (
                    "artificialsweetener_A_pink-haired_anime_witch_stands_beneath_"
                    "1b977da5-c46c-41c0-a850-54692f41adbe.webp"
                ),
                "content_type": "image/webp",
            }
        ],
        "components": [{"components": [{"custom_id": _VIDEO_UPSCALE_CUSTOM_ID}]}],
    }

    interpreted_preview = parser.interpret("MESSAGE_CREATE", extend_preview)
    assert interpreted_preview is not None

    handled_preview = AnimateReactor().handle_message(inst, "MESSAGE_CREATE", interpreted_preview)

    assert handled_preview is True
    assert t.status == JobStatus.IN_PROGRESS
    assert t.context.message_id == "extend-preview-message"
    assert t.context.message_hash == "1b977da5-c46c-41c0-a850-54692f41adbe"
    assert t.context.prompt_video_follow_up_requested is True
