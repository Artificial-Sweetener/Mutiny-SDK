**<- Previous:** [Configuration Reference](configuration-reference.md)

# Facade And Lifecycle

Mutiny is intentionally narrow at the integration layer: one public client, one config model, one running session per account.

That is not a limitation pretending to be elegance. It is the product shape.

## The Facade Contract

The canonical public entrypoint is `Mutiny(config)`.

Most host apps only need:

- `Config.create(...)`
- `Mutiny(config)`
- `start()`
- `wait_ready()`
- one or more submission methods
- `events()` or `wait_for_job()`
- `close()`

If your integration can stay inside that boundary, life gets simpler fast.

## Constructing The Client

Build a `Config`, then hand that snapshot to `Mutiny`.

```python
from mutiny import Config, Mutiny

config = Config.create(
    token_provider=my_token_provider,
    guild_id="YOUR_GUILD_ID",
    channel_id="YOUR_CHANNEL_ID",
)

client = Mutiny(config)
```

`Config` is the configuration surface. `Mutiny` is the running facade. Keep that split clean and the rest of the library makes a lot more sense.

## Normal Lifecycle

```python
await client.start()

if not await client.wait_ready(timeout_s=60):
    raise RuntimeError("Gateway not ready")

# submit work, consume events, wait for jobs

await client.close()
```

Practical notes:

- call `start()` before submission
- use `wait_ready()` when you want a real readiness check instead of hopeful sleeping
- treat `close()` as the clean end of the session
- one long-lived client per account is the happy path

## Observation Helpers

Mutiny gives you two complementary ways to stay in sync with work.

### `events()`

Use `events()` when your host needs live UI, logs, websockets, or a central runtime model.

- `events()` streams the whole session
- `events(job_id=...)` narrows the stream to one job
- the stream yields `ProgressUpdate` and `JobSnapshot`

See [Events](events.md) for the detailed consumption pattern.

### `wait_for_job()`

Use `wait_for_job(job_id)` when you want the smallest possible integration.

It waits for a terminal state and returns one `JobSnapshot`. That makes it a good first tool for scripts, CLI hosts, workers, and smoke tests.

### `get_job()` and `list_jobs()`

Use these when your app already has the job id and wants point-in-time state.

- `get_job(job_id)` returns one `JobSnapshot`
- `list_jobs()` returns all known jobs as snapshots
- `list_jobs(active_only=True)` is the quick answer to "what is still moving right now?"
- `list_jobs(status=JobStatus.SUCCEEDED)` is useful for host-side filtering and reconciliation

## Recovery Helpers

Saved outputs do not have to become dead files.

The facade owns three helpers for reconnecting old media to live host workflows:

- `resolve_image(image)` returns `ImageResolution | None`
- `resolve_video(video)` returns `VideoResolution | None`
- `split_image_result(job_id, image)` returns `tuple[ImageTile, ...]`

Use them like this:

- `resolve_image()` when a user drags an old image back into your app and you want to know which job and tile it came from
- `resolve_video()` when a saved animation clip needs an extend button again
- `split_image_result()` when you have a known grid result and want tile-level affordances in your own UI

See [Video and Artifact Workflows](video-and-artifact-workflows.md) for the full recovery story.

## Event Model In One Sentence

Mutiny returns a `JobHandle` immediately, then streams `ProgressUpdate` and `JobSnapshot` values as the work moves.

That split matters:

- `JobHandle` is the submission receipt
- `ProgressUpdate` is the lightweight "still moving" pulse
- `JobSnapshot` is the durable public state

## Error Boundaries

Facade methods raise ordinary Python exceptions:

- `ValueError` for validation failures
- `RuntimeError` for runtime and service failures

That keeps host code straightforward. You can write normal async client code instead of threading internal result wrappers through your app.

## Scope Guardrails

Mutiny is for building on Midjourney, not for pretending Midjourney's account and moderation realities are optional.

If your product needs multi-account orchestration, subscription bypass, or a magic escape hatch from platform limits, you are building a different product.

**Continue ->** [Job Actions](job-actions.md)
