---
title: AGI Simulation V1 — Completion and Integration Hardening
type: feat
status: active
date: 2026-04-10
origin: docs/brainstorms/2026-03-26-agi-entity-simulation-requirements.md
---

# AGI Simulation V1 — Completion and Integration Hardening

## Overview

The AGI entity simulation has all seven architectural layers implemented across five commits (07dcd67→b7b1531). This plan addresses the remaining gaps that prevent the simulation from satisfying its success criteria at runtime: reproduction is never triggered, dead entities pollute the environment, the GenePool is duplicated across two modules, and the test suite has not been verified to pass. This plan does not redesign any layer — it completes and hardens what is already written.

## Problem Frame

A code-complete system is not a working system. The gap between "all files written" and "all success criteria satisfied" is: wiring the divide action to the reproduction handler, fixing environment cleanup on death, consolidating the split GenePool, addressing per-tick file I/O, and ensuring tests pass and can be run from a fresh checkout. The archive API endpoint is also a 501 stub that blocks external observers from reading entity history.

## Requirements Trace

| Requirement | Description | Gap Addressed | Unit |
|-------------|-------------|---------------|------|
| R2 | Each tick: resolve cached action, dispatch next LLM call | C1: divide action never resolved | Unit 1 |
| R3 | Entity death: lifespan expiry → archived, removed from world | C2: void never cleaned | Unit 1 |
| R20 | Asexual reproduction via divide neuron | C1: ReproductionHandler never called | Unit 1 |
| R5 | Universal neuron pool | C4: pool re-loaded from disk per tick | Unit 2 |
| R17-R18 | Gene pool, genomes | C3: two GenePool classes in flight | Unit 2 |
| R29 | Storage layer abstracted behind repository interfaces | I6: archive endpoint 501 | Unit 3 |
| R15 | Anthropic Claude provider | I7: wrong model ID in hardcoded list | Unit 3 |
| R1 | No tick blocked by LLM latency | M3: inbox grows unbounded, inflates manifest | Unit 4 |
| R28-R30 | Storage: entity archive | Missing .env.example, pytest.ini untracked | Unit 5 |

## Scope Boundaries

- This plan does not implement sexual reproduction (V2 scope boundary preserved)
- WebSocket streaming for the web UI is not added here (basic state endpoint exists)
- Redis connection pooling tuning is deferred
- Vector database / embeddings are out of scope
- No authentication or multi-user support
- `VoidEnvironment` position data exposed to API via stale Redis values is documented as a known V1 limitation, not fixed (Gap I3 deferred)
- Provider reassignment for entities with failed LLM calls (Gap I2) deferred — log-and-skip is acceptable behavior for V1

## Context & Research

### Relevant Code and Patterns

- `simulation/tick.py` — `_process_entity()` and `_execute_action()` — where C1 and C2 fixes land
- `engine.py` — constructs `TickEngine`, `EntityFactory`, `GenePool`, `NeuronPool`; does not instantiate `ReproductionHandler`
- `genetics/pool.py` — minimal original GenePool imported by `simulation/`, `engine.py`
- `genetics/gene_pool.py` — richer GenePool exported via `genetics/__init__.py` but never used in simulation path
- `genetics/__init__.py` — re-exports `GenePool` from `gene_pool`; must be the single import source after consolidation
- `environment/void.py` — `VoidEnvironment.remove_entity()` exists at line 39 but is never called from the engine
- `simulation/reproduction.py` — `ReproductionHandler.spawn_offspring()` is correct; just not wired
- `agents/providers/anthropic.py` — hardcoded model list includes `"claude-opus-4-6"` (wrong ID)
- `api/routes/entities.py` — always returns 501; `RedisEntityRepository.load_archive()` is already implemented in `storage/redis.py`
- `tests/conftest.py` — modified (M status); `tests/genetics/` — new untracked directory
- `neural/pool.py` — `NeuronPool.load()` reads disk each call; `engine.py` already loads it once but does not pass it to `TickEngine`

### Key Patterns to Follow

- `EntityArchive` is already injected into `TickEngine.__init__` — use the same pattern to inject `ReproductionHandler` and `NeuronPool`
- `asyncio.gather(*tasks, return_exceptions=True)` for concurrent entity processing in tick
- `rng: random.Random | None = None` pattern — all randomness accepts a seeded RNG for test determinism
- `fakeredis.aioredis.FakeRedis()` for all storage tests — no real Redis required
- `respx` for mocking httpx calls (Ollama/LMStudio providers)
- `typing.Protocol` with `@runtime_checkable` for all cross-module interfaces

### Institutional Learnings

- The hybrid tick model is the core invariant: world state is synchronous, LLM calls are async and cached. Nothing should block a tick.
- Capability Manifest is the sole neural↔agent interface: actions outside the manifest are silently rejected.
- Every entity in the living set is processed every tick; the living set is the single source of truth for what is alive.

## Key Technical Decisions

- **Inject ReproductionHandler into TickEngine**: Consistent with how `EntityArchive` is already injected. Avoids giving `TickEngine` the responsibility of constructing its own dependencies. (Resolves flow analysis Q1.)
- **Re-execute cached action every tick between thinks**: An entity continuously acts on its last decision until the LLM provides a new one. `cached_action` is not cleared after execution. (Resolves flow analysis Q2 — this is intentional V1 behavior.)
- **Log-and-skip for missing provider**: When a provider is absent from the pool, the entity skips thinking that tick. No reassignment for V1. (Resolves flow analysis Q3.)
- **Stale position data in Redis is acceptable for V1**: The API reads `position_x`/`position_y` from Redis, updated only on move. This is documented, not fixed. (Resolves flow analysis Q4.)
- **Message inbox TTL: 10 ticks, max 20 messages**: Evict in `VoidEnvironment.age_messages()`. (Resolves flow analysis Q5.)
- **Delete genetics/pool.py, update all importers to genetics.gene_pool or genetics**: One canonical GenePool. No interface changes — both classes have identical public methods.

## Open Questions

### Resolved During Planning

- **ReproductionHandler ownership in TickEngine**: Inject via `__init__` parameter, optional (`None` disables reproduction). Consistent with `EntityArchive` injection pattern.
- **Cached action lifecycle**: Re-execute every tick (continuous behavior). Not a bug.
- **Message TTL**: 10 ticks age limit, 20 message max per entity inbox.
- **GenePool consolidation target**: `genetics/gene_pool.py` (richer) is canonical; `genetics/pool.py` is deleted.
- **Archive endpoint wiring**: Use existing `RedisEntityRepository.load_archive()` — no storage changes needed, only the route.
- **Anthropic model ID**: Fix `"claude-opus-4-6"` → `"claude-opus-4-5"` (or whichever is the correct v4 Opus ID per current provider docs).

### Deferred to Implementation

- Exact retry/backoff behavior when `LLMConnectionError` is raised repeatedly for the same entity (Gap I2)
- Optimal `asyncio.gather` timeout value for entity processing per tick under high entity counts
- Whether `_sexual_reproduction()` in `genetics/genome.py` needs a seeded RNG now or can wait for V2

## High-Level Technical Design

> *This illustrates the intended approach and is directional guidance for review, not implementation specification. The implementing agent should treat it as context, not code to reproduce.*

### Reproduction Flow After Fix

```
_process_entity(entity, tick)
  └─ execute _execute_action(entity, tick)
       ├─ action.type == "locomotion" → void.move()
       ├─ action.type == "signal_emitter" → void.broadcast()
       └─ action.type == "divide" AND self._reproduction_handler is not None
            └─ asyncio.create_task(self._reproduction_handler.spawn_offspring(entity, tick, rng))
               [non-blocking: offspring appears in living set next tick]

  └─ entity.age >= entity.lifespan
       ├─ repo.save(entity.alive=False)     [removes from living_set]
       ├─ archive.archive(entity.id)
       └─ void.remove_entity(entity.id)     ← NEW: cleanup position + inbox
```

### GenePool Import Graph After Consolidation

```
genetics/gene_pool.py  ← canonical GenePool class (richer, with create_gene_instance)
genetics/__init__.py   ← re-exports GenePool, Genome, etc. from gene_pool
genetics/pool.py       ← DELETED

engine.py              ← imports GenePool from genetics (via __init__)
simulation/factory.py  ← imports GenePool from genetics
simulation/reproduction.py ← imports GenePool from genetics
```

### NeuronPool Threading After Fix

```
engine.py
  └─ neuron_pool = NeuronPool.load()      [once at startup]
  └─ TickEngine(neuron_pool=neuron_pool)  ← NEW parameter

TickEngine._load_entity(data)
  └─ Brain.from_genome(genome, self._neuron_pool, rng)  ← uses pre-loaded pool
     [no disk I/O per tick]
```

## Implementation Units

- [ ] **Unit 1: Wire Reproduction and Fix Environment Cleanup**

**Goal:** Ensure the divide action triggers offspring creation and dead entities are removed from the VoidEnvironment. This unblocks the core evolutionary success criterion.

**Requirements:** R2, R3, R20

**Dependencies:** None (all constituent components exist; this is wiring only)

**Files:**
- Modify: `simulation/tick.py` — add `divide` branch in `_execute_action()`, accept `ReproductionHandler` in `__init__`, call `void.remove_entity()` on death
- Modify: `engine.py` — instantiate `ReproductionHandler`, pass to `TickEngine`
- Test: `tests/test_tick_engine.py` (new) or extend `tests/test_integration.py`

**Approach:**
- In `TickEngine.__init__`, add `reproduction_handler: ReproductionHandler | None = None` parameter, store as `self._reproduction_handler`
- In `_execute_action()`, add `elif action_type == "divide"` branch: if `self._reproduction_handler` is not None, call `asyncio.create_task(self._reproduction_handler.spawn_offspring(entity, tick))` so reproduction is non-blocking relative to the current tick's entity processing
- In `_process_entity()`, after `archive.archive()`, call `self._void.remove_entity(entity.id)` — one line
- In `engine.py`, after constructing `EntityFactory`, construct `ReproductionHandler(gene_pool, neuron_pool, factory, repo, void)` and pass to `TickEngine`

**Patterns to follow:**
- `simulation/tick.py` `_execute_action()` existing switch for `locomotion` and `signal_emitter`
- `EntityArchive` injection in `TickEngine.__init__`
- `asyncio.create_task()` for non-blocking background work

**Test scenarios:**
- Happy path: entity with divide neuron and age >= reproduction_threshold gets divide action cached; on next tick `_execute_action` dispatches spawn_offspring; offspring appears in `repo.list_living()` on the tick after
- Happy path: entity dies (age >= lifespan); `void.get_nearby()` with other entities no longer includes the dead entity's position
- Edge case: `TickEngine` constructed with `reproduction_handler=None`; divide action is executed; no exception raised, no offspring created
- Edge case: entity reaches lifespan on same tick it would reproduce; death takes precedence (age check runs before reproduce check)
- Integration: two-generation test — parent entity lives to reproduction threshold, divides, offspring inherits mutated genome, both entities subsequently appear in `repo.list_living()`

**Verification:**
- `tests/test_integration.py` two-generation test passes using the production `TickEngine.tick()` call path, not manual `spawn_offspring()` calls
- `void.get_nearby()` never returns dead entity IDs after a full tick cycle

---

- [ ] **Unit 2: Consolidate GenePool and Thread NeuronPool**

**Goal:** Eliminate the duplicate GenePool, make `genetics/__init__.py` the single import source, and pass the pre-loaded NeuronPool through TickEngine to eliminate per-tick file I/O.

**Requirements:** R5, R17-R18, R33

**Dependencies:** Unit 1 (engine.py changes from Unit 1 should land first to avoid merge conflicts on TickEngine constructor)

**Files:**
- Delete: `genetics/pool.py`
- Modify: `genetics/__init__.py` — verify all public symbols re-exported from `gene_pool`, `genome`, `reproduction`, `protocols`, `models`
- Modify: `genetics/reproduction.py` — update import if it references `genetics.pool`
- Modify: `engine.py` — update GenePool import from `genetics.pool` → `genetics`
- Modify: `simulation/factory.py` — update GenePool import from `genetics.pool` → `genetics`
- Modify: `simulation/reproduction.py` — update GenePool import from `genetics.pool` → `genetics`
- Modify: `simulation/tick.py` — add `neuron_pool: NeuronPool` to `TickEngine.__init__`, use it in `_load_entity()`
- Modify: `engine.py` — pass `neuron_pool` to `TickEngine`
- Test: `tests/genetics/test_gene_pool.py`, `tests/genetics/test_reproduction.py` (already present as untracked — verify and commit)

**Approach:**
- Delete `genetics/pool.py` entirely (both classes implement identical public methods; the simulation layer only uses `load()` and `default_genome()`, both of which exist in `gene_pool.py`)
- Search-replace `from genetics.pool import GenePool` → `from genetics import GenePool` across the codebase
- In `TickEngine.__init__`, add `neuron_pool: NeuronPool` parameter; store as `self._neuron_pool`
- In `_load_entity()`, replace `NeuronPool.load()` call with `self._neuron_pool`
- NeuronPool does not need a Protocol change — this is a dependency injection, not an interface change

**Patterns to follow:**
- `genetics/__init__.py` existing re-export pattern
- `TickEngine.__init__` parameter injection pattern (established in Unit 1)

**Test scenarios:**
- Happy path: `from genetics import GenePool` resolves to the richer `gene_pool.GenePool` class with `create_gene_instance()` available
- Happy path: `TickEngine._load_entity()` calls `Brain.from_genome()` using the pool passed at construction, not a fresh `NeuronPool.load()` call (assert no file I/O in `_load_entity` after the change)
- Edge case: `genetics/pool.py` absent from repo; no ImportError in any simulation module
- Integration: full `TickEngine.tick()` call completes without loading neuron pool from disk mid-tick

**Verification:**
- `grep -r "genetics.pool" .` returns no matches (excluding docs and git history)
- `pytest tests/genetics/` passes with the consolidated GenePool
- `TickEngine._load_entity()` does not call `NeuronPool.load()` (verified by inspection or mock)

---

- [ ] **Unit 3: Complete Archive API Endpoint and Fix Anthropic Model ID**

**Goal:** Wire the archive endpoint so external observers can retrieve entity history. Fix the wrong Anthropic model ID that causes silent LLM failures for any entity assigned that model.

**Requirements:** R29, R15, R31

**Dependencies:** None (independent of Units 1 and 2)

**Files:**
- Modify: `api/routes/entities.py` — wire `GET /entities/archived/{entity_id}` to `RedisEntityRepository.load_archive()`
- Modify: `api/main.py` — inject Redis connection into the entities router (currently not wired)
- Modify: `agents/providers/anthropic.py` — fix `"claude-opus-4-6"` model ID
- Test: `tests/test_api_entities.py` (new)

**Approach:**
- The entities router needs a Redis connection — follow the same pattern as `web/main.py` which opens Redis in `@app.before_serving`. In FastAPI, use a lifespan context manager or a dependency that provides `RedisEntityRepository`
- `RedisEntityRepository.load_archive(entity_id)` already returns a dict or None — return 404 if None, 200 with the dict if found
- For Anthropic model ID: confirm the correct model ID string from the Anthropic SDK model list (`claude-opus-4-5` or the current Opus 4 ID). Update the hardcoded list in `AnthropicProvider`

**Patterns to follow:**
- `api/routes/genes.py` module-level `_pool` singleton pattern (acceptable for read-only data); for Redis, prefer a lifespan-managed connection
- `storage/redis.py` `RedisEntityRepository.load_archive()` — already implemented, returns `dict | None`
- `web/main.py` `@app.before_serving` Redis connection pattern (adapt for FastAPI lifespan)

**Test scenarios:**
- Happy path: `GET /entities/archived/known-id` returns 200 with entity dict when archive entry exists in fakeredis
- Error path: `GET /entities/archived/unknown-id` returns 404 when no archive entry exists
- Error path: `GET /entities/archived/unknown-id` returns 404 (not 500) when Redis is available but entity not found
- Happy path: `AnthropicProvider.get_available_models()` returns only valid Anthropic model IDs; no invalid ID causes a model-not-found error when used in `provider.generate()`

**Verification:**
- `GET /entities/archived/{id}` returns 200 with archived entity data (not 501)
- `AnthropicProvider.get_available_models()` list contains no `"claude-opus-4-6"` string
- `pytest tests/test_api_entities.py` passes

---

- [ ] **Unit 4: Message Inbox TTL and Environment Correctness**

**Goal:** Prevent unbounded message inbox growth in VoidEnvironment, and fix the null-action caching issue to avoid wasteful manifest parsing.

**Requirements:** R27 (V1 interactions), R1 (no blocking in hot path)

**Dependencies:** None (independent)

**Files:**
- Modify: `environment/void.py` — add message eviction in `age_messages()` (max age 10 ticks, max 20 messages per entity)
- Modify: `agents/output.py` — `is_valid_for_manifest()` should return False when `action is None`
- Test: `tests/test_environment.py` (new) or extend existing environment tests

**Approach:**
- In `VoidEnvironment.age_messages()`, after incrementing `ticks_ago` for each message, remove entries where `ticks_ago > 10` or where the total count per entity exceeds 20 (keep the 20 most recent)
- In `agents/output.py` `AgentOutput.is_valid_for_manifest()`, add an early return of `False` when `self.action is None`; this prevents null-action responses from being cached and re-parsed every tick

**Patterns to follow:**
- `environment/void.py` existing `age_messages()` loop structure
- `agents/output.py` existing `is_valid_for_manifest()` logic

**Test scenarios:**
- Happy path: after 10 ticks of `age_messages()`, messages older than 10 ticks are absent from `get_messages()`
- Edge case: entity receives 25 messages in one tick; `get_messages()` returns at most 20
- Edge case: entity with no messages never raises during `age_messages()`
- Happy path: `AgentOutput(action=None, user_prompt_update=None).is_valid_for_manifest(manifest)` returns `False`
- Happy path: `AgentOutput(action=AgentAction(type="locomotion", parameters={})).is_valid_for_manifest(manifest_with_locomotion)` still returns `True`

**Verification:**
- `pytest tests/test_environment.py` passes
- Long-running entity (100 ticks) never accumulates more than 20 messages in inbox (assertable in integration test with fakeredis)

---

- [ ] **Unit 5: Dev Environment, Config Files, and Test Suite Verification**

**Goal:** Ensure a fresh checkout can install, configure, and run the simulation and its full test suite. Stage and commit all untracked files that are production-ready.

**Requirements:** R28 (Redis), R31-R34 (service architecture)

**Dependencies:** Units 1-4 (so the test suite validates the corrected code)

**Files:**
- Create: `pyproject.toml` — project metadata, dependencies, optional dev extras
- Create: `.env.example` — all required env vars with placeholder values and comments
- Create: `docker-compose.yml` — Redis service definition for local development
- Create: `data/prompts/system_template.j2` — Jinja2 template for system prompt generation (referenced by EntityFactory)
- Commit (already written): `genetics/gene_pool.py`, `genetics/genome.py`, `genetics/protocols.py`, `genetics/__init__.py`, `genetics/reproduction.py`, `tests/conftest.py`, `requirements.txt`, `pytest.ini`, `tests/genetics/`
- Delete: corrupted file at repo root (`C\357\200\272UsersiuriDownloadscvsc2agentsprovidersprovider.py`)

**Approach:**
- `pyproject.toml` should declare the same dependencies as `requirements.txt`, plus a `[project.optional-dependencies] dev = [...]` section for `pytest`, `pytest-asyncio`, `fakeredis`, `respx`
- `.env.example` must cover: `OPENROUTER_API_KEY`, `ANTHROPIC_API_KEY`, `REDIS_URL`, `OLLAMA_BASE_URL`, `LMSTUDIO_BASE_URL`, `TICK_INTERVAL`, `N_ENTITIES`
- `docker-compose.yml` needs a single `redis` service with the default port
- `data/prompts/system_template.j2`: EntityFactory selects from 8 hardcoded personality strings seeded by `PERSONALITY_SEED` gene; a Jinja2 template is referenced in the plan but the current code uses inline strings — create a minimal template or remove the reference from the plan depending on what `factory.py` actually does
- For the corrupted filename: `git rm` the file using its exact git-index name (inspect with `git ls-files --others` to get the exact name)
- Run `pip install -e ".[dev]"` and confirm `pytest` passes with no failures or import errors

**Patterns to follow:**
- Existing `requirements.txt` as the source of truth for production dependencies
- `pytest.ini` existing configuration (`asyncio_mode = auto`, `testpaths = tests`)

**Test scenarios:**
- Happy path: `pytest` run from a fresh clone (after `pip install -e ".[dev]"`) completes with 0 failures
- Happy path: `docker compose up -d redis && python engine.py` starts without import errors
- Edge case: missing `.env` values produce clear error messages at startup, not silent failures
- Integration: `pytest tests/test_integration.py` passes (full simulation loop test already written)

**Verification:**
- `pytest` exits 0 with no skip markers on integration tests
- `git status` shows no untracked production files
- `docker compose up -d redis && python engine.py` starts and processes at least one tick without exception

---

## System-Wide Impact

- **Interaction graph**: `TickEngine._process_entity()` is the hot path — Units 1, 2, and 4 all touch it. Sequence them carefully; Unit 1 lands first to establish the constructor signature that Unit 2 extends.
- **Error propagation**: `ReproductionHandler.spawn_offspring()` is dispatched via `asyncio.create_task()` — exceptions in the task are not awaited. Add `task.add_done_callback()` or a try/except inside the coroutine to log reproduction failures without crashing the tick.
- **State lifecycle risks**: The `divide` action must not trigger reproduction again on the entity's next tick (it will re-execute its cached action). The entity's cached action remains `"divide"` until the LLM provides a new action. This means an entity can reproduce multiple times if it keeps returning `"divide"` and meets the threshold each tick. This is intentional for V1 — no reproduction cooldown is specified.
- **API surface parity**: The archive endpoint now returns live data from Redis; the entities route currently has no `RedisEntityRepository` dependency. After Unit 3, the FastAPI app needs Redis to be running. Document this in `.env.example` and `docker-compose.yml`.
- **Integration coverage**: The two-generation integration test (Unit 1 test scenario 5) is the most important end-to-end proof. It exercises genetics → neural → agent → tick → reproduction → genetics in sequence, which no unit test can cover.
- **Unchanged invariants**: The hybrid tick model is not changed. The Capability Manifest schema is not changed. The `LLMProvider` Protocol is not changed. The Redis storage format (hash per entity, string values) is not changed.

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| `asyncio.create_task()` for divide dispatch — exceptions are fire-and-forget | Wrap `spawn_offspring` coroutine body in try/except; log failures with entity_id context |
| Deleting `genetics/pool.py` may break an import not found by grep (e.g., dynamic import) | Run `pytest` immediately after deletion to confirm no ImportError |
| `TickEngine` constructor signature changes across Units 1 and 2 — call sites in `engine.py` and tests must be updated in same commit | Land Unit 1 and Unit 2 changes to `TickEngine.__init__` in a single commit or back-to-back commits |
| Corrupted filename deletion may require shell escaping on Windows | Use `git ls-files --others` to get the exact git-index entry, then `git rm` with quotes |
| `data/prompts/system_template.j2` referenced in plan but may not be referenced in actual code | Inspect `simulation/factory.py` before creating the file; if unused, omit it |
| Anthropic model ID change — if `"claude-opus-4-6"` is actually valid and we change it, entities previously assigned that model string in Redis will reference a model the updated provider no longer lists | Check Redis for any live entity hashes with `model` field value `claude-opus-4-6` before deploying |

## Documentation / Operational Notes

- Add a `README.md` startup section documenting: `docker compose up -d redis`, `pip install -e ".[dev]"`, copy `.env.example` to `.env`, `python engine.py`
- Document the known V1 limitation: position data in Redis is stale for stationary entities; the web UI shows last-known position, not a live coordinate
- Update `AGENTS.md` after completion to reflect the final module structure and any protocol changes

## Sources & References

- **Origin document:** [docs/brainstorms/2026-03-26-agi-entity-simulation-requirements.md](docs/brainstorms/2026-03-26-agi-entity-simulation-requirements.md)
- **Prior plan:** [docs/plans/2026-03-26-001-feat-agi-entity-simulation-v1-plan.md](docs/plans/2026-03-26-001-feat-agi-entity-simulation-v1-plan.md)
- Related code: `simulation/tick.py` (_execute_action), `simulation/reproduction.py` (ReproductionHandler), `environment/void.py` (remove_entity), `genetics/gene_pool.py` (canonical GenePool), `agents/providers/anthropic.py` (model ID list)
- Flow analysis: gap report produced by workflow:spec-flow-analyzer (2026-04-10)
