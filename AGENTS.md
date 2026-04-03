# Assistant Engineering Guidelines (Mutiny)

You are contributing to Mutiny, a production-grade Midjourney integration platform.
The primary goal is Stability, Consistency, and Clean Architecture.

## 1) The Golden Rule: Behavior Freeze
- MJ and Discord behavior must not change.
- Only refactor structure, naming, and internal organization.
- Protocol lock: Discord payloads and custom_id formats must remain identical.

## 2) Internal Clean Break (No Shims)
- Internal refactors must be complete. No compatibility shims inside the codebase.
- If an internal signature changes, update all internal callers immediately.
- The code should look like the new design was the original design.

## 3) Separation of Concerns (Target Shape)
- domain/: Job, Action, Status, and transitions (pure logic)
- engine/: queue, scheduling, lifecycle, dispatch
- discord/: payload builder, gateway client, REST client, message parsing
- services/: notify, store, cache, persistence

## 4) Public API vs Internal API
- Internal is fluid. Refactor freely under the Golden Rule.
- The public SDK surface is the `Mutiny` facade plus the root-exported config and public models from `mutiny`.
- External API compatibility is optional.
- The PyPI distribution name is `mutiny-sdk`.
- The Python import package and package directory remain `mutiny`.
- Do not add alternate import namespaces such as `mutiny_sdk`.
- Do not rename the `mutiny/` package directory or introduce a `src/` layout as part of packaging work.
- Do not reintroduce config feature flags for built-in actions such as `custom_zoom` or `inpaint`.

## 5) Behavior Safety Net
- Add and maintain behavior-freeze tests:
  - Snapshot request/response payloads.
  - Task lifecycle invariants (queue -> in_progress -> success/failure).
  - No changes to Discord payload bytes.
- Treat these tests as non-negotiable.

## 6) Coding Standards
- Type hints required for new code.
- Docstrings required for public APIs; concise summaries for internals.
- Avoid comments except for non-obvious constraints.
- Naming: internal modules/functions snake_case, classes PascalCase, constants UPPER_SNAKE_CASE.

## 7) Error Boundaries
- Never crash the process. Handle errors at the right boundary.
- Centralize errors and messages in a Mutiny error catalog.

## 8) Verification
- Run lint, format, and tests before reporting success.
- Include behavior-freeze tests in verification runs.
- Run tests inside the active venv and prefer parallelized pytest (xdist) in normal contributor environments.
- Run Black and Ruff as part of verification.
- For documentation changes, verify English/Chinese file parity and link parity before reporting success.
- Use these commands:
  - `python -m black .`
  - `python -m ruff check .`
  - `python -m pytest -n auto`
- Network tests (`-m network`) run only upon explicit request.

## 9) Documentation Localization
- English docs are the source of truth.
- Keep Simplified Chinese docs in sync with English docs for all user-facing documentation.
- Use this structure:
  - `README.md` and `README.zh-CN.md`
  - `docs/*.md` and matching `docs/zh-CN/*.md`
- When an English doc changes, update the matching Chinese doc in the same change unless the user explicitly asks for English-only work.
- New English docs must include a matching Chinese doc stub or translation in the same change.
- Keep indexes, links, examples, warnings, and operational guidance aligned across languages.
- Do not knowingly ship stale Chinese docs without explicitly calling out the gap as a blocker.

## 10) Discord Debugging Notes
- Prefer Mutiny-side gateway dumps for Discord event analysis.
- Enable gateway dumps with `MJ_WS_CAPTURE_ENABLED=1`, then inspect `.cache/mutiny/mj_responses/index.jsonl` and `gw_*.json`.
- Discord message `content` can be multi-line (e.g., Midjourney appends a “Create, explore…” line), so success regexes must allow newlines.
- Progress updates commonly arrive as `MESSAGE_UPDATE` on a single message id; `interaction.id` may be present for imagine but can be absent for inpaint.
- Region-edit progress often references the base upscaled message via `message_reference.message_id`; use that for correlation.
