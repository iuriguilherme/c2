---
date: 2026-04-12
topic: open
focus: open-ended (no specific focus)
---

# Ideation: c2 AGI Entity Simulation — Open

## Codebase Context

**Project shape:** Python 3.14+ AGI entity simulation. Entities have genetics (Gene/Genome, mutation, reproduction), neural systems (NeuronPool, CapabilityManifest), and LLM-driven decisions. FastAPI REST API + Quart web UI + asyncio. Redis persistence. 113 pytest tests with fakeredis CI.

**Key architecture:**
- Hybrid tick engine: Phase A executes cached actions synchronously; Phase B dispatches async LLM calls via `asyncio.gather` over all living entities
- `LLMProvider` Protocol (Anthropic, OpenRouter, Ollama) — async generator, not ABC
- `CapabilityManifest.get_available_actions()` gates neural→LLM
- Message eviction: 10-tick age cap, 20-message cap (OOM guard)
- Fakeredis fallback on Redis connection failure
- `Brain.from_genome()` re-derived every tick via deterministic RNG seed
- `Entity.cached_action` + `cached_action_tick` stores last LLM decision (outcome never fed back)

**Known open todos (pre-triaged, bounded):**
- Replace module-global `_redis_client` with `app.state.redis`
- Add auth to `GET /entities/archived/{entity_id}`
- Wire `system_template.j2` into `EntityFactory` (unused; inline f-strings used instead)
- Add done-callback for fire-and-forget reproduction task

**Notable leverage points:**
- `LLMProvider` Protocol extensible — adding providers low friction
- `CapabilityManifest extra="allow"` — forward-compatible neuron types
- Redis Stream as tick log — stable schema, queryable
- V2 hooks reserved in genetics (sexual reproduction interface)

## Ranked Ideas

### 1. Integration Test Harness with Deterministic Tick Stepping
**Description:** Build a test fixture that drives a full Phase A + Phase B cycle using a `MockLLMProvider` returning scripted action sequences. Expose `step(n)` to advance exactly N ticks and assert on world state. The `LLMProvider` Protocol makes `MockLLMProvider` trivial — no engine changes needed.
**Rationale:** 113 unit tests cover components in isolation but the hybrid tick's Phase A/B concurrency is untested. One harness multiplies the value of every future simulation feature by providing a reliable correctness baseline.
**Downsides:** Scripted LLM responses cannot catch emergent behavior bugs; tests engine correctness, not simulation fidelity.
**Confidence:** 90%
**Complexity:** Low
**Status:** Unexplored

---

### 2. Persistent Brain Activation State
**Description:** `Brain` is re-derived from the genome on every tick using a deterministic RNG seed — activation levels are throwaway. Store the brain as a mutable Redis structure persisted between ticks, so activation levels accumulate and decay across the entity's lifetime, enabling Hebbian-style plasticity.
**Rationale:** The deterministic-seed workaround (`hash(data["id"]) % 2**31`) is a technical debt signal that the design knows brains should be stable but deferred it. This is the minimum precondition for any learned behavior or habituation — entities currently reset cognitively every 2 seconds.
**Downsides:** Adds brain-state to the Redis entity hash (schema migration); persistent activation could amplify early biases in unexpected ways.
**Confidence:** 85%
**Complexity:** Medium
**Status:** Explored — brainstorm initiated 2026-04-12

---

### 3. Coherent Action Intelligence Layer
**Description:** Three interlocking improvements sharing the `CapabilityManifest` surface: (a) formalize actions as structured schemas (name, preconditions, postconditions, cost model) in a Semantic Action Schema Registry; (b) log every capability-gate event (entity, capability missing, tick) to Redis so the neural→LLM black box becomes observable; (c) close the open feedback loop by including `action_result` in the next tick's manifest, so the LLM knows whether its last action succeeded. Each is independently shippable.
**Rationale:** `cached_action` is stored but the outcome of `_execute_action()` returns `None` and is never fed back — the LLM operates without consequence feedback, making every think cycle memoryless relative to outcomes. Action schemas make gating explicit and auditable; capability logs surface silent freezes; outcome feedback makes decisions grounded.
**Downsides:** Schema registry is non-trivial upfront investment; outcome feedback must be carefully scoped to avoid flooding LLM context; all three together represent significant surface area.
**Confidence:** 85%
**Complexity:** High (compound) / Medium (individually)
**Status:** Unexplored

---

### 4. Batched LLM via Anthropic Message Batches API
**Description:** Replace `asyncio.gather` over N individual LLM HTTP calls with a single Anthropic Batches API request covering all `should_think` entities per tick. Poll for completion before advancing the tick. The existing `LLMProvider` Protocol is the natural integration point as a new `AnthropicBatchProvider`.
**Rationale:** At 1000 entities, current Phase B opens 1000 concurrent TCP connections to one endpoint — connection pool exhaustion and rate-limit throttling are inevitable. The Batches API collapses this to a handful of round-trips with ~50% cost reduction per Anthropic's documentation.
**Downsides:** Batching introduces latency variance (tick duration becomes poll-round-trip); batch API does not support streaming. Requires a new provider implementation and a tick timing model that tolerates async batch completion.
**Confidence:** 90%
**Complexity:** Medium
**Status:** Unexplored

---

### 5. Offspring Spawn Rate Governor
**Description:** Add a per-tick global cap on new spawns (e.g., max 5% population growth per tick) enforced in the reproduction Phase B dispatch. Entities that would breach the cap queue for the next tick rather than being silently dropped.
**Rationale:** `REPRODUCTION_THRESHOLD` is a gene subject to evolutionary pressure toward 0. Combined with fire-and-forget `asyncio.create_task`, a single tick of mass reproduction can double population and double LLM concurrency — compounding on every subsequent tick until server collapse. This is the primary self-amplifying failure mode.
**Downsides:** The cap introduces artificial selection pressure (entities that reproduce at the right time succeed); requires choosing a sensible default and exposing it as a config parameter.
**Confidence:** 88%
**Complexity:** Low
**Status:** Unexplored

---

### 6. Behavioral Mimicry via Action Observation
**Description:** When assembling an entity's LLM context, include the `cached_action` of each nearby entity as an observable field: "entity_X did Y last tick." `cached_action` is already persisted; `VoidEnvironment` already has proximity queries. This is almost entirely a prompt-engineering change with one extra context field.
**Rationale:** Enables social learning and cultural transmission without any explicit teaching mechanism — entities can copy successful neighbors, driving behavioral monocultures that mutation then disrupts. Arms races, fashions, and specialization become emergent without scripting.
**Downsides:** Adds tokens to every LLM context proportional to neighbor count; at high density this expands prompts significantly, increasing cost and potentially exceeding context windows.
**Confidence:** 82%
**Complexity:** Low
**Status:** Unexplored

---

### 7. Seeded RNG + Experiment Manifest
**Description:** Two paired ideas: (a) capture the full RNG state at simulation start in a seed manifest, making any run reproducible by restoring that state; (b) define a declarative `experiment.yaml` specifying initial population, gene pool subset, halt conditions, tick budget, and all tunable parameters — replacing scattered env vars as the single artifact describing a run.
**Rationale:** Without reproducibility, no finding is distinguishable from a lucky draw. Without a manifest, no experimental setup can be shared or compared. These are the minimum prerequisites for c2 to produce knowledge rather than just animations.
**Downsides:** RNG seeding must cover all stochastic surfaces (entity creation, mutation, LLM temperature sampling); manifest validation adds startup complexity; retrofitting to env var conventions requires migration.
**Confidence:** 80%
**Complexity:** Medium
**Status:** Unexplored

---

## Rejection Summary

| # | Idea | Reason Rejected |
|---|------|-----------------|
| 1 | Authenticated Archive Endpoint | Already on todos list |
| 2 | Redis Client → app.state Migration | Already on todos list |
| 3 | Supervised Reproduction Queue | Already on todos list (todo item 4) |
| 4 | Auto-Generate API Contract | Trivial FastAPI feature; not ideation material |
| 5 | Jinja2 Template Pipeline Activation | Conflicts with delete-Jinja2 position; weaker |
| 6 | Delete Jinja2 Dependency | Cleanup task; not a strategic direction |
| 7 | Per-Provider Latency Dashboard | Narrow; subsumed by Action Intelligence Layer |
| 8 | critical-patterns.md from Test Failures | Documentation workflow; not product capability |
| 9 | Genome Diff / Lineage Viewer | Premature; V2 genetics not yet built |
| 10 | Provider Failover + Degradation Mode | Operational concern; lower priority |
| 11 | Competitive Provider Assignment | Speculative; no grounding |
| 12 | Evolving Gene/Neuron Pool Ontology | V2+++ scope; too expensive |
| 13 | Salience-Pinned Message Retention | Subsumed by Contextual Memory System (itself later cut) |
| 14 | Energy / Metabolic Cost for Actions | Good design choice; better as brainstorm seed |
| 15 | Provider SDK ADR / Decision Log | Documentation workflow |
| 16 | Orphaned Doc Archival Check CI | Process workflow |
| 17 | Phenotype Cache | V2 prerequisite; premature |
| 18 | Provider Capability Negotiation | Subsumed by Provider Failover idea (rejected) |
| 19 | Auto-Generate Fixtures from Redis Schema | Fixture pain unconfirmed; speculative |
| 20 | Live Genome Drift (within-lifetime) | Destabilizes simulation without persistent brain first |
| 21 | Genetic Operator Protocol | Premature abstraction; V2 scope |
| 22 | Entity Introspection API Endpoint | Subsumed by Replay + Action Intelligence Layer |
| 23 | Within-Lifetime Learning Stack (compound) | Genome drift part risky; sequencing problem |
| 24 | Deception / Forged Capability Announcements | Speculative; requires gene + LLM output parsing for false manifests |
| 25 | Social Reputation Eviction Queue | Subsumed by Contextual Memory System (itself cut) |
| 26 | Arms-Race Jamming Gene | Not grounded in current genetics |
| 27 | Asymmetric Public/Private Genome | Vague; overlaps Reproductive Signaling direction |
| 28 | Tick-Locked Pledges | High complexity; uncertain payoff; better as brainstorm seed |
| 29 | Run Comparison Report | Derivative; requires Snapshot + Stats first |
| 30 | Experiment Registry | Derivative; premature |
| 31 | VoidEnvironment → Redis (crash recovery) | Operational; not simulation capability |
| 32 | Redis Pipeline Batching | Tactical; subsumed by scale work |
| 33 | Population Snapshot Exporter | Dependent on Experiment Manifest first |
| 34 | Conditional Halt Triggers | Useful but narrow; not strategic |
| 35 | Fitness Function Plugin Interface | Absorbed into Experiment Manifest (selection pressure config) |
| 36 | LLM Decision Audit Log | Absorbed into Coherent Action Intelligence Layer |
| 37 | Population Dynamics Metrics | Absorbed into existing Tick Stream Replay (later cut) |
| 38 | Coalition Inbox Channels | Complex; brainstorm variant after social foundation |
| 39 | Norm Enforcement via Collective Punishment | Complex social mechanic; brainstorm variant |
| 40 | VoidEnvironment Positional Index | Tactical scale fix; lower priority than Batched LLM |
| 41 | Gene/NeuronPool Hot-Reload | Derivative of Experiment Manifest |
| 42 | Reproductive Signaling / Courtship | Depends on social foundation first |
| 43 | Brain Derivation LRU Cache | Subsumed by Persistent Brain Activation State (#2) |
| 44 | Contextual Memory System | 70% confidence; message genealogy depends on LLM output parsing (weak link) |
| 45 | Tick Stream Replay Engine | High debugging value; nice-to-have vs. need-to-have |
| 46 | Operator-Injected World Events | Partially covered by Experiment Manifest (#7) |
| 47 | Entity-Owned Cognitive Rhythm | Medium-High complexity; two sub-ideas ship independently; less foundational |
| 48 | LLM Provider Rate-Limit Semaphore | Operational; tactical; doesn't require brainstorming |
| 49 | Offspring Spawn Rate Governor | Kept (see #5) |

## Session Log
- 2026-04-12: Initial ideation — 4 frames, ~30 raw candidates, 7 survivors (open-ended)
- 2026-04-12: Refinement round 1 — 3 new frames (social dynamics, scale/performance, research instrument), 28 new candidates, 6 new survivors added (total 13)
- 2026-04-12: Second strict pass — cut to 7 final survivors; notable cuts: Brain LRU Cache (subsumed by #2), Contextual Memory System (LLM output parsing dependency), Tick Stream Replay (nice-to-have), Entity-Owned Cognitive Rhythm (complexity vs. foundational value)
- 2026-04-12: Brainstorm initiated for idea #2 (Persistent Brain Activation State)
