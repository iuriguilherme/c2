---
date: 2026-04-16
topic: interaction-and-brain-visualization
---

# Interaction and Brain Visualization

## Problem Frame
Entities in the AGI simulation evolve genetically and process information through a neural network before making decisions via LLMs. However, currently, the user cannot see "under the hood" of these brains or the raw LLM exchanges. Furthermore, interactions between entities (like signals or proximity effects) are hard to track without a centralized log.

## Requirements
- R1. **Neural State Visualization**: Display the current `CapabilityManifest` (perceptions and available actions) for a selected entity.
- R2. **Raw LLM Exchange**: Display the full prompt sent to the LLM (System + User + Manifest) and the exact raw response received for a selected entity.
- R3. **Global Interaction Log**: A centralized "chatbox" or log panel that displays significant events:
    - Entity signals (broadcasts)
    - Movement/Encounters (optional but helpful)
    - Life events (Births, Deaths)
    - Successful actions
- R4. **Real-time Updates**: These visualizations should update as the simulation ticks.

## Success Criteria
- User can select an entity and see exactly what it "saw" (manifest) and what it "thought" (LLM raw exchange).
- User can see a stream of events from all entities in one place.

## Scope Boundaries
- Visualization will be text-based (JSON/Preformatted text) in the existing Quart/FastAPI web interface.
- No changes to the underlying neural network logic or LLM provider implementation.

## Key Decisions
- **Storage**: Use a Redis Stream (`interactions:main`) for the global log to ensure efficient real-time updates and historical persistence within the session.
- **Entity State**: Store `last_manifest` and `last_llm_exchange` (prompt + response) in the Redis entity hash for retrieval by the web UI.

## Outstanding Questions

### Deferred to Planning
- [Technical] Should we limit the size of the `last_llm_exchange` to avoid ballooning Redis memory?
- [Technical] How to deduplicate movement logs to avoid noise? (e.g., only log significant movement or interactions).

## Next Steps
→ /ce:plan
