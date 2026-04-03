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
from mutiny.engine.progress import (
    PROMOTION_PROGRESS_KIND,
    PROMOTION_STATUS_TEXT,
    JobProgress,
    build_promotion_progress,
)


def test_job_progress_start_assigns_progress_message_and_prompt():
    progress = JobProgress()
    job = Job(id="j1", action=JobAction.IMAGINE, status=JobStatus.SUBMITTED)
    message = {"id": "m1", "content": "**hello** <@123> (relaxed)"}
    parser = DiscordMessageParser()
    interpreted = parser.interpret("MESSAGE_CREATE", message)
    assert interpreted is not None
    parsed = interpreted.as_progress()

    assert parsed is not None
    event = progress.apply_start(job, interpreted, parsed)

    assert job.status == JobStatus.IN_PROGRESS
    assert job.context.progress_message_id == "m1"
    assert job.context.final_prompt == "hello"
    assert job.context.not_fast is True
    assert event.kind == "start"
    assert event.not_fast is True


def test_job_progress_update_sets_cancel_and_image_fields():
    progress = JobProgress()
    job = Job(id="j2", action=JobAction.IMAGINE, status=JobStatus.IN_PROGRESS)
    job.context.progress_message_id = "m2"
    message = {
        "id": "m2",
        "content": "**hello** <@123> (waiting)",
        "flags": 64,
        "attachments": [{"url": "https://cdn.example/abc_grid_0.webp"}],
        "components": [{"components": [{"custom_id": "MJ::CancelJob::ByJobid::job-123"}]}],
    }
    parser = DiscordMessageParser()
    interpreted = parser.interpret("MESSAGE_CREATE", message)
    assert interpreted is not None
    parsed = interpreted.as_progress()

    assert parsed is not None
    event = progress.apply_progress_update(job, interpreted, parsed)

    assert job.progress == "waiting"
    assert job.context.cancel_message_id == "m2"
    assert job.context.cancel_job_id == "job-123"
    assert job.context.flags == 64
    assert job.image_url == "https://cdn.example/abc_grid_0.webp"
    assert job.context.message_hash == "abc"
    assert event.kind == "progress"
    assert event.flags == 64


def test_build_promotion_progress_uses_promoted_job_surface():
    job = Job(id="j-promo", action=JobAction.PAN_LEFT, status=JobStatus.IN_PROGRESS)
    job.prompt = "castle on a cliff at sunrise"
    job.image_url = "https://cdn.example/promoted.png"
    job.context.message_id = "promoted-message"
    job.context.message_hash = "aa11"
    job.context.flags = 64
    job.context.final_prompt = "castle on a cliff at sunrise"

    event = build_promotion_progress(job)

    assert event.job_id == "j-promo"
    assert event.kind == PROMOTION_PROGRESS_KIND
    assert event.status_text == PROMOTION_STATUS_TEXT
    assert event.prompt == "castle on a cliff at sunrise"
    assert event.progress_message_id is None
    assert event.message_id == "promoted-message"
    assert event.flags == 64
    assert event.image_url == "https://cdn.example/promoted.png"
    assert event.message_hash == "aa11"
    assert event.not_fast is None


def test_job_progress_match_job_normalizes_rewritten_reference_urls():
    progress = JobProgress()
    job = Job(
        id="j3",
        action=JobAction.IMAGINE,
        prompt=(
            "She's taking a closeup selfie and making a funny face --ar 3:4 "
            "--seed 1721175614 --niji 6 --cref https://cdn.example.com/cref.png"
        ),
        status=JobStatus.IN_PROGRESS,
    )
    JobStateMachine.apply(job, JobTransition.START)
    job.context.final_prompt = job.prompt

    class FakeInstance:
        def __init__(self, tasks):
            self._tasks = tasks

        def get_running_job_by_condition(self, predicate):
            return next((tk for tk in self._tasks if predicate(tk)), None)

    parser = DiscordMessageParser()
    interpreted = parser.interpret(
        "MESSAGE_CREATE",
        {
            "id": "m3",
            "content": (
                "**She's taking a closeup selfie and making a funny face --ar 3:4 "
                "--seed 1721175614 --niji 6 --cref https://s.mj.run/CxoXXAGJKlI** "
                "- <@123> (85%) (fast)\nCreate, explore, and organize on midjourney.com"
            ),
        },
    )
    assert interpreted is not None
    parsed = interpreted.as_progress()
    assert parsed is not None

    matched = progress.match_job(
        FakeInstance([job]),
        interaction_id=None,
        nonce=None,
        progress_message_id=None,
        referenced_message_id=None,
        message_hash=None,
        prompt=parsed.prompt,
    )

    assert matched is job


def test_job_progress_match_job_uses_extend_prompt_before_new_hash_exists():
    progress = JobProgress()
    job = Job(
        id="j4",
        action=JobAction.ANIMATE_EXTEND_LOW,
        prompt="idle animation --motion low --bs 1 --video 1 --aspect 1:1",
        status=JobStatus.IN_PROGRESS,
    )
    JobStateMachine.apply(job, JobTransition.START)

    class FakeInstance:
        def __init__(self, tasks):
            self._tasks = tasks

        def get_running_job_by_condition(self, predicate):
            return next((tk for tk in self._tasks if predicate(tk)), None)

    parser = DiscordMessageParser()
    interpreted = parser.interpret(
        "MESSAGE_UPDATE",
        {
            "id": "pm-extend",
            "content": (
                "**idle animation --motion low --bs 1 --video 1 --aspect 1:1** "
                "- <@123> (Waiting to start)"
            ),
            "flags": 64,
        },
    )
    assert interpreted is not None
    parsed = interpreted.as_progress()
    assert parsed is not None

    matched = progress.match_job(
        FakeInstance([job]),
        interaction_id=None,
        nonce=None,
        progress_message_id=None,
        referenced_message_id=None,
        message_hash=None,
        prompt=parsed.prompt,
    )

    assert matched is job
