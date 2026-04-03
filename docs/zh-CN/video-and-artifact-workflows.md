**<- 上一页：** [事件](events.md)

# 视频与产物工作流

之所以需要这一页，是因为 Mutiny 最有用的一类行为，同时也是最不显眼的一类行为之一：

已保存的输出产物不必变成死文件。

Mutiny 往往可以识别先前保存的图像或视频，恢复其背后的 Midjourney 上下文，并把你的应用重新接回可用工作流。

## 心智模型

这里有三个恢复辅助方法：

- `resolve_image(...)`
- `resolve_video(...)`
- `split_image_result(...)`

这很重要，因为应用通常只想要两类东西中的一种：

- 足够的源身份信息，用来决定该显示哪些控件
- 一个分块投影，用来重建网格类后续操作

## 图像恢复

相关辅助方法：

- `Mutiny.resolve_image(image)`
- `Mutiny.split_image_result(job_id, image)`

`resolve_image(...)` 返回 `ImageResolution | None`。

它会给你：

- `job_id`
- `index`

`index` 表示识别出来的是哪种交互表面：

- `0` 表示单图表面
- `1` 到 `4` 表示网格分块

当你要从已保存图像里重建后续操作控件时，这个索引很关键。

`split_image_result(job_id, image)` 方向相反：它接收一张已知结果图像，并返回一组可用于挂 UI 的 `ImageTile` 值。

对待 Pan 结果时，应和其他 2x2 Midjourney 网格一样处理：

- 当宿主应用需要分块级控件时，把它拆成分块
- 当后续操作是按分块寻址时，保留恢复出来的分块 `index`
- 对于只能作用在单图表面上的后续操作，预期它会通过与其他网格分块一致的提升表面行为来路由

对待已完成的 zoom 结果时，也应如此：

- 固定 zoom 和 custom zoom 输出都会作为 2x2 网格分块恢复
- `split_image_result(...)` 应当把这些输出投影为四个逻辑分块
- 后续基于已保存产物的操作，应像处理 Pan 和 variation-family 网格一样使用恢复得到的分块索引

## 视频恢复

相关辅助方法：

- `Mutiny.resolve_video(video)`

`resolve_video(...)` 返回 `VideoResolution | None`。

直白地说：Mutiny 会对已保存剪辑做指纹匹配，把它与持久化的 animate-family 输出对上号；如果成功，就把源 `job_id` 还给你。

## 重启之后的缓存恢复

这是恢复表面开始真正发挥价值的地方。

如果进程重启导致实时任务存储为空，识别流程仍然可以恢复足够的源身份信息，让宿主应用重建有用控件。

这意味着：

- 原始运行时会话可能已经没了
- 但这个产物仍然能从持久化产物缓存里恢复出足够的上下文，用于后续操作
- 可跨重启的恢复依赖于磁盘支持的产物缓存，而不是会话内 RAM 缓存

恢复**做不到**的是：

- 重放历史事件流
- 假装原始运行时会话仍然活着
- 把无法识别的衍生文件硬说成已知源产物
- 在跨进程之后恢复实时 modal 或 iframe 交互状态

恢复是用来重建控件的，不是用来伪造完整事件历史的。

## `animate(...)` 路由选择

在门面下面，`Mutiny.animate(...)` 实际上有两条路。

### 后续操作式 Animate 路由

当满足以下条件时，Mutiny 优先走原生后续操作路径：

- `start_frame_data_url` 是一张可识别的 Midjourney upscale 图像
- 没有提供 `end_frame_data_url`
- 没有使用仅属于 prompt-video 的控制项
- 没有提供 `batch_size`

这是最原生的“基于现有结果做 animate”路径。

### Prompt-Video 路由

当你提供了只在那条路径上才有意义的控制项时，Mutiny 会退回到 prompt-video 生成，例如：

- `end_frame_data_url`
- 非空提示词
- `batch_size`

它依旧通过同一个公共方法暴露出来，但底层走的已不是同一条 Midjourney 路线。

## `extend(...)` 路由选择

`Mutiny.extend(...)` 也有两条上下文路径。

### 实时任务路径

当 animate-family 任务还在实时存储里时，使用 `job_id=...`。

要求：

- 任务必须存在
- 任务必须处于 `JobStatus.SUCCEEDED`
- 任务动作必须属于 animate-family 动作之一

### 已识别视频路径

当你手里只剩已保存输出视频时，使用 `video=...`。

要求：

- 这个视频必须能被持久化签名索引识别

这条恢复路径会让旧视频在原始实时任务已经不存在之后，仍然保持可用。

## 实用模式

### 为已保存图像重建控件

```python
resolution = client.resolve_image(saved_image_bytes)
if resolution is not None:
    print("Recovered job:", resolution.job_id, "index:", resolution.index)
```

### 把已知网格重新拆回分块

```python
tiles = client.split_image_result(job_id="job-grid", image=saved_grid_bytes)
for tile in tiles:
    print("Tile:", tile.job_id, tile.index, len(tile.image_bytes))
```

### 为已保存视频重建控件

```python
resolution = client.resolve_video(saved_video_bytes)
if resolution is not None:
    print("Recovered animate-family job:", resolution.job_id)
```

### 从已保存视频做 Extend

```python
extend = await client.extend(video=saved_video_bytes)
```

## 常见陷阱

- 被识别出来的产物，不等于被重放出来的事件历史
- `resolve_image()` 会给你一个 `index`；`resolve_video()` 不会
- `split_image_result()` 需要已知 `job_id`，因为分块投影依赖源任务
- `animate(...)` 会根据你提供的输入切换路线
- `extend(video=...)` 只适用于 Mutiny 能识别的视频

如果恢复失败，先看 [故障排查](troubleshooting.md)，再去假设这个功能坏了。大多数失败都来自缺上下文、产物无法识别，或者宿主应用以为自己知道的事情和运行时实际知道的事情并不一致。

**继续 ->** [故障排查](troubleshooting.md)
