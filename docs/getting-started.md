# Getting Started

**English** | [简体中文](zh-CN/getting-started.md)

Mutiny is for the moment when "just use Discord manually" stops being a serious architecture plan.

This guide shows the smallest useful integration:

- install the package
- build a `Config`
- start the client
- submit one job
- wait for a real result
- understand where live events fit when your host grows up

> **Before you start:** Read the [Important Disclaimer](../README.md#important-disclaimer) first. This guide assumes you understand the account, token-handling, and platform-risk implications of using Mutiny.

## Install

```bash
pip install mutiny-sdk
```

Install name is `mutiny-sdk`. Python imports stay `mutiny`.

## Minimal Integration

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

That is the smallest honest integration:

- `Config.create(...)` builds the snapshot
- `Mutiny(config)` owns the running session
- submission returns `JobHandle`
- `wait_for_job(handle.id)` returns `JobSnapshot`

## What `JobHandle` Is For

`JobHandle` is the immediate submission receipt. Right after you call `imagine()`, `describe()`, `blend()`, or any other submission method, the handle gives you the new job id through `handle.id`.

That id is what you use for:

- `wait_for_job(handle.id)`
- `events(job_id=handle.id)`
- `get_job(handle.id)`
- later follow-up actions tied to the source job

## When To Use Live Events

`wait_for_job()` is the cleanest first success path, but most real hosts eventually want live updates.

`Mutiny.events()` yields two public event types:

- `ProgressUpdate` for in-flight status text and preview images
- `JobSnapshot` for durable job state

That usually maps to host-app behavior like this:

- use `JobSnapshot` to drive your main store, database row, or UI model
- use `ProgressUpdate` for temporary status text, preview thumbnails, and activity indicators

Here is the smallest job-scoped event watcher:

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

## Consume The Firehose In One Place

`Mutiny.events()` is a firehose. Treat it like one.

The safest pattern is:

1. run one long-lived consumer task
2. update your store or in-memory model there
3. fan out from that model to websockets, UI widgets, or job-specific listeners

Do not scatter random consumers around your app and hope they all stay in agreement.

## A Note On Inputs

When later pages show image or video parameters, you can usually pass what your host already has:

- raw `bytes`
- local path string
- local `Path`
- remote `http/https` URL
- existing data URL

That becomes especially useful with `describe()`, `vary_region()`, `animate()`, `extend()`, and the recovery helpers.

## Development Setup

Even in local development, keep the public mental model simple:

- build a `Config`
- hand it to `Mutiny`
- treat env-backed shortcuts as tooling convenience, not as the main product story

That keeps your host code honest from day one.

## What To Read Next

- Want to tune transport, cache, or engine behavior? Read [Configuration](configuration.md).
- Want the client and lifecycle explained end to end? Read [Facade and Lifecycle](facade-and-lifecycle.md).
- Want follow-up actions, tile rules, and animation routes? Read [Job Actions](job-actions.md).
- Want the live event model in more detail? Read [Events](events.md).

**Continue ->** [Configuration](configuration.md)
