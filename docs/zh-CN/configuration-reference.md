**<- 上一页：** [配置](configuration.md)

# 配置参考

这一页是 Mutiny 配置模型在 `mutiny/config.py` 中的精确视图。

如果你想看“我该改什么、为什么改”的版本，请先读 [配置](configuration.md)。这一页讲的是精确名称、默认值、辅助方法行为和 env 覆盖范围。

## `Config.create(...)`

必需输入：

- `token_provider`
- `guild_id`
- `channel_id`

便捷输入：

- `user_agent`
- `api_endpoint`
- `api_secret`

`Config.create(...)` 接受的 section 覆写：

- `api`
- `discord`
- `http`
- `websocket`
- `cdn`
- `cache`
- `engine`
- `execution`

行为说明：

- section 覆写既可以接受具体 dataclass，也可以接受 mapping
- `execution=...` 是覆写 `engine.execution` 的简写
- `engine=` 和 `execution=` 不能同时提供

## `Config` 辅助方法

- `Config.create(...)`：基于身份信息和可选 section 覆写的规范构造器
- `Config.configure(...)`：把覆写合并进一个快照或 mapping
- `Config.from_dict(...)`：从序列化数据重建；需要 `token_provider`
- `Config.copy()`：深拷贝
- `Config.as_dict()`：嵌套字典形式，不含 `token_provider`

## `ApiConfig`

- `secret`
  - 默认值：`"your-secret-key"`
  - env：`MJ_API_SECRET`
  - 含义：Mutiny 面向 API 的表面所使用的本地 API secret

## `DiscordConfig`

- `guild_id`
  - 必填
  - env：`MJ_GUILD_ID`
  - 含义：Mutiny 提交任务的 Discord guild
- `channel_id`
  - 必填
  - env：`MJ_CHANNEL_ID`
  - 含义：Mutiny 提交任务的 Discord channel
- `user_agent`
  - 默认值：`Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.7680.165 Safari/537.36`
  - env：`MJ_USER_AGENT`
  - 含义：发送给 Discord 的 user agent
- `api_endpoint`
  - 默认值：`https://discord.com/api/v9`
  - env：`MJ_DISCORD_API_ENDPOINT`
  - 含义：Discord REST API 基础 URL

## `HttpConfig`

- `connect_timeout`
  - 默认值：`5.0`
  - env：`MJ_HTTP_CONNECT_TIMEOUT`
- `read_timeout`
  - 默认值：`20.0`
  - env：`MJ_HTTP_READ_TIMEOUT`
- `write_timeout`
  - 默认值：`10.0`
  - env：`MJ_HTTP_WRITE_TIMEOUT`
- `pool_timeout`
  - 默认值：`5.0`
  - env：`MJ_HTTP_POOL_TIMEOUT`
- `max_retries`
  - 默认值：`3`
  - env：`MJ_HTTP_MAX_RETRIES`
- `backoff_initial`
  - 默认值：`0.5`
  - env：`MJ_HTTP_BACKOFF_INITIAL`
- `backoff_max`
  - 默认值：`8.0`
  - env：`MJ_HTTP_BACKOFF_MAX`
- `backoff_jitter`
  - 默认值：`0.3`
  - env：`MJ_HTTP_BACKOFF_JITTER`
- `max_retry_after`
  - 默认值：`30.0`
  - env：`MJ_HTTP_MAX_RETRY_AFTER`

这些字段控制 Discord REST 行为：超时预算、重试策略和 retry-after 上限。

## `WebSocketConfig`

- `backoff_initial`
  - 默认值：`1.0`
  - env：`MJ_WS_BACKOFF_INITIAL`
- `backoff_max`
  - 默认值：`30.0`
  - env：`MJ_WS_BACKOFF_MAX`
- `backoff_jitter`
  - 默认值：`0.3`
  - env：`MJ_WS_BACKOFF_JITTER`
- `capture_enabled`
  - 默认值：`False`
  - env：`MJ_WS_CAPTURE_ENABLED`
  - 含义：通过响应转储服务启用 gateway 事件捕获

## `CdnConfig`

- `connect_timeout`
  - 默认值：`5.0`
  - env：`MJ_CDN_CONNECT_TIMEOUT`
- `read_timeout`
  - 默认值：`20.0`
  - env：`MJ_CDN_READ_TIMEOUT`
- `write_timeout`
  - 默认值：`20.0`
  - env：`MJ_CDN_WRITE_TIMEOUT`
- `pool_timeout`
  - 默认值：`5.0`
  - env：`MJ_CDN_POOL_TIMEOUT`

这些字段控制产物下载超时。

## `CacheConfig`

- `image_cache_ttl_seconds`
  - 默认值：`86400`
  - env：`MJ_IMAGE_CACHE_TTL_SECONDS`
- `image_cache_max_entries`
  - 默认值：`5000`
  - env：`MJ_IMAGE_CACHE_MAX_ENTRIES`
- `job_index_ttl_seconds`
  - 默认值：`604800`
  - env：`MJ_JOB_INDEX_TTL_SECONDS`
- `job_index_max_entries`
  - 默认值：`10000`
  - env：`MJ_JOB_INDEX_MAX_ENTRIES`
- `artifact_cache_ram_max_bytes`
  - 默认值：`33554432`
  - env：`MJ_ARTIFACT_CACHE_RAM_MAX_BYTES`
  - 含义：已识别产物元数据和签名的内存预算
- `disk_cache_enabled`
  - 默认值：`True`
  - env：`MJ_DISK_CACHE_ENABLED`
- `disk_cache_dir`
  - 默认值：`.cache/mutiny`
  - env：`MJ_DISK_CACHE_DIR`
  - 含义：持久化产物缓存目录；相对路径会解析到稳定的每用户位置，而不是当前进程 cwd
- `disk_cache_max_bytes`
  - 默认值：`268435456`
  - env：`MJ_DISK_CACHE_MAX_BYTES`
- `response_dump_dir`
  - 默认值：`.cache/mutiny/mj_responses`
  - env：无
  - 含义：响应和 gateway 转储的输出目录

> **注意：** `response_dump_dir` 是真实配置字段，但 `_load_env_config()` 目前不会从 env 变量里填充它。请通过 `Config.create(...)` 或 `Config.configure(...)` 设置。

## `EngineConfig`

- `execution`
  - 类型：`ExecutionPolicy`
  - 含义：队列与 worker 大小，以及任务超时策略

## `ExecutionPolicy`

- `queue_size`
  - 默认值：`10`
  - env：`MJ_QUEUE_SIZE`
- `core_size`
  - 默认值：`3`
  - env：`MJ_CORE_SIZE`
- `video_core_size`
  - 默认值：`1`
  - env：`MJ_VIDEO_CORE_SIZE`
- `task_timeout_minutes`
  - 默认值：`5`
  - env：`MJ_TASK_TIMEOUT_MINUTES`

## 开发环境映射

除非 `MUTINY_ENV=development` 或 `MJ_ENV=development`，否则 env 加载会被禁用。

这是为了配置启动和工具链提供的开发期便利。正常产品路径仍然是“构建一个 `Config`，然后把它交给 `Mutiny`”。

开启开发模式后，`_load_env_config()` 会读取以下 `MJ_` 值：

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

## 示例快照

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

**继续 ->** [门面与生命周期](facade-and-lifecycle.md)
