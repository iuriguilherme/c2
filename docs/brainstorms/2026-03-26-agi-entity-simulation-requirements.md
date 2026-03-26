---
date: 2026-03-26
topic: agi-entity-simulation
---

# AGI — Agent-driven Genetic-simulated Individual-organisms

## Problem Frame

We want to simulate the emergence of complex adaptive behavior in a population of individual entities. Each entity has three interacting layers: a **genetic layer** (heritable traits, mutation, evolution), a **neural layer** (capability gating — what the entity can perceive and do), and an **agent layer** (LLM-driven reasoning — what the entity decides to do). The goal is to build a minimal but complete loop in V1 that proves all three layers interact correctly and can produce diverging individual histories.

## Requirements

### Core Simulation Loop

- R1. The simulation runs in **hybrid tick mode**: the world advances in discrete ticks, but LLM calls happen asynchronously between ticks and cache their output for the entity's next action. No tick is blocked waiting for an LLM response.
- R2. Each tick, all living entities: resolve their cached action against the world, update their state, then dispatch the next async LLM call with updated context.
- R3. Entities have a finite lifespan measured in ticks. At lifespan expiry, the entity dies and its data is archived (user prompt preserved for potential inheritance).
- R4. Every entity has a configurable **think interval** — the minimum number of ticks between LLM calls. This prevents API saturation and allows cheap entities (local models) to think more often than expensive ones.

### Neural Network System

- R5. There is a universal **neuron pool** — a fixed catalogue of neuron types, each granting a specific perception or action capability.
- R6. Each entity has a **brain** — a subset of neurons drawn from the universal pool, connected by directed weighted edges. The specific neurons present and their wiring determine the entity's capability profile.
- R7. Each tick, the brain computes a **Capability Manifest**: a structured snapshot of what the entity can currently perceive and what actions are available, with activation weights. This manifest is the sole interface between the neural layer and the agent layer.
- R8. LLM output is validated against the current Capability Manifest before execution. Actions outside the entity's neural capacity are silently rejected; the entity does nothing that tick.
- R9. V1 neuron types (minimal viable set):
  - **Sensory**: proximity (detects nearby entities), signal-receiver (receives broadcast messages)
  - **Motor**: locomotion (move in the void), signal-emitter (broadcast a message to nearby entities)
  - **Reproductive**: divide (asexual reproduction trigger)
  - **Interneuron**: memory-cell (short-term state across ticks, not persisted to user prompt)

### Agent Prompt System

- R10. Each entity has two prompts:
  - **System prompt** (fixed at birth): encodes personality, influenced by genes and optionally by parent system prompt.
  - **User prompt** (mutable): encodes accumulated learning and character traits. Updated by the entity itself during its lifetime.
- R11. The LLM receives: system prompt + user prompt + Capability Manifest (structured) + recent interaction history. It outputs a structured action and optionally a user prompt update.
- R12. The entity *may not* modify its system prompt. It *may* modify its user prompt each tick.
- R13. On entity death, the user prompt is archived and available to offspring (with mutation) during reproduction.
- R14. Each entity is assigned an LLM model from a pool spanning multiple providers. The simulation runtime is provider-agnostic — it interacts with a unified model interface regardless of whether the underlying model is local or remote.
- R15. Supported providers in V1:
  - **Ollama** — local, OpenAI-compatible API over TCP
  - **LM Studio** — local, OpenAI-compatible API over TCP
  - **OpenRouter** — remote, API key from `.env`
  - **Anthropic Claude** — via Agent Client Protocol using `claude-agent-acp`
- R16. Model assignment strategy is configurable per-run (e.g. random assignment, gene-driven assignment, or explicit mapping). V1 default: random from available pool.

### Genetic Algorithm System

- R17. There is a universal **gene pool** — a fixed catalogue of gene types. Each gene type specifies: what it controls, its base dominance probability, and its base mutation rate.
- R18. An entity's **genome** is a set of gene instances drawn from the universal pool. Genes influence: brain configuration (neuron selection and wiring), system prompt generation, user prompt seed, lifespan, and think interval.
- R19. V1 gene set (minimal viable set):
  - **lifespan** — controls max age in ticks
  - **brain-size** — controls how many neurons the entity receives
  - **neuron-affinity** — biases which neuron types are drawn from the pool
  - **personality-seed** — influences system prompt generation
  - **think-interval** — controls LLM call frequency
  - **reproduction-threshold** — controls at what age/condition the divide neuron activates
- R20. The reproduction interface accepts `parent1` and optional `parent2`. V1 implements asexual (division) only — `parent2` is `None`. The interface is designed so sexual reproduction can be added in V2 without restructuring the genetic algorithm.
- R21. Asexual reproduction: offspring receives a copy of the parent genome with per-gene mutation applied according to each gene's mutation rate.
- R22. Gene dominance is reserved for sexual reproduction in V2 but the data structure carries dominance values from V1.
- R23. Offspring system prompt is derived from parent system prompt + gene influence + random noise. Offspring user prompt is either empty or seeded from parent user prompt (configurable).

### Environment System

- R24. V1 environment is a **void**: a bounded coordinate space with no terrain, resources, or survival pressure.
- R25. Entities have a position in the void. Locomotion moves an entity. Proximity is determined by distance between positions.
- R26. The environment interface is abstract — future versions can add terrain, resources, and hazards without changing entity or simulation loop code.
- R27. V1 interactions: movement, proximity detection, broadcast message emission and reception, asexual reproduction.

### Data and Storage

- R28. V1 storage:
  - Gene pool, neuron pool: JSON files (read-only at runtime)
  - Prompt templates and personality seeds: Markdown files
  - Entity runtime state: Redis key-value store
  - Simulation message passing and tick coordination: Redis Streams
- R29. The storage layer is abstracted behind repository interfaces so the backing store can migrate to PostgreSQL + pgvector (future) without changing simulation logic.
- R30. Entity data (genome, brain, prompts, state) is stored in Redis during lifetime and archived to a persistent store on death.

### Application Architecture

- R31. The system consists of two independent services:
  - **API service** (FastAPI): manages the gene pool, neuron pool, prompt templates, entity archive, and simulation configuration. Authoritative data store.
  - **Web service** (Quart, async): renders the simulation UI, proxies requests to the API, streams live simulation state to the browser.
- R32. The simulation engine runs as a background process coordinated via Redis Streams. It is not embedded in either web service.
- R33. All inter-module boundaries are defined as abstract interfaces (Python ABCs or Protocols) so any module (`genetics/`, `neural/`, `agents/`, `environment/`) can be independently replaced with a Rust extension or PyTorch implementation.
- R34. The entire stack uses async I/O throughout. No synchronous blocking calls in the hot path.

## Success Criteria

- An entity is born, assigned a model, generates a Capability Manifest each tick, makes LLM-driven decisions constrained by the manifest, accumulates learning in its user prompt, and dies at lifespan expiry.
- Two generations of entities exist where offspring demonstrably inherit and mutate parent genome and prompts.
- Entities with different neuron configurations have meaningfully different Capability Manifests and therefore different available actions.
- The simulation runs with at least two different model providers active simultaneously (e.g. one Ollama entity, one OpenRouter entity) without special-casing in the simulation loop.
- Adding a new gene type or neuron type requires changes only within the `genetics/` or `neural/` module, with no changes to the simulation loop or agent layer.

## Scope Boundaries

- V1 is a void — no food, no threats, no survival pressure. Entities do not need resources to survive.
- Sexual reproduction is out of scope for V1. The interface and data structures are forward-compatible, but two-parent reproduction is not implemented.
- Vector database, embeddings, and embedding-model calls are out of scope for V1.
- No UI beyond a basic entity list, tick counter, and per-entity state view.
- No authentication or multi-user support.
- Entity communication in V1 is broadcast-only (no directed messaging, no private channels).

## Key Decisions

- **Hybrid tick model**: World state advances synchronously on tick boundaries; LLM calls are async and cached. Balances determinism with LLM latency variance.
- **Quart over Flask**: Async is non-negotiable given concurrent LLM calls per entity. Quart is Flask-compatible and async-native.
- **Redis Streams over RabbitMQ (V1)**: Reduces infrastructure complexity since Redis is already required for entity state. Can migrate to RabbitMQ if throughput demands it.
- **Capability Manifest as the neural↔LLM interface**: The neural network does not directly call the LLM. It produces a manifest; the agent layer consumes it. Clean separation, independently testable.
- **Reproduction interface is parent1 + optional parent2 from day one**: Ensures asexual-only V1 does not create technical debt blocking sexual reproduction in V2.
- **Think interval per entity**: Prevents LLM API saturation. Local-model entities can think faster; remote/expensive models think less frequently.
- **PostgreSQL + pgvector (future)**: Preferred over a separate vector database — combines relational and vector search in one service.

## Dependencies / Assumptions

- Ollama and LM Studio are running locally and accessible via TCP before simulation start.
- OpenRouter API key is available in `.env`.
- `claude-agent-acp` (https://github.com/zed-industries/claude-agent-acp) is available and installable as a Python dependency.
- Redis is available locally (Docker or native install).

## Outstanding Questions

### Resolve Before Planning
*(none — all product decisions resolved)*

### Deferred to Planning

- [Affects R7][Technical] Exact schema of the Capability Manifest (JSON structure, field names, activation weight representation).
- [Affects R11][Technical] Prompt template format for injecting the Capability Manifest into LLM context. How structured should the injection be (plain text description vs. JSON block)?
- [Affects R14][Needs research] `claude-agent-acp` integration: how it exposes the ACP client, what the async call pattern looks like, and whether it fits the unified provider interface cleanly.
- [Affects R16][Technical] Model assignment strategy implementation: how the pool of available models is discovered at runtime (e.g. querying Ollama's model list, reading a config file).
- [Affects R28][Technical] Redis data structure design for entity state — hash per entity vs. serialized JSON blob vs. separate keys per field.
- [Affects R30][Technical] Archive format and trigger — does archiving happen synchronously at death or via a background job?
- [Affects R33][Technical] Which Python abstract base class vs. Protocol pattern to use for module interfaces, and whether to enforce this with runtime checks or type checking only.

## Next Steps

→ `/ce:plan` for structured implementation planning
