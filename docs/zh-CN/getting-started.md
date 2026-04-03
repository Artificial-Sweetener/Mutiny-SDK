# 快速开始

[English](../getting-started.md) | **简体中文**

当“直接手动用 Discord”已经不能算是一份正经架构方案时，Mutiny 就是为那个时刻准备的。

本指南会带你完成最小但有用的集成：

- 安装包
- 构建一个 `Config`
- 启动客户端
- 提交一个任务
- 等待真实结果
- 理解当宿主应用开始长大时，实时事件该放在哪个位置

> **开始之前：** 先阅读 [重要免责声明](../../README.zh-CN.md#重要免责声明)。本指南默认你已经理解使用 Mutiny 所涉及的账号风险、token 处理风险和平台风险。

## 安装

```bash
pip install mutiny-sdk
```

安装名是 `mutiny-sdk`。Python 导入名保持为 `mutiny`。

## 最小集成

```python
import asyncio

import keyring

from mutiny import Config, JobStatus, Mutiny


class KeyringTokenProvider:
    def __init__(self, service: str, username: str = "mj_user_token") -> None:
        self._service = service
        self._username = username

    def get_token(self) -> str:
        token = keyring.get_password(self._service, self._username)
        if not token:
            raise RuntimeError(
                f"Missing token in keyring for service={self._service!r} user={self._username!r}"
            )
        return token


async def main() -> None:
    config = Config.create(
        token_provider=KeyringTokenProvider("mutiny"),
        guild_id="YOUR_GUILD_ID",
        channel_id="YOUR_CHANNEL_ID",
    )
    client = Mutiny(config)

    await client.start()
    try:
        if not await client.wait_ready(timeout_s=60):
            raise RuntimeError("Gateway not ready")

        handle = await client.imagine("futuristic city skyline at dusk")
        print("Submitted job:", handle.id)

        snapshot = await client.wait_for_job(handle.id, timeout_s=180)
        print("Final status:", snapshot.status.name)

        if snapshot.status is JobStatus.SUCCEEDED and snapshot.output is not None:
            print("Output:", snapshot.output)
    finally:
        await client.close()


asyncio.run(main())
```

这就是最小且不自欺欺人的集成：

- `Config.create(...)` 构建配置快照
- `Mutiny(config)` 拥有运行中的会话
- 提交会返回 `JobHandle`
- `wait_for_job(handle.id)` 会返回 `JobSnapshot`

## `JobHandle` 是干什么的

`JobHandle` 是提交之后立刻拿到的回执。你调用 `imagine()`、`describe()`、`blend()` 或其他任何提交方法后，handle 会通过 `handle.id` 给你新的任务 id。

这个 id 用在：

- `wait_for_job(handle.id)`
- `events(job_id=handle.id)`
- `get_job(handle.id)`
- 之后绑定到源任务的后续操作

## 什么时候该用实时事件

`wait_for_job()` 是最干净的第一条成功路径，但多数真实宿主应用最终都需要实时更新。

`Mutiny.events()` 会产出两种公共事件类型：

- `ProgressUpdate`，用于在途状态文本和预览图
- `JobSnapshot`，用于持久化任务状态

这通常会映射成类似这样的宿主应用行为：

- 用 `JobSnapshot` 驱动你的主存储、数据库行或 UI 模型
- 用 `ProgressUpdate` 显示临时状态文本、预览缩略图和活动指示器

下面是最小的单任务事件监听器：

```python
from mutiny import JobSnapshot, ProgressUpdate


async def watch_job(client: Mutiny, job_id: str) -> None:
    stream = client.events(job_id=job_id)
    try:
        async for update in stream:
            if isinstance(update, ProgressUpdate):
                print("Progress:", update.job_id, update.status_text)
            elif isinstance(update, JobSnapshot):
                print("Job:", update.id, update.status.name, update.kind)
                if update.status in {JobStatus.SUCCEEDED, JobStatus.FAILED}:
                    break
    finally:
        await stream.aclose()
```

## 把事件总线集中在一个地方消费

`Mutiny.events()` 是消防水带。就按消防水带来对待。

最稳妥的模式是：

1. 跑一个长期存在的 consumer task
2. 在那里更新你的存储或内存模型
3. 再从这个模型扇出到 websocket、UI 组件或任务级监听器

不要在应用里到处散落随机 consumer，然后指望它们最后都能保持一致。

## 关于输入的一点说明

后面的页面提到图像或视频参数时，你通常可以直接传宿主应用手上已经有的东西：

- 原始 `bytes`
- 本地路径字符串
- 本地 `Path`
- 远程 `http/https` URL
- 现成的 data URL

这在 `describe()`、`vary_region()`、`animate()`、`extend()` 和恢复辅助方法里尤其有用。

## 开发环境设置

即使是在本地开发里，也尽量把公共心智模型保持简单：

- 构建一个 `Config`
- 把它交给 `Mutiny`
- 把基于 env 的捷径当成工具层面的便利，而不是产品故事本身

这样你的宿主代码从第一天起就会更诚实。

## 接下来读什么

- 想调整传输、缓存或引擎行为？读 [配置](configuration.md)。
- 想从头到尾理解客户端和生命周期？读 [门面与生命周期](facade-and-lifecycle.md)。
- 想看后续操作、分块规则和动画路由？读 [任务操作](job-actions.md)。
- 想更深入理解实时事件模型？读 [事件](events.md)。

**继续 ->** [配置](configuration.md)
