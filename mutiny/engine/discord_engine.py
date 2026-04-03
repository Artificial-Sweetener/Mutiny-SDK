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

"""Discord execution engine that coordinates queueing, dispatch, and reactors."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Optional

from ..config import Config
from ..discord.identity import DiscordIdentity
from ..discord.message_interpreter import DiscordMessageParser
from ..discord.provider import DiscordProvider
from ..domain.state_machine import JobStateMachine, JobTransition
from ..domain.time import get_current_timestamp_ms
from ..interfaces.image import ImageProcessor
from ..services.cache.artifact_cache import ArtifactCacheService
from ..services.interaction_cache import InteractionCache
from ..services.job_store import JobStore
from ..services.logging_utils import clear_job_context, set_job_context
from ..services.metrics.service import MetricsService
from ..services.notify.event_bus import JobUpdateBus
from ..services.response_dump import ResponseDumpService
from ..services.video_signature import VideoSignatureService
from ..types import Job, JobAction, JobStatus
from .action_dispatcher import ActionContext, execute_action
from .event_bus import JobEventBus
from .events import JobCompleted, ProviderMessageReceived, SystemError
from .execution_policy import EnginePolicy
from .indexing import IndexingCoordinator
from .queue_policy import QueuePolicy
from .reactors.context import ReactorContext
from .reactors.registry import build_reactors
from .runtime.job_lookup import ActiveJobRegistry, JobLookupService
from .timeouts import JobTimeoutScheduler

logger = logging.getLogger(__name__)


class DiscordEngine:
    """Drive Discord provider execution, queueing, and job lifecycle flow."""

    def __init__(
        self,
        identity: DiscordIdentity,
        job_store: JobStore,
        notify_bus: JobUpdateBus,
        *,
        config: Config,
        policy: EnginePolicy,
        artifact_cache: ArtifactCacheService,
        video_signature_service: VideoSignatureService,
        image_processor: ImageProcessor,
        interaction_cache: InteractionCache,
        response_dump: ResponseDumpService,
        metrics: MetricsService,
    ) -> None:
        self.identity = identity
        self.metrics = metrics
        self.policy = policy
        self._event_bus = JobEventBus()
        for reactor in build_reactors():
            self._event_bus.subscribe(ProviderMessageReceived, reactor)
        self.provider = DiscordProvider(
            identity=identity,
            config=config,
            interaction_cache=interaction_cache,
            metrics=metrics,
            response_dump=response_dump,
            message_handler=self.handle_provider_message,
        )
        self.commands = self.provider.commands
        self.message_parser = DiscordMessageParser()
        self.job_store = job_store
        self.notify_bus = notify_bus
        self.artifact_cache = artifact_cache
        self.image_processor = image_processor
        self.interaction_cache = interaction_cache
        self.response_dump = response_dump
        self._active_registry = ActiveJobRegistry(job_store)
        self.job_lookup = JobLookupService(self._active_registry, job_store)
        self.indexer = IndexingCoordinator(
            commands=self.commands,
            image_processor=image_processor,
            artifact_cache=artifact_cache,
            video_signature_service=video_signature_service,
            report_system_error=self._publish_system_error,
        )
        self.reactor_context = ReactorContext(
            lookup=self.job_lookup,
            indexer=self.indexer,
            apply_transition=self._apply_transition,
            save_and_notify=self.save_and_notify,
            schedule_prompt_video_follow_up=self._schedule_prompt_video_follow_up,
            schedule_internal_follow_up_action=self._schedule_internal_follow_up_action,
            notify_bus=notify_bus,
            response_dump=response_dump,
        )
        self.queue = asyncio.Queue[Job](maxsize=policy.queue_size)
        self.semaphore = asyncio.Semaphore(policy.core_size)
        self.video_semaphore = asyncio.Semaphore(policy.video_core_size)
        self._main_task: Optional[asyncio.Task] = None
        self.queue_policy = QueuePolicy(self.queue, metrics=metrics)
        self.timeout_scheduler = JobTimeoutScheduler(
            job_store=job_store,
            notify_bus=notify_bus,
            policy=policy,
        )

    def apply_execution_policy(self, policy: EnginePolicy) -> None:
        """Hot-apply execution policy updates (queue/semaphores/timeouts)."""

        old_policy = self.policy
        self.policy = policy

        # Update queue capacity in place; existing items remain.
        try:
            self.queue_policy.update_limits(policy.queue_size)
        except Exception:
            self.queue._maxsize = policy.queue_size  # type: ignore[attr-defined]

        # Retune semaphores to preserve current acquisition counts while applying new limits.
        self._retune_semaphore(self.semaphore, old_policy.core_size, policy.core_size)
        self._retune_semaphore(
            self.video_semaphore, old_policy.video_core_size, policy.video_core_size
        )

        # Propagate to timeout scheduler
        self.timeout_scheduler.update_policy(policy)

    async def startup(self) -> None:
        """Launch provider, worker, and timeout scheduler tasks if not already running."""
        if self._main_task and not self._main_task.done():
            return
        self._main_task = asyncio.create_task(self._run())

    async def shutdown(self) -> None:
        """Stop all engine tasks and close the Discord provider."""
        if self._main_task:
            self._main_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._main_task
        else:
            await self.indexer.drain_pending()
            await self.provider.close()

    async def submit_job(self, job: Job) -> bool:
        """Enqueue a job for execution using the configured queue policy."""
        return await self.queue_policy.enqueue(job)

    def save_and_notify(self, job: Job):
        self.job_store.save(job)
        self.notify_bus.publish_job(job)
        if job.status in {JobStatus.SUCCEEDED, JobStatus.FAILED}:
            self._event_bus.publish(
                JobCompleted(job=job, finished_at_ms=get_current_timestamp_ms())
            )

    async def _run(self) -> None:
        """Run provider, worker, and timeout scheduler concurrently.

        Captures task-group failures and forwards them to the job event bus without
        mutating provider payloads to preserve behavior-freeze guarantees.
        """
        try:
            async with asyncio.TaskGroup() as tg:
                tg.create_task(self.provider.start())
                tg.create_task(self.worker())
                tg.create_task(self.timeout_scheduler.run())
        except Exception as exc:
            exceptions = getattr(exc, "exceptions", (exc,))
            for err in exceptions:
                self._publish_system_error(
                    err,
                    {"task_group": "engine"},
                )
                logger.exception("Engine task failed")
        finally:
            await self.indexer.drain_pending()
            await self.provider.close()

    def _apply_transition(
        self, job: Job, transition: JobTransition, reason: str | None = None
    ) -> bool:
        ok = JobStateMachine.apply(job, transition, reason)
        if not ok:
            self._event_bus.publish(
                SystemError(
                    source="DiscordEngine",
                    error=RuntimeError(
                        f"Invalid transition {transition.value} from {job.status.value}"
                    ),
                    context={"job_id": job.id},
                    occurred_at_ms=get_current_timestamp_ms(),
                )
            )
        return ok

    def _publish_system_error(self, error: Exception, context: dict[str, object]) -> None:
        """Forward one internal runtime failure to the shared system-error bus."""

        self._event_bus.publish(
            SystemError(
                source="DiscordEngine",
                error=error,
                context=context,
                occurred_at_ms=get_current_timestamp_ms(),
            )
        )

    async def worker(self):
        """Process queued jobs, dispatch provider commands, and manage completion flow."""
        logger.info(f"Worker started for account {self.identity.channel_id}")
        while True:
            job = await self.queue.get()
            self.queue_policy.record_dequeue()
            self._active_registry.add(job.id)
            try:
                if not self.provider.is_ready():
                    self._apply_transition(
                        job, JobTransition.FAIL, "Account not connected to WebSocket"
                    )
                    set_job_context(job_id=job.id, action=job.action.value, status=job.status.value)
                    self.save_and_notify(job)
                    self._log_completion(job)
                    continue

                nonce = str(get_current_timestamp_ms())
                job.context.nonce = nonce
                if not self._apply_transition(job, JobTransition.START):
                    self.save_and_notify(job)
                    self._log_completion(job)
                    continue
                set_job_context(
                    job_id=job.id,
                    action=job.action.value,
                    status=job.status.value,
                )
                if job.start_time:
                    self.metrics.observe_dispatch_latency_ms(
                        max(0, job.start_time - job.submit_time)
                    )
                self.save_and_notify(job)

                result: str | None = None
                sem = (
                    self.video_semaphore
                    if job.action
                    in {
                        JobAction.ANIMATE_HIGH,
                        JobAction.ANIMATE_LOW,
                        JobAction.ANIMATE_EXTEND_HIGH,
                        JobAction.ANIMATE_EXTEND_LOW,
                    }
                    else self.semaphore
                )
                async with sem:
                    action_ctx = self._build_action_context()
                    result = await execute_action(action_ctx, job, nonce)

                if result != "Success":
                    self._apply_transition(
                        job,
                        JobTransition.FAIL,
                        result or "Failed to send command to Discord",
                    )

                if job.fail_reason:
                    self.save_and_notify(job)
                    self._log_completion(job)
                    continue

                try:
                    await asyncio.wait_for(
                        job.completion_event.wait(), timeout=self.policy.timeout_seconds
                    )
                except asyncio.TimeoutError:
                    logger.warning(f"Job {job.id} timed out.")
                    self._apply_transition(
                        job,
                        JobTransition.FAIL,
                        f"Task timed out after {self.policy.task_timeout_minutes} minutes",
                    )
                    self.save_and_notify(job)
                self._log_completion(job)

            except Exception as e:
                logger.exception(f"Error processing job {job.id}: {e}")
                self._apply_transition(job, JobTransition.FAIL, str(e))
                self.save_and_notify(job)
                self._log_completion(job)
            finally:
                self.queue.task_done()
                self.queue_policy.record_dequeue()
                self._active_registry.discard(job.id)
                clear_job_context()

    async def handle_provider_message(self, event_type: str, message: dict) -> None:
        if event_type not in ("MESSAGE_CREATE", "MESSAGE_UPDATE"):
            return
        interpreted = self.message_parser.interpret(event_type, message)
        if not interpreted:
            return
        self._event_bus.publish(
            ProviderMessageReceived(
                event_type=event_type,
                message=interpreted,
                context=self.reactor_context,
                received_at_ms=get_current_timestamp_ms(),
            )
        )

    def has_active_jobs(self) -> bool:
        return self._active_registry.has_active()

    def _schedule_prompt_video_follow_up(
        self,
        job: Job,
        *,
        message_id: str,
        custom_id: str,
        message_flags: int,
    ) -> None:
        """Submit the prompt-video follow-up interaction without blocking reactors."""

        async def _dispatch() -> None:
            nonce = str(get_current_timestamp_ms())
            try:
                result = await self.commands.send_button_interaction(
                    message_id=message_id,
                    custom_id=custom_id,
                    message_flags=message_flags,
                    nonce=nonce,
                )
            except Exception as exc:
                logger.exception(
                    "Prompt-video follow-up dispatch crashed",
                    extra={
                        "job_id": job.id,
                        "message_id": message_id,
                        "custom_id": custom_id,
                    },
                )
                if job.status not in {JobStatus.SUCCEEDED, JobStatus.FAILED}:
                    self._apply_transition(
                        job,
                        JobTransition.FAIL,
                        f"Prompt-video follow-up failed: {exc}",
                    )
                    self.save_and_notify(job)
                return

            if result == "Success":
                logger.info(
                    "Prompt-video follow-up dispatched",
                    extra={
                        "job_id": job.id,
                        "message_id": message_id,
                        "custom_id": custom_id,
                    },
                )
                return

            logger.error(
                "Prompt-video follow-up was rejected",
                extra={
                    "job_id": job.id,
                    "message_id": message_id,
                    "custom_id": custom_id,
                    "result": result,
                },
            )
            if job.status not in {JobStatus.SUCCEEDED, JobStatus.FAILED}:
                self._apply_transition(
                    job,
                    JobTransition.FAIL,
                    result or "Prompt-video follow-up failed",
                )
                self.save_and_notify(job)

        asyncio.create_task(_dispatch())

    def _schedule_internal_follow_up_action(self, job: Job) -> None:
        """Dispatch the next provider action for one multi-step in-flight job.

        This is used for flows where an intermediate message must be observed before
        the originally requested action can be sent, such as implicit tile promotion.
        """

        async def _dispatch() -> None:
            nonce = str(get_current_timestamp_ms())
            job.context.nonce = nonce
            job.context.progress_message_id = None
            job.context.interaction_id = None
            self.save_and_notify(job)
            try:
                result = await execute_action(self._build_action_context(), job, nonce)
            except Exception as exc:
                logger.exception(
                    "Internal follow-up dispatch crashed",
                    extra={"job_id": job.id, "action": job.action.value},
                )
                if job.status not in {JobStatus.SUCCEEDED, JobStatus.FAILED}:
                    self._apply_transition(
                        job,
                        JobTransition.FAIL,
                        f"Internal follow-up failed: {exc}",
                    )
                    self.save_and_notify(job)
                return

            if result == "Success":
                logger.info(
                    "Internal follow-up dispatched",
                    extra={"job_id": job.id, "action": job.action.value},
                )
                return

            logger.error(
                "Internal follow-up was rejected",
                extra={"job_id": job.id, "action": job.action.value, "result": result},
            )
            if job.status not in {JobStatus.SUCCEEDED, JobStatus.FAILED}:
                self._apply_transition(
                    job,
                    JobTransition.FAIL,
                    result or "Internal follow-up failed",
                )
                self.save_and_notify(job)

        asyncio.create_task(_dispatch())

    def _build_action_context(self) -> ActionContext:
        """Build the provider/caching context used by one dispatched provider action."""

        return ActionContext(
            commands=self.commands,
            artifact_cache=self.artifact_cache,
            interaction_cache=self.interaction_cache,
            channel_id=self.identity.channel_id,
        )

    def _log_completion(self, job: Job) -> None:
        latency_ms = None
        if job.finish_time and job.submit_time:
            latency_ms = max(0, job.finish_time - job.submit_time)
        elif job.submit_time:
            latency_ms = max(0, get_current_timestamp_ms() - job.submit_time)
        set_job_context(
            job_id=job.id,
            action=job.action.value,
            status=job.status.value,
            latency_ms=latency_ms,
        )
        logger.info("Job completed")

    @staticmethod
    def _retune_semaphore(sem: asyncio.Semaphore, old_limit: int, new_limit: int) -> None:
        try:
            acquired = max(0, int(old_limit) - int(sem._value))  # type: ignore[attr-defined]
            new_value = max(0, int(new_limit) - acquired)
            sem._value = new_value  # type: ignore[attr-defined]
        except Exception:
            try:
                sem._value = max(0, int(new_limit))  # type: ignore[attr-defined]
            except Exception:
                # Ignore retune failures; concurrency will settle as tasks complete.
                pass


__all__ = ["DiscordEngine"]
