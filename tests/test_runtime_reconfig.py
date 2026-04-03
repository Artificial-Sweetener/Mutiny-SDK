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

import pytest

from mutiny.config import Config
from mutiny.discord.gateway_client import DiscordGatewayClient
from mutiny.discord.identity import DiscordIdentity, DiscordSessionState
from mutiny.discord.rest_client import DiscordRestClient
from mutiny.engine.runtime.state import State
from mutiny.services.cache.artifact_cache import ArtifactCacheService
from mutiny.services.context import AppContext, ContextOverrides
from mutiny.services.interaction_cache import InteractionCache
from mutiny.services.job_store import InMemoryJobStoreService
from mutiny.services.metrics.service import MetricsService
from mutiny.services.notify.event_bus import StreamingJobUpdateBus
from mutiny.services.response_dump import ResponseDumpService


class _FakeGateway:
    def __init__(self, response_dump: ResponseDumpService):
        self.response_dump = response_dump


class _FakeProvider:
    def __init__(self, response_dump: ResponseDumpService):
        self._response_dump = response_dump
        self.gateway = _FakeGateway(response_dump)
        self.commands = object()
        self.apply_config_calls: list = []

    async def apply_config(self, *, config, response_dump: ResponseDumpService):
        self.apply_config_calls.append(config)
        self._response_dump = response_dump
        self.gateway.response_dump = response_dump


class _FakeEngine:
    def __init__(self, *_, response_dump: ResponseDumpService, **__):
        self.queue: asyncio.Queue = asyncio.Queue()
        self.active_job_ids: set[str] = set()
        self.provider = _FakeProvider(response_dump)
        self.started = False
        self.shutdown_called = False
        self.policy = None
        self.semaphore = asyncio.Semaphore(3)
        self.video_semaphore = asyncio.Semaphore(1)

    async def startup(self) -> None:
        self.started = True

    async def shutdown(self) -> None:
        self.shutdown_called = True

    def has_active_jobs(self) -> bool:
        return bool(self.active_job_ids)

    def apply_execution_policy(self, policy) -> None:
        # Minimal tracking to confirm update was invoked
        self.policy = policy
        try:
            self.queue._maxsize = policy.queue_size  # type: ignore[attr-defined]
        except Exception:
            pass


class _FakeAsyncClient:
    def __init__(self, *_, **kwargs):
        self.kwargs = kwargs
        self.closed = False

    async def aclose(self):
        self.closed = True


def _ctx(cfg: Config, response_dump: ResponseDumpService, engine=None) -> AppContext:
    return AppContext(
        config=cfg,
        job_store=InMemoryJobStoreService(),
        notify_bus=StreamingJobUpdateBus(),
        artifact_cache=ArtifactCacheService(),
        response_dump=response_dump,
        interaction_cache=InteractionCache(),
        metrics=MetricsService(),
        engine=engine,
    )


@pytest.mark.asyncio
async def test_start_respects_overrides_and_external_engine(test_config):
    cfg = test_config.copy()
    response_dump = ResponseDumpService(enabled=False)
    engine = _FakeEngine(response_dump=response_dump)

    overrides = ContextOverrides(
        job_store=InMemoryJobStoreService(),
        notify_bus=StreamingJobUpdateBus(),
        artifact_cache=ArtifactCacheService(),
        response_dump=response_dump,
        interaction_cache=InteractionCache(),
        metrics=MetricsService(),
        engine=engine,
    )

    state = State(config=cfg, overrides=overrides)

    await state.start()

    ctx = state.require_context()
    assert ctx.engine is engine
    assert ctx.response_dump is response_dump
    assert ctx.job_store is overrides.job_store
    assert ctx.artifact_cache is overrides.artifact_cache
    assert state._owned_engine is False


@pytest.mark.asyncio
async def test_apply_settings_rejects_removed_feature_overrides(test_config):
    cfg = test_config.copy()
    response_dump = ResponseDumpService(enabled=False)
    ctx = _ctx(cfg, response_dump=response_dump, engine=_FakeEngine(response_dump=response_dump))
    state = State(context=ctx)
    state._owned_engine = True

    with pytest.raises(KeyError, match="Unknown config section: features"):
        await state.apply_settings(features={"custom_zoom": False})


@pytest.mark.asyncio
async def test_apply_settings_accepts_config_snapshot(test_config):
    cfg = test_config.copy()
    response_dump = ResponseDumpService(enabled=False)
    ctx = _ctx(cfg, response_dump=response_dump, engine=_FakeEngine(response_dump=response_dump))
    state = State(context=ctx)
    state._owned_engine = True
    replacement = cfg.configure(cache={"disk_cache_enabled": False})

    await state.apply_settings(config=replacement)

    assert state.settings.cache.disk_cache_enabled is False


@pytest.mark.asyncio
async def test_apply_settings_config_and_overrides_prioritizes_overrides(test_config):
    cfg = test_config.copy()
    response_dump = ResponseDumpService(enabled=False)
    ctx = _ctx(cfg, response_dump=response_dump, engine=_FakeEngine(response_dump=response_dump))
    state = State(context=ctx)
    state._owned_engine = True
    replacement = cfg.configure(cache={"disk_cache_enabled": False})

    await state.apply_settings(config=replacement, cache={"disk_cache_enabled": True})

    assert state.settings.cache.disk_cache_enabled is True


@pytest.mark.asyncio
async def test_apply_settings_rejects_non_config_snapshot(test_config):
    cfg = test_config.copy()
    response_dump = ResponseDumpService(enabled=False)
    ctx = _ctx(cfg, response_dump=response_dump, engine=_FakeEngine(response_dump=response_dump))
    state = State(context=ctx)
    state._owned_engine = True

    with pytest.raises(TypeError):
        await state.apply_settings(config=cfg.as_dict())  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_apply_settings_allows_config_before_start(test_config):
    cfg = test_config.copy()
    replacement = cfg.configure(cache={"disk_cache_enabled": False})
    state = State(config=cfg)

    await state.apply_settings(config=replacement)

    assert state.started is False
    assert state.settings.cache.disk_cache_enabled is False


@pytest.mark.asyncio
async def test_hot_apply_response_dump_toggles(monkeypatch, test_config):
    cfg = test_config.copy()
    response_dump = ResponseDumpService(enabled=False)
    engine = _FakeEngine(response_dump=response_dump)
    ctx = _ctx(cfg, response_dump=response_dump, engine=engine)
    state = State(context=ctx)
    state._owned_engine = True

    await state.apply_settings(websocket={"capture_enabled": True})

    assert engine.provider._response_dump.is_enabled()
    assert engine.provider.gateway.response_dump.is_enabled()
    assert state.settings.websocket.capture_enabled is True
    assert engine.provider.apply_config_calls, "provider apply_config should be called"


@pytest.mark.asyncio
async def test_hot_apply_reuses_engine_and_refreshes_provider(test_config):
    cfg = test_config.copy()
    response_dump = ResponseDumpService(enabled=False)
    engine = _FakeEngine(response_dump=response_dump)
    ctx = _ctx(cfg, response_dump=response_dump, engine=engine)
    state = State(context=ctx)
    state._owned_engine = True

    await state.apply_settings(http={"read_timeout": cfg.http.read_timeout + 1})

    assert state.require_context().engine is engine
    assert engine.provider.apply_config_calls, "provider apply_config should be called"
    assert state.settings.http.read_timeout == cfg.http.read_timeout + 1


@pytest.mark.asyncio
async def test_hot_apply_cache_and_disk(tmp_path, test_config):
    cfg = test_config.copy()
    response_dump = ResponseDumpService(enabled=False)
    engine = _FakeEngine(response_dump=response_dump)
    ctx = _ctx(cfg, response_dump=response_dump, engine=engine)
    state = State(context=ctx)
    state._owned_engine = True

    disk_dir = tmp_path / "cache"
    await state.apply_settings(
        cache={
            "image_cache_ttl_seconds": 1,
            "image_cache_max_entries": 1,
            "artifact_cache_ram_max_bytes": 1024,
            "disk_cache_enabled": True,
            "disk_cache_dir": str(disk_dir),
            "disk_cache_max_bytes": 1024,
        }
    )

    state.require_context().artifact_cache.put_image_upload("k", "v")
    assert state.require_context().artifact_cache.get_image_upload_url("k") == "v"


@pytest.mark.asyncio
async def test_hot_apply_execution_updates_policy(test_config):
    cfg = test_config.copy()
    response_dump = ResponseDumpService(enabled=False)
    engine = _FakeEngine(response_dump=response_dump)
    ctx = _ctx(cfg, response_dump=response_dump, engine=engine)
    state = State(context=ctx)
    state._owned_engine = True

    await state.apply_settings(engine={"execution": {"queue_size": 5, "core_size": 2}})

    assert engine.policy is not None
    assert getattr(engine.queue, "_maxsize", None) == 5


@pytest.mark.asyncio
async def test_restart_on_identity_change_rebuilds_engine(monkeypatch, test_config):
    cfg = test_config.copy()
    response_dump = ResponseDumpService(enabled=False)
    engine = _FakeEngine(response_dump=response_dump)
    ctx = _ctx(cfg, response_dump=response_dump, engine=engine)
    state = State(context=ctx)
    state._owned_engine = True

    original_job_store = ctx.job_store
    original_cache = ctx.artifact_cache
    original_metrics = ctx.metrics
    original_interaction_cache = ctx.interaction_cache

    monkeypatch.setattr("mutiny.engine.runtime.state.DiscordEngine", _FakeEngine)

    await state.apply_settings(discord={"guild_id": "new-guild"})

    ctx_after = state.require_context()
    assert isinstance(ctx_after.engine, _FakeEngine)
    assert ctx_after.config.discord.guild_id == "new-guild"
    assert ctx_after.job_store is original_job_store
    assert ctx_after.artifact_cache is original_cache
    assert ctx_after.metrics is original_metrics
    assert ctx_after.interaction_cache is original_interaction_cache
    assert ctx_after.response_dump is not response_dump


@pytest.mark.asyncio
async def test_restart_rejected_with_external_engine(test_config):
    cfg = test_config.copy()
    response_dump = ResponseDumpService(enabled=False)
    engine = _FakeEngine(response_dump=response_dump)
    ctx = _ctx(cfg, response_dump=response_dump, engine=engine)
    state = State(context=ctx)

    with pytest.raises(RuntimeError):
        await state.apply_settings(discord={"guild_id": "g2"})


@pytest.mark.asyncio
async def test_restart_rejected_when_jobs_active(monkeypatch, test_config):
    cfg = test_config.copy()
    response_dump = ResponseDumpService(enabled=False)
    engine = _FakeEngine(response_dump=response_dump)
    await engine.queue.put("job")
    engine.active_job_ids.add("job-1")
    ctx = _ctx(cfg, response_dump=response_dump, engine=engine)
    state = State(context=ctx)
    state._owned_engine = True

    monkeypatch.setattr("mutiny.engine.runtime.state.DiscordEngine", _FakeEngine)

    with pytest.raises(RuntimeError):
        await state.apply_settings(discord={"guild_id": "g2"})


@pytest.mark.asyncio
async def test_hot_apply_network_guard_when_jobs_active(test_config):
    cfg = test_config.copy()
    response_dump = ResponseDumpService(enabled=False)
    engine = _FakeEngine(response_dump=response_dump)
    await engine.queue.put("job")
    engine.active_job_ids.add("job-1")
    ctx = _ctx(cfg, response_dump=response_dump, engine=engine)
    state = State(context=ctx)
    state._owned_engine = True

    with pytest.raises(RuntimeError):
        await state.apply_settings(http={"read_timeout": cfg.http.read_timeout + 1})


@pytest.mark.asyncio
async def test_disk_cache_reuse_and_rebuild(tmp_path, monkeypatch, test_config):
    cfg = test_config.copy().configure(
        cache={"disk_cache_dir": str(tmp_path / "cache"), "disk_cache_max_bytes": 1024}
    )
    monkeypatch.setattr("mutiny.engine.runtime.state.DiscordEngine", _FakeEngine)
    state = State(config=cfg)

    await state.start()

    first_cache = state._disk_cache
    assert first_cache is not None

    await state.apply_settings(
        cache={"disk_cache_dir": str(tmp_path / "cache"), "disk_cache_max_bytes": 1024}
    )

    assert state._disk_cache is first_cache

    await state.apply_settings(
        cache={"disk_cache_dir": str(tmp_path / "cache"), "disk_cache_max_bytes": 2048}
    )

    assert state._disk_cache is not first_cache
    assert state._disk_cache is not None
    assert state._disk_cache.max_total_bytes == 2048


@pytest.mark.asyncio
async def test_relative_disk_cache_path_is_stable_across_cwd_changes(
    tmp_path, monkeypatch, test_config
):
    cfg = test_config.copy().configure(
        cache={"disk_cache_dir": ".cache/mutiny", "disk_cache_max_bytes": 1024}
    )
    monkeypatch.setattr("mutiny.engine.runtime.state.DiscordEngine", _FakeEngine)
    state = State(config=cfg)
    first_cwd = tmp_path / "first"
    second_cwd = tmp_path / "second"
    first_cwd.mkdir()
    second_cwd.mkdir()

    monkeypatch.chdir(first_cwd)
    await state.start()
    first_path = state._disk_cache.db_path if state._disk_cache else None

    monkeypatch.chdir(second_cwd)
    await state.apply_settings(
        cache={"disk_cache_dir": ".cache/mutiny", "disk_cache_max_bytes": 1024}
    )
    second_path = state._disk_cache.db_path if state._disk_cache else None

    assert first_path is not None
    assert second_path == first_path


@pytest.mark.asyncio
async def test_rest_client_apply_config_swaps_clients(monkeypatch, test_config):
    created = []

    def _timeout(**kwargs):
        return {"timeout": kwargs}

    class _Recorder(_FakeAsyncClient):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            created.append(self)

    monkeypatch.setattr("mutiny.discord.rest_client.httpx.AsyncClient", _Recorder)
    monkeypatch.setattr("mutiny.discord.rest_client.httpx.Timeout", _timeout)

    cfg = test_config.copy()
    identity = DiscordIdentity(
        guild_id=cfg.discord.guild_id,
        channel_id=cfg.discord.channel_id,
        token_provider=cfg.token_provider,
        user_agent=cfg.discord.user_agent,
    )
    rest = DiscordRestClient(
        identity=identity,
        session=DiscordSessionState(),
        config=cfg,
        interaction_cache=InteractionCache(),
        metrics=MetricsService(),
    )

    original_http = rest.client
    original_cdn = rest.cdn_client

    new_cfg = cfg.configure(http={"read_timeout": cfg.http.read_timeout + 1})
    await rest.apply_config(new_cfg)

    assert original_http.closed is True
    assert original_cdn.closed is True
    assert rest.client is not original_http
    assert rest.cdn_client is not original_cdn
    assert rest.client.closed is False
    assert rest.cdn_client.closed is False
    assert len(created) == 4  # two from init, two from apply_config


@pytest.mark.asyncio
async def test_gateway_reconnect_refreshes_token_and_closes_ws(test_config):
    cfg = test_config.copy()

    class _TokenProvider:
        def __init__(self):
            self.calls: list[str] = []

        def get_token(self) -> str:
            token = f"token-{len(self.calls)}"
            self.calls.append(token)
            return token

    class _FakeWS:
        def __init__(self):
            self.closed = False
            self.code = None
            self.reason = None

        async def close(self, code=None, reason=None):
            self.closed = True
            self.code = code
            self.reason = reason

    provider = _TokenProvider()
    identity = DiscordIdentity(
        guild_id=cfg.discord.guild_id,
        channel_id=cfg.discord.channel_id,
        token_provider=provider,
        user_agent=cfg.discord.user_agent,
    )
    gw = DiscordGatewayClient(
        identity=identity,
        session=DiscordSessionState(),
        config=cfg,
        interaction_cache=InteractionCache(),
        metrics=MetricsService(),
        response_dump=ResponseDumpService(enabled=False),
        message_handler=lambda *_: None,
    )
    gw.ws = _FakeWS()

    new_cfg = cfg.configure(websocket={"backoff_initial": cfg.websocket.backoff_initial + 1})
    await gw.reconnect_with_config(new_cfg)

    assert gw.config is new_cfg
    assert gw.ws.closed is True
    assert gw.ws.code == 2002
    assert provider.calls[-1] == gw._token
    assert len(provider.calls) == 2  # initial + refresh
