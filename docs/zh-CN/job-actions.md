**<- 上一页：** [门面与生命周期](facade-and-lifecycle.md)

# 任务操作

这一页回答的是很实际的问题：我到底能发什么，以及每种操作需要什么上下文？

所有公共提交方法都会返回 `JobHandle`。这个 handle 会立刻通过 `handle.id` 给你新的任务 id；后面不管是 `events(job_id=...)`、`wait_for_job()`、`get_job()` 还是后续操作，都是靠它。

## 一条到处都值回票价的输入规则

当某个方法接收图像或视频时，Mutiny 接受的就是宿主应用手里大概率已经有的那些形状：

- 原始 `bytes`
- 本地路径 `str`
- 本地 `Path`
- 远程 `http/https` URL
- 现成的 data URL

这是门面替你做的便利工作。你不需要在调用客户端前先把所有输入预处理成 data URL。

## 创建新任务

### `imagine(...)`

当你从提示词文本开始时，用 `imagine()`。

- `prompt` 是必需的
- `prompt_images` 用来附加提示词图像
- `style_references` 用来附加风格参考图
- `character_references` 用来附加角色参考图
- `omni_reference` 用来附加一张 omni 参考图
- 返回 `JobHandle`

```python
handle = await client.imagine(
    "editorial portrait, wet pavement, sodium-vapor glow",
    prompt_images=("C:\\images\\street.png",),
    style_references=("https://example.com/style-board.webp",),
)
```

### `describe(...)`

当你想让 Midjourney 把一张图变成提示词文本时，用 `describe()`。

- 接收一张图像输入
- 返回 `JobHandle`
- 终态输出会以 `TextOutput` 的形式出现在最终 `JobSnapshot` 上

```python
handle = await client.describe("C:\\images\\mood-board.jpg")
```

### `blend(...)`

当输入本身才是重点时，用 `blend()`。

- 接收 `images: tuple[...]`
- 接受 2 到 5 张图像
- 提交前会拒绝重复图像
- `dimensions` 会变成 Midjourney 的宽高比选择
- 返回 `JobHandle`

```python
handle = await client.blend(
    (
        "C:\\images\\look-1.webp",
        "C:\\images\\look-2.webp",
    ),
    dimensions="16:9",
)
```

### `vary_region(...)`

当你已经明确知道要提交哪张底图和哪张遮罩时，用 `vary_region()`。

- 接收 `image` 和 `mask`
- 可选 `prompt` 用来引导编辑
- 返回 `JobHandle`

```python
handle = await client.vary_region(
    image="C:\\images\\base.png",
    mask="C:\\images\\mask.png",
    prompt="keep the composition, add ivy and rain streaks",
)
```

## 基于已知任务做后续操作

当宿主应用已经知道源 `job_id` 时，下面这些方法就是常规后续路径。

### `upscale(...)`

- 需要 `job_id`
- 需要 `index`
- `mode` 可选 `"standard"`、`"subtle"` 或 `"creative"`
- 返回 `JobHandle`

### `vary(...)`

- 需要 `job_id`
- 需要 `index`
- `mode` 可选 `"standard"`、`"subtle"` 或 `"strong"`
- 返回 `JobHandle`

### `pan(...)`

- 需要 `job_id`
- 需要 `direction`，取值为 `"left"`、`"right"`、`"up"` 或 `"down"`
- 当源交互表面是按分块寻址时，可提供 `index`
- 返回 `JobHandle`

Pan 结果一旦完成，就应该像普通 2x2 网格那样处理。如果宿主应用需要分块级后续操作，或以后要从已保存图像中恢复，请保留对应分块的 `index`。

### `zoom(...)`

- 需要 `job_id`
- 接收 `factor`
- `prompt` 对 custom zoom 文本来说是可选的
- 当源交互表面是按分块寻址时，可提供 `index`
- 返回 `JobHandle`

`zoom(..., factor=2.0)` 和 `zoom(..., factor=1.5)` 会走 Midjourney 原生 zoom 路径。其他倍数会走 custom zoom 路径，但公共方法保持不变。

已完成的 zoom 输出应被视为普通 2x2 网格，而不是最终的单图表面。如果宿主应用之后需要分块级后续操作或已保存产物恢复，请保留恢复得到的分块 `index`。

```python
base = await client.imagine("cathedral interior in gold and smoke")

upscale = await client.upscale(base.id, index=1)
zoomed = await client.zoom(upscale.id, factor=1.75, prompt="tighter on the altar")
```

## 动画流程

### `animate(...)`

当你要从一张图开始做运动时，用 `animate()`。

- `start_frame` 是必需的
- `end_frame` 是可选的
- `prompt` 是可选的
- `motion` 可选 `"low"` 或 `"high"`
- 如果提供 `batch_size`，则必须是 `1`、`2` 或 `4`
- 返回 `JobHandle`

实际行为：

- 如果 Mutiny 能把起始帧识别成兼容的 Midjourney 表面，并且你走的是简单后续路径，它会复用那条路径
- 如果你提供了只在 prompt-video 流程里才有意义的控制项，比如结束帧、提示词文本或批量大小，Mutiny 就会提交 prompt-video 风格请求

这样公共方法就能保持简单，同时尽量走最合适的路径。

### `extend(...)`

当源运动结果已经存在时，用 `extend()`。

- 如果你手里还有 animate-family 任务，就传 `job_id`
- 如果用户是之后带着已保存剪辑回来的，就传 `video`
- `motion` 可选 `"low"` 或 `"high"`
- 返回 `JobHandle`

```python
animate = await client.animate("C:\\frames\\start.png", motion="high")
extended = await client.extend(job_id=animate.id, motion="low")
```

## 状态标签

每个提交方法都接受 `state`，用于宿主应用给任务打一个小的关联字符串。

这对下面这些场景有用：

- 把某个 UI 操作重新接回之后的任务快照
- 把宿主侧工作流 id 串进提交过程
- 给一次性任务打日志标签

如果你不需要，就忽略它。

## 这些交互表面规则值得知道

Mutiny 尽量让后续操作路由从外面看起来很无聊，但有几条规则值得记住：

- 基于分块的后续操作需要分块索引
- Pan 结果完成后会进入同一套分块系统
- zoom 结果完成后也会进入同一套分块系统
- 某些后续操作即使用户是从网格分块开始，也会作用在提升后的单图表面上
- 这个提升步骤仍然发生在同一个公共任务里，不会变成第二套需要你手动驱动的公共 API

从宿主应用视角看，实用结论很简单：

- 当你知道源任务时，就用 `job_id`
- 当你需要分块特定的后续操作时，就保留分块索引
- 当你之后只剩已保存媒体时，就用 [视频与产物工作流](video-and-artifact-workflows.md) 里的恢复辅助方法

## 常见流程

### Imagine -> Upscale

```python
base = await client.imagine("portrait of an astronaut in watercolor")
upscaled = await client.upscale(base.id, index=1)
```

### 已知任务 -> Variation

```python
base = await client.imagine("botanical illustration, moonlit greenhouse")
variant = await client.vary(base.id, index=2, mode="strong")
```

### 区域编辑

```python
edit = await client.vary_region(
    image="C:\\images\\portrait.png",
    mask="C:\\images\\fog-mask.png",
    prompt="keep lighting, add subtle fog",
)
```

### Animate 与 Extend

```python
animate = await client.animate("C:\\frames\\start.png")
extend = await client.extend(job_id=animate.id)
```

**继续 ->** [事件](events.md)
