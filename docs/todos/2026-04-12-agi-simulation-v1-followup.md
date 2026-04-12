---
title: AGI Simulation V1 — Post-Completion Follow-up Items
date: 2026-04-12
status: open
source: ce-review (feat/agi-simulation-completion)
priority: low
---

# AGI Simulation V1 — Post-Completion Follow-up Items

These items were flagged as advisory (P3) during the ce-review pass on `feat/agi-simulation-completion`. They are not blocking for V1 but should be addressed before a V2 feature cycle begins.

---

## 1. Replace global `_redis_client` with `app.state.redis`

**File:** `api/main.py`, `api/routes/entities.py`

The FastAPI app uses a module-level global `_redis_client` that is set during lifespan and injected via `set_redis_client()`. The idiomatic FastAPI pattern is `app.state.redis`, which ties the client lifecycle to the app instance and avoids module-level mutation.

**Current pattern:**
```python
# api/main.py
_redis_client: Redis | FakeRedis | None = None

def set_redis_client(client):
    global _redis_client
    _redis_client = client
```

**Target pattern:**
```python
# api/main.py lifespan
app.state.redis = redis_client

# api/routes/entities.py
def get_redis(request: Request) -> Redis | FakeRedis:
    if not hasattr(request.app.state, "redis"):
        raise HTTPException(status_code=503, detail="Storage not ready")
    return request.app.state.redis
```

**Why it matters:** Module-level mutation makes parallel test isolation hard (tests share the global). `app.state` is reset per-app-instance.

---

## 2. Add authentication to the archive endpoint

**File:** `api/routes/entities.py`

`GET /entities/archived/{entity_id}` is unauthenticated. Entity archive data includes genome, personality, full action history, and user_prompt reflections. Any caller with network access can read the full history of any entity.

**Minimum viable guard:** API key header check (e.g., `X-API-Key`) read from environment. FastAPI `Depends()` makes this easy to apply uniformly.

**Why it matters:** If the API is ever exposed beyond localhost (e.g., Docker on a cloud VM), all entity history is publicly readable.

---

## 3. Wire `system_template.j2` into `simulation/factory.py`

**File:** `simulation/factory.py`, `data/prompts/system_template.j2`

The Jinja2 template at `data/prompts/system_template.j2` was created in commit `c5b6ded` but `EntityFactory.create()` still builds system prompts from inline f-strings. The template includes `{{ lifespan }}`, `{{ think_interval }}`, and `{{ brain_size }}` variables not present in the current inline prompt.

**What to do:** Load the template via `jinja2.Environment(loader=FileSystemLoader("data/prompts"))` and render it with genome values in `EntityFactory.create()`. Remove the inline string.

**Why it matters:** The template is the documented interface for prompt customisation; having two sources of truth for system prompt content will diverge.

---

## 4. Add `asyncio.create_task` done-callback for reproduction errors

**File:** `simulation/tick.py` — `_execute_action()` divide branch

`asyncio.create_task(self._reproduction_handler.spawn_offspring(...))` dispatches reproduction non-blocking, but unhandled exceptions in fire-and-forget tasks are silently swallowed until Python 3.11+ raises `TaskGroup` warnings.

**Fix:**
```python
task = asyncio.create_task(
    self._reproduction_handler.spawn_offspring(entity, tick=self.current_tick)
)
task.add_done_callback(
    lambda t: logger.error("Reproduction failed for %s: %s", entity.id, t.exception())
    if not t.cancelled() and t.exception() else None
)
```

**Why it matters:** Reproduction failures are currently invisible in logs. An entity that consistently fails to reproduce will appear to behave normally while the offspring is never created.

---

## 5. Two-generation integration test

**File:** `tests/test_integration.py` or `tests/test_tick_engine.py`

Unit 1 plan verification criterion specifies: *"tests/test_integration.py two-generation test passes using the production TickEngine.tick() call path, not manual spawn_offspring() calls."* This test was not written in the completion sprint — the existing integration tests exercise the tick loop and genetics but do not assert that an entity with a `divide` cached action produces an offspring that subsequently appears in `repo.list_living()`.

**Test outline:**
1. Create entity with `divide` action pre-cached and `reproduction_threshold` set low
2. Run `tick_engine.tick(1)` — `_execute_action` should dispatch `spawn_offspring`
3. Allow the task to complete (`await asyncio.sleep(0)` or use `asyncio.gather`)
4. Assert `len(await repo.list_living()) == 2`
5. Load offspring entity and assert its genome is a mutated child of the parent's genome

**Why it matters:** This is the only end-to-end proof that genetics → neural → agent → tick → reproduction → genetics works in sequence.
