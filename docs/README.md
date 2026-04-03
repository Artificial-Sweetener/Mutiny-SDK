# Mutiny Documentation

Mutiny is for legitimate Midjourney customers who want to build something better than "open Discord and hope for the best."

Mutiny has one public client, one config surface, one live event story, and a small set of recovery helpers for when users come back with saved outputs.

> **Important:** Before integrating Mutiny, read the [Important Disclaimer](../README.md#important-disclaimer). Mutiny requires a real Discord user token and a paid Midjourney account, and its use may carry account-risk implications.

This docs set is split by job:

- onboarding pages that get you from zero to a working integration
- workflow guides for advanced and recovery-heavy flows
- reference pages for the exact surface area

## Start Here

- [Getting Started](getting-started.md): The smallest real integration, including startup, event consumption, and one submitted job.
- [Configuration](configuration.md): The practical guide to Mutiny's settings and when to reach for them.
- [Facade and Lifecycle](facade-and-lifecycle.md): The public client model, lifecycle behavior, observation helpers, and recovery helpers.

## If You Need To Ship Fast

Read these in order:

1. [Getting Started](getting-started.md)
2. [Configuration](configuration.md)
3. [Job Actions](job-actions.md)
4. [Events](events.md)

That path gets you from "I have a token and a channel" to "my app can submit work, stay in sync, and expose follow-up controls without lying to the user."

## If You Need The Exact Knobs

- [Configuration Reference](configuration-reference.md): Every config section, default, helper, and env-mapped field.
- [API Reference](api-reference.md): The exact root imports, facade methods, and public models.

## If You Care About Saved Outputs And Video

- [Video and Artifact Workflows](video-and-artifact-workflows.md): Image/video resolution helpers, tile rebuilding, animate route selection, and extend semantics.
- [Job Actions](job-actions.md): Action rules, index requirements, and the follow-up matrix.

## If You Are Debugging Something Weird

- [Events](events.md): The event stream contract, consumer guidance, and the public model shape.
- [Troubleshooting](troubleshooting.md): Common failure modes, response dumps, stale host assumptions, and where to look first.
- [Configuration](configuration.md): Especially the sections on `websocket.capture_enabled` and `cache.response_dump_dir`.

## Page Map

- [Getting Started](getting-started.md): Your first useful integration.
- [Configuration](configuration.md): Which settings matter and why.
- [Configuration Reference](configuration-reference.md): Exact fields, defaults, and helper behavior.
- [Facade and Lifecycle](facade-and-lifecycle.md): How the public client is shaped.
- [Job Actions](job-actions.md): What you can send and what context each action needs.
- [Events](events.md): What comes through the event stream and how to consume it sanely.
- [Video and Artifact Workflows](video-and-artifact-workflows.md): Recovery, tile rebuilding, and animate/extend behavior.
- [Troubleshooting](troubleshooting.md): Symptom -> cause -> fix.
- [API Reference](api-reference.md): The compact public surface index.
