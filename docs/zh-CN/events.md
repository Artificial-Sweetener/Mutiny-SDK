**<- 上一页：** [任务操作](job-actions.md)

# 事件

Mutiny 是故意把实时故事做简单的。

`events()` 产出的是公共投影模型，而不是内部运行时记录：

- `ProgressUpdate`
- `JobSnapshot`

这就是宿主应用应当围绕其构建的契约。

## 事件流 API

- `Mutiny.events()`
- `Mutiny.events(job_id=...)`

当你需要会话级事件流时，用 `events()`。当你只想看单个任务的窄流时，用 `events(job_id=...)`。

```python
from mutiny import JobSnapshot, ProgressUpdate


async def consume_all(client):
    stream = client.events()
    try:
        async for update in stream:
            if isinstance(update, ProgressUpdate):
                print("Progress:", update.job_id, update.status_text)
            elif isinstance(update, JobSnapshot):
                print("Job:", update.id, update.status.name, update.kind)
    finally:
        await stream.aclose()
```

把它当成一条连续事件流来处理。集中在一个地方消费，再扇出到应用其他部分。

## `ProgressUpdate`

`ProgressUpdate` 是轻量级的“还在推进中”事件。

字段：

- `job_id`
- `status_text`
- `preview_image_url`

适用场景：

- 活动日志
- 状态胶囊
- 加载指示器
- 进行中的预览缩略图

`preview_image_url` 是可选的。存在时，它就是 Mutiny 在当前时刻所知道的预览/进度图。

## `JobSnapshot`

`JobSnapshot` 是一个任务的持久化公共状态。

字段：

- `id`
- `kind`
- `status`
- `progress_text`
- `preview_image_url`
- `fail_reason`
- `prompt_text`
- `output`

大多数宿主应用最先关心的是：

- `kind` 是小写动作名，例如 `"imagine"`、`"describe"` 或 `"animate_low"`
- `status` 是 `JobStatus`
- `prompt_text` 是 Mutiny 目前掌握的该任务最佳公共提示词文本
- `output` 是 `ImageOutput`、`VideoOutput`、`TextOutput` 或 `None`

在最终输出准备好之前，`preview_image_url` 很有用。最终结果则落在 `output` 上。

## `JobSnapshot.output`

`output` 字段是一个小 union，而不是一个庞大的兜底对象。

- `ImageOutput` 表示任务解析成了图像结果
- `VideoOutput` 表示任务解析成了视频结果
- `TextOutput` 表示任务解析成了文本结果，这就是 `describe()` 的产物
- `None` 表示任务还没有公共最终输出

这种形状能让宿主代码保持相当无聊：

```python
from mutiny import ImageOutput, JobSnapshot, TextOutput, VideoOutput


def render_result(snapshot: JobSnapshot) -> None:
    if isinstance(snapshot.output, ImageOutput):
        print("Image:", snapshot.output.image_url)
    elif isinstance(snapshot.output, VideoOutput):
        print("Video:", snapshot.output.video_url or snapshot.output.website_url)
    elif isinstance(snapshot.output, TextOutput):
        print("Text:", snapshot.output.text)
```

## 推荐消费模式

这里无聊的架构就是好架构：

1. 启动一个长期存在的 consumer task
2. 由这个 task 更新你的中心模型或存储
3. 再由那个模型驱动 UI、websocket 和通知

不要在事件循环里阻塞。如果某个处理器需要昂贵工作，把它移交出去，保持 consumer 持续排空更新。

如果宿主应用只关心一个任务，过滤后的流就很合适：

```python
async def watch_job(client, job_id: str) -> None:
    stream = client.events(job_id=job_id)
    try:
        async for update in stream:
            print(update)
    finally:
        await stream.aclose()
```

## 实用限制

这些是有用的约束，不是戏剧化表述：

- 这个流是会话范围的，不是历史回放系统
- 恢复辅助方法可以之后从持久化产物缓存里把已保存媒体重新接回来，但不会重放旧的实时事件流
- 一个持久化 consumer 比一群短命监听器更像样

如果你的应用需要在重启时重建状态，请组合使用：

- 持久化的应用状态
- `list_jobs()` 和 `get_job()`
- `resolve_image()` / `resolve_video()`

## 调试与转储

在配置允许的情况下，Mutiny 可以写出响应和 gateway 诊断信息。

相关配置：

- `websocket.capture_enabled`
- `cache.response_dump_dir`

文件会写进已配置的转储目录，默认是 `.cache/mutiny/mj_responses`。

常见产物包括：

- 按消息分开的 JSON 载荷文件
- `index.jsonl` 摘要
- 形如 `gw_*.json` 的 gateway 捕获文件

把这些转储文件当成敏感诊断信息，而不是无害的日志碎屑。

## 另请参阅

- [视频与产物工作流](video-and-artifact-workflows.md)
- [故障排查](troubleshooting.md)
- [API 参考](api-reference.md)

**继续 ->** [视频与产物工作流](video-and-artifact-workflows.md)
