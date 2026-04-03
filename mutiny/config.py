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

from __future__ import annotations

import copy
import logging
from dataclasses import asdict, dataclass, fields, is_dataclass, replace
from typing import Any, Mapping, MutableMapping, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

from .engine.execution_policy import ExecutionPolicy
from .services.token_provider import EnvTokenProvider, TokenProvider, get_env_label, is_dev_env

logger = logging.getLogger(__name__)


class _EnvSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_prefix="MJ_",
        extra="ignore",
    )

    api_secret: str = "your-secret-key"

    user_token: str
    guild_id: str
    channel_id: str
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:141.0) Gecko/20100101 Firefox/141.0"
    )
    discord_api_endpoint: str = "https://discord.com/api/v9"

    task_timeout_minutes: int = 5

    http_connect_timeout: float = 5.0
    http_read_timeout: float = 20.0
    http_write_timeout: float = 10.0
    http_pool_timeout: float = 5.0
    http_max_retries: int = 3
    http_backoff_initial: float = 0.5
    http_backoff_max: float = 8.0
    http_backoff_jitter: float = 0.3
    http_max_retry_after: float = 30.0

    ws_backoff_initial: float = 1.0
    ws_backoff_max: float = 30.0
    ws_backoff_jitter: float = 0.3

    ws_capture_enabled: bool = False

    cdn_connect_timeout: float = 5.0
    cdn_read_timeout: float = 20.0
    cdn_write_timeout: float = 20.0
    cdn_pool_timeout: float = 5.0

    image_cache_ttl_seconds: int = 24 * 3600
    image_cache_max_entries: int = 5000
    job_index_ttl_seconds: int = 7 * 24 * 3600
    job_index_max_entries: int = 10000
    artifact_cache_ram_max_bytes: int = 32 * 1024 * 1024

    disk_cache_enabled: bool = True
    disk_cache_dir: str = ".cache/mutiny"
    disk_cache_max_bytes: int = 256 * 1024 * 1024

    core_size: int = 3
    video_core_size: int = 1
    queue_size: int = 10


@dataclass(frozen=True)
class ApiConfig:
    secret: str = "your-secret-key"


@dataclass(frozen=True)
class DiscordConfig:
    guild_id: str
    channel_id: str
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:141.0) Gecko/20100101 Firefox/141.0"
    )
    api_endpoint: str = "https://discord.com/api/v9"


@dataclass(frozen=True)
class HttpConfig:
    connect_timeout: float = 5.0
    read_timeout: float = 20.0
    write_timeout: float = 10.0
    pool_timeout: float = 5.0
    max_retries: int = 3
    backoff_initial: float = 0.5
    backoff_max: float = 8.0
    backoff_jitter: float = 0.3
    max_retry_after: float = 30.0


@dataclass(frozen=True)
class WebSocketConfig:
    backoff_initial: float = 1.0
    backoff_max: float = 30.0
    backoff_jitter: float = 0.3
    capture_enabled: bool = False


@dataclass(frozen=True)
class CdnConfig:
    connect_timeout: float = 5.0
    read_timeout: float = 20.0
    write_timeout: float = 20.0
    pool_timeout: float = 5.0


@dataclass(frozen=True)
class CacheConfig:
    image_cache_ttl_seconds: int = 24 * 3600
    image_cache_max_entries: int = 5000
    job_index_ttl_seconds: int = 7 * 24 * 3600
    job_index_max_entries: int = 10000
    artifact_cache_ram_max_bytes: int = 32 * 1024 * 1024
    disk_cache_enabled: bool = True
    disk_cache_dir: str = ".cache/mutiny"
    disk_cache_max_bytes: int = 256 * 1024 * 1024
    response_dump_dir: str = ".cache/mutiny/mj_responses"


@dataclass(frozen=True)
class EngineConfig:
    execution: ExecutionPolicy = ExecutionPolicy()


@dataclass(frozen=True)
class Config:
    token_provider: TokenProvider
    api: ApiConfig
    discord: DiscordConfig
    http: HttpConfig
    websocket: WebSocketConfig
    cdn: CdnConfig
    cache: CacheConfig
    engine: EngineConfig

    @classmethod
    def create(
        cls,
        *,
        token_provider: TokenProvider,
        guild_id: str,
        channel_id: str,
        user_agent: str = DiscordConfig.user_agent,
        api_endpoint: str = DiscordConfig.api_endpoint,
        api_secret: str = ApiConfig.secret,
        api: Optional[ApiConfig | Mapping[str, Any]] = None,
        discord: Optional[DiscordConfig | Mapping[str, Any]] = None,
        http: Optional[HttpConfig | Mapping[str, Any]] = None,
        websocket: Optional[WebSocketConfig | Mapping[str, Any]] = None,
        cdn: Optional[CdnConfig | Mapping[str, Any]] = None,
        cache: Optional[CacheConfig | Mapping[str, Any]] = None,
        engine: Optional[EngineConfig | Mapping[str, Any]] = None,
        execution: Optional[ExecutionPolicy | Mapping[str, Any]] = None,
    ) -> "Config":
        """Construct a Config snapshot using Mutiny defaults for Discord/MJ operation."""

        api_cfg = _coerce_section(ApiConfig, api or {"secret": api_secret}, "api")
        discord_cfg = _coerce_section(
            DiscordConfig,
            discord
            or {
                "guild_id": guild_id,
                "channel_id": channel_id,
                "user_agent": user_agent,
                "api_endpoint": api_endpoint,
            },
            "discord",
        )
        http_cfg = _coerce_section(HttpConfig, http or {}, "http")
        websocket_cfg = _coerce_section(WebSocketConfig, websocket or {}, "websocket")
        cdn_cfg = _coerce_section(CdnConfig, cdn or {}, "cdn")
        cache_cfg = _coerce_section(CacheConfig, cache or {}, "cache")

        if engine and execution:
            raise ValueError("Provide either engine or execution, not both")
        execution_cfg = _coerce_section(ExecutionPolicy, execution or {}, "engine.execution")
        engine_cfg = _coerce_section(
            EngineConfig,
            engine or {"execution": execution_cfg},
            "engine",
        )

        return cls(
            token_provider=token_provider,
            api=api_cfg,
            discord=discord_cfg,
            http=http_cfg,
            websocket=websocket_cfg,
            cdn=cdn_cfg,
            cache=cache_cfg,
            engine=engine_cfg,
        )

    def configure(
        config_obj: "Config" | Mapping[str, Any],
        *,
        token_provider: TokenProvider | None = None,
        **overrides: Any,
    ) -> "Config":
        """Return a new Config snapshot from a base object plus overrides."""

        base = (
            config_obj
            if isinstance(config_obj, Config)
            else Config.from_dict(config_obj, token_provider=token_provider)
        )
        if isinstance(config_obj, Mapping) and token_provider is None:
            raise ValueError("token_provider is required when configuring from a mapping")
        return base._configure_instance(**overrides)

    @classmethod
    def from_dict(
        cls, data: Mapping[str, Any], *, token_provider: TokenProvider | None = None
    ) -> "Config":
        """Rebuild a Config snapshot from an as_dict payload."""

        if token_provider is None:
            raise ValueError("token_provider is required when rebuilding a Config from dict")
        api_cfg = _coerce_section(ApiConfig, data.get("api", {}), "api")
        discord_cfg = _coerce_section(DiscordConfig, data.get("discord", {}), "discord")
        http_cfg = _coerce_section(HttpConfig, data.get("http", {}), "http")
        websocket_cfg = _coerce_section(WebSocketConfig, data.get("websocket", {}), "websocket")
        cdn_cfg = _coerce_section(CdnConfig, data.get("cdn", {}), "cdn")
        cache_cfg = _coerce_section(CacheConfig, data.get("cache", {}), "cache")

        engine_data = data.get("engine", {})
        if isinstance(engine_data, Mapping):
            execution_data = engine_data.get("execution", {})
        else:
            execution_data = {}
        execution_cfg = _coerce_section(ExecutionPolicy, execution_data, "engine.execution")
        engine_cfg = _coerce_section(EngineConfig, {"execution": execution_cfg}, "engine")

        return cls(
            token_provider=token_provider,
            api=api_cfg,
            discord=discord_cfg,
            http=http_cfg,
            websocket=websocket_cfg,
            cdn=cdn_cfg,
            cache=cache_cfg,
            engine=engine_cfg,
        )

    def _configure_instance(self, **overrides: Any) -> "Config":
        """Return a new Config snapshot with validated overrides applied."""
        if not overrides:
            return self.copy()
        updated = {}
        for key, value in overrides.items():
            if not hasattr(self, key):
                raise KeyError(f"Unknown config section: {key}")
            current = getattr(self, key)
            if is_dataclass(current):
                updated[key] = _merge_dataclass(current, value, key)
            else:
                updated[key] = value
        return replace(self, **updated)

    def copy(self) -> "Config":
        """Return a deep copy of this Config snapshot."""
        return copy.deepcopy(self)

    def as_dict(self) -> dict[str, Any]:
        """Return a stable, nested dict representation of the config."""
        payload = asdict(self)
        payload.pop("token_provider", None)
        return payload


def _load_env_config() -> Config:
    """Load config from environment (MJ_ prefix) and .env file (dev only)."""
    if not is_dev_env():
        label = get_env_label() or "unset"
        logger.error(
            "Env config loading is disabled unless MUTINY_ENV=development (current: %s).",
            label,
        )
        raise RuntimeError("Env config loading requires MUTINY_ENV=development")
    env = _EnvSettings()
    return Config(
        token_provider=EnvTokenProvider(),
        api=ApiConfig(secret=env.api_secret),
        discord=DiscordConfig(
            guild_id=env.guild_id,
            channel_id=env.channel_id,
            user_agent=env.user_agent,
            api_endpoint=env.discord_api_endpoint,
        ),
        http=HttpConfig(
            connect_timeout=env.http_connect_timeout,
            read_timeout=env.http_read_timeout,
            write_timeout=env.http_write_timeout,
            pool_timeout=env.http_pool_timeout,
            max_retries=env.http_max_retries,
            backoff_initial=env.http_backoff_initial,
            backoff_max=env.http_backoff_max,
            backoff_jitter=env.http_backoff_jitter,
            max_retry_after=env.http_max_retry_after,
        ),
        websocket=WebSocketConfig(
            backoff_initial=env.ws_backoff_initial,
            backoff_max=env.ws_backoff_max,
            backoff_jitter=env.ws_backoff_jitter,
            capture_enabled=env.ws_capture_enabled,
        ),
        cdn=CdnConfig(
            connect_timeout=env.cdn_connect_timeout,
            read_timeout=env.cdn_read_timeout,
            write_timeout=env.cdn_write_timeout,
            pool_timeout=env.cdn_pool_timeout,
        ),
        cache=CacheConfig(
            image_cache_ttl_seconds=env.image_cache_ttl_seconds,
            image_cache_max_entries=env.image_cache_max_entries,
            job_index_ttl_seconds=env.job_index_ttl_seconds,
            job_index_max_entries=env.job_index_max_entries,
            artifact_cache_ram_max_bytes=env.artifact_cache_ram_max_bytes,
            disk_cache_enabled=env.disk_cache_enabled,
            disk_cache_dir=env.disk_cache_dir,
            disk_cache_max_bytes=env.disk_cache_max_bytes,
        ),
        engine=EngineConfig(
            execution=ExecutionPolicy(
                core_size=env.core_size,
                video_core_size=env.video_core_size,
                queue_size=env.queue_size,
                task_timeout_minutes=env.task_timeout_minutes,
            )
        ),
    )


def _merge_dataclass(current: Any, value: Any, label: str):
    if isinstance(value, Mapping):
        field_names = {f.name for f in fields(current)}
        unknown = set(value.keys()) - field_names
        if unknown:
            raise KeyError(f"Unknown {label} keys: {', '.join(sorted(unknown))}")
        updates = {}
        for key, val in value.items():
            field_value = getattr(current, key)
            if is_dataclass(field_value) and isinstance(val, Mapping):
                updates[key] = _merge_dataclass(field_value, val, f"{label}.{key}")
            else:
                updates[key] = val
        return replace(current, **updates)
    if isinstance(value, current.__class__):
        return value
    raise TypeError(f"{label} must be a mapping or {current.__class__.__name__}")


def _coerce_section(section_cls, value: Any, label: str):
    if isinstance(value, section_cls):
        return value
    if isinstance(value, MutableMapping):
        return section_cls(**value)
    if isinstance(value, Mapping):
        return section_cls(**dict(value))
    if value == {}:
        return section_cls()
    raise TypeError(f"{label} must be a mapping or {section_cls.__name__}")


__all__ = [
    "ApiConfig",
    "CacheConfig",
    "CdnConfig",
    "Config",
    "DiscordConfig",
    "EngineConfig",
    "HttpConfig",
    "WebSocketConfig",
    "_load_env_config",
]
