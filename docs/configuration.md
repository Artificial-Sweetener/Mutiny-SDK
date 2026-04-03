**<- Previous:** [Getting Started](getting-started.md)

# Configuration

`Config` is a snapshot, not a bag of globals.

That matters because Mutiny lets you:

- build a config once
- copy or serialize it
- derive a changed snapshot later
- keep setup decisions explicit instead of hiding them in globals

## Build A Config

`Config.create(...)` is the normal constructor.

The required inputs are:

- `token_provider`
- `guild_id`
- `channel_id`

```python
from mutiny import Config

config = Config.create(
    token_provider=my_token_provider,
    guild_id="1234567890",
    channel_id="0987654321",
)
```

## Convenience Inputs Worth Knowing

`Config.create(...)` also supports top-level convenience inputs for the settings people change most often:

- `user_agent`
- `api_endpoint`
- `api_secret`
- `execution=...`

That means you can do either of these:

```python
config = Config.create(
    token_provider=my_token_provider,
    guild_id="123",
    channel_id="456",
    user_agent="Mozilla/5.0 ...",
)
```

```python
config = Config.create(
    token_provider=my_token_provider,
    guild_id="123",
    channel_id="456",
    execution={"queue_size": 20, "core_size": 4},
)
```

> **Heads-up:** `engine=` and `execution=` are mutually exclusive. `execution=` is shorthand for the common case where you only want to override `EngineConfig.execution`.

## Modify A Snapshot

Useful helpers:

- `Config.configure(...)`
- `Config.copy()`
- `Config.as_dict()`
- `Config.from_dict(...)`

Example:

```python
updated = Config.configure(
    config,
    http={"read_timeout": 30.0},
    cache={"disk_cache_enabled": False},
)
```

Behavior notes:

- unknown top-level sections raise `KeyError`
- unknown nested keys raise `KeyError`
- wrong section types raise `TypeError`
- `Config.from_dict(...)` requires `token_provider`
- `Config.configure(...)` also requires `token_provider` when the source is a plain mapping instead of an existing `Config`

The important design choice is simple: you shape the snapshot first, then hand it to `Mutiny`. This page is about building that snapshot well.

## Config Areas

Mutiny keeps config split by concern so you can change one layer without destabilizing the rest of the integration.

Config is split by concern: transport, cache, execution, and diagnostics.

### `ApiConfig`

Change this when:

- you need to set the local API secret explicitly

### `DiscordConfig`

Change this when:

- you need a different guild/channel target
- you need to override the default user agent
- you need to point at a different Discord API endpoint

### `HttpConfig`

Change this when:

- Discord REST calls are timing out in your environment
- you need different retry/backoff behavior

### `WebSocketConfig`

Change this when:

- gateway reconnect timing needs tuning
- you want gateway event capture enabled through `capture_enabled`

### `CdnConfig`

Change this when:

- large artifact downloads need different timeout behavior

### `CacheConfig`

Change this when:

- you want tighter or looser artifact-cache memory budgets
- you want to disable or relocate the disk cache
- you want response dumps written somewhere specific

`response_dump_dir` lives here. That matters because debugging output lands in the cache section, not the websocket section.

### `EngineConfig`

Change this when:

- you need a bigger queue
- you want different worker sizing
- you need a different task timeout policy

Most builders can think in terms of `execution=...` and ignore the rest of `EngineConfig`.

## Two Practical Scenarios

### Tighten Cache Budgets

If your app is sharing memory with other heavy workloads, start here:

```python
config = Config.create(
    token_provider=my_token_provider,
    guild_id="123",
    channel_id="456",
    cache={
        "artifact_cache_ram_max_bytes": 16 * 1024 * 1024,
        "disk_cache_max_bytes": 128 * 1024 * 1024,
    },
)
```

### Turn On Response Dumps

If you are debugging Midjourney/Discord behavior, the useful knobs are:

- `websocket.capture_enabled`
- `cache.response_dump_dir`

```python
config = Config.create(
    token_provider=my_token_provider,
    guild_id="123",
    channel_id="456",
    websocket={"capture_enabled": True},
    cache={"response_dump_dir": ".cache/mutiny/mj_responses"},
)
```

> **Why this matters:** `capture_enabled` controls gateway event capture. The response dump directory is where the dump service writes files. If you care about diagnostics, you usually care about both.

## Snapshot Storage And Rebuilds

Two helpers matter when your host wants to persist config safely:

- `Config.as_dict()` returns a nested mapping without the token provider
- `Config.from_dict(...)` rebuilds the snapshot when you supply a fresh `token_provider`

That split is deliberate. Secrets stay in your token provider, not inside the serialized config payload.

## Development Env Notes

Env-based token/config loading exists as a development convenience and is deliberately gated:

- allowed only when `MUTINY_ENV=development` or `MJ_ENV=development`
- otherwise raises `RuntimeError`

That friction is deliberate. It keeps the convenience path from quietly becoming your production secret-management strategy.

## See Also

- [Configuration Reference](configuration-reference.md)
- [Troubleshooting](troubleshooting.md)
- [API Reference](api-reference.md)

**Continue ->** [Configuration Reference](configuration-reference.md)
