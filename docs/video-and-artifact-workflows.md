**<- Previous:** [Events](events.md)

# Video And Artifact Workflows

This page exists because one of Mutiny's most useful behaviors is also one of its least obvious ones:

saved outputs do not have to become dead files.

Mutiny can often recognize a previously saved image or video, recover the Midjourney context behind it, and give your app a usable way back into the workflow.

## The Mental Model

There are three recovery helpers:

- `resolve_image(...)`
- `resolve_video(...)`
- `split_image_result(...)`

That matters because apps usually want one of two things:

- enough source identity to decide what controls to show
- a tile projection they can use to rebuild grid follow-ups

## Image Recovery

Relevant helpers:

- `Mutiny.resolve_image(image)`
- `Mutiny.split_image_result(job_id, image)`

`resolve_image(...)` returns `ImageResolution | None`.

That gives you:

- `job_id`
- `index`

`index` tells you which surface was recognized:

- `0` for a single-image surface
- `1` through `4` for grid tiles

That index matters when you are rebuilding follow-up affordances from saved images.

`split_image_result(job_id, image)` goes the other direction: it takes a known result image and gives you `ImageTile` values you can hang UI on.

Treat Pan results the same way you treat other 2x2 Midjourney grids:

- split them into tiles when the host needs tile-level controls
- keep the recovered tile `index` when follow-ups are tile-addressed
- expect solo-only follow-ups to route through the same promoted-surface behavior as other grid tiles

Treat completed zoom results the same way:

- fixed zoom and custom zoom outputs recover as 2x2 grid tiles
- `split_image_result(...)` should project those outputs into four logical tiles
- later saved-artifact follow-ups should use the recovered tile index the same way they do for Pan and variation-family grids

## Video Recovery

Relevant helpers:

- `Mutiny.resolve_video(video)`

`resolve_video(...)` returns `VideoResolution | None`.

In plain English: Mutiny fingerprints the saved clip, matches it against persisted animate-family outputs, and gives you back the source `job_id` when it can.

## Cache-Backed Recovery After Restart

This is where the recovery surface starts paying rent.

If the live job store is empty because the process restarted, recognition can still recover enough source identity for your host to rebuild useful controls.

That means:

- the original runtime session may be gone
- but the artifact can still recover enough context for follow-up behavior from the durable artifact cache
- restart-safe recovery depends on the disk-backed artifact cache, not on session RAM caches

What recovery does **not** do:

- replay the historical event stream
- pretend the original runtime session is still alive
- turn an unrecognized derivative into a known source asset
- resume live modal or iframe interaction state from a previous process

Use recovery to rebuild affordances, not to fake a complete event history.

## `animate(...)` Route Selection

`Mutiny.animate(...)` has two real routes behind the facade.

### Follow-Up Animate Route

Mutiny prefers the native follow-up route when:

- `start_frame_data_url` is a recognized upscaled Midjourney image
- `end_frame_data_url` is not provided
- prompt-video-only controls are not in play
- `batch_size` is not provided

This is the most native "animate from an existing result" path.

### Prompt-Video Route

Mutiny falls back to prompt-video generation when you provide controls that only make sense there, such as:

- `end_frame_data_url`
- a non-empty prompt
- `batch_size`

That path still goes through one public method, but it is not the same Midjourney route under the hood.

## `extend(...)` Route Selection

`Mutiny.extend(...)` also has two context paths.

### Live Job Path

Use `job_id=...` when you still have the animate-family job in the live store.

Requirements:

- the job must exist
- the job must have `JobStatus.SUCCEEDED`
- the job action must be one of the animate-family actions

### Recognized Video Path

Use `video=...` when you only have the saved output video.

Requirement:

- the video must be recognized by the persisted signature index

This is the recovery path that keeps old videos useful even when the original live job is gone.

## Practical Patterns

### Rebuild Controls For A Saved Image

```python
resolution = client.resolve_image(saved_image_bytes)
if resolution is not None:
    print("Recovered job:", resolution.job_id, "index:", resolution.index)
```

### Split A Known Grid Back Into Tiles

```python
tiles = client.split_image_result(job_id="job-grid", image=saved_grid_bytes)
for tile in tiles:
    print("Tile:", tile.job_id, tile.index, len(tile.image_bytes))
```

### Rebuild Controls For A Saved Video

```python
resolution = client.resolve_video(saved_video_bytes)
if resolution is not None:
    print("Recovered animate-family job:", resolution.job_id)
```

### Extend From A Saved Video

```python
extend = await client.extend(video=saved_video_bytes)
```

## Common Pitfalls

- a recognized artifact is not the same thing as a replayed event history
- `resolve_image()` gives you an `index`; `resolve_video()` does not
- `split_image_result()` needs a known `job_id` because tile projection depends on the source job
- `animate(...)` changes route based on the inputs you supply
- `extend(video=...)` only works for videos Mutiny can recognize

If recovery fails, move to [Troubleshooting](troubleshooting.md) before assuming the feature is broken. Most failures come from missing context, unrecognized artifacts, or a mismatch between what the host assumes and what the runtime actually knows.

**Continue ->** [Troubleshooting](troubleshooting.md)
