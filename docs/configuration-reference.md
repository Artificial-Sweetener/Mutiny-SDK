**<- Previous:** [Configuration](configuration.md)

# Configuration Reference

This is the exact view of Mutiny's config model as implemented in `mutiny/config.py`.

If you want the "what should I change and why?" version, read [Configuration](configuration.md) first. This page is for exact names, defaults, helper behavior, and env coverage.

## `Config.create(...)`

Required inputs:

- `token_provider`
- `guild_id`
- `channel_id`

Convenience inputs:

- `user_agent`
- `api_endpoint`
- `api_secret`

Section overrides accepted by `Config.create(...)`:

- `api`
- `discord`
- `http`
- `websocket`
- `cdn`
- `cache`
- `engine`
- `execution`

Behavior notes:

- section overrides accept either the concrete dataclass or a mapping
- `execution=...` is shorthand for overriding `engine.execution`
- `engine=` and `execution=` cannot be supplied together

## `Config` Helper Methods

- `Config.create(...)`: canonical constructor from identity plus optional section overrides
- `Config.configure(...)`: merge overrides into a snapshot or mapping
- `Config.from_dict(...)`: rebuild from serialized data; requires `token_provider`
- `Config.copy()`: deep copy
- `Config.as_dict()`: nested dictionary form, excluding `token_provider`

## `ApiConfig`

- `secret`
  - default: `"your-secret-key"`
  - env: `MJ_API_SECRET`
  - meaning: local API secret used by Mutiny's API-facing surfaces

## `DiscordConfig`

- `guild_id`
  - required
  - env: `MJ_GUILD_ID`
  - meaning: Discord guild Mutiny submits into
- `channel_id`
  - required
  - env: `MJ_CHANNEL_ID`
  - meaning: Discord channel Mutiny submits into
- `user_agent`
  - default: `Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:141.0) Gecko/20100101 Firefox/141.0`
  - env: `MJ_USER_AGENT`
  - meaning: user agent sent to Discord
- `api_endpoint`
  - default: `https://discord.com/api/v9`
  - env: `MJ_DISCORD_API_ENDPOINT`
  - meaning: Discord REST API base URL

## `HttpConfig`

- `connect_timeout`
  - default: `5.0`
  - env: `MJ_HTTP_CONNECT_TIMEOUT`
- `read_timeout`
  - default: `20.0`
  - env: `MJ_HTTP_READ_TIMEOUT`
- `write_timeout`
  - default: `10.0`
  - env: `MJ_HTTP_WRITE_TIMEOUT`
- `pool_timeout`
  - default: `5.0`
  - env: `MJ_HTTP_POOL_TIMEOUT`
- `max_retries`
  - default: `3`
  - env: `MJ_HTTP_MAX_RETRIES`
- `backoff_initial`
  - default: `0.5`
  - env: `MJ_HTTP_BACKOFF_INITIAL`
- `backoff_max`
  - default: `8.0`
  - env: `MJ_HTTP_BACKOFF_MAX`
- `backoff_jitter`
  - default: `0.3`
  - env: `MJ_HTTP_BACKOFF_JITTER`
- `max_retry_after`
  - default: `30.0`
  - env: `MJ_HTTP_MAX_RETRY_AFTER`

These control Discord REST behavior: timeout budgets, retry policy, and retry-after ceilings.

## `WebSocketConfig`

- `backoff_initial`
  - default: `1.0`
  - env: `MJ_WS_BACKOFF_INITIAL`
- `backoff_max`
  - default: `30.0`
  - env: `MJ_WS_BACKOFF_MAX`
- `backoff_jitter`
  - default: `0.3`
  - env: `MJ_WS_BACKOFF_JITTER`
- `capture_enabled`
  - default: `False`
  - env: `MJ_WS_CAPTURE_ENABLED`
  - meaning: enables gateway-event capture through the response dump service

## `CdnConfig`

- `connect_timeout`
  - default: `5.0`
  - env: `MJ_CDN_CONNECT_TIMEOUT`
- `read_timeout`
  - default: `20.0`
  - env: `MJ_CDN_READ_TIMEOUT`
- `write_timeout`
  - default: `20.0`
  - env: `MJ_CDN_WRITE_TIMEOUT`
- `pool_timeout`
  - default: `5.0`
  - env: `MJ_CDN_POOL_TIMEOUT`

These control artifact download timeouts.

## `CacheConfig`

- `image_cache_ttl_seconds`
  - default: `86400`
  - env: `MJ_IMAGE_CACHE_TTL_SECONDS`
- `image_cache_max_entries`
  - default: `5000`
  - env: `MJ_IMAGE_CACHE_MAX_ENTRIES`
- `job_index_ttl_seconds`
  - default: `604800`
  - env: `MJ_JOB_INDEX_TTL_SECONDS`
- `job_index_max_entries`
  - default: `10000`
  - env: `MJ_JOB_INDEX_MAX_ENTRIES`
- `artifact_cache_ram_max_bytes`
  - default: `33554432`
  - env: `MJ_ARTIFACT_CACHE_RAM_MAX_BYTES`
  - meaning: in-memory budget for recognized artifact metadata and signatures
- `disk_cache_enabled`
  - default: `True`
  - env: `MJ_DISK_CACHE_ENABLED`
- `disk_cache_dir`
  - default: `.cache/mutiny`
  - env: `MJ_DISK_CACHE_DIR`
  - meaning: durable artifact-cache directory; relative paths are resolved to a stable per-user location instead of the process cwd
- `disk_cache_max_bytes`
  - default: `268435456`
  - env: `MJ_DISK_CACHE_MAX_BYTES`
- `response_dump_dir`
  - default: `.cache/mutiny/mj_responses`
  - env: none
  - meaning: output directory for response and gateway dumps

> **Heads-up:** `response_dump_dir` is a real config field, but `_load_env_config()` does not currently populate it from an env var. Set it through `Config.create(...)` or `Config.configure(...)`.

## `EngineConfig`

- `execution`
  - type: `ExecutionPolicy`
  - meaning: queue and worker sizing plus task timeout policy

## `ExecutionPolicy`

- `queue_size`
  - default: `10`
  - env: `MJ_QUEUE_SIZE`
- `core_size`
  - default: `3`
  - env: `MJ_CORE_SIZE`
- `video_core_size`
  - default: `1`
  - env: `MJ_VIDEO_CORE_SIZE`
- `task_timeout_minutes`
  - default: `5`
  - env: `MJ_TASK_TIMEOUT_MINUTES`

## Development Env Mapping

Env loading is disabled unless `MUTINY_ENV=development` or `MJ_ENV=development`.

This is development-only convenience for config bootstrapping and tooling. The normal product story is still "build a `Config` and pass it to `Mutiny`."

When development mode is enabled, `_load_env_config()` reads the following `MJ_` values:

- `MJ_USER_TOKEN`
- `MJ_GUILD_ID`
- `MJ_CHANNEL_ID`
- `MJ_API_SECRET`
- `MJ_USER_AGENT`
- `MJ_DISCORD_API_ENDPOINT`
- `MJ_HTTP_CONNECT_TIMEOUT`
- `MJ_HTTP_READ_TIMEOUT`
- `MJ_HTTP_WRITE_TIMEOUT`
- `MJ_HTTP_POOL_TIMEOUT`
- `MJ_HTTP_MAX_RETRIES`
- `MJ_HTTP_BACKOFF_INITIAL`
- `MJ_HTTP_BACKOFF_MAX`
- `MJ_HTTP_BACKOFF_JITTER`
- `MJ_HTTP_MAX_RETRY_AFTER`
- `MJ_WS_BACKOFF_INITIAL`
- `MJ_WS_BACKOFF_MAX`
- `MJ_WS_BACKOFF_JITTER`
- `MJ_WS_CAPTURE_ENABLED`
- `MJ_CDN_CONNECT_TIMEOUT`
- `MJ_CDN_READ_TIMEOUT`
- `MJ_CDN_WRITE_TIMEOUT`
- `MJ_CDN_POOL_TIMEOUT`
- `MJ_IMAGE_CACHE_TTL_SECONDS`
- `MJ_IMAGE_CACHE_MAX_ENTRIES`
- `MJ_JOB_INDEX_TTL_SECONDS`
- `MJ_JOB_INDEX_MAX_ENTRIES`
- `MJ_ARTIFACT_CACHE_RAM_MAX_BYTES`
- `MJ_DISK_CACHE_ENABLED`
- `MJ_DISK_CACHE_DIR`
- `MJ_DISK_CACHE_MAX_BYTES`
- `MJ_QUEUE_SIZE`
- `MJ_CORE_SIZE`
- `MJ_VIDEO_CORE_SIZE`
- `MJ_TASK_TIMEOUT_MINUTES`

## Example Snapshot

```python
config_dict = {
    "api": {"secret": "your-secret-key"},
    "discord": {
        "guild_id": "123",
        "channel_id": "456",
        "user_agent": "Mozilla/5.0 ...",
        "api_endpoint": "https://discord.com/api/v9",
    },
    "http": {"read_timeout": 20.0, "max_retries": 3},
    "websocket": {"capture_enabled": False},
    "cdn": {"read_timeout": 20.0},
    "cache": {
        "disk_cache_enabled": True,
        "disk_cache_dir": ".cache/mutiny",
        "disk_cache_max_bytes": 268435456,
        "artifact_cache_ram_max_bytes": 33554432,
        "response_dump_dir": ".cache/mutiny/mj_responses",
    },
    "engine": {
        "execution": {
            "queue_size": 10,
            "core_size": 3,
            "video_core_size": 1,
            "task_timeout_minutes": 5,
        }
    },
}
```

**Continue ->** [Facade and Lifecycle](facade-and-lifecycle.md)
