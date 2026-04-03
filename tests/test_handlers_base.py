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

from mutiny.discord.message_interpreter import DiscordMessageParser, extract_message_hash
from mutiny.domain.job import Job, JobAction, JobStatus
from mutiny.domain.state_machine import JobStateMachine, JobTransition
from mutiny.engine.reactors.base import MessageReactor


def test_event_listener_static_helpers():
    # image url extraction
    msg = {"attachments": [{"url": "https://cdn.example.com/path/abc_12345_grid_0.webp"}]}
    parser = DiscordMessageParser()
    interpreted = parser.interpret("MESSAGE_CREATE", msg)
    assert interpreted is not None
    assert interpreted.image_url == msg["attachments"][0]["url"]
    # hash extraction handles special pattern
    assert extract_message_hash(msg["attachments"][0]["url"]) == "abc_12345"
    # generic filename pattern
    url2 = "https://cdn.example.com/dir/image_abcd1234.png"
    assert extract_message_hash(url2) == "abcd1234"
    # final prompt-video mp4 replies embed the actual MJ job hash before suffix tokens
    url3 = (
        "https://cdn.discordapp.com/attachments/123/456/"
        "3dabc83d-4d24-4f89-aea8-c1c8c112a3ca_1_720_N.mp4?ex=123&is=456"
    )
    assert extract_message_hash(url3) == "3dabc83d-4d24-4f89-aea8-c1c8c112a3ca"


def test_find_and_finish_image_job_happy_path():
    # Prepare a running task that matches final_prompt
    t = Job(id="x1", action=JobAction.UPSCALE)
    t.context.final_prompt = "My prompt"
    JobStateMachine.apply(t, JobTransition.SUBMIT)
    JobStateMachine.apply(t, JobTransition.START)
    assert t.status == JobStatus.IN_PROGRESS

    # Fake instance with active task and a save hook
    class FakeInstance:
        def __init__(self, tasks):
            self._tasks = tasks
            self.saved = []

        def get_running_job_by_condition(self, predicate):
            return next((tk for tk in self._tasks if predicate(tk)), None)

        def save_and_notify(self, job):
            self.saved.append(job)

        def _apply_transition(
            self, job: Job, transition: JobTransition, reason: str | None = None
        ) -> bool:
            return JobStateMachine.apply(job, transition, reason)

        def apply_transition(
            self, job: Job, transition: JobTransition, reason: str | None = None
        ) -> bool:
            return JobStateMachine.apply(job, transition, reason)

    instance = FakeInstance([t])

    # Incoming message with attachment and an id
    msg = {
        "id": "mid",
        "flags": 64,
        "attachments": [{"url": "https://cdn.example.com/path/file_abcd1234.png"}],
    }

    class DummyListener(MessageReactor):
        def handle_message(self, instance, event_type: str, message: dict) -> bool:
            return False

    parser = DiscordMessageParser()
    interpreted = parser.interpret("MESSAGE_CREATE", msg)
    assert interpreted is not None
    handled = DummyListener().find_and_finish_image_job(
        instance, JobAction.UPSCALE, "My prompt", interpreted
    )
    assert handled is t
    assert t.status == JobStatus.SUCCEEDED
    assert t.context.message_id == "mid"
    assert t.context.message_hash == "abcd1234"
    assert t.context.flags == 64
    assert instance.saved == [t]


def test_find_and_finish_image_job_normalizes_rewritten_reference_urls():
    prompt = (
        "She's taking a closeup selfie and making a funny face --ar 3:4 "
        "--seed 1721175614 --niji 6 --cref https://cdn.example.com/cref.png"
    )
    t = Job(id="x2", action=JobAction.IMAGINE)
    t.context.final_prompt = prompt
    JobStateMachine.apply(t, JobTransition.SUBMIT)
    JobStateMachine.apply(t, JobTransition.START)
    assert t.status == JobStatus.IN_PROGRESS

    class FakeInstance:
        def __init__(self, tasks):
            self._tasks = tasks
            self.saved = []

        def get_running_job_by_condition(self, predicate):
            return next((tk for tk in self._tasks if predicate(tk)), None)

        def save_and_notify(self, job):
            self.saved.append(job)

        def apply_transition(
            self, job: Job, transition: JobTransition, reason: str | None = None
        ) -> bool:
            return JobStateMachine.apply(job, transition, reason)

    instance = FakeInstance([t])
    msg = {
        "id": "mid2",
        "content": (
            "**She's taking a closeup selfie and making a funny face --ar 3:4 "
            "--seed 1721175614 --niji 6 --cref https://s.mj.run/CxoXXAGJKlI** "
            "- <@123> (fast)"
        ),
        "attachments": [{"url": "https://cdn.example.com/path/abc_98765_grid_0.webp"}],
    }

    class DummyListener(MessageReactor):
        def handle_message(self, instance, event_type: str, message: dict) -> bool:
            return False

    parser = DiscordMessageParser()
    interpreted = parser.interpret("MESSAGE_CREATE", msg)
    assert interpreted is not None
    handled = DummyListener().find_and_finish_image_job(
        instance,
        JobAction.IMAGINE,
        interpreted.prompt or "",
        interpreted,
    )

    assert handled is t
    assert t.status == JobStatus.SUCCEEDED
    assert t.context.message_id == "mid2"
    assert t.context.message_hash == "abc_98765"
    assert instance.saved == [t]


def test_find_and_finish_image_job_can_require_a_new_result_message():
    t = Job(id="x3", action=JobAction.UPSCALE_V7_2X_SUBTLE)
    t.context.final_prompt = "Mage portrait"
    t.context.message_id = "source-message"
    t.context.message_hash = "source-hash"
    JobStateMachine.apply(t, JobTransition.SUBMIT)
    JobStateMachine.apply(t, JobTransition.START)
    assert t.status == JobStatus.IN_PROGRESS

    class FakeInstance:
        def __init__(self, tasks):
            self._tasks = tasks
            self.saved = []

        def get_running_job_by_condition(self, predicate):
            return next((tk for tk in self._tasks if predicate(tk)), None)

        def save_and_notify(self, job):
            self.saved.append(job)

        def apply_transition(
            self, job: Job, transition: JobTransition, reason: str | None = None
        ) -> bool:
            return JobStateMachine.apply(job, transition, reason)

    instance = FakeInstance([t])
    msg = {
        "id": "source-message",
        "content": "**Mage portrait** - Image #4 <@123>",
        "attachments": [{"url": "https://cdn.example.com/path/file_samehash.png"}],
    }

    class DummyListener(MessageReactor):
        def handle_message(self, instance, event_type: str, message: dict) -> bool:
            return False

    parser = DiscordMessageParser()
    interpreted = parser.interpret("MESSAGE_UPDATE", msg)
    assert interpreted is not None
    handled = DummyListener().find_and_finish_image_job(
        instance,
        JobAction.UPSCALE_V7_2X_SUBTLE,
        interpreted.prompt or "",
        interpreted,
        require_new_message=True,
    )

    assert handled is None
    assert t.status == JobStatus.IN_PROGRESS
    assert instance.saved == []
