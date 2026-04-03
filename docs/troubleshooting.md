**<- Previous:** [Video and Artifact Workflows](video-and-artifact-workflows.md)

# Troubleshooting

Use this page when the integration is not behaving the way you expect.

Use the symptom that matches what you are seeing, then work outward from there.

## The Client Never Becomes Ready

Symptom:

- `await client.wait_ready(...)` returns `False`
- or startup stalls until your timeout expires

Check:

- token validity
- guild and channel ids
- whether the target account can actually access that channel
- whether your network environment is interfering with Discord websocket traffic

Also verify that the client was started before waiting:

```python
await client.start()
ready = await client.wait_ready(timeout_s=60)
```

## `Config.create(...)` Raises

Common causes:

- missing `token_provider`
- missing `guild_id`
- missing `channel_id`
- invalid section keys inside mapping overrides
- supplying both `engine=` and `execution=...`

If you are rebuilding from a dict:

- `Config.from_dict(...)` requires `token_provider`
- `Config.configure(...)` also requires `token_provider` when the source is a plain mapping

## `wait_for_job()` Times Out

Symptom:

- `await client.wait_for_job(job_id, timeout_s=...)` raises because the timeout expires

Check:

- whether the job id is correct
- whether the client is still running and connected
- whether the job ever actually reached Mutiny's store
- whether your timeout matches the kind of work you submitted

`wait_for_job()` is a terminal-state helper, not a transport watchdog. If you need live confidence while waiting, pair it with `events(job_id=...)`.

## A Follow-Up Action Is Rejected

Usually this means the action and the recovered surface do not actually match.

Check:

- whether you supplied the required `index` to `upscale(...)` or `vary(...)`
- whether the action is valid for the source surface
- whether the source job actually succeeded
- whether the source image/video was recognized

Important rule:

- tile-addressed follow-ups need the tile index they came from

If the user is acting on a saved artifact rather than a live job, prefer the recognition helpers before assuming a stale `job_id` still exists.

## `events()` Is Not Producing What You Expected

Symptom:

- your code is waiting for raw jobs or old progress objects
- your type checks never match
- your UI never sees the fields it expects

Check:

- `events()` yields `ProgressUpdate` and `JobSnapshot`
- submission methods return `JobHandle`, not a raw string
- durable result data lives on `JobSnapshot.output`
- preview data lives on `ProgressUpdate.preview_image_url` and `JobSnapshot.preview_image_url`

If the host is still shaped around older assumptions, fix the host model first. The stream is only useful if your app is listening for the right public types.

## `resolve_image()` Returns `None`

Symptom:

- `resolve_image(...)` returns `None`

Check:

- whether the image came from a Mutiny-observed Midjourney flow
- whether the artifact cache and disk cache were preserved
- whether you are feeding the saved output or a lightly re-encoded copy rather than a heavily edited derivative

Recognition is based on Mutiny's durable exact and fuzzy signatures. Light re-encoding can still resolve when the stored fuzzy signature remains close enough. Heavy edits, crops, or major recompression can still destroy the recoverable identity.

## `resolve_video()` Returns `None`

Symptom:

- `resolve_video(...)` returns `None`
- `extend(video=...)` fails because the video cannot be recognized

Check:

- whether the video is a saved animate-family output Mutiny has seen before
- whether the underlying artifact cache survived
- whether the bytes were re-encoded or transcoded

Video recovery depends on the persisted video signature index. It is not a general "recognize any Midjourney-ish video" feature.

## A Local Path Input Fails

Symptom:

- `describe()`, `vary_region()`, `animate()`, `extend()`, or a recovery helper raises before submission

Check:

- whether the path exists
- whether the path points at the file you think it does
- whether the image type can be identified from the extension or bytes

Mutiny treats local path inputs as a convenience, not as magical path guessing. Missing files raise `FileNotFoundError`. Unknown image types can raise `ValueError`.

## A Remote URL Input Fails

Symptom:

- a submission or recovery helper raises while fetching a remote image or video URL

Check:

- whether the URL is reachable from the machine running Mutiny
- whether the server allows the fetch
- whether the response is actually the media you expected

Remote URLs are fetched as part of input normalization. HTTP failures bubble up instead of being silently swallowed.

## I Need Raw Evidence

Mutiny gives you two useful diagnostic knobs:

- `websocket.capture_enabled`
- `cache.response_dump_dir`

Example:

```python
config = Config.create(
    token_provider=my_token_provider,
    guild_id="123",
    channel_id="456",
    websocket={"capture_enabled": True},
    cache={"response_dump_dir": ".cache/mutiny/mj_responses"},
)
```

Useful output files:

- `.cache/mutiny/mj_responses/index.jsonl`
- per-message JSON payloads
- gateway dump files like `gw_*.json`

### One Important Nuance

`websocket.capture_enabled` controls gateway-event dumps.

It does **not** mean "no dump files of any kind exist unless this is on." Reactor-driven message dumps use the same response dump service and write into `response_dump_dir` through a different path in the current implementation.

If the dump behavior surprises you, inspect:

- whether the file is a gateway dump or a message dump
- which config directory it wrote into
- whether gateway capture was explicitly enabled

## The Host Broke After A Mutiny Upgrade

This is usually a stale-assumption problem.

Examples of the kind of breakage to look for:

- code still assuming old event types instead of `ProgressUpdate` and `JobSnapshot`
- code still treating submission results as raw ids instead of `JobHandle`
- code still assuming removed recovery helpers exist
- code assuming artifact recovery replays historical events
- code assuming RAM-only modal or iframe state survives a process restart

The fix is almost always the same:

1. compare the host integration against the current public facade
2. check [API Reference](api-reference.md)
3. check [Configuration Reference](configuration-reference.md)
4. check the dumps if behavior changed somewhere deeper than the facade

## Tools That Help

- [Events](events.md): event stream behavior and dump semantics
- [Video and Artifact Workflows](video-and-artifact-workflows.md): recovery-specific behavior
- [../tools/README.md](../tools/README.md): capture and consistency tools

**Continue ->** [API Reference](api-reference.md)
