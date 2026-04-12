---
title: AGI Entity Simulation V1 — Architecture and Design Patterns
date: 2026-04-11
last_updated: 2026-04-12
type: knowledge
problem_type: architecture_decision
track: knowledge
module: simulation
component: tick_engine, genetics, neural, agents, api, environment
tags:
  - simulation
  - hybrid-tick
  - async
  - redis
  - llm-provider
  - genetics
  - capability-manifest
  - fastapi
  - fakeredis
applies_when:
  - Building a simulation loop that must advance world state synchronously while dispatching slow LLM or external calls asynchronously
  - Agents need capability gating derived from internal state (neural wiring, permissions)
  - Services must run without infrastructure (no Redis, no GPU) in dev/CI while being production-ready
  - Multiple LLM providers must be interchangeable at runtime per-entity
status: verified
---

# AGI Entity Simulation V1 — Architecture and Design Patterns

## Context

The AGI (Agent-driven Genetic-simulated Individual-organisms) simulation was a greenfield V1 implementation. The core challenge was combining three distinct behavioral layers — genetic heredity, neural capability gating, and LLM-driven decision-making — into a coherent runtime loop given the mismatch between deterministic world ticks and latency-variable LLM calls.

Prior to this work, no simulation foundation existed. The system needed to be runnable in zero-infrastructure environments (no Redis, no GPU) for development and CI, while being production-ready with real dependencies present.

---

## Guidance

### Three-Layer Architecture

The layers are separated by interface contracts, not inheritance.

**Layer 1 — Genetic** (`genetics/`): Pydantic v2 models for `Gene` and `Genome`. Gene pool is a JSON file loaded at startup (`data/gene_pool.json`). Reproduction is `Genome.reproduce(parent2=None)` — `None` = asexual V1; passing a second genome activates dominance-based selection (V2 interface reserved). Per-gene mutation is stochastic: each gene carries its own `mutation_rate` and applies `random.gauss(0, std)` independently.

**Layer 2 — Neural** (`neural/`): A `NeuronPool` holds the catalogue of available neuron types (`data/neuron_pool.json`). A `Brain` is constructed via `Brain.from_genome(genome, neuron_pool, rng)` — `BRAIN_SIZE` and `NEURON_AFFINITY` genes control which neurons are wired. Every tick `generate_manifest(...)` produces a `CapabilityManifest` describing what the entity can perceive and which actions are available.

**Layer 3 — Agent** (`agents/`): `LLMProvider` is a `@runtime_checkable` Protocol. Providers (Anthropic, OpenRouter, Ollama, LM Studio) satisfy it structurally — no inheritance. The manifest JSON is injected into the user message between `### CAPABILITIES ###` delimiters. The LLM responds with a JSON object; `AgentOutput.parse_llm_response` extracts the first `{...}` from raw text, tolerating preamble.

### The Hybrid Tick Model

The tick engine (`simulation/tick.py`) decouples decision time from execution time with a two-phase per-entity cycle:

- **Phase A — Execute** (sync): Re-parse and execute the action cached from the *previous* tick.
- **Phase B — Think** (async): If `should_think(tick)` is true, call the LLM provider. On a valid response, store the raw text as `cached_action` for Phase A next tick.

All entities are processed concurrently with `asyncio.gather(*tasks, return_exceptions=True)`. LLM latency for one entity never blocks others, and a crashed entity cannot abort the gather.

### Protocol over ABC

`typing.Protocol` with `@runtime_checkable` means providers do not inherit from a base class. This is specifically important for `async def generate(...) -> AsyncGenerator` — ABC abstract methods do not compose cleanly with async generators. Future Rust/C extensions can also satisfy the protocol without touching the Python class hierarchy.

### Fakeredis Fallback Pattern

The FastAPI lifespan attempts a real Redis `ping()`. On failure, it falls back to `fakeredis.aioredis.FakeRedis()` with an explicit warning log. The same `set_redis_client` wires either backend into route dependencies identically — the fallback is transparent to all route code. This enables a fully functional API surface in zero-infrastructure environments.

### Redis Data Layout

| Key pattern | Structure | Purpose |
|---|---|---|
| `entity:{id}` | Redis Hash | Full entity state — all fields stringified |
| `archive:{id}` | Redis Hash | Snapshot of entity at death |
| `living_entities` | Redis Set | Membership roster for `list_living()` |
| `ticks:main` | Redis Stream (XADD) | Ordered tick log; readable by web UI |

`save()` atomically updates the hash and living set. `archive()` copies the entity hash to the archive key and removes the live key.

### Message Eviction Policy

`void.age_messages()` runs once per tick after all entity tasks. Two rules:
1. Drop messages older than 10 ticks (`ticks_ago > 10`).
2. If more than 20 messages remain, keep the 20 most recent.

Without eviction, a large broadcasting population produces unbounded inbox growth in memory and in every subsequent manifest, increasing LLM token cost and risking OOM.

---

## Why This Matters

- **Hybrid tick**: Naive approaches either block the world tick on LLM latency (unacceptable for populations) or allow out-of-order state (incorrect). The cache-and-execute pattern advances the world at a rate bounded by `asyncio.gather`, not by the slowest single LLM call.

- **Capability gating**: The LLM can only choose actions that `get_available_actions()` exposes. An action the entity's brain hasn't wired is invisible to the LLM and silently rejected if attempted. This prevents hallucinated actions from corrupting world state.

- **Fakeredis fallback**: CI runs, developer demos, and quick iteration work identically to production without any code change. The warning log ensures operators never silently run production on volatile in-memory storage.

- **503 guard**: FastAPI's lifespan completion is not atomic with request acceptance. A request arriving before lifespan finishes (e.g., slow startup probe) would get an unhelpful `AttributeError` from `RedisEntityRepository(None)`. The guard converts this to a clean 503.

---

## When to Apply

Apply this architecture when:
- A simulation or game loop must advance world state synchronously while dispatching slow external calls asynchronously without stalling the tick.
- Agents need capability gating derived from internal state rather than static roles.
- A service must be runnable without infrastructure for CI/dev, while production-ready with real dependencies.
- Multiple LLM providers must be interchangeable at runtime per-entity with graceful degradation.
- Genetic/evolutionary state must survive entity death and be queryable independently of living state.

Do not apply the hybrid tick model when:
- Action latency must be zero (real-time games require a different concurrency model).
- LLM responses must be validated against world state that changes within the same tick window (requires a transaction model, not a cache model).

---

## Examples

### Hybrid Tick Core (`simulation/tick.py`)

```python
async def tick(self, tick: int) -> None:
    entity_ids = await self._repo.list_living()
    tasks = [self._process_entity(eid, tick) for eid in entity_ids]
    await asyncio.gather(*tasks, return_exceptions=True)  # never cancels on one failure
    self._void.age_messages()
    await self._stream.publish_tick(tick=tick, entity_count=len(entity_ids))

async def _process_entity(self, entity_id: str, tick: int) -> None:
    # Load entity state from Redis
    data = await self._repo.load(entity_id)
    entity = self._load_entity(data)

    # Phase A: Execute action decided LAST tick
    if entity.cached_action and entity.cached_action_tick >= 0:
        await self._execute_action(entity, entity.cached_action)
    # Phase B: Think for NEXT tick
    if entity.should_think(tick):
        raw = await self._collect_llm_response(...)
        output = AgentOutput.parse_llm_response(raw)
        if output and output.is_valid_for_manifest(manifest):
            entity.cached_action = raw
            entity.cached_action_tick = tick
        # LLM may also update the entity's user_prompt (self-reflection)
        if output and output.user_prompt_update:
            entity.user_prompt = output.user_prompt_update
    await self._repo.save(entity_id, entity.to_storage_dict())
```

### is_valid_for_manifest Fix (`agents/output.py`)

Before — `AttributeError` if LLM returns `{"user_prompt_update": "..."}` with no `action`:
```python
def is_valid_for_manifest(self, manifest: CapabilityManifest) -> bool:
    available = manifest.get_available_actions()
    return self.action.type in available  # crash if self.action is None
```

After:
```python
def is_valid_for_manifest(self, manifest: CapabilityManifest) -> bool:
    if self.action is None:
        return False  # no action requested — do not cache; hold previous cached_action
    available = manifest.get_available_actions()
    return self.action.type in available
```

`False` means "don't update the cache" — the entity keeps its previous `cached_action`. It is not an error.

### Lifespan + Fakeredis Fallback (`api/main.py`)

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis_client
    try:
        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")
        redis_client = Redis.from_url(redis_url)
        await redis_client.ping()
    except Exception as exc:
        logger.warning(
            "Redis unavailable (%s: %s) — falling back to in-process fakeredis. "
            "All entity data will be lost on restart.",
            type(exc).__name__, exc,
        )
        redis_client = fakeredis.aioredis.FakeRedis()
    set_redis_client(redis_client)  # single injection point for all routes
    yield
    if redis_client is not None:
        await redis_client.aclose()
```

### 503 Guard + entity_id Validation (`api/routes/entities.py`)

```python
# Note: _redis_client type is Redis | FakeRedis; add a type alias for cleaner annotations
def get_redis() -> "Redis | FakeRedis":
    if _redis_client is None:
        raise HTTPException(status_code=503, detail="Storage not ready")
    return _redis_client

@router.get("/archived/{entity_id}")
async def get_archived_entity(
    entity_id: str = Path(..., pattern=r"^[\w-]{1,128}$"),  # blocks colon-injection
    redis=Depends(get_redis),
) -> dict:
    repo = RedisEntityRepository(redis)
    data = await repo.load_archive(entity_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Archived entity not found")
    return data
```

Three independent failure modes: 422 (invalid ID format), 503 (storage not ready), 404 (not found) — each handled at the correct layer.

### Capability Manifest (`neural/models.py`)

```python
class CapabilityManifest(BaseModel):
    model_config = ConfigDict(extra="allow")  # extensible for future neuron types
    schema_version: Literal["1.0"] = "1.0"
    agent_id: str
    tick: int = Field(ge=0)
    perception: dict[str, ProximityPerception | SignalReceiverPerception] = {}
    actions: dict[str, ActionCapability] = {}
    memory: MemoryState = Field(default_factory=lambda: MemoryState(available=False))

    def get_available_actions(self) -> list[str]:
        return [name for name, cap in self.actions.items() if cap.available]
```

`get_available_actions()` is the sole source of truth for what actions an entity may choose. Adding a new neuron type in V2 means adding a new `ActionCapability` entry — no changes to `CapabilityManifest` needed.

### Message Eviction (`environment/void.py`)

```python
def age_messages(self) -> None:
    for entity_id, msgs in self._message_inbox.items():
        for m in msgs:
            m["ticks_ago"] += 1
        # Keep messages with ticks_ago <= 10 (evict those aged past 10 ticks)
        msgs[:] = [m for m in msgs if m["ticks_ago"] <= 10]
        # Cap at 20 most recent
        if len(msgs) > 20:
            msgs.sort(key=lambda msg: msg["ticks_ago"])
            msgs[:] = msgs[:20]
```

`msgs[:] = ...` mutates the list in-place — required because the dict value is a list reference; `msgs = [...]` would create a new list the dict no longer points to.

---

## Key Files

| File | Role |
|---|---|
| `simulation/tick.py` | Hybrid tick engine — the central orchestration logic |
| `agents/output.py` | AgentOutput, is_valid_for_manifest, parse_llm_response |
| `neural/models.py` | CapabilityManifest and sub-models — the neural/agent interface contract |
| `agents/protocol.py` | LLMProvider Protocol and error hierarchy |
| `agents/providers/anthropic.py` | Reference provider implementation |
| `api/main.py` | Lifespan, fakeredis fallback, router wiring |
| `api/routes/entities.py` | 503 guard, entity_id validation, DI pattern |
| `storage/redis.py` | Redis repository and tick stream; key naming conventions |
| `environment/void.py` | VoidEnvironment, message inbox, age_messages eviction |
| `simulation/factory.py` | EntityFactory — genome + neuron pool + model assignment → Entity |
| `docs/plans/archive/2026-03-26-001-feat-agi-entity-simulation-v1-plan.md` | Full design rationale, resolved decisions, requirements trace |
