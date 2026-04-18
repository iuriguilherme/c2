---
title: "feat: Add LLM Providers Usage Log"
type: feat
status: completed
date: 2026-04-17
origin: docs/brainstorms/2026-04-17-llm-providers-usage-log-requirements.md
---

# feat: Add LLM Providers Usage Log

## Overview

Adds real-time observability for LLM usage and errors directly in the web UI. This allows users to see if providers like LM Studio are rejecting requests or timing out without needing to inspect backend Docker logs. The generic "Settings" page is also renamed to "LLM Providers" to better reflect its focus.

## Problem Frame

Currently, there's no visibility into real-time LLM usage or provider failures from the web interface. If a provider is failing or misconfigured, it's hard to debug without diving into backend logs. Furthermore, the existing settings page is mostly dedicated to LLM provider configuration (since neural settings were split out), but is generically named "Settings".

## Requirements Trace

- R1. Rename the "Settings" page and nav links to "LLM Providers".
- R2. Add an LLM Usage Log table/section to the new "LLM Providers" page showing recent requests and their status.
- R3. Error logs must accumulate up to a generous hard cap (e.g., 1000 items) to prevent performance issues while ensuring they aren't missed, while successes can rotate out faster.
- R4. Provide actionable error details within the log.
- R5. Include a "Clear Errors" button.

## Scope Boundaries

- This is a UI observability feature. It does not change how providers authenticate, nor does it implement a heavy, full-scale log aggregation system (like ELK stack).
- Does not cover logging general application errors, only LLM provider interactions.

## Context & Research

### Relevant Code and Patterns

- `simulation/tick.py` (`TickEngine._collect_llm_response`): This is where the LLM calls are currently made and where exceptions are caught and logged with `logger.warning`.
- `storage/redis.py`: Home to `RedisInteractionStream` and `RedisTickStream`. A new repository class `RedisLLMLogStream` is a natural fit here.
- `api/routes/settings.py`: The existing FastAPI router for settings. We can add our new endpoints here to avoid creating entirely new routers just for logs.
- `web/main.py` and `web/templates/*`: Need updates to rename "Settings" to "LLM Providers".

### Institutional Learnings

- `RedisInteractionStream` uses `maxlen=1000, approximate=True` with `XADD` to bound memory usage. We should use this exact pattern for the error log stream.

## Key Technical Decisions

- **Two separate Redis streams for logs**: `llm_logs:success` (maxlen=100) and `llm_logs:error` (maxlen=1000). This gracefully handles R3 (errors persist longer than successes). The API layer will read both, merge, and sort them chronologically before sending to the frontend.
- **Dependency Injection**: Create `RedisLLMLogStream` in `engine.py` and inject it into `TickEngine`, just like `RedisInteractionStream`.
- **Rename Strategy**: Change `web/templates/settings.html` to `web/templates/llm_providers.html`. Change the route in `web/main.py` to `@app.route("/llm-providers")`. Keep the API prefix `/settings` in `api/routes/settings.py` for backend stability, but add the log fetching and clearing endpoints there.

## Open Questions

### Resolved During Planning

- **How to manage log retention?** Use Redis `XADD` with `maxlen` to inherently cap stream length.
- **Where to log?** In `TickEngine._collect_llm_response`. Measure the duration using `asyncio.get_event_loop().time()` or `time.time()` to provide more actionable context.

### Deferred to Implementation

- **Exact table layout and styling**: Defer CSS and layout specifics of the usage log table to execution, aligning it with the existing dark theme monospace styling.

## Implementation Units

- [ ] **Unit 1: Update Routing and Navigation**

**Goal:** Rename the "Settings" page to "LLM Providers" in the UI.

**Requirements:** R1

**Dependencies:** None

**Files:**
- Modify: `web/main.py`
- Modify: `web/templates/index.html`
- Modify: `web/templates/prompts.html`
- Rename: `web/templates/settings.html` -> `web/templates/llm_providers.html`

**Approach:**
- In `web/main.py`, rename `@app.route("/settings")` to `@app.route("/llm-providers")` and update the template name.
- In `index.html` and `prompts.html`, change `<a href="/settings">Settings</a>` to `<a href="/llm-providers">LLM Providers</a>`.
- In `llm_providers.html` (formerly `settings.html`), update the `<title>` and `<h1>` to "LLM Providers".

**Patterns to follow:**
- Existing navigation links in the templates.

**Test scenarios:**
- Navigating to `/llm-providers` successfully loads the page.

**Verification:**
- The word "Settings" is replaced with "LLM Providers" in the top navigation of the main app.

- [ ] **Unit 2: Storage Layer for LLM Logs**

**Goal:** Create a Redis stream wrapper for tracking LLM usage and errors.

**Requirements:** R3, R4, R5

**Dependencies:** None

**Files:**
- Modify: `storage/redis.py`

**Approach:**
- Add `class RedisLLMLogStream:`
- Implement `publish_log(provider: str, model: str, success: bool, duration_ms: int, details: str)`
- Internally use two streams: `llm_logs:success` (`maxlen=100`) and `llm_logs:error` (`maxlen=1000`). If `success` is True, publish to the success stream. If False, publish to the error stream.
- Implement `read_recent(count: int = 100) -> list[dict]`: read from both streams, combine, sort by timestamp descending, and return the `count` most recent.
- Implement `clear_errors()`: `await self._r.delete("llm_logs:error")`.

**Patterns to follow:**
- `RedisInteractionStream` using `self._r.xadd(..., maxlen=..., approximate=True)` and `xrevrange`.

**Test scenarios:**
- Publishing 150 success logs correctly caps at ~100.
- `clear_errors()` successfully empties the error stream.

**Verification:**
- `RedisLLMLogStream` correctly caps streams and merges them properly on read.

- [ ] **Unit 3: Logging LLM Requests in Engine**

**Goal:** Capture the result of LLM generations and write them to the storage layer.

**Requirements:** R2, R4

**Dependencies:** Unit 2

**Files:**
- Modify: `simulation/tick.py`
- Modify: `engine.py`
- Modify: `tests/test_tick_engine.py`
- Modify: `tests/test_simulation.py`
- Modify: `tests/test_integration.py`

**Approach:**
- In `TickEngine.__init__`, add `llm_log_stream: RedisLLMLogStream`.
- In `TickEngine._collect_llm_response`, record start time. On success, call `llm_log_stream.publish_log(..., success=True, details="OK")`.
- On exception, call `llm_log_stream.publish_log(..., success=False, details=str(e))`.
- In `engine.py`, instantiate `RedisLLMLogStream` and pass it to `TickEngine`.
- Update all test fixtures across `tests/test_tick_engine.py`, `tests/test_simulation.py`, and `tests/test_integration.py` to instantiate and pass a `RedisLLMLogStream` mock or instance to `TickEngine`.

**Patterns to follow:**
- `interaction_stream` injection in `engine.py` and `TickEngine` test files.

**Test scenarios:**
- Simulated LLM failure results in an error log written to the stream.
- Ensure all existing tick engine tests pass after signature change.

**Verification:**
- LLM calls during a tick populate the `llm_logs:success` or `llm_logs:error` streams, and all tests pass.

- [ ] **Unit 4: API Endpoints for LLM Logs**

**Goal:** Expose the logs to the frontend via FastAPI.

**Requirements:** R2, R5

**Dependencies:** Unit 2

**Files:**
- Modify: `api/routes/settings.py`
- Modify: `api/main.py`

**Approach:**
- In `api/routes/settings.py`, follow the existing project pattern for Redis dependency injection by adding a `set_redis_client(client)` function and a global `_redis_client`.
- Add `GET /settings/llm-logs` which calls `RedisLLMLogStream(_redis_client).read_recent()`.
- Add `DELETE /settings/llm-logs/errors` which calls `RedisLLMLogStream(_redis_client).clear_errors()`.
- In `api/main.py`, import `set_redis_client` from `api.routes.settings` (aliased appropriately, e.g., `set_settings_redis_client`) and call it in the `lifespan` context manager, passing the established `redis_client`.

**Patterns to follow:**
- `set_redis_client` pattern currently used by `api/routes/simulation.py` and `api/routes/entities.py`.

**Test scenarios:**
- Calling `GET /settings/llm-logs` returns a list of log dicts.
- Calling `DELETE /settings/llm-logs/errors` returns 200 OK.

**Verification:**
- Endpoint successfully serves the merged logs using the injected Redis client.

- [ ] **Unit 5: Frontend Usage Log UI**

**Goal:** Display the logs in the newly renamed LLM Providers page.

**Requirements:** R2, R5

**Dependencies:** Unit 1, Unit 4

**Files:**
- Modify: `web/templates/llm_providers.html`

**Approach:**
- Add a new section `<h2>LLM Usage Log</h2>`.
- Add a `<button onclick="clearLlmErrors()">Clear Errors</button>`.
- Add a `<table>` with columns: Timestamp, Provider, Model, Status, Details.
- Implement JavaScript to `fetch('${API_URL}/settings/llm-logs')` every ~5 seconds.
- Render the rows. Style success in green (e.g. text color or subtle background) and errors in red so they stand out.

**Patterns to follow:**
- Existing vanilla JS `fetch` and DOM injection used in `settings.html` and `index.html`.

**Test scenarios:**
- Frontend successfully polls and displays new logs.
- Clicking "Clear Errors" empties the error logs and immediately updates the UI.

**Verification:**
- The LLM Usage Log is visible, auto-updates, and clearly highlights errors.

## System-Wide Impact

- **State lifecycle risks:** None. The log streams are heavily size-capped by Redis.
- **Interaction graph:** Modifies `_collect_llm_response` which is in the critical think-path, but pushing to Redis streams via `aioredis` is extremely fast and non-blocking.

## Risks & Dependencies

- **API Route Redis Access:** `api/routes/settings.py` currently loads JSON from disk and doesn't use Redis. It will need to access the Redis client via `request.app.state.redis` or a dependency. If Redis isn't connected, it should gracefully return an empty list.

## Sources & References

- **Origin document:** [docs/brainstorms/2026-04-17-llm-providers-usage-log-requirements.md](docs/brainstorms/2026-04-17-llm-providers-usage-log-requirements.md)
