**<- 上一页：** [快速开始](getting-started.md)

# 配置

`Config` 是一个快照，不是一袋到处飘的全局变量。

这点很重要，因为 Mutiny 允许你：

- 构建一次配置
- 复制或序列化它
- 之后再派生出一个变更后的快照
- 让设置决策保持显式，而不是藏进全局变量里

## 构建一个 Config

`Config.create(...)` 是常规构造方式。

必需输入是：

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

## 值得知道的便捷输入

`Config.create(...)` 也支持一些顶层便捷输入，覆盖大家最常改的设置：

- `user_agent`
- `api_endpoint`
- `api_secret`
- `execution=...`

也就是说，你可以这样写：

```python
config = Config.create(
    token_provider=my_token_provider,
    guild_id="123",
    channel_id="456",
    user_agent="Mozilla/5.0 ...",
)
```

也可以这样写：

```python
config = Config.create(
    token_provider=my_token_provider,
    guild_id="123",
    channel_id="456",
    execution={"queue_size": 20, "core_size": 4},
)
```

> **注意：** `engine=` 和 `execution=` 互斥。`execution=` 是一种简写，适合你只想覆写 `EngineConfig.execution` 的常见场景。

## 修改一个快照

常用辅助方法：

- `Config.configure(...)`
- `Config.copy()`
- `Config.as_dict()`
- `Config.from_dict(...)`

示例：

```python
updated = Config.configure(
    config,
    http={"read_timeout": 30.0},
    cache={"disk_cache_enabled": False},
)
```

行为说明：

- 未知的顶层 section 会抛出 `KeyError`
- 未知的嵌套键会抛出 `KeyError`
- 错误的 section 类型会抛出 `TypeError`
- `Config.from_dict(...)` 需要 `token_provider`
- 当源是普通 mapping 而不是现有 `Config` 时，`Config.configure(...)` 也需要 `token_provider`

这里的重要设计选择很简单：先把快照塑形，再把它交给 `Mutiny`。这一页讲的就是如何把这个快照塑好。

## Config 区域

Mutiny 按关注点拆分配置，这样你可以改一层而不把整个集成其余部分也搞乱。

Config 按关注点分成：传输、缓存、执行和诊断。

### `ApiConfig`

在这些情况下改它：

- 你需要显式设置本地 API secret

### `DiscordConfig`

在这些情况下改它：

- 你需要不同的 guild/channel 目标
- 你需要覆写默认 user agent
- 你需要指向不同的 Discord API endpoint

### `HttpConfig`

在这些情况下改它：

- 你的环境里 Discord REST 调用经常超时
- 你需要不同的重试/退避行为

### `WebSocketConfig`

在这些情况下改它：

- gateway 重连时序需要调优
- 你想通过 `capture_enabled` 开启 gateway 事件捕获

### `CdnConfig`

在这些情况下改它：

- 大型产物下载需要不同的超时行为

### `CacheConfig`

在这些情况下改它：

- 你想把产物缓存内存预算收得更紧或放得更宽
- 你想禁用磁盘缓存或把它移到别的位置
- 你想把响应转储写到指定目录

`response_dump_dir` 在这里。这点重要，因为调试输出落在 cache 分区，而不是 websocket 分区。

### `EngineConfig`

在这些情况下改它：

- 你需要更大的队列
- 你想调整 worker 大小
- 你需要不同的任务超时策略

大多数构建者只需要从 `execution=...` 角度去理解，而可以忽略 `EngineConfig` 的其余部分。

## 两个实用场景

### 收紧缓存预算

如果你的应用要和其他重负载共享内存，从这里开始：

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

### 打开响应转储

如果你在调试 Midjourney/Discord 行为，有用的旋钮是：

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

> **为什么重要：** `capture_enabled` 控制 gateway 事件捕获。响应转储目录则是转储服务写文件的地方。如果你关心诊断，通常就会同时关心这两个设置。

## 快照存储和重建

当宿主应用想安全持久化配置时，有两个辅助方法特别重要：

- `Config.as_dict()` 会返回一个不含 token provider 的嵌套 mapping
- `Config.from_dict(...)` 会在你提供新的 `token_provider` 时重建这个快照

这种拆分是刻意的。密钥应该留在 token provider 里，而不是塞进序列化后的配置载荷里。

## 开发环境说明

基于 env 的令牌/配置加载只是开发便利功能，而且有明确门槛：

- 只有在 `MUTINY_ENV=development` 或 `MJ_ENV=development` 时才允许
- 否则会抛出 `RuntimeError`

这种摩擦是故意的。它能防止这条便捷路径悄悄演变成你的生产密钥管理策略。

## 另请参阅

- [配置参考](configuration-reference.md)
- [故障排查](troubleshooting.md)
- [API 参考](api-reference.md)

**继续 ->** [配置参考](configuration-reference.md)
