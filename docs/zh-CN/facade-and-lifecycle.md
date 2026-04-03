**<- 上一页：** [配置参考](configuration-reference.md)

# 门面与生命周期

Mutiny 在集成层上刻意做得很窄：一个公共客户端、一个配置模型、每个账号一个运行中的会话。

这不是把限制包装成优雅。它本来就是产品形状。

## 门面契约

规范的公共入口是 `Mutiny(config)`。

大多数宿主应用只需要：

- `Config.create(...)`
- `Mutiny(config)`
- `start()`
- `wait_ready()`
- 一个或多个提交方法
- `events()` 或 `wait_for_job()`
- `close()`

如果你的集成能待在这个边界里，很多事情都会立刻简单不少。

## 构建客户端

先构建一个 `Config`，再把这个快照交给 `Mutiny`。

```python
from mutiny import Config, Mutiny

config = Config.create(
    token_provider=my_token_provider,
    guild_id="YOUR_GUILD_ID",
    channel_id="YOUR_CHANNEL_ID",
)

client = Mutiny(config)
```

`Config` 是配置表面。`Mutiny` 是运行中的门面。把这个拆分保持清楚，库里的其他部分就会顺眼很多。

## 正常生命周期

```python
await client.start()

if not await client.wait_ready(timeout_s=60):
    raise RuntimeError("Gateway not ready")

# submit work, consume events, wait for jobs

await client.close()
```

实用说明：

- 提交前先调用 `start()`
- 当你想要真实的就绪检查而不是碰运气地 sleep 时，用 `wait_ready()`
- 把 `close()` 当成会话的干净结束
- 每个账号一个长生命周期客户端是最顺手的路径

## 观察辅助方法

Mutiny 给了你两种互补的同步方式。

### `events()`

当宿主应用需要实时 UI、日志、websocket 或一个集中式运行时模型时，使用 `events()`。

- `events()` 会流出整个会话
- `events(job_id=...)` 会把流收窄到单个任务
- 这个流会产出 `ProgressUpdate` 和 `JobSnapshot`

详细消费模式见 [事件](events.md)。

### `wait_for_job()`

当你想要最小可用集成时，使用 `wait_for_job(job_id)`。

它会等待终态并返回一个 `JobSnapshot`。因此它很适合脚本、CLI 宿主、worker 和 smoke test。

### `get_job()` 和 `list_jobs()`

当你的应用已经有任务 id，并且只想要某个时间点的状态时，用这两个方法。

- `get_job(job_id)` 返回一个 `JobSnapshot`
- `list_jobs()` 返回所有已知任务的快照
- `list_jobs(active_only=True)` 是回答“现在还有哪些任务在动？”的最快方式
- `list_jobs(status=JobStatus.SUCCEEDED)` 很适合宿主侧过滤和对账

## 恢复辅助方法

已保存的输出产物不必变成死文件。

这个门面拥有三个辅助方法，用来把旧媒体重新接回宿主应用里的实时工作流：

- `resolve_image(image)` 返回 `ImageResolution | None`
- `resolve_video(video)` 返回 `VideoResolution | None`
- `split_image_result(job_id, image)` 返回 `tuple[ImageTile, ...]`

可以这样理解它们：

- 当用户把旧图拖回你的应用，而你想知道它来自哪个任务和哪个分块时，用 `resolve_image()`
- 当一段已保存动画剪辑又需要 `extend` 按钮时，用 `resolve_video()`
- 当你手上有一个已知网格结果，并且想在自己的 UI 里提供分块级控制时，用 `split_image_result()`

完整恢复故事见 [视频与产物工作流](video-and-artifact-workflows.md)。

## 用一句话概括事件模型

Mutiny 会立刻返回一个 `JobHandle`，然后在任务推进过程中持续产出 `ProgressUpdate` 和 `JobSnapshot`。

这个拆分很重要：

- `JobHandle` 是提交回执
- `ProgressUpdate` 是轻量级的“还在跑”脉冲
- `JobSnapshot` 是持久化的公共状态

## 错误边界

门面方法抛出普通 Python 异常：

- `ValueError` 用于校验失败
- `RuntimeError` 用于运行时和服务失败

这样宿主代码就能保持简单。你可以写普通的异步客户端代码，而不用把内部结果包装对象一路塞进应用。

## 范围护栏

Mutiny 是给你基于 Midjourney 构建产品用的，不是让你假装 Midjourney 的账号与审核现实不存在。

如果你的产品需要多账号编排、订阅绕过，或逃离平台限制的魔法后门，那你做的就是另一个产品。

**继续 ->** [任务操作](job-actions.md)
