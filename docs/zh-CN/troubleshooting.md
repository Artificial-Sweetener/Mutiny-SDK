**<- 上一页：** [视频与产物工作流](video-and-artifact-workflows.md)

# 故障排查

当你的集成行为和预期不一致时，就看这一页。

先找到与你看到的现象最匹配的症状，再从那里向外排查。

## 客户端一直无法进入就绪状态

症状：

- `await client.wait_ready(...)` 返回 `False`
- 或者启动一直卡到超时

检查：

- 令牌是否有效
- guild 和 channel id 是否正确
- 目标账号是否真的能访问那个 channel
- 你的网络环境是否在干扰 Discord websocket 流量

另外也要确认在等待之前已经启动了客户端：

```python
await client.start()
ready = await client.wait_ready(timeout_s=60)
```

## `Config.create(...)` 抛异常

常见原因：

- 缺少 `token_provider`
- 缺少 `guild_id`
- 缺少 `channel_id`
- mapping 覆写里存在无效的 section 键
- 同时提供了 `engine=` 和 `execution=...`

如果你是在从 dict 重建：

- `Config.from_dict(...)` 需要 `token_provider`
- 当源是普通 mapping 时，`Config.configure(...)` 也需要 `token_provider`

## `wait_for_job()` 超时

症状：

- `await client.wait_for_job(job_id, timeout_s=...)` 因超时而抛异常

检查：

- 任务 id 是否正确
- 客户端是否仍在运行并保持连接
- 任务是否真的进入了 Mutiny 的存储
- 你的超时设置是否符合提交的任务类型

`wait_for_job()` 是终态辅助方法，不是传输层看门狗。如果你在等待时需要实时信心，就把它和 `events(job_id=...)` 搭配起来。

## 某个后续操作被拒绝

通常这意味着该操作和恢复出来的交互表面其实并不匹配。

检查：

- 你是否给 `upscale(...)` 或 `vary(...)` 提供了必需的 `index`
- 该操作对当前源交互表面是否有效
- 源任务是否真的成功了
- 源图像/视频是否被识别出来了

重要规则：

- 按分块寻址的后续操作，需要它来自的那个分块索引

如果用户操作的是已保存产物而不是实时任务，先优先走识别辅助方法，而不是假设一个陈旧的 `job_id` 仍然可用。

## `events()` 产出的内容和预期不一样

症状：

- 你的代码在等原始 job 或旧版 progress 对象
- 你的类型判断永远匹配不上
- 你的 UI 永远拿不到预期字段

检查：

- `events()` 产出的是 `ProgressUpdate` 和 `JobSnapshot`
- 提交方法返回的是 `JobHandle`，不是原始字符串
- 持久结果数据在 `JobSnapshot.output` 上
- 预览数据在 `ProgressUpdate.preview_image_url` 和 `JobSnapshot.preview_image_url` 上

如果宿主应用还建立在旧假设上，先修宿主模型。只有当你的应用在监听正确的公共类型时，这条事件流才有意义。

## `resolve_image()` 返回 `None`

症状：

- `resolve_image(...)` 返回 `None`

检查：

- 这张图是否来自一个 Mutiny 观察过的 Midjourney 流程
- 产物缓存和磁盘缓存是否被保留下来
- 你喂进去的是已保存输出，还是轻度重编码的副本，而不是严重编辑过的衍生图

识别基于 Mutiny 持久化的精确签名和模糊签名。轻度重编码在已存模糊签名仍足够接近时，仍可能识别成功。重度编辑、裁剪或大幅重新压缩，则仍然会破坏可恢复身份。

## `resolve_video()` 返回 `None`

症状：

- `resolve_video(...)` 返回 `None`
- `extend(video=...)` 因为无法识别视频而失败

检查：

- 这个视频是否是 Mutiny 以前见过的 animate-family 输出
- 底层产物缓存是否还在
- 这些字节是否被重新编码或转码过

视频恢复依赖持久化的视频签名索引。它不是一个“识别任何看起来像 Midjourney 的视频”的通用功能。

## 本地路径输入失败

症状：

- `describe()`、`vary_region()`、`animate()`、`extend()` 或某个恢复辅助方法在提交前就抛异常

检查：

- 路径是否存在
- 路径是否真的是你以为的那个文件
- 是否能从扩展名或字节识别图像类型

Mutiny 把本地路径输入当作便利功能，不是魔法路径猜测。缺失文件会抛 `FileNotFoundError`。未知图像类型可能会抛 `ValueError`。

## 远程 URL 输入失败

症状：

- 某个提交或恢复辅助方法在抓取远程图像或视频 URL 时抛异常

检查：

- 运行 Mutiny 的机器是否能访问该 URL
- 服务器是否允许抓取
- 响应内容是否真的是你预期的媒体

远程 URL 会在输入归一化期间被抓取。HTTP 失败会原样冒泡，而不是被静默吞掉。

## 我需要原始证据

Mutiny 给你两个有用的诊断旋钮：

- `websocket.capture_enabled`
- `cache.response_dump_dir`

示例：

```python
config = Config.create(
    token_provider=my_token_provider,
    guild_id="123",
    channel_id="456",
    websocket={"capture_enabled": True},
    cache={"response_dump_dir": ".cache/mutiny/mj_responses"},
)
```

有用的输出文件：

- `.cache/mutiny/mj_responses/index.jsonl`
- 按消息输出的 JSON 载荷文件
- 形如 `gw_*.json` 的 gateway 转储文件

### 一个重要细节

`websocket.capture_enabled` 控制的是 gateway 事件转储。

它**不表示**“除非它开启，否则任何类型的转储文件都不会存在”。在当前实现里，reactor 驱动的消息转储会走同一套 response dump 服务，但经由不同路径写进 `response_dump_dir`。

如果转储行为让你意外，请检查：

- 这个文件是 gateway 转储还是消息转储
- 它写进了哪个配置目录
- gateway 捕获是否真的被显式启用

## Mutiny 升级后宿主应用坏了

这通常是陈旧假设的问题。

常见排查方向：

- 代码仍在假设旧事件类型，而不是 `ProgressUpdate` 和 `JobSnapshot`
- 代码仍把提交结果当作原始 id，而不是 `JobHandle`
- 代码仍在假设已删除的恢复辅助方法存在
- 代码在假设产物恢复会重放历史事件
- 代码在假设只存在于 RAM 的 modal 或 iframe 状态能跨进程重启保留

修法通常也差不多：

1. 把宿主集成和当前公共门面对一遍
2. 查 [API 参考](api-reference.md)
3. 查 [配置参考](configuration-reference.md)
4. 如果变化深入到门面之下，就去看转储文件

## 有帮助的工具

- [事件](events.md)：事件流行为和转储语义
- [视频与产物工作流](video-and-artifact-workflows.md)：恢复相关行为
- [../tools/README.md](../tools/README.md)：捕获和一致性工具

**继续 ->** [API 参考](api-reference.md)
