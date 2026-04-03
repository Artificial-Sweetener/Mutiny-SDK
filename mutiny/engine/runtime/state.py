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

"""Runtime state owner that builds and reconfigures Mutiny services."""

from __future__ import annotations

import asyncio
import os
from typing import Optional

from ... import config as config_module
from ...config import Config
from ...discord.identity import DiscordIdentity
from ...engine.discord_engine import DiscordEngine
from ...engine.execution_policy import EnginePolicy
from ...engine.runtime.config_manager import ChangePlan, HotAction, diff_config, plan_changes
from ...services.cache.artifact_cache import ArtifactCacheService
from ...services.cache.cache_paths import resolve_cache_directory
from ...services.context import AppContext, ContextOverrides
from ...services.image_processor import OpenCVImageProcessor
from ...services.interaction_cache import InteractionCache
from ...services.job_store import InMemoryJobStoreService
from ...services.metrics.service import MetricsService
from ...services.notify.event_bus import StreamingJobUpdateBus
from ...services.persistence.persistent_kv import PersistentKV
from ...services.response_dump import ResponseDumpService
from ...services.video_signature import VideoSignatureService


class State:
    """Owns config and runtime services for a Mutiny session."""

    def __init__(
        self,
        config: Optional[Config] = None,
        *,
        context: Optional[AppContext] = None,
        overrides: Optional[ContextOverrides] = None,
    ) -> None:
        if context and overrides:
            raise ValueError("Provide context or overrides, not both")
        if context and config and context.config != config:
            raise ValueError("Config must match the provided context")
        if context and config is None:
            config = context.config
        self._config = config
        if self._config:
            self._validate_single_identity(self._config)
        self._context = context
        self._overrides = overrides or ContextOverrides()
        self._started = context is not None
        self._owned_engine = False
        self._apply_lock = asyncio.Lock()
        self._reconfiguring = False
        self._disk_cache: PersistentKV | None = None

    @property
    def settings(self) -> Config:
        if self._config is None:
            if os.getenv("MJ_USER_TOKEN"):
                self._config = getattr(config_module, "_load_env_config")()
            else:
                raise RuntimeError("Config is required when MJ_USER_TOKEN is not set")
        self._validate_single_identity(self._config)
        return self._config

    @property
    def started(self) -> bool:
        return self._started

    def require_context(self) -> AppContext:
        if not self._context:
            raise RuntimeError("Mutiny is not started")
        if self._reconfiguring:
            raise RuntimeError("Mutiny is applying settings; try again")
        return self._context

    async def apply_settings(self, *, config: Config | None = None, **overrides) -> None:
        async with self._apply_lock:
            current_cfg = self.settings
            if config is not None and not isinstance(config, Config):
                raise TypeError("config must be a Config instance")
            source_cfg = config if config is not None else current_cfg
            new_cfg = source_cfg.configure(**overrides)
            self._validate_single_identity(new_cfg)

            if not self._started:
                self._config = new_cfg
                return

            plan = plan_changes(diff_config(current_cfg, new_cfg))
            self._reconfiguring = True
            try:
                if plan.requires_restart:
                    await self._apply_with_restart(new_cfg, plan)
                else:
                    await self._apply_hot(new_cfg, plan)
                self._config = new_cfg
            finally:
                self._reconfiguring = False

    async def start(self) -> None:
        if self._started:
            return
        cfg = self.settings
        self._validate_single_identity(cfg)

        ctx, owned_engine = await self._build_runtime(
            cfg,
            overrides=self._overrides,
            base_ctx=None,
            rebuild_response_dump=False,
            force_new_engine=False,
        )

        self._context = ctx
        self._owned_engine = owned_engine
        self._started = True

    async def _apply_with_restart(self, new_cfg: Config, plan: ChangePlan) -> None:
        """Apply settings that require a full engine restart with idle guard.

        Raises if the engine is externally owned or jobs are active; rebuilds
        response dump and cache wiring to mirror the new config before
        reinitializing the engine.
        """
        if not self._owned_engine:
            raise RuntimeError(
                "Cannot restart engine while using an externally provided engine; restart Mutiny"
            )
        ctx = self._context
        if not ctx:
            raise RuntimeError("Mutiny is not started")
        engine = ctx.engine
        if engine is None:
            raise RuntimeError("Engine is not initialized")

        idle = await self._wait_for_engine_idle(engine)
        if not idle:
            reasons = "; ".join(plan.restart_reasons) or "restart required"
            raise RuntimeError(
                "Cannot apply settings while jobs are active; try again later. "
                f"Pending restart reasons: {reasons}"
            )

        await engine.shutdown()

        new_context, owned_engine = await self._build_runtime(
            new_cfg,
            overrides=self._overrides,
            base_ctx=ctx,
            rebuild_response_dump=True,
            force_new_engine=True,
        )

        self._context = new_context
        self._owned_engine = owned_engine

    async def _apply_hot(self, new_cfg: Config, plan: ChangePlan) -> None:
        """Apply hot-configurable settings without restarting the engine.

        Guards on active jobs when hot actions require idle, refreshes cache and
        response-dump config, and triggers provider reconfiguration when
        transports or policy change.
        """
        ctx = self._context
        if not ctx:
            raise RuntimeError("Mutiny is not started")
        engine = ctx.engine
        if not engine:
            raise RuntimeError("Engine is not initialized")

        idle_guard_actions = {
            HotAction.UPDATE_HTTP,
            HotAction.UPDATE_CDN,
            HotAction.UPDATE_WEBSOCKET,
            HotAction.UPDATE_EXECUTION,
        }
        pending_idle = [a for a in plan.hot_actions if a in idle_guard_actions]
        if pending_idle:
            idle = await self._wait_for_engine_idle(engine, timeout_s=0.0)
            if not idle:
                kinds = ", ".join(sorted(a.name.lower() for a in pending_idle))
                raise RuntimeError(
                    "Cannot apply settings while jobs are active; hot actions require idle: "
                    f"{kinds}"
                )

        # Track which components we update to avoid repeated work
        needs_provider_refresh = False

        for action in plan.hot_actions:
            if action == HotAction.UPDATE_CACHE:
                disk_kv = self._build_disk_cache(new_cfg)
                ctx.artifact_cache.apply_config(
                    image_cache_ttl_seconds=new_cfg.cache.image_cache_ttl_seconds,
                    image_cache_max_entries=new_cfg.cache.image_cache_max_entries,
                    job_index_ttl_seconds=new_cfg.cache.job_index_ttl_seconds,
                    job_index_max_entries=new_cfg.cache.job_index_max_entries,
                    ram_max_bytes=new_cfg.cache.artifact_cache_ram_max_bytes,
                    disk=disk_kv if new_cfg.cache.disk_cache_enabled else None,
                )
            if action == HotAction.UPDATE_RESPONSE_DUMP:
                if not engine:
                    raise RuntimeError("Engine is not initialized")
                ctx.response_dump.apply_config(
                    root_dir=new_cfg.cache.response_dump_dir,
                    enabled=new_cfg.websocket.capture_enabled,
                )
                needs_provider_refresh = True
            if action in (HotAction.UPDATE_HTTP, HotAction.UPDATE_CDN, HotAction.UPDATE_WEBSOCKET):
                if not engine:
                    raise RuntimeError("Engine is not initialized")
                needs_provider_refresh = True
            if action == HotAction.UPDATE_EXECUTION:
                if not engine:
                    raise RuntimeError("Engine is not initialized")
                policy = EnginePolicy(new_cfg.engine.execution)
                engine.apply_execution_policy(policy)

        if needs_provider_refresh:
            if not engine:
                raise RuntimeError("Engine is not initialized")
            await engine.provider.apply_config(config=new_cfg, response_dump=ctx.response_dump)

        ctx.config = new_cfg

    async def _wait_for_engine_idle(self, engine: DiscordEngine, timeout_s: float = 10.0) -> bool:
        """Poll the engine queue and active jobs until idle or timeout.

        Returns True when idle, False on timeout; never raises to avoid breaking
        reconfiguration flows.
        """
        loop = asyncio.get_running_loop()
        if engine.queue.empty() and not engine.has_active_jobs():
            return True
        deadline = loop.time() + timeout_s
        while loop.time() < deadline:
            if engine.queue.empty() and not engine.has_active_jobs():
                return True
            await asyncio.sleep(0.1)
        return False

    async def _build_runtime(
        self,
        cfg: Config,
        *,
        overrides: ContextOverrides,
        base_ctx: AppContext | None,
        rebuild_response_dump: bool,
        force_new_engine: bool,
    ) -> tuple[AppContext, bool]:
        """Compose runtime services and engine from config/overrides/base context."""

        job_store = overrides.job_store or (
            base_ctx.job_store if base_ctx else InMemoryJobStoreService()
        )
        notify_bus = overrides.notify_bus or (
            base_ctx.notify_bus if base_ctx else StreamingJobUpdateBus()
        )

        artifact_cache = overrides.artifact_cache or (
            base_ctx.artifact_cache
            if base_ctx
            else ArtifactCacheService(
                image_cache_ttl_seconds=cfg.cache.image_cache_ttl_seconds,
                image_cache_max_entries=cfg.cache.image_cache_max_entries,
                job_index_ttl_seconds=cfg.cache.job_index_ttl_seconds,
                job_index_max_entries=cfg.cache.job_index_max_entries,
                ram_max_bytes=cfg.cache.artifact_cache_ram_max_bytes,
            )
        )
        video_signature_service = overrides.video_signature_service or (
            base_ctx.video_signature_service if base_ctx else VideoSignatureService()
        )

        image_processor = (
            base_ctx.image_processor
            if base_ctx and base_ctx.image_processor
            else OpenCVImageProcessor()
        )

        disk_kv = self._build_disk_cache(cfg)
        artifact_cache.apply_config(
            image_cache_ttl_seconds=cfg.cache.image_cache_ttl_seconds,
            image_cache_max_entries=cfg.cache.image_cache_max_entries,
            job_index_ttl_seconds=cfg.cache.job_index_ttl_seconds,
            job_index_max_entries=cfg.cache.job_index_max_entries,
            ram_max_bytes=cfg.cache.artifact_cache_ram_max_bytes,
            disk=disk_kv if cfg.cache.disk_cache_enabled else None,
        )

        if rebuild_response_dump:
            response_dump = ResponseDumpService(
                root_dir=cfg.cache.response_dump_dir,
                enabled=cfg.websocket.capture_enabled,
            )
        else:
            response_dump = (
                overrides.response_dump
                or (base_ctx.response_dump if base_ctx else None)
                or ResponseDumpService(
                    root_dir=cfg.cache.response_dump_dir,
                    enabled=cfg.websocket.capture_enabled,
                )
            )

        interaction_cache = overrides.interaction_cache or (
            base_ctx.interaction_cache if base_ctx else InteractionCache()
        )
        metrics = overrides.metrics or (base_ctx.metrics if base_ctx else MetricsService())

        engine = (
            None
            if force_new_engine
            else overrides.engine or (base_ctx.engine if base_ctx else None)
        )
        owned_engine = False
        if engine is None:
            identity = DiscordIdentity(
                guild_id=cfg.discord.guild_id,
                channel_id=cfg.discord.channel_id,
                token_provider=cfg.token_provider,
                user_agent=cfg.discord.user_agent,
            )
            policy = EnginePolicy(cfg.engine.execution)
            engine = DiscordEngine(
                identity=identity,
                job_store=job_store,
                notify_bus=notify_bus,
                config=cfg,
                policy=policy,
                artifact_cache=artifact_cache,
                video_signature_service=video_signature_service,
                image_processor=image_processor,
                interaction_cache=interaction_cache,
                response_dump=response_dump,
                metrics=metrics,
            )
            await engine.startup()
            owned_engine = True

        context = AppContext(
            config=cfg,
            job_store=job_store,
            notify_bus=notify_bus,
            artifact_cache=artifact_cache,
            video_signature_service=video_signature_service,
            image_processor=image_processor,
            response_dump=response_dump,
            interaction_cache=interaction_cache,
            metrics=metrics,
            engine=engine,
        )

        return context, owned_engine

    def _validate_single_identity(self, cfg: Config) -> None:
        if not isinstance(cfg.discord.guild_id, str) or not isinstance(cfg.discord.channel_id, str):
            raise ValueError(
                "Mutiny is single-account; provide exactly one guild_id and one channel_id"
            )
        token_provider = cfg.token_provider
        if isinstance(token_provider, (list, tuple, set, dict)):
            raise ValueError("Mutiny expects a single token provider instance, not a collection")
        if not callable(getattr(token_provider, "get_token", None)):
            raise ValueError("token_provider must expose a get_token() method")

    async def close(self) -> None:
        if not self._started:
            return
        if self._owned_engine and self._context and self._context.engine:
            await self._context.engine.shutdown()
        if self._disk_cache:
            self._disk_cache.close()
        if self._context:
            await self._context.notify_bus.close()
        self._started = False

    async def wait_ready(self, timeout_s: int | None = None) -> bool:
        if timeout_s is None:
            timeout_s = 180
        deadline = asyncio.get_event_loop().time() + timeout_s
        while asyncio.get_event_loop().time() < deadline:
            try:
                eng = self._context.engine if self._context else None
                if eng:
                    provider = eng.provider
                    if provider and provider.is_ready():
                        return True
            except Exception:
                pass
            await asyncio.sleep(1)
        return False

    def _build_disk_cache(self, cfg: Config) -> PersistentKV | None:
        """Create or reuse the disk cache store based on cache config.

        Closes and clears existing stores when disabled, reuses the current
        handle when path/size match, and otherwise rebuilds backing storage for
        new disk cache settings.
        """
        cache_cfg = cfg.cache
        if not cache_cfg.disk_cache_enabled:
            if self._disk_cache:
                self._disk_cache.close()
            self._disk_cache = None
            return None
        cache_dir = resolve_cache_directory(cache_cfg.disk_cache_dir)
        path = str((cache_dir / "kv.sqlite").resolve())
        # Reuse if path/size unchanged
        if (
            self._disk_cache
            and self._disk_cache.db_path == path
            and (self._disk_cache.max_total_bytes == cache_cfg.disk_cache_max_bytes)
        ):
            return self._disk_cache
        if self._disk_cache:
            self._disk_cache.close()
        self._disk_cache = PersistentKV(path, max_total_bytes=cache_cfg.disk_cache_max_bytes)
        return self._disk_cache


__all__ = ["State"]
