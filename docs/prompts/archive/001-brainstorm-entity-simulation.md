/ce:brainstorm

<objective>
Brainstorm the architecture and design of a genetic-algorithm-driven entity simulation with neural networks and LLM-powered agent behavior. The goal is to define the core systems, data models, module boundaries, and technology choices before writing any code.
</objective>

<context>
This is a greenfield Python web application simulating individual entities that evolve through genetic algorithms, interact via neural networks, and are driven by LLM agent prompts.

Each entity has:
- A **lifespan** (finite lifetime)
- A **genome** (set of genes from a universal gene pool)
- A **private neural network** (neurons drawn from a universal neuron pool, wired by genetics)
- A **system prompt** (fixed personality, influenced by genes and parent prompts)
- A **user prompt** (mutable character traits, accumulates learning during lifetime — acts as memory)
- An **assigned LLM model** (from a pool of available models across multiple providers)

The neural network is the "intuitive animal" layer — it determines what the entity can perceive and do. The LLM prompts are the "spirit/soul" layer — they drive higher-level agency and decision-making.

**Model providers** (entities can be assigned models from any of these):
- **Ollama** — local models accessed via standard TCP (localhost API)
- **LM Studio** — local models accessed via standard TCP (localhost API)
- **OpenRouter** — remote models accessed via API key (stored in `.env` file)
- **Anthropic (Claude)** — accessed via Agent Client Protocol using [claude-agent-acp](https://github.com/zed-industries/claude-agent-acp) (Zed's Claude Agent SDK ACP implementation)
</context>

<key_systems_to_brainstorm>

<neural_network_system>
- Universal neuron pool: what types of neurons exist and what capabilities they grant
- Brain wiring: how neurons connect and what connectivity patterns mean for perception/action
- Neuron types to consider: sensory neurons (perceive environment), motor neurons (interact with environment/entities), communication neurons (exchange information), reproductive neurons (enable reproduction)
- How the neural network interfaces with the agent prompt system
- Minimal viable neuron set for v1 (void environment, limited interactions)
</neural_network_system>

<agent_prompt_system>
- System prompt generation: how genes + randomness + parent prompts combine to create fixed personality
- User prompt evolution: how entities modify their own user prompt through experience
- Memory management: how learning accumulates and what happens at entity death
- Model assignment: strategy for assigning LLM models from a pool across providers (Ollama, LM Studio, OpenRouter, Anthropic via ACP)
- Provider abstraction: unified interface so the simulation doesn't care which provider serves a given entity's model
- Prompt-to-action pipeline: how LLM output translates into entity actions within neural network constraints
- The entity can only act within its neural network capacity — how to enforce this constraint
- ACP integration: how to use claude-agent-acp (https://github.com/zed-industries/claude-agent-acp) for Anthropic models
</agent_prompt_system>

<genetic_algorithm_system>
- Universal gene pool: what genes exist and what they control
- Gene dominance: some genes more likely to transmit than others
- Mutation rates: some genes more likely to mutate than others
- Sexual reproduction: gene merging strategy from two parents
- Asexual reproduction: division with rare mutation
- How genes influence: brain configuration, system prompt, user prompt, lifespan, other traits
- Minimal viable gene set for v1
</genetic_algorithm_system>

<environment_system>
- V1 is a void with no survival challenges (no food, no threats)
- Entities are "floating brains" with limited interactions
- What minimal interactions should exist in v1 to test the system?
- How to design the environment interface so future versions can add terrain, resources, challenges
</environment_system>

</key_systems_to_brainstorm>

<technology_decisions>
Thoroughly explore and recommend the best approach for each:

1. **Backend API**: FastAPI for the data/simulation backend (confirmed)
2. **Web frontend**: Flask vs Quart (async) vs other Python web framework — recommend with reasoning
3. **Data storage strategy**:
   - V1: Markdown files for prompts, JSON files for genes/genomes/neurons/brains
   - Entity runtime data: Redis or alternative key-value store
   - Message queue: RabbitMQ or alternative for simulation speed
   - Future: vector database for embeddings, SQLAlchemy + Alembic for relational data
4. **Modularity**: architecture must allow swapping modules to Rust or PyTorch without blocking other development
5. **Simulation loop**: how to run the simulation tick-by-tick, handle entity actions, resolve interactions
6. **Async considerations**: should the entire stack be async? What are the trade-offs?

5. **Model provider integration**:
   - Ollama and LM Studio: local TCP access (OpenAI-compatible API)
   - OpenRouter: remote API with key from `.env` file
   - Anthropic Claude: via Agent Client Protocol using claude-agent-acp (https://github.com/zed-industries/claude-agent-acp)
   - How to abstract multiple providers behind a unified interface
   - Cost/latency trade-offs: local models (free, fast) vs remote models (more capable, costs money)

The maintainer is proficient in Python. Suggest improvements to the tech stack but keep it Python-based.
</technology_decisions>

<constraints>
- Python is the primary language (non-negotiable)
- System must be highly modular (parts may be rewritten in Rust/PyTorch later)
- V1 should be minimal — just enough to prove the core loop works
- Storage starts simple (files) but must be designed for migration to databases
- The simulation must handle many entities efficiently (consider this in architecture)
</constraints>

<brainstorm_focus>
Go beyond surface-level architecture. Deeply consider:

1. **The core simulation loop**: What happens each tick? How do entities decide actions? How are interactions resolved?
2. **The neural-network-to-LLM interface**: This is the most novel part — how does a neural network constrain/inform an LLM agent?
3. **Emergent behavior potential**: How might this system produce interesting emergent behavior? What design choices maximize this?
4. **Scalability concerns**: With many entities each needing LLM calls, how to manage API costs and latency?
5. **Data model design**: What are the core data structures for Gene, Neuron, Brain, Entity, Genome?
6. **Module boundaries**: Where are the clean interfaces between systems so they can be independently developed/replaced?
7. **V1 scope**: What is the absolute minimum to prove the concept works end-to-end?
</brainstorm_focus>
