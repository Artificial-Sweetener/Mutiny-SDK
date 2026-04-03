# Mutiny

**English** | [简体中文](README.zh-CN.md)

[![License: AGPL v3+](https://img.shields.io/badge/License-AGPLv3%2B-blue.svg)](LICENSE) [![semantic-release](https://img.shields.io/badge/semantic--release-angular-e10079?logo=semantic-release)](https://github.com/semantic-release/semantic-release) [![PyPI](https://img.shields.io/pypi/v/mutiny-sdk.svg)](https://pypi.org/project/mutiny-sdk/) [![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/) [![OpenCV](https://img.shields.io/badge/OpenCV-4.10%2B-5C3EE8?logo=opencv&logoColor=white)](https://opencv.org/)

**Mutiny** is an **unofficial**, **unaffiliated** Python library for putting Midjourney inside your own app.

You get one clean facade (`Mutiny`), one config surface (`Config`), one live event model, recovery helpers for saved outputs, and the full follow-up surface for building real product workflows instead of one-off prompt scripts.

The public contract is intentionally small:

- submit with one client
- get back a `JobHandle`
- observe work through `ProgressUpdate` and `JobSnapshot`
- recover useful context later with `resolve_image()`, `resolve_video()`, and `split_image_result()`

Mutiny is...

- A single-account Midjourney integration surface for host apps.
- Built for image and video workflows, not just one-shot prompts.
- Designed so saved outputs stay useful: Mutiny can often recognize an old image or video later and reconnect it to the next valid actions.

Mutiny is not...

- A way around Midjourney subscriptions, moderation, or account limits.
- A multi-account automation framework.
- A token vault. Bring a real `TokenProvider` for anything you plan to ship.

## Important Disclaimer

Mutiny interacts with Discord and Midjourney in ways that could be interpreted as violating their Terms of Service. **We make no guarantees about safety.** Use of Mutiny could result in action against your Discord account, your Midjourney account, or both, including warnings, restrictions, or bans.

Mutiny is designed to behave politely and conservatively. It is not intended to spam, hammer endpoints, evade limits, or behave abusively. We do not expect most legitimate users to have issues, but we cannot promise that. You are responsible for judging the risks for yourself before using it.

Mutiny requires your **Discord token** to function. That is sensitive account access material. Handling it is inherently risky, and if it is exposed or mishandled, someone else could gain access to your Discord account. Mutiny is shaped around `TokenProvider`, but secure storage and handling are still the host application's responsibility.

Mutiny also requires a **paid Midjourney account**. It is not a way to get free Midjourney access. It is not designed to bypass Midjourney's moderation systems, payment requirements, rate limits, or other platform restrictions. It is not intended for running multiple accounts or automating activity across multiple accounts. Mutiny is meant for legitimate use by a single user operating their own account.

## Why Mutiny Exists

Midjourney is too interesting to be trapped in one chat pane.

The usual alternatives are all annoying in their own special way:

- manual Discord use, which is fine until your product needs state, recovery, or sane UI affordances
- brittle button-scraping code, which tends to age like milk
- "wrapper" libraries that can submit a prompt but cannot explain what happened after that

Mutiny is the infrastructure layer for builders who want better than that. It keeps the Midjourney/Discord reality intact, but gives your app a cleaner contract:

- submit work through one client
- observe state through one event stream
- recover context from saved artifacts when users come back later
- drive follow-up actions without turning your codebase into a pile of Discord trivia

## Highlights

- `imagine`, `describe`, `blend`, `vary_region`, `animate`, and `extend`
- follow-up actions for upscale, variation, pan, and zoom without making the host think in Discord buttons
- `JobHandle` on submission, then `ProgressUpdate` and `JobSnapshot` while work moves
- cache-backed image and video recovery helpers so saved outputs do not become dead files
- host-friendly image and video inputs: bytes, paths, URLs, and data URLs

## Security

Discord user tokens are high-risk credentials. Mutiny tries to steer you toward sane handling, but the host app is still responsible for storage and operational hygiene.

- The library is shaped around `TokenProvider`.
- Development-only env loading exists for convenience.
- Env token/config loading is rejected unless `MUTINY_ENV=development` or `MJ_ENV=development`.

If you are shipping something real, use keychain or secret-manager storage and treat `.env` like temporary scaffolding, not architecture.

## Installation

```bash
pip install mutiny-sdk
```

Install name is `mutiny-sdk`. Python imports stay `mutiny`.

```bash
pip install "mutiny-sdk[dev]"
```

This adds development and debugging tooling on top of the normal install.

## Quick Start

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

Facade methods raise normal Python exceptions:

- `ValueError` for validation failures
- `RuntimeError` for runtime and service failures

## Reference

`examples/reference.py` shows how to integrate Mutiny into a simple UI.

If you want a fuller real-world deployment, see [ComfyUI-Mutiny](https://github.com/Artificial-Sweetener/ComfyUI-Mutiny), which uses Mutiny inside a larger host application.

## Documentation

- [Getting Started](docs/getting-started.md): First integration, first event consumer, first submitted job.
- [Configuration](docs/configuration.md): The narrative guide to shaping `Config` and knowing which knobs matter.
- [Configuration Reference](docs/configuration-reference.md): Exact fields, defaults, helper methods, and env coverage.
- [Facade and Lifecycle](docs/facade-and-lifecycle.md): The shape of the `Mutiny` client, lifecycle rules, observation helpers, and recovery helpers.
- [Job Actions](docs/job-actions.md): What you can submit, what each action expects, and how follow-up workflows stay sane.
- [Events](docs/events.md): How `ProgressUpdate` and `JobSnapshot` fit into a real host app.
- [Video and Artifact Workflows](docs/video-and-artifact-workflows.md): How saved images and videos become useful again.
- [Troubleshooting](docs/troubleshooting.md): Common failures, response dumps, input problems, and recovery misses.
- [API Reference](docs/api-reference.md): The exact public import surface in one place.

## License

Mutiny is licensed under the **GNU Affero General Public License v3.0 or later
(AGPL-3.0-or-later)**.
Please read the full [LICENSE](LICENSE) included with this repo.

AGPL-3.0-or-later is a strong copyleft license. If you distribute Mutiny (or a
modified version), you must provide the corresponding source; and if you let
users interact with a modified version over a network, you must offer those
users the corresponding source for that modified version.

**THIS MEANS**, for example, if you build a hosted app that uses Mutiny to let your users interact with Discord/Midjourney, you must add a **source link** in your UI. In other words, the user needs to be *reasonably able* to obtain the source (or a link to the source) for the version of Mutiny they interact with through your service. If you make **modifications** to Mutiny, then that means your users are entitled to a copy of your **modified version of the source**. If you didn't, then you need only link them to this repo and the **exact version** you're running.

## From the Developer 💖

I made Mutiny because I wanted Midjourney to be something builders could actually build on, not just something trapped in a chat pane forever. If this project saves you time, helps you ship something weird and useful, or gives you a cleaner foundation than I had when I started, that means a lot to me.

- **Buy Me a Coffee**: You can help fuel more projects like this at my [Ko-fi page](https://ko-fi.com/artificial_sweetener).
- **My Website & Socials**: See my art, poetry, and other dev updates at [artificialsweetener.ai](https://artificialsweetener.ai).
- **If you like this project**, it would mean a lot to me if you gave me a star here on Github!! ⭐
