**<- Previous:** [Troubleshooting](troubleshooting.md)

# API Reference

Quick public map for Mutiny: what you import from `mutiny`, what the facade returns, and which method to reach for next.

Start with the guides if you want narrative context:

- [Getting Started](getting-started.md)
- [Facade and Lifecycle](facade-and-lifecycle.md)
- [Job Actions](job-actions.md)
- [Events](events.md)
- [Video and Artifact Workflows](video-and-artifact-workflows.md)

## Package-Root Imports

Import these directly from `mutiny`:

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

## Facade Setup

- `Mutiny(config: Config)` creates one client around one owned config snapshot.
- `Mutiny.start() -> None` starts the runtime and gateway work.
- `Mutiny.wait_ready(timeout_s: int | None = None) -> bool` waits for the gateway to become ready.
- `Mutiny.close() -> None` shuts the runtime down.
- `Mutiny.events(job_id: str | None = None) -> AsyncIterator[ProgressUpdate | JobSnapshot]` streams live updates for all jobs or one job.

See [Facade and Lifecycle](facade-and-lifecycle.md) for the full client story.

## Submission Methods

All submission methods return `JobHandle`. Use `handle.id` for later lookups, live event filters, and follow-up actions.

- `Mutiny.imagine(prompt: str, *, prompt_images=(), style_references=(), character_references=(), omni_reference=None, state=None) -> JobHandle`
  Creates a new image job from text and optional image references.
- `Mutiny.describe(image, *, state=None) -> JobHandle`
  Generates prompt text from one image.
- `Mutiny.vary_region(image, mask, *, prompt=None, state=None) -> JobHandle`
  Runs a region edit using a base image plus mask.
- `Mutiny.blend(images, *, dimensions="1:1", state=None) -> JobHandle`
  Submits a blend from 2 to 5 images.
- `Mutiny.upscale(job_id: str, *, index: int, mode="standard", state=None) -> JobHandle`
  Runs an upscale-style follow-up from a known job and tile index.
- `Mutiny.vary(job_id: str, *, index: int, mode="standard", state=None) -> JobHandle`
  Runs a variation follow-up from a known job and tile index.
- `Mutiny.pan(job_id: str, *, index=None, direction, state=None) -> JobHandle`
  Runs a pan follow-up from a known job. Completed Pan results use the same grid-tile recovery and splitting surface as other 2x2 image grids.
- `Mutiny.zoom(job_id: str, *, index=None, factor: float, prompt=None, state=None) -> JobHandle`
  Runs a zoom follow-up. `2.0` and `1.5` map to native zoom actions; other factors use custom zoom text under the hood. Completed zoom outputs use the same grid-tile recovery and splitting surface as other 2x2 image grids.
- `Mutiny.animate(start_frame, *, end_frame=None, prompt=None, motion="low", batch_size=None, state=None) -> JobHandle`
  Starts an animation flow from one frame, optionally with an end frame and prompt-video controls.
- `Mutiny.extend(*, job_id=None, video=None, motion="low", state=None) -> JobHandle`
  Extends an existing animate-family result from a known job or a recognized saved video.

Image parameters accept raw `bytes`, local path strings, `Path` objects, remote `http/https` URLs, and existing data URLs. Video parameters accept the same host-facing shapes.

See [Job Actions](job-actions.md) for workflow guidance and examples.

## Observation And Recovery

- `Mutiny.get_job(job_id: str) -> JobSnapshot`
  Returns the current public snapshot for one known job.
- `Mutiny.wait_for_job(job_id: str, *, timeout_s: float | None = None) -> JobSnapshot`
  Waits for a job to reach a terminal state and returns the final snapshot.
- `Mutiny.list_jobs(*, status: JobStatus | None = None, active_only: bool = False) -> list[JobSnapshot]`
  Lists known jobs as public snapshots.
- `Mutiny.resolve_image(image) -> ImageResolution | None`
  Tries to reconnect a saved image to its source job and tile index.
- `Mutiny.resolve_video(video) -> VideoResolution | None`
  Tries to reconnect a saved video to its source animate-family job.
- `Mutiny.split_image_result(job_id: str, image) -> tuple[ImageTile, ...]`
  Splits a known result image into facade-owned tiles for host-side follow-up UI.

See [Facade and Lifecycle](facade-and-lifecycle.md), [Events](events.md), and [Video and Artifact Workflows](video-and-artifact-workflows.md).

## Public Models

- `JobHandle`
  Stable submission result with one field: `id`.
- `ProgressUpdate`
  Lightweight live progress update with `job_id`, `status_text`, and optional `preview_image_url`.
- `JobSnapshot`
  Durable public job view with:
  `id`, `kind`, `status`, `progress_text`, `preview_image_url`, `fail_reason`, `prompt_text`, and `output`.
- `ImageOutput`
  Completed image result with `image_url` and optional `local_file_path`.
- `VideoOutput`
  Completed video result with optional `video_url`, `local_file_path`, and `website_url`.
- `TextOutput`
  Completed text result with `text`.
- `ImageResolution`
  Recognized image source metadata with `job_id` and `index`.
- `VideoResolution`
  Recognized video source metadata with `job_id`.
- `ImageTile`
  Split tile projection with `job_id`, `index`, and raw `image_bytes`.
- `JobStatus`
  The public status enum used by `JobSnapshot.status` and `list_jobs(status=...)`.

## Config

- `Config.create(...) -> Config`
  Main constructor for a new config snapshot.
- `Config.configure(...) -> Config`
  Returns a new config built from a base config or config mapping plus overrides.
- `Config.from_dict(...) -> Config`
  Rebuilds a config snapshot from `as_dict()` output.
- `Config.copy() -> Config`
  Deep-copies the current snapshot.
- `Config.as_dict() -> dict[str, Any]`
  Returns a stable nested mapping suitable for storage or inspection.

See [Configuration](configuration.md) and [Configuration Reference](configuration-reference.md).

## Exception Shape

Facade calls raise ordinary Python exceptions:

- `ValueError` for validation failures
- `RuntimeError` for runtime or service failures

That is the whole point. The public client is supposed to feel like one product surface, not a pile of transport return objects.

**Back ->** [Mutiny Documentation](README.md)
