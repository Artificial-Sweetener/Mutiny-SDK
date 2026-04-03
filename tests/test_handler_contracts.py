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
from pathlib import Path

from mutiny.discord.message_interpreter import DiscordMessageParser
from mutiny.domain.job import Job, JobAction
from mutiny.domain.state_machine import JobStateMachine, JobTransition
from mutiny.engine.reactors.error_reactor import ErrorReactor
from mutiny.engine.reactors.progress_reactor import ProgressReactor

SNAPSHOT_DIR = Path(__file__).resolve().parent / "snapshots" / "discord_contracts"


def _canonical(obj: object) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _snapshot_text(name: str) -> str:
    path = SNAPSHOT_DIR / f"{name}.json"
    assert path.exists(), f"Missing snapshot: {path}"
    return path.read_text(encoding="utf-8").rstrip("\r\n")


def _assert_snapshot(name: str, obj: object) -> None:
    assert _canonical(obj) == _snapshot_text(name)


class _FakeInstance:
    def __init__(self, tasks):
        self.tasks = tasks
        self.saved = []
        self.notify_bus = _FakeNotifyBus()

    def get_running_job_by_condition(self, predicate):
        return next((t for t in self.tasks if predicate(t)), None)

    def save_and_notify(self, job: Job):
        self.saved.append(job)

    def _apply_transition(
        self, job: Job, transition: JobTransition, reason: str | None = None
    ) -> bool:
        return JobStateMachine.apply(job, transition, reason)

    def apply_transition(
        self, job: Job, transition: JobTransition, reason: str | None = None
    ) -> bool:
        return JobStateMachine.apply(job, transition, reason)


class _FakeNotifyBus:
    def publish_progress(self, event):  # pragma: no cover - not used
        return None


def test_error_embed_failure_reason_snapshot():
    t = Job(id="t1", action=JobAction.IMAGINE)
    JobStateMachine.apply(t, JobTransition.SUBMIT)
    JobStateMachine.apply(t, JobTransition.START)
    t.context.progress_message_id = "pm1"
    inst = _FakeInstance([t])

    msg = {
        "embeds": [{"color": 15548997, "title": "Error", "description": "bad"}],
        "message_reference": {"message_id": "pm1"},
    }
    parser = DiscordMessageParser()
    interpreted = parser.interpret("MESSAGE_CREATE", msg)
    assert interpreted is not None
    handled = ErrorReactor().handle_message(inst, "MESSAGE_CREATE", interpreted)
    assert handled is True
    _assert_snapshot("error_embed_failure_reason", {"fail_reason": t.fail_reason})


def test_decline_error_failure_reason_snapshot():
    t = Job(id="t1b", action=JobAction.IMAGINE)
    JobStateMachine.apply(t, JobTransition.SUBMIT)
    JobStateMachine.apply(t, JobTransition.START)
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
    parser = DiscordMessageParser()
    interpreted = parser.interpret("MESSAGE_CREATE", msg)
    assert interpreted is not None
    handled = ErrorReactor().handle_message(inst, "MESSAGE_CREATE", interpreted)
    assert handled is True
    _assert_snapshot("decline_error_failure_reason", {"fail_reason": t.fail_reason})


def test_cancel_button_discovery_snapshot():
    t = Job(id="t2", action=JobAction.IMAGINE)
    JobStateMachine.apply(t, JobTransition.SUBMIT)
    JobStateMachine.apply(t, JobTransition.START)
    t.context.progress_message_id = "pm2"
    inst = _FakeInstance([t])

    msg = {
        "id": "pm2",
        "content": "**Prompt** - <@123> (fast 25%)",
        "flags": 64,
        "interaction": {"id": "ix-3", "name": "imagine"},
        "components": [{"components": [{"custom_id": "MJ::CancelJob::ByJobid::job-1"}]}],
    }
    parser = DiscordMessageParser()
    interpreted = parser.interpret("MESSAGE_CREATE", msg)
    assert interpreted is not None
    handled = ProgressReactor().handle_message(inst, "MESSAGE_CREATE", interpreted)
    assert handled is True
    _assert_snapshot(
        "cancel_button_discovery",
        {
            "cancel_message_id": t.context.cancel_message_id,
            "cancel_job_id": t.context.cancel_job_id,
            "flags": t.context.flags,
        },
    )
