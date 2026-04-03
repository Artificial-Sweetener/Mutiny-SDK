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
from mutiny.engine.reactors.upscale_reactor import UpscaleReactor


def test_upscale_handler_finishes_v7_like_actions_when_content_matches():
    # Prepare running tasks with different actions but same prompt
    prompt = "Sunlit marble bust"
    t1 = Job(id="t1", action=JobAction.UPSCALE_V7_2X_SUBTLE)
    t1.context.final_prompt = prompt
    JobStateMachine.apply(t1, JobTransition.SUBMIT)
    JobStateMachine.apply(t1, JobTransition.START)
    t2 = Job(id="t2", action=JobAction.PAN_LEFT)
    t2.context.final_prompt = prompt
    JobStateMachine.apply(t2, JobTransition.SUBMIT)
    JobStateMachine.apply(t2, JobTransition.START)

    # Fake instance that exposes the minimal API used by handler
    class FakeInstance:
        def __init__(self, tasks):
            self.tasks = tasks
            self.index_calls = []

        def get_running_job_by_condition(self, predicate):
            return next((tk for tk in self.tasks if predicate(tk)), None)

        def save_and_notify(self, job):  # pragma: no cover - not asserted
            pass

        def _apply_transition(
            self, job: Job, transition: JobTransition, reason: str | None = None
        ) -> bool:
            return JobStateMachine.apply(job, transition, reason)

        def apply_transition(
            self, job: Job, transition: JobTransition, reason: str | None = None
        ) -> bool:
            return JobStateMachine.apply(job, transition, reason)

        def schedule_image_indexing(self, action, message, job):
            self.index_calls.append((action, message.get("id"), job.id))

    inst = FakeInstance([t1, t2])

    # Compose a message that matches UpscaleSuccessListener content regex
    msg = {
        "id": "mid-1",
        "flags": 0,
        "content": f"**{prompt}** - Upscaled by <@123> (fast)",
        "attachments": [{"url": "https://cdn/x/file_abcd1234.png"}],
    }

    parser = DiscordMessageParser()
    interpreted = parser.interpret("MESSAGE_CREATE", msg)
    assert interpreted is not None
    handled = UpscaleReactor().handle_message(inst, "MESSAGE_CREATE", interpreted)
    assert handled is True
    # One of the tasks should be finished; message_id set; indexing scheduled
    done = [tk for tk in (t1, t2) if tk.status == JobStatus.SUCCEEDED]
    assert len(done) == 1
    assert done[0].context.message_id == "mid-1"
    assert inst.index_calls and inst.index_calls[0][0] == JobAction.UPSCALE_V7_2X_SUBTLE
