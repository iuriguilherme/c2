---
title: AGI Entity Simulation V1 — Known Scale Pathologies
date: 2026-04-12
last_updated: 2026-04-12
problem_type: best_practice
track: knowledge
module: simulation
component: tick_engine, environment, storage, genetics, agents
tags:
  - simulation
  - scale
  - performance
  - redis
  - async
  - population
  - brain
  - environment
  - llm-provider
  - oom-risk
applies_when:
  - Scaling the simulation beyond single-digit entity counts
  - Adding features that interact with per-tick entity processing, broadcasting, Redis streams, or reproduction
  - Planning a V2 performance pass or capacity review
  - Reviewing why simulation throughput degrades nonlinearly as population grows
status: verified
discovery_method: codebase-analysis (ce:ideate session 2026-04-12)
---

# AGI Entity Simulation V1 — Known Scale Pathologies

## Context

The AGI simulation V1 was designed and implemented with correctness and feature completeness as the primary goals. Scale was deliberately deferred. During an ideation session (ce:ideate, 2026-04-12), the codebase was analysed for design gaps that would become acute as population grows. Five distinct pathologies were identified and verified against the actual source.

These are not bugs introduced accidentally — they are structural choices that are correct at small populations and collapse at larger ones. This document records them so future sessions do not rediscover them, and so the V2 performance pass can be scoped accurately.

None of these pathologies were fixed during the discovery session. The code in the referenced files reflects the unpatched state as of 2026-04-12.

---

## Guidance

### 1. Brain Re-derivation Every Tick

**Where:** `simulation/tick.py` (inside `_load_entity`), `neural/brain.py`

`_load_entity()` calls `Brain.from_genome(genome, neuron_pool, rng)` on every tick for every living entity. The seed passed to the RNG is computed once from the entity ID:

```python
rng=random.Random(hash(data["id"]) % (2**31))
```

Because the seed is fixed and deterministic, the brain produced is identical every single tick. It is never mutated, never evolved, and never serialised — `Entity.to_storage_dict()` does not include brain state. The result:

- **O(n) brain construction cost per tick** — all n entities rebuild their brain from scratch.
- **Zero plasticity** — wiring that "fires together" cannot wire together; activations are reset to initial values every 2 seconds.
- **Cognitive reset** — any activation state accumulated during a tick is discarded before the next one.

The fix is to cache the brain (keyed on genome hash) so it is only rebuilt when the genome actually changes (after mutation or reproduction), and to serialise/restore activation state alongside entity data.

> **Note (session history):** A related but distinct per-tick redundancy — `NeuronPool.load()` reading `data/neuron_pool.json` from disk on every entity every tick — was identified and fixed in the Apr 10 session by threading a pre-loaded `NeuronPool` instance through `TickEngine.__init__`. That fix is in the current codebase. Brain re-derivation via `Brain.from_genome()` is a *separate, still-open* issue at a different layer.

---

### 2. O(n²) Broadcast via Linear Spatial Scan

**Where:** `environment/void.py`

`VoidEnvironment.get_nearby(entity_id, radius)` scans the entire `_positions` dict linearly — it examines all n entries to find neighbours. `broadcast()` calls `get_nearby()` for each broadcasting entity. In a tick where k entities broadcast:

- Each call to `get_nearby` is O(n).
- `broadcast` is called k times.
- Total cost: **O(k × n)**, which approaches **O(n²)** when most of the population broadcasts.

There is no spatial index (grid, quadtree, k-d tree, or similar) in V1. All entities currently occupy the void with positions, but neighbourhood queries are brute-force.

The fix is to add a spatial index. For the void environment a 2D grid bucketed by cell is sufficient; bucket size = broadcast radius eliminates most cross-bucket comparisons.

---

### 3. Unbounded Redis Stream (Silent OOM Risk)

**Where:** `storage/redis.py`

`RedisTickStream.publish_tick()` calls `xadd` with no `maxlen` parameter:

```python
await self._redis.xadd(self._STREAM_KEY, {...})
```

Redis Streams grow indefinitely unless trimmed. At a 2-second tick interval:

| Window | Entries added |
|---|---|
| 1 day | ~43,200 |
| 1 month | ~1,300,000 |
| 1 year | ~15,700,000 |

There is no TTL on the stream key, no background trimming, no monitoring, and no alerting. A long-running simulation will silently exhaust Redis memory. This will not surface as an error until Redis begins evicting keys or the host runs out of memory — at which point entity state may be lost.

The minimal fix is to pass `maxlen` to `xadd`:

```python
await self._redis.xadd(self._STREAM_KEY, {...}, maxlen=10_000, approximate=True)
```

A more complete fix adds a monitoring endpoint that reports stream length alongside other health metrics.

---

### 4. Self-Amplifying Population Explosion

**Where:** `simulation/tick.py` lines 145–149, `genetics/models.py`

Reproduction is triggered in the tick engine via fire-and-forget:

```python
asyncio.create_task(self._reproduction_handler.spawn_offspring(...))
```

There is no per-tick spawn cap, no rate limiter, and no population ceiling enforced before spawning. The reproduction threshold is a gene:

```
REPRODUCTION_THRESHOLD (gene in genetics/models.py)
```

Because genes are subject to evolutionary pressure, `REPRODUCTION_THRESHOLD` will drift toward 0 over generations — meaning entities reproduce more readily over time.

The cascade is:
1. A tick with many mature, well-fed entities triggers mass reproduction.
2. `create_task` fires n new `spawn_offspring` coroutines into the event loop without waiting.
3. The population doubles (or more) by the next tick.
4. The next tick has 2n entities, each of which may also reproduce.
5. Each additional entity adds one LLM call per think-tick — concurrency doubles alongside population.
6. LLM provider rate limits are hit; `_collect_llm_response` silently swallows failures (see Pathology 5).

The fix requires at minimum: a configurable `MAX_POPULATION` constant checked before spawning, and a per-tick spawn budget (e.g., cap new spawns to 10% of current population per tick).

> **Note (session history):** The fire-and-forget task failure (missing done-callback) was separately flagged as P3 advisory in the V1 code review and written to `docs/todos/2026-04-12-agi-simulation-v1-followup.md` (item 4) with an exact fix. The population explosion risk documented here is a distinct, higher-severity consequence of the same uncapped dispatch mechanism.

---

### 5. Silent LLM Failure Swallowing

**Where:** `simulation/tick.py` lines 111–125

`_collect_llm_response` catches all exceptions from the LLM call path and logs a warning:

```python
except Exception as e:
    logger.warning("LLM call failed for %s: %s", entity_id, e)
    return None
```

There is no retry, no exponential backoff, no failure counter, and no metric. The method returns `None` silently. The tick engine treats `None` as "no new decision this tick" — the entity simply re-executes its previous cached action or idles.

At scale, when a provider hits rate limits (which is certain during a population explosion — see Pathology 4), a large fraction of all LLM calls will fail silently every tick. The simulation appears to continue normally while a significant portion of entities make no decisions at all. There is no observable signal — no error rate dashboard, no degraded-mode indicator.

The fix has two parts: (a) structured retry with exponential backoff for transient failures (429, 503), and (b) a per-entity and per-tick failure counter exposed to the monitoring endpoint so operators can observe the degraded state.

---

## Why This Matters

These five pathologies are **independently harmful** and **interact**:

- Pathology 4 (population explosion) directly triggers Pathology 5 (LLM failures) by exhausting rate limits.
- Pathology 5 (silent failures) masks Pathology 4 — the simulation looks normal while reproduction continues unchecked.
- Pathology 2 (O(n²) broadcast) means that a doubled population from Pathology 4 quadruples broadcast cost per tick.
- Pathology 1 (brain re-derivation) means that cost also doubles for every new entity, with no compensating benefit from learning or plasticity.
- Pathology 3 (Redis stream) means that a runaway simulation will corrupt the infrastructure it runs on, taking down the API and all entity state.

Individually, any one of them is tolerable at small populations (< ~20 entities). Together, they make the simulation fragile above that threshold and potentially dangerous (OOM, data loss) above ~100 entities under continuous operation.

---

## When to Apply

Consult this document when:

- Adding any feature that increases broadcast frequency, per-entity tick cost, or LLM call rate.
- Planning a V2 performance pass — this is the enumerated list of known issues; scope from here.
- Debugging why a simulation with a growing population degrades nonlinearly in tick duration.
- Reviewing a proposed reproduction or population-management change — the cap and budget requirements (Pathology 4) must be part of any such change.
- Setting up monitoring or observability — Pathologies 3 and 5 both require instrumentation to be detectable.
- Evaluating whether the simulation is safe to run unattended for more than a few hours.

Do not treat this as a blocker for small-scale experiments (< 20 entities, short runs). These pathologies surface at scale and under sustained load.

---

## Examples

### Pathology 1 — Brain re-derived every tick with fixed seed (`simulation/tick.py`, `neural/brain.py`)

```python
# In _load_entity() — called once per entity per tick
brain = Brain.from_genome(
    genome=entity.genome,
    neuron_pool=self._neuron_pool,
    rng=random.Random(hash(data["id"]) % (2**31)),  # seed never changes
)
```

`Brain.from_genome` wires neurons, sets initial activations, and returns a new object. Because the seed is constant, the returned object is byte-for-byte identical to last tick's brain. `to_storage_dict()` does not include brain state, so nothing is ever persisted or restored.

---

### Pathology 2 — Linear scan in `get_nearby` (`environment/void.py`)

```python
def get_nearby(self, entity_id: str, radius: float) -> list[str]:
    pos = self._positions.get(entity_id)
    if pos is None:
        return []
    return [
        eid for eid, epos in self._positions.items()  # iterates ALL positions
        if eid != entity_id and _distance(pos, epos) <= radius
    ]
```

With n entities, this is O(n) per call. `broadcast()` calls this once per broadcasting entity, making the broadcast phase O(n²) at full-population broadcasting.

---

### Pathology 3 — Unbounded stream append (`storage/redis.py`)

```python
async def publish_tick(self, tick: int, entity_count: int) -> None:
    await self._redis.xadd(
        self._STREAM_KEY,
        {"tick": tick, "entity_count": entity_count, "ts": time.time()},
        # no maxlen — stream grows forever
    )
```

---

### Pathology 4 — Fire-and-forget reproduction (`simulation/tick.py`)

```python
# No cap, no budget, no await — spawns are unbound
asyncio.create_task(
    self._reproduction_handler.spawn_offspring(entity, tick)
)
```

`REPRODUCTION_THRESHOLD` in `genetics/models.py` is a heritable gene. Under selection pressure (entities that reproduce more outcompete those that reproduce less), this gene drifts toward 0, meaning more entities reproduce each tick, meaning more tasks are fired each tick.

---

### Pathology 5 — Silent LLM failure swallowing (`simulation/tick.py`)

```python
async def _collect_llm_response(self, entity, manifest, tick) -> str | None:
    try:
        raw = await self._provider.generate(...)
        return raw
    except Exception as e:
        logger.warning("LLM call failed for %s: %s", entity.id, e)
        return None  # caller treats None as "no decision this tick" — no retry, no metric
```

At scale, when provider rate limits are hit, every entity in the affected tick returns `None` here. The tick completes normally; there is no observable degradation signal.

---

## Key Files

| File | Pathology | Role |
|---|---|---|
| `simulation/tick.py` | 1, 4, 5 | Per-entity tick logic; brain construction, reproduction dispatch, LLM failure handling |
| `neural/brain.py` | 1 | `Brain.from_genome` — full brain construction called every tick |
| `environment/void.py` | 2 | `get_nearby` linear scan; `broadcast` caller |
| `storage/redis.py` | 3 | `RedisTickStream.publish_tick` — unbounded `xadd` |
| `genetics/models.py` | 4 | `REPRODUCTION_THRESHOLD` gene definition |

## Related

- [AGI Entity Simulation V1 Architecture](agi-entity-simulation-v1-architecture-2026-04-11.md) — the design patterns this document critiques at scale; message eviction (documented there) is the one existing mitigation for related inbox-growth risk
- `docs/todos/2026-04-12-agi-simulation-v1-followup.md` — item 4 contains the specific done-callback fix for Pathology 4's task supervision gap
- `docs/ideation/2026-04-12-open-ideation.md` — ideation session that discovered these pathologies; survivors include architectural responses (Batched LLM, Offspring Spawn Rate Governor, Persistent Brain Activation State)
