**<- 上一页：** [故障排查](troubleshooting.md)

# API 参考

Mutiny 的快速公共地图：你从 `mutiny` 导入什么、门面返回什么、接下来该用哪个方法。

如果你想先看叙述性上下文，请从这些指南开始：

- [快速开始](getting-started.md)
- [门面与生命周期](facade-and-lifecycle.md)
- [任务操作](job-actions.md)
- [事件](events.md)
- [视频与产物工作流](video-and-artifact-workflows.md)

## 包根导入

下面这些都直接从 `mutiny` 导入：

- `Mutiny`
- `Config`
- `JobHandle`
- `JobSnapshot`
- `ProgressUpdate`
- `JobStatus`
- `ImageResolution`
- `VideoResolution`
- `ImageTile`
- `ImageOutput`
- `VideoOutput`
- `TextOutput`
- `__version__`

```python
from mutiny import Config, JobHandle, JobSnapshot, JobStatus, Mutiny, ProgressUpdate
```

## 门面初始化

- `Mutiny(config: Config)` 会围绕一个自有配置快照创建一个客户端。
- `Mutiny.start() -> None` 启动运行时和 gateway 相关工作。
- `Mutiny.wait_ready(timeout_s: int | None = None) -> bool` 等待 gateway 进入就绪状态。
- `Mutiny.close() -> None` 关闭运行时。
- `Mutiny.events(job_id: str | None = None) -> AsyncIterator[ProgressUpdate | JobSnapshot]` 为所有任务或单个任务流出实时更新。

完整客户端故事见 [门面与生命周期](facade-and-lifecycle.md)。

## 提交方法

所有提交方法都返回 `JobHandle`。后续查询、实时事件过滤和后续操作都请使用 `handle.id`。

- `Mutiny.imagine(prompt: str, *, prompt_images=(), style_references=(), character_references=(), omni_reference=None, state=None) -> JobHandle`
  从文本和可选图像参考创建新的图像任务。
- `Mutiny.describe(image, *, state=None) -> JobHandle`
  从一张图生成提示词文本。
- `Mutiny.vary_region(image, mask, *, prompt=None, state=None) -> JobHandle`
  使用底图加遮罩执行区域编辑。
- `Mutiny.blend(images, *, dimensions="1:1", state=None) -> JobHandle`
  提交一个由 2 到 5 张图像组成的 blend。
- `Mutiny.upscale(job_id: str, *, index: int, mode="standard", state=None) -> JobHandle`
  基于已知任务和分块索引执行 upscale 风格后续操作。
- `Mutiny.vary(job_id: str, *, index: int, mode="standard", state=None) -> JobHandle`
  基于已知任务和分块索引执行 variation 后续操作。
- `Mutiny.pan(job_id: str, *, index=None, direction, state=None) -> JobHandle`
  基于已知任务执行 pan 后续操作。已完成的 Pan 结果使用和其他 2x2 图像网格一样的网格分块恢复与拆分表面。
- `Mutiny.zoom(job_id: str, *, index=None, factor: float, prompt=None, state=None) -> JobHandle`
  执行 zoom 后续操作。`2.0` 和 `1.5` 会映射到原生 zoom 动作；其他倍数会在底层使用 custom zoom 文本。已完成的 zoom 输出使用与其他 2x2 图像网格相同的网格分块恢复与拆分表面。
- `Mutiny.animate(start_frame, *, end_frame=None, prompt=None, motion="low", batch_size=None, state=None) -> JobHandle`
  从一个起始帧启动动画流程，可选结束帧和 prompt-video 控制项。
- `Mutiny.extend(*, job_id=None, video=None, motion="low", state=None) -> JobHandle`
  基于已知任务或已识别的已保存视频，延长一个 animate-family 结果。

图像参数接受原始 `bytes`、本地路径字符串、`Path` 对象、远程 `http/https` URL 和现成 data URL。视频参数接受同样面向宿主应用的形状。

工作流指导和示例见 [任务操作](job-actions.md)。

## 观察与恢复

- `Mutiny.get_job(job_id: str) -> JobSnapshot`
  返回某个已知任务当前的公共快照。
- `Mutiny.wait_for_job(job_id: str, *, timeout_s: float | None = None) -> JobSnapshot`
  等待任务进入终态，并返回最终快照。
- `Mutiny.list_jobs(*, status: JobStatus | None = None, active_only: bool = False) -> list[JobSnapshot]`
  以公共快照形式列出已知任务。
- `Mutiny.resolve_image(image) -> ImageResolution | None`
  试图把一张已保存图像重新接回其源任务和分块索引。
- `Mutiny.resolve_video(video) -> VideoResolution | None`
  试图把一段已保存视频重新接回其源 animate-family 任务。
- `Mutiny.split_image_result(job_id: str, image) -> tuple[ImageTile, ...]`
  把一张已知结果图像拆成由门面拥有的分块，用于宿主侧后续操作 UI。

见 [门面与生命周期](facade-and-lifecycle.md)、[事件](events.md) 和 [视频与产物工作流](video-and-artifact-workflows.md)。

## 公共模型

- `JobHandle`
  稳定的提交结果，只有一个字段：`id`。
- `ProgressUpdate`
  轻量级实时进度更新，含 `job_id`、`status_text` 和可选 `preview_image_url`。
- `JobSnapshot`
  持久化公共任务视图，字段有：
  `id`、`kind`、`status`、`progress_text`、`preview_image_url`、`fail_reason`、`prompt_text` 和 `output`。
- `ImageOutput`
  已完成图像结果，含 `image_url` 和可选 `local_file_path`。
- `VideoOutput`
  已完成视频结果，含可选 `video_url`、`local_file_path` 和 `website_url`。
- `TextOutput`
  已完成文本结果，含 `text`。
- `ImageResolution`
  已识别图像的源元数据，含 `job_id` 和 `index`。
- `VideoResolution`
  已识别视频的源元数据，含 `job_id`。
- `ImageTile`
  拆分后的分块投影，含 `job_id`、`index` 和原始 `image_bytes`。
- `JobStatus`
  公共状态枚举，供 `JobSnapshot.status` 和 `list_jobs(status=...)` 使用。

## Config

- `Config.create(...) -> Config`
  新建配置快照的主构造器。
- `Config.configure(...) -> Config`
  基于基础配置或配置 mapping 加上覆写，返回一个新配置。
- `Config.from_dict(...) -> Config`
  从 `as_dict()` 输出重建配置快照。
- `Config.copy() -> Config`
  深拷贝当前快照。
- `Config.as_dict() -> dict[str, Any]`
  返回适合存储或检查的稳定嵌套 mapping。

见 [配置](configuration.md) 和 [配置参考](configuration-reference.md)。

## 异常形状

门面调用抛出普通 Python 异常：

- `ValueError` 用于校验失败
- `RuntimeError` 用于运行时或服务失败

这正是重点。公共客户端应该感觉像一个完整产品表面，而不是一堆传输层返回对象。

**返回 ->** [Mutiny 文档](README.md)
