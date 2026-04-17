---
title: AGI Entity Simulation V1 — Architecture and Design Patterns
date: 2026-04-11
last_updated: 2026-04-16
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
  - observability
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
| `entity:{id}` | Redis Hash | Full entity state — includes `last_manifest`, `last_activations`, `last_llm_exchange` |
| `archive:{id}` | Redis Hash | Snapshot of entity at death |
| `living_entities` | Redis Set | Membership roster for `list_living()` |
| `ticks:main` | Redis Stream (XADD) | Ordered tick log; readable by web UI |
| `interactions:main` | Redis Stream (XADD) | Global log of birth, death, signal, and movement events; `MAXLEN 1000` |

`save()` atomically updates the hash and living set. `archive()` copies the entity hash to the archive key and removes the live key.

### Message Eviction Policy

`void.age_messages()` runs once per tick after all entity tasks. Two rules:
1. Drop messages older than 10 ticks (`ticks_ago > 10`).
2. If more than 20 messages remain, keep the 20 most recent.

### Observability Architecture

To overcome the "black box" nature of LLM entities, the system implements a multi-tier observability strategy:

1. **Granular Storage**: The `Entity` hash stores the most recent `CapabilityManifest` (JSON), raw neuron activations (float list), and the full `last_llm_exchange` (JSON object with system/user prompts and raw response).
2. **Capped Interaction Logging**: Transient social events (signals, movement > 1.0, births, deaths) are published to the `interactions:main` Redis stream. The stream uses `MAXLEN 1000` with approximate capping to maintain history without unbounded memory growth.
3. **API Differentiation**: To maintain performance, bulk state APIs (overview list) use `HMGET` via `load_many_partial` in the repository to skip the large observability strings, while detail APIs fetch the full hash.

---

## Why This Matters

- **Hybrid tick**: Naive approaches either block the world tick on LLM latency (unacceptable for populations) or allow out-of-order state (incorrect). The cache-and-execute pattern advances the world at a rate bounded by `asyncio.gather`, not by the slowest single LLM call.

- **Capability gating**: The LLM can only choose actions that `get_available_actions()` exposes. An action the entity's brain hasn't wired is invisible to the LLM and silently rejected if attempted. This prevents hallucinated actions from corrupting world state.

- **Observability**: Real-time logging of interactions and internal brain state allows for empirical verification of social evolution and neural wiring effectiveness.

- **Fakeredis fallback**: CI runs, developer demos, and quick iteration work identically to production without any code change. The warning log ensures operators never silently run production on volatile in-memory storage.

---

## When to Apply

Apply this architecture when:
- A simulation or game loop must advance world state synchronously while dispatching slow external calls asynchronously without stalling the tick.
- Agents need capability gating derived from internal state rather than static roles.
- Real-time logging of entity interactions is needed without affecting tick performance.
- Internal agent state (prompts/brain state) must be inspectable for debugging or analysis.
- A service must be runnable without infrastructure for CI/dev, while production-ready with real dependencies.

---

## Examples

### Hybrid Tick Core (`simulation/tick.py`)

```python
async def _process_entity(self, entity_id: str, tick: int) -> None:
    # ... load and age check ...
    if entity.should_think(tick):
        manifest = entity.brain.generate_manifest(...)
        entity.last_manifest = manifest.model_dump_json()
        entity.last_activations = json.dumps([n.activation for n in entity.brain.neurons])

        raw = await self._collect_llm_response(...)
        
        # Capture full exchange for observability
        entity.last_llm_exchange = json.dumps({
            "system": entity.system_prompt,
            "user": entity.user_prompt or "...",
            "manifest": manifest.model_dump(),
            "response": raw
        })

        output = AgentOutput.parse_llm_response(raw)
        if output and output.is_valid_for_manifest(manifest):
            entity.cached_action = raw
            entity.cached_action_tick = tick
        # LLM may also update the entity's user_prompt (self-reflection)
        if output and output.user_prompt_update:
            entity.user_prompt = output.user_prompt_update
    await self._repo.save(entity_id, entity.to_storage_dict())
```

### Optimized Bulk Load (`storage/redis.py`)

```python
async def load_many_partial(self, entity_ids: list[str], fields: list[str]) -> list[dict]:
    pipe = self._r.pipeline(transaction=False)
    for eid in entity_ids:
        pipe.hmget(f"entity:{eid}", *fields)
    results = await pipe.execute()
    # ... map results back to dicts ...
```

### is_valid_for_manifest Fix (`agents/output.py`)

```python
def is_valid_for_manifest(self, manifest: CapabilityManifest) -> bool:
    if self.action is None:
        return False  # no action requested — do not cache; hold previous cached_action
    available = manifest.get_available_actions()
    return self.action.type in available
```

---

## Key Files

| File | Role |
|---|---|
| `simulation/tick.py` | Hybrid tick engine and interaction event publisher |
| `storage/redis.py` | Redis repository, tick stream, and interaction stream (`MAXLEN` capping) |
| `web/templates/index.html` | Tabbed entity visualization and interaction log panel |
| `agents/output.py` | AgentOutput, is_valid_for_manifest, parse_llm_response |
| `neural/models.py` | CapabilityManifest and sub-models — the neural/agent interface contract |
| `agents/protocol.py` | LLMProvider Protocol and error hierarchy |
| `api/main.py` | Lifespan, fakeredis fallback, router wiring |
| `api/routes/entities.py` | 503 guard, entity_id validation, DI pattern |
| `environment/void.py` | VoidEnvironment, message inbox, age_messages eviction |
| `simulation/factory.py` | EntityFactory — genome + neuron pool + model assignment → Entity |
| `docs/plans/archive/2026-03-26-001-feat-agi-entity-simulation-v1-plan.md` | Full design rationale, resolved decisions, requirements trace |
