**<- Previous:** [Job Actions](job-actions.md)

# Events

Mutiny keeps the live story simple on purpose.

`events()` yields public projection models, not internal runtime records:

- `ProgressUpdate`
- `JobSnapshot`

That is the contract your host should build around.

## Event Stream API

- `Mutiny.events()`
- `Mutiny.events(job_id=...)`

Use `events()` when you want one session-wide feed. Use `events(job_id=...)` when you want a narrow stream for one job.

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

Treat this as one continuous event stream. Consume it in one place, then fan out into the rest of your app.

## `ProgressUpdate`

`ProgressUpdate` is the lightweight "still moving" event.

Fields:

- `job_id`
- `status_text`
- `preview_image_url`

Use it for:

- activity logs
- status pills
- loading indicators
- in-progress preview thumbnails

`preview_image_url` is optional. When it is present, it is the preview/progress image Mutiny knows about at that moment.

## `JobSnapshot`

`JobSnapshot` is the durable public state for a job.

Fields:

- `id`
- `kind`
- `status`
- `progress_text`
- `preview_image_url`
- `fail_reason`
- `prompt_text`
- `output`

The fields most hosts care about first:

- `kind` is the lower-case action name such as `"imagine"`, `"describe"`, or `"animate_low"`
- `status` is `JobStatus`
- `prompt_text` is the best public prompt text Mutiny has for that job
- `output` is one of `ImageOutput`, `VideoOutput`, `TextOutput`, or `None`

`preview_image_url` is useful before the final output is ready. `output` is where the completed result lands.

## `JobSnapshot.output`

The `output` field is a small union rather than one huge catch-all object.

- `ImageOutput` means the job resolved to an image result
- `VideoOutput` means the job resolved to a video result
- `TextOutput` means the job resolved to text, which is what `describe()` produces
- `None` means the job does not have a public final output yet

That shape keeps host code pleasantly boring:

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

## Recommended Consumption Pattern

The boring architecture is the good architecture here:

1. start one long-lived consumer task
2. update your central model or store from that task
3. drive UI, websockets, and notifications from that model

Do not block inside the event loop. If a handler needs expensive work, hand it off and keep the consumer draining updates.

If your host only needs one job, the filtered stream is a good fit:

```python
async def watch_job(client, job_id: str) -> None:
    stream = client.events(job_id=job_id)
    try:
        async for update in stream:
            print(update)
    finally:
        await stream.aclose()
```

## Practical Limits

These are useful constraints, not drama:

- the stream is session-scoped, not a historical replay system
- recovery helpers can reconnect saved media later from the durable artifact cache, but they do not replay the old live stream
- one durable consumer is a better architecture than a flock of short-lived listeners

If your app needs restart-time reconstruction, combine:

- persisted app state
- `list_jobs()` and `get_job()`
- `resolve_image()` / `resolve_video()`

## Debugging And Dumps

Mutiny can write response and gateway diagnostics when configured to do so.

Relevant config:

- `websocket.capture_enabled`
- `cache.response_dump_dir`

Files land under the configured dump directory, which defaults to `.cache/mutiny/mj_responses`.

Common artifacts include:

- per-message JSON payload files
- `index.jsonl` summaries
- gateway capture files named like `gw_*.json`

Treat dump files like sensitive diagnostics, not harmless log crumbs.

## See Also

- [Video and Artifact Workflows](video-and-artifact-workflows.md)
- [Troubleshooting](troubleshooting.md)
- [API Reference](api-reference.md)

**Continue ->** [Video and Artifact Workflows](video-and-artifact-workflows.md)
