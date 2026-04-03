# Mutiny

[English](README.md) | **简体中文**

[![License: AGPL v3+](https://img.shields.io/badge/License-AGPLv3%2B-blue.svg)](LICENSE) [![semantic-release](https://img.shields.io/badge/semantic--release-angular-e10079?logo=semantic-release)](https://github.com/semantic-release/semantic-release) [![PyPI](https://img.shields.io/pypi/v/mutiny-sdk.svg)](https://pypi.org/project/mutiny-sdk/) [![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/) [![OpenCV](https://img.shields.io/badge/OpenCV-4.10%2B-5C3EE8?logo=opencv&logoColor=white)](https://opencv.org/)

**Mutiny** 是一个**非官方**、**无关联方背书**的 Python 库，用来把 Midjourney 放进你自己的应用里。

你会得到一个清晰的门面接口（`Mutiny`）、一个配置表面（`Config`）、一个实时事件模型、面向已保存输出产物的恢复辅助方法，以及一整套后续操作表面，让你能构建真正的产品工作流，而不是一次性的提示词脚本。

公开契约刻意保持得很小：

- 用一个客户端提交
- 拿回一个 `JobHandle`
- 通过 `ProgressUpdate` 和 `JobSnapshot` 观察任务
- 之后可用 `resolve_image()`、`resolve_video()` 和 `split_image_result()` 恢复有用上下文

Mutiny 是……

- 面向宿主应用的单账号 Midjourney 集成表面。
- 为图像和视频工作流而建，不只是一次性提示词。
- 让已保存的输出产物继续有用：Mutiny 往往能在之后识别旧图像或视频，并把它重新接回下一步有效操作。

Mutiny 不是……

- 绕过 Midjourney 订阅、审核或账号限制的手段。
- 多账号自动化框架。
- 令牌保险箱。只要你准备真正上线，就请接入一个正经的 `TokenProvider`。

## 重要免责声明

Mutiny 与 Discord 和 Midjourney 的交互方式，可能会被解释为违反它们的服务条款。**我们不对安全性作任何保证。** 使用 Mutiny 可能导致你的 Discord 账号、Midjourney 账号，或两者都受到处理，包括警告、限制或封禁。

Mutiny 的设计目标是尽量礼貌、保守地运行。它并不打算用于刷屏、猛打接口、规避限制，或实施滥用行为。我们不认为大多数正当用户一定会遇到问题，但我们也不能作出承诺。你需要在使用前自行判断并承担相关风险。

Mutiny 运行时需要你的 **Discord token**。那是敏感的账号访问凭据。处理这类凭据本身就有风险；一旦泄露或处理不当，其他人就可能获得你 Discord 账号的访问权限。Mutiny 围绕 `TokenProvider` 设计，但安全存储和安全处理仍然是宿主应用的责任。

Mutiny 还要求你拥有一个**付费 Midjourney 账号**。它不是用来白嫖 Midjourney 的工具。它并不为绕过 Midjourney 的审核系统、付费要求、速率限制或其他平台约束而设计。它也不打算用于运行多个账号，或跨多个账号执行自动化活动。Mutiny 面向的是单个用户对其自有账号的正当使用。

## 为什么会有 Mutiny

Midjourney 太有意思了，不该永远被困在一个聊天窗口里。

常见替代方案各有各的麻烦：

- 手动用 Discord，在产品还不需要状态恢复和像样 UI 之前还勉强说得过去
- 脆弱的按钮抓取代码，通常很快就会变质
- 那些只能提交提示词、却说不清后续发生了什么的“wrapper”库

Mutiny 是给想做得更像样的构建者准备的基础设施层。它不篡改 Midjourney/Discord 的现实，但会给你的应用一个更干净的契约：

- 通过一个客户端提交工作
- 通过一个事件流观察状态
- 当用户日后回来时，从已保存产物中恢复上下文
- 驱动后续操作，而不是把你的代码库堆成一团 Discord 琐碎细节

## 亮点

- `imagine`、`describe`、`blend`、`vary_region`、`animate` 和 `extend`
- 对 upscale、variation、pan 和 zoom 的后续操作支持，不需要让宿主应用去理解 Discord 按钮
- 提交时得到 `JobHandle`，任务推进过程中得到 `ProgressUpdate` 和 `JobSnapshot`
- 由缓存支撑的图像和视频恢复辅助方法，让已保存输出产物不至于变成死文件
- 面向宿主应用的图像和视频输入：bytes、路径、URL 和 data URL 都可直接用

## 安全

Discord 用户令牌是高风险凭据。Mutiny 会尽量把你往更稳妥的处理方式上带，但宿主应用仍然要对存储和运维卫生负责。

- 整个库围绕 `TokenProvider` 设计。
- 仅开发环境可用的 env 加载只是为了方便。
- 除非 `MUTINY_ENV=development` 或 `MJ_ENV=development`，否则会拒绝从 env 加载令牌和配置。

如果你在做真正要上线的东西，请使用 keychain 或 secret manager 来存储密钥，并把 `.env` 当成临时脚手架，而不是架构本身。

## 安装

```bash
pip install mutiny-sdk
```

安装名是 `mutiny-sdk`。Python 导入名保持为 `mutiny`。

```bash
pip install "mutiny-sdk[dev]"
```

这会在普通安装之上额外安装开发和调试工具。

## 快速开始

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

        handle = await client.imagine("cinematic mountain landscape at sunrise")
        print("Submitted job:", handle.id)

        snapshot = await client.wait_for_job(handle.id, timeout_s=180)
        print("Final status:", snapshot.status.name)

        if snapshot.status is JobStatus.SUCCEEDED:
            print("Output:", snapshot.output)
    finally:
        await client.close()


asyncio.run(main())
```

门面方法会抛出普通的 Python 异常：

- `ValueError` 用于校验失败
- `RuntimeError` 用于运行时和服务失败

## 参考

`examples/reference.py` 展示了如何把 Mutiny 接进一个简单 UI。

如果你想看更完整、更贴近真实部署的集成，可以参考 [ComfyUI-Mutiny](https://github.com/Artificial-Sweetener/ComfyUI-Mutiny)。这个项目把 Mutiny 用在了一个更大的宿主应用里。

## 文档

- [快速开始](docs/zh-CN/getting-started.md)：第一次集成、第一次事件消费、第一次提交任务。
- [配置](docs/zh-CN/configuration.md)：如何塑造 `Config`，以及哪些旋钮真正值得关心。
- [配置参考](docs/zh-CN/configuration-reference.md)：精确字段、默认值、辅助方法和 env 覆盖范围。
- [门面与生命周期](docs/zh-CN/facade-and-lifecycle.md)：`Mutiny` 客户端的形状、生命周期规则、观察辅助方法和恢复辅助方法。
- [任务操作](docs/zh-CN/job-actions.md)：你能提交什么、每种操作需要什么、后续工作流如何保持清晰。
- [事件](docs/zh-CN/events.md)：`ProgressUpdate` 和 `JobSnapshot` 如何放进真实宿主应用里。
- [视频与产物工作流](docs/zh-CN/video-and-artifact-workflows.md)：已保存图像和视频如何重新变得有用。
- [故障排查](docs/zh-CN/troubleshooting.md)：常见故障、响应转储、输入问题和恢复失败。
- [API 参考](docs/zh-CN/api-reference.md)：把完整公共导入表面集中放在一页里。

## 许可证

Mutiny 采用 **GNU Affero General Public License v3.0 or later
(AGPL-3.0-or-later)** 许可。
请阅读仓库中附带的完整 [LICENSE](LICENSE)。

AGPL-3.0-or-later 是强 copyleft 许可证。如果你分发 Mutiny（或它的修改版本），你必须提供对应源码；如果你让用户通过网络与修改后的版本交互，你也必须向这些用户提供该修改版本对应的源码。

**这意味着**，举例来说，如果你构建了一个托管应用，让用户通过它与 Discord/Midjourney 交互，并且这个应用使用了 Mutiny，那么你必须在 UI 中提供一个**源码链接**。换句话说，用户必须能够以*合理可行*的方式拿到他们正在通过你的服务交互的那一版 Mutiny 的源码，或该源码链接。如果你对 Mutiny 做了**修改**，那你的用户就有权获取你**修改后的源码版本**。如果你没有修改，那么只需要给出本仓库以及你正在运行的**确切版本**即可。

## 开发者的话 💖

我做 Mutiny，是因为我想让 Midjourney 变成真正可供构建者拿来构建的东西，而不只是永远困在一个聊天窗口里。如果这个项目替你省了时间，帮你做出了奇怪但有用的东西，或者给了你一个比我当初更干净的基础，那对我来说意义很大。

- **请我喝杯咖啡**：如果你愿意支持更多这样的项目，可以去我的 [Ko-fi 页面](https://ko-fi.com/artificial_sweetener)。
- **我的网站和社交账号**：想看我的艺术、诗歌和其他开发动态，可以访问 [artificialsweetener.ai](https://artificialsweetener.ai)。
- **如果你喜欢这个项目**，欢迎在 Github 上给我点一个 star。⭐
