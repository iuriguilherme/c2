---
module: visualization
tags: [observability, redis, llm, neural, frontend]
problem_type: integration_issue
date: 2026-04-16
---

# Interaction and Brain Visualization Observability

## Problem Symptom
Entities in the AGI simulation were "black boxes." Internal neural processing (`CapabilityManifest`, activations) and raw LLM exchanges (prompts/responses) were invisible. Interactions between entities (signals, movement) were not tracked centrally, making the simulation's "social" behavior hard to verify.

## Investigation Steps
- Scanned `simulation/entity.py` and `storage/redis.py`: Confirmed missing storage fields for detailed state.
- Checked `engine.py` and `simulation/tick.py`: Found capture points for brain manifests but no persistence or event broadcasting.
- Inspected `web/templates/index.html`: UI lacked panels for global logging or deep entity state.

## Root Cause
The simulation lacked a dedicated stream for transient interaction events and granular storage in the entity hash for its most expensive/complex internal data (neural/LLM outputs). Bulk state APIs were too naive (fetching full objects), which discouraged adding large fields.

## Working Solution

### 1. Granular Storage
Added observability fields to `Entity` and `RedisEntityRepository.to_storage_dict`.

```python
# simulation/entity.py
last_manifest: str = ""
last_activations: str = ""
last_llm_exchange: str = ""

def to_storage_dict(self) -> dict:
    return {
        # ...
        "last_manifest": self.last_manifest,
        "last_activations": self.last_activations,
        "last_llm_exchange": self.last_llm_exchange,
    }
```

### 2. Capped Interaction Stream
Implemented `RedisInteractionStream` with `MAXLEN 1000` to prevent memory exhaustion.

```python
# storage/redis.py
class RedisInteractionStream:
    async def publish_interaction(self, event_type, source_id, message, extra_data=None):
        await self._r.xadd("interactions:main", payload, maxlen=1000, approximate=True)
```

### 3. Tick Loop Capture
Updated `TickEngine` to populate these fields and publish events during the tick cycle (birth, death, signal, significant movement).

### 4. API Optimization
Optimized bulk state fetch to skip large strings using `HMGET`.

```python
# storage/redis.py
async def load_many_partial(self, entity_ids, fields):
    # Uses pipeline and HMGET for specific fields only
```

### 5. Tabbed UI
Revamped `index.html` with a scrollable interaction log and a tabbed details panel (Prompts, Neural, Exchange, Genetics).

## Prevention Strategies
- **Expose Internal State Early:** For agentic systems, the prompt/response loop is the primary diagnostic tool. Always persist the "last exchange."
- **Use Capped Streams for Events:** Never use unbounded logs in memory-sensitive storage like Redis.
- **Differentiate Bulk vs. Detail APIs:** Avoid sending multi-kilobyte strings in overview lists. Use `HMGET` or separate endpoints for "heavy" data.

## Related Documentation
- [AGI Architecture (2026-04-11)](../best-practices/agi-entity-simulation-v1-architecture-2026-04-11.md) - Now candidate for refresh regarding event stream patterns.
