**<- Previous:** [Facade and Lifecycle](facade-and-lifecycle.md)

# Job Actions

This page answers the practical question: what can I actually send, and what kind of context does it need?

All public submission methods return `JobHandle`. That handle gives you the new job id immediately through `handle.id`, which is what you use with `events(job_id=...)`, `wait_for_job()`, `get_job()`, and later follow-ups.

## One Input Rule That Pays Off Everywhere

When a method takes an image or video, Mutiny accepts the host-facing shape you probably already have:

- raw `bytes`
- local path as `str`
- local `Path`
- remote `http/https` URL
- existing data URL

That is the facade doing convenience work for you. You do not need to pre-normalize everything into data URLs before calling the client.

## Create New Work

### `imagine(...)`

Use `imagine()` when you are starting from prompt text.

- `prompt` is required
- `prompt_images` attaches prompt images
- `style_references` attaches style reference images
- `character_references` attaches character reference images
- `omni_reference` attaches one omni reference image
- returns `JobHandle`

```python
handle = await client.imagine(
    "editorial portrait, wet pavement, sodium-vapor glow",
    prompt_images=("C:\\images\\street.png",),
    style_references=("https://example.com/style-board.webp",),
)
```

### `describe(...)`

Use `describe()` when you want Midjourney to turn one image into prompt text.

- takes one image input
- returns `JobHandle`
- terminal output arrives as `TextOutput` on the final `JobSnapshot`

```python
handle = await client.describe("C:\\images\\mood-board.jpg")
```

### `blend(...)`

Use `blend()` when the input is the point.

- takes `images: tuple[...]`
- accepts 2 to 5 images
- rejects duplicate images before submission
- `dimensions` becomes the Midjourney aspect-ratio choice
- returns `JobHandle`

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

Use `vary_region()` when you already know the base image and mask you want to send.

- takes `image` and `mask`
- optional `prompt` lets you steer the edit
- returns `JobHandle`

```python
handle = await client.vary_region(
    image="C:\\images\\base.png",
    mask="C:\\images\\mask.png",
    prompt="keep the composition, add ivy and rain streaks",
)
```

## Follow-Ups From Known Jobs

These methods are the normal follow-up path when your host already knows the source `job_id`.

### `upscale(...)`

- requires `job_id`
- requires `index`
- `mode` is `"standard"`, `"subtle"`, or `"creative"`
- returns `JobHandle`

### `vary(...)`

- requires `job_id`
- requires `index`
- `mode` is `"standard"`, `"subtle"`, or `"strong"`
- returns `JobHandle`

### `pan(...)`

- requires `job_id`
- requires `direction` of `"left"`, `"right"`, `"up"`, or `"down"`
- `index` is available when the source surface is tile-addressed
- returns `JobHandle`

Pan results should be treated like normal 2x2 grids once they complete. Keep the tile `index` if your host needs tile-level follow-ups or later recovery from saved images.

### `zoom(...)`

- requires `job_id`
- takes `factor`
- `prompt` is optional for custom zoom text
- `index` is available when the source surface is tile-addressed
- returns `JobHandle`

`zoom(..., factor=2.0)` and `zoom(..., factor=1.5)` take the native Midjourney zoom routes. Other factors use the custom zoom path while keeping the public method the same.

Completed zoom outputs should be treated as normal 2x2 grids, not final solo surfaces. Keep the recovered tile `index` if your host needs later tile-level follow-ups or saved-artifact recovery.

```python
base = await client.imagine("cathedral interior in gold and smoke")

upscale = await client.upscale(base.id, index=1)
zoomed = await client.zoom(upscale.id, factor=1.75, prompt="tighter on the altar")
```

## Animation Flows

### `animate(...)`

Use `animate()` when you are starting motion from an image.

- `start_frame` is required
- `end_frame` is optional
- `prompt` is optional
- `motion` is `"low"` or `"high"`
- `batch_size` must be `1`, `2`, or `4` when provided
- returns `JobHandle`

Practical behavior:

- if Mutiny recognizes the frame as a compatible Midjourney surface and you are asking for the simple follow-up route, it reuses that route
- if you provide prompt-video controls like an end frame, prompt text, or batch size, Mutiny submits the prompt-video style request instead

That keeps the public method simple while still taking the best route it can.

### `extend(...)`

Use `extend()` when the source motion already exists.

- give it `job_id` when you still have the animate-family job
- give it `video` when the user came back later with a saved clip
- `motion` is `"low"` or `"high"`
- returns `JobHandle`

```python
animate = await client.animate("C:\\frames\\start.png", motion="high")
extended = await client.extend(job_id=animate.id, motion="low")
```

## State Tags

Every submission method accepts `state` when your host wants to stamp a small correlation string onto the job.

That is useful for:

- reconnecting a UI action to a later job snapshot
- threading host-side workflow ids through submissions
- tagging one-shot jobs in logs

If you do not need it, ignore it.

## Surface Rules That Matter

Mutiny tries to keep follow-up routing boring from the outside, but a few rules are worth knowing:

- tile-based follow-ups need a tile index
- Pan results use that same tile system once they complete
- zoom results use that same tile system once they complete
- some follow-ups operate on a promoted solo surface even when the user started from a grid tile
- the promotion step stays inside one public job rather than becoming a second public API you have to drive manually

The useful host-level reading is simple:

- when you know the source job, use `job_id`
- when you need tile-specific follow-ups, keep the tile index
- when you only have saved media later, use the recovery helpers from [Video and Artifact Workflows](video-and-artifact-workflows.md)

## Common Flows

### Imagine -> Upscale

```python
base = await client.imagine("portrait of an astronaut in watercolor")
upscaled = await client.upscale(base.id, index=1)
```

### Known Job -> Variation

```python
base = await client.imagine("botanical illustration, moonlit greenhouse")
variant = await client.vary(base.id, index=2, mode="strong")
```

### Region Edit

```python
edit = await client.vary_region(
    image="C:\\images\\portrait.png",
    mask="C:\\images\\fog-mask.png",
    prompt="keep lighting, add subtle fog",
)
```

### Animate And Extend

```python
animate = await client.animate("C:\\frames\\start.png")
extend = await client.extend(job_id=animate.id)
```

**Continue ->** [Events](events.md)
