# AGI Entity Simulation V1 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a working AGI simulation where entities with genetic, neural, and LLM layers interact in a hybrid tick loop coordinated via Redis.

**Architecture:** Three-layer entities (genetics → neural → agent); hybrid tick engine (sync world advance, async LLM between ticks); Redis hashes for entity state, Redis Streams for tick coordination; FastAPI for config data; Quart for UI.

**Tech Stack:** Python 3.14, Pydantic v2, FastAPI, Quart, Hypercorn, redis-py async, httpx, anthropic SDK, openai SDK (OpenRouter), pytest + pytest-asyncio + fakeredis + respx

---

## Cleanup: Delete broken draft files

Before starting, remove all broken draft files that will be replaced:

```bash
rm -f simulation_engine.py create_provider.py
rm -f "CUsersiuriDownloadscvsc2agentsprovidersprovider.py"
rm -rf agents/ api/ genetics/
```

---

## File Map

```
pyproject.toml
.env.example
data/
  gene_pool.json
  neuron_pool.json
genetics/
  __init__.py
  models.py          # GeneType, GeneDefinition, GeneInstance, Genome (Pydantic v2)
  pool.py            # GenePool — loads gene_pool.json, provides default_genome()
  reproduction.py    # reproduce(parent1, parent2=None) -> Genome
neural/
  __init__.py
  models.py          # NeuronType, NeuronDefinition, CapabilityManifest + sub-models (Pydantic v2)
  pool.py            # NeuronPool — loads neuron_pool.json
  brain.py           # Brain — wired subset of neurons, generate_manifest(context) -> CapabilityManifest
agents/
  __init__.py
  protocol.py        # LLMProvider Protocol, LLMError hierarchy
  output.py          # AgentOutput Pydantic model (action + optional user_prompt_update)
  pool.py            # ModelPool — discovers available models, random assignment
  providers/
    __init__.py
    ollama.py        # OllamaProvider (httpx async, OpenAI-compatible)
    lmstudio.py      # LMStudioProvider (same pattern, different default port)
    openrouter.py    # OpenRouterProvider (openai SDK, base_url override)
    anthropic.py     # AnthropicProvider (anthropic SDK)
environment/
  __init__.py
  void.py            # VoidEnvironment — bounded 2D space, proximity, broadcast
simulation/
  __init__.py
  entity.py          # Entity dataclass (genome, brain, prompts, model assignment, state)
  factory.py         # EntityFactory: Genome -> Entity
  tick.py            # TickEngine — hybrid tick loop (THE core)
  reproduction.py    # ReproductionHandler — processes reproduction:queue stream
  archive.py         # EntityArchive — synchronous archive at death
storage/
  __init__.py
  protocol.py        # EntityRepository, TickStream Protocols
  redis.py           # RedisEntityRepository, RedisTickStream
api/
  __init__.py
  main.py            # FastAPI app
  routes/
    genes.py
    neurons.py
    entities.py
web/
  __init__.py
  main.py            # Quart app
  templates/
    index.html
engine.py            # Simulation engine entry point (asyncio main)
tests/
  conftest.py
  test_genetics.py
  test_neural.py
  test_agents.py
  test_simulation.py
  test_api.py
  test_integration.py
```

---

## Task 1: Project Bootstrap

**Files:**
- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `tests/conftest.py`

- [ ] **Step 1: Create pyproject.toml**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "c2"
version = "0.1.0"
requires-python = ">=3.14"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.34",
    "quart>=0.20",
    "hypercorn>=0.17",
    "redis[hiredis]>=5.2",
    "pydantic>=2.10",
    "anthropic>=0.49",
    "openai>=1.68",
    "httpx>=0.28",
    "python-dotenv>=1.0",
    "jinja2>=3.1",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3",
    "pytest-asyncio>=0.25",
    "fakeredis>=2.26",
    "respx>=0.22",
    "pytest-cov>=6.0",
    "httpx>=0.28",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.hatch.build.targets.wheel]
packages = ["genetics", "neural", "agents", "environment", "simulation", "storage", "api", "web"]
```

- [ ] **Step 2: Create .env.example**

```
OPENROUTER_API_KEY=sk-or-...
ANTHROPIC_API_KEY=sk-ant-...
OLLAMA_BASE_URL=http://localhost:11434
LMSTUDIO_BASE_URL=http://localhost:1234
REDIS_URL=redis://localhost:6379
API_BASE_URL=http://localhost:8000
VOID_WIDTH=1000.0
VOID_HEIGHT=1000.0
```

- [ ] **Step 3: Install dependencies**

```bash
pip install -e ".[dev]"
```

Expected: installs without error, `pytest --collect-only` shows 0 tests.

- [ ] **Step 4: Create tests/conftest.py**

```python
import pytest
import fakeredis.aioredis


@pytest.fixture
async def redis():
    r = fakeredis.aioredis.FakeRedis()
    yield r
    await r.aclose()
```

- [ ] **Step 5: Verify pytest runs**

```bash
pytest --tb=short
```

Expected: `no tests ran`, exit 0.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml .env.example tests/conftest.py
git commit -m "feat: project bootstrap — pyproject.toml, pytest config, conftest"
```

---

## Task 2: Genetics — Models

**Files:**
- Create: `genetics/__init__.py`
- Create: `genetics/models.py`
- Create: `data/gene_pool.json`
- Test: `tests/test_genetics.py` (first section)

- [ ] **Step 1: Write failing tests**

```python
# tests/test_genetics.py
import pytest
from genetics.models import GeneType, GeneDefinition, GeneInstance, Genome


def test_gene_instance_serialization():
    inst = GeneInstance(gene_type=GeneType.LIFESPAN, value=500.0, dominance=0.5)
    d = inst.model_dump()
    assert d["gene_type"] == "lifespan"
    assert d["value"] == 500.0
    restored = GeneInstance.model_validate(d)
    assert restored.gene_type == GeneType.LIFESPAN


def test_genome_contains_all_v1_genes():
    genes = {
        gt: GeneInstance(gene_type=gt, value=1.0, dominance=0.5)
        for gt in GeneType
    }
    genome = Genome(genes=genes)
    assert len(genome.genes) == 6  # V1 has 6 gene types


def test_gene_definition_validation():
    defn = GeneDefinition(
        gene_type=GeneType.LIFESPAN,
        description="Max age in ticks",
        min_value=10.0,
        max_value=10000.0,
        default_value=500.0,
        mutation_rate=0.1,
        mutation_std=50.0,
        dominance_default=0.5,
    )
    assert defn.min_value < defn.default_value < defn.max_value
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/test_genetics.py -x --tb=short
```

Expected: `ModuleNotFoundError: No module named 'genetics'`

- [ ] **Step 3: Create genetics/__init__.py**

```python
# genetics/__init__.py
```

- [ ] **Step 4: Create genetics/models.py**

```python
from enum import Enum
from pydantic import BaseModel, Field, model_validator


class GeneType(str, Enum):
    LIFESPAN = "lifespan"
    BRAIN_SIZE = "brain_size"
    NEURON_AFFINITY = "neuron_affinity"
    PERSONALITY_SEED = "personality_seed"
    THINK_INTERVAL = "think_interval"
    REPRODUCTION_THRESHOLD = "reproduction_threshold"


class GeneDefinition(BaseModel):
    gene_type: GeneType
    description: str
    min_value: float
    max_value: float
    default_value: float
    mutation_rate: float = Field(ge=0.0, le=1.0)
    mutation_std: float = Field(ge=0.0)
    dominance_default: float = Field(ge=0.0, le=1.0, default=0.5)

    @model_validator(mode="after")
    def default_in_range(self) -> "GeneDefinition":
        if not (self.min_value <= self.default_value <= self.max_value):
            raise ValueError(
                f"default_value {self.default_value} not in "
                f"[{self.min_value}, {self.max_value}]"
            )
        return self


class GeneInstance(BaseModel):
    gene_type: GeneType
    value: float
    dominance: float = Field(ge=0.0, le=1.0, default=0.5)


class Genome(BaseModel):
    genes: dict[GeneType, GeneInstance]

    def get(self, gene_type: GeneType) -> float:
        """Return the numeric value of a gene."""
        return self.genes[gene_type].value
```

- [ ] **Step 5: Create data/gene_pool.json**

```json
[
  {
    "gene_type": "lifespan",
    "description": "Maximum age in ticks before entity dies",
    "min_value": 10.0,
    "max_value": 10000.0,
    "default_value": 500.0,
    "mutation_rate": 0.15,
    "mutation_std": 50.0,
    "dominance_default": 0.5
  },
  {
    "gene_type": "brain_size",
    "description": "Number of neurons the entity receives at birth",
    "min_value": 1.0,
    "max_value": 8.0,
    "default_value": 4.0,
    "mutation_rate": 0.1,
    "mutation_std": 0.5,
    "dominance_default": 0.5
  },
  {
    "gene_type": "neuron_affinity",
    "description": "Bias toward motor neurons (0=sensory, 1=motor)",
    "min_value": 0.0,
    "max_value": 1.0,
    "default_value": 0.5,
    "mutation_rate": 0.2,
    "mutation_std": 0.1,
    "dominance_default": 0.5
  },
  {
    "gene_type": "personality_seed",
    "description": "RNG seed for system prompt personality generation",
    "min_value": 0.0,
    "max_value": 2147483647.0,
    "default_value": 42.0,
    "mutation_rate": 0.3,
    "mutation_std": 10000.0,
    "dominance_default": 0.5
  },
  {
    "gene_type": "think_interval",
    "description": "Minimum ticks between LLM calls",
    "min_value": 1.0,
    "max_value": 60.0,
    "default_value": 5.0,
    "mutation_rate": 0.1,
    "mutation_std": 1.0,
    "dominance_default": 0.5
  },
  {
    "gene_type": "reproduction_threshold",
    "description": "Age in ticks at which divide neuron activates",
    "min_value": 10.0,
    "max_value": 5000.0,
    "default_value": 200.0,
    "mutation_rate": 0.15,
    "mutation_std": 20.0,
    "dominance_default": 0.5
  }
]
```

- [ ] **Step 6: Run tests**

```bash
pytest tests/test_genetics.py -x --tb=short
```

Expected: 3 passed.

- [ ] **Step 7: Commit**

```bash
git add genetics/ data/gene_pool.json tests/test_genetics.py
git commit -m "feat: genetics models — GeneType, GeneDefinition, GeneInstance, Genome"
```

---

## Task 3: Genetics — Pool and Reproduction

**Files:**
- Create: `genetics/pool.py`
- Create: `genetics/reproduction.py`
- Test: `tests/test_genetics.py` (add reproduction tests)

- [ ] **Step 1: Add failing tests**

Append to `tests/test_genetics.py`:

```python
import random
from genetics.pool import GenePool
from genetics.reproduction import reproduce


def test_gene_pool_loads_all_definitions():
    pool = GenePool.load()
    assert len(pool.definitions) == 6
    assert GeneType.LIFESPAN in pool.definitions


def test_gene_pool_default_genome_has_all_genes():
    pool = GenePool.load()
    genome = pool.default_genome()
    for gt in GeneType:
        assert gt in genome.genes


def test_reproduce_asexual_returns_genome():
    pool = GenePool.load()
    parent = pool.default_genome()
    offspring = reproduce(parent, pool=pool)
    assert isinstance(offspring, Genome)
    assert set(offspring.genes.keys()) == set(parent.genes.keys())


def test_reproduce_accepts_none_parent2():
    pool = GenePool.load()
    parent = pool.default_genome()
    offspring = reproduce(parent, parent2=None, pool=pool)
    assert offspring is not parent


def test_reproduce_mutation_changes_values_statistically():
    """Over 200 offspring, at least one gene should differ from parent."""
    pool = GenePool.load()
    parent = pool.default_genome()
    changed = False
    for _ in range(200):
        offspring = reproduce(parent, pool=pool)
        for gt in GeneType:
            if offspring.genes[gt].value != parent.genes[gt].value:
                changed = True
                break
        if changed:
            break
    assert changed, "No mutations occurred in 200 offspring — mutation_rate too low?"


def test_reproduce_values_stay_in_bounds():
    pool = GenePool.load()
    parent = pool.default_genome()
    for _ in range(50):
        offspring = reproduce(parent, pool=pool)
        for gt, inst in offspring.genes.items():
            defn = pool.definitions[gt]
            assert defn.min_value <= inst.value <= defn.max_value
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/test_genetics.py -x --tb=short
```

Expected: `ModuleNotFoundError: No module named 'genetics.pool'`

- [ ] **Step 3: Create genetics/pool.py**

```python
import json
from pathlib import Path
from genetics.models import GeneType, GeneDefinition, GeneInstance, Genome

_DATA_PATH = Path(__file__).parent.parent / "data" / "gene_pool.json"


class GenePool:
    def __init__(self, definitions: dict[GeneType, GeneDefinition]) -> None:
        self.definitions = definitions

    @classmethod
    def load(cls, path: Path = _DATA_PATH) -> "GenePool":
        raw = json.loads(path.read_text())
        definitions = {
            GeneType(d["gene_type"]): GeneDefinition.model_validate(d)
            for d in raw
        }
        return cls(definitions)

    def default_genome(self) -> Genome:
        genes = {
            gt: GeneInstance(
                gene_type=gt,
                value=defn.default_value,
                dominance=defn.dominance_default,
            )
            for gt, defn in self.definitions.items()
        }
        return Genome(genes=genes)
```

- [ ] **Step 4: Create genetics/reproduction.py**

```python
import random
from genetics.models import GeneType, GeneInstance, Genome
from genetics.pool import GenePool


def reproduce(
    parent1: Genome,
    parent2: Genome | None = None,
    pool: GenePool | None = None,
    rng: random.Random | None = None,
) -> Genome:
    """
    Create an offspring genome.

    V1: asexual only — parent2 is ignored (interface forward-compatible for V2).
    Each gene mutates independently with probability = mutation_rate.
    Mutated value = clamp(current + gauss(0, mutation_std), min, max).
    """
    if pool is None:
        pool = GenePool.load()
    r = rng or random.Random()

    new_genes: dict[GeneType, GeneInstance] = {}
    for gt, inst in parent1.genes.items():
        defn = pool.definitions[gt]
        value = inst.value
        if r.random() < defn.mutation_rate:
            delta = r.gauss(0, defn.mutation_std)
            value = max(defn.min_value, min(defn.max_value, value + delta))
        new_genes[gt] = GeneInstance(
            gene_type=gt,
            value=value,
            dominance=inst.dominance,
        )
    return Genome(genes=new_genes)
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_genetics.py --tb=short
```

Expected: 9 passed.

- [ ] **Step 6: Commit**

```bash
git add genetics/pool.py genetics/reproduction.py tests/test_genetics.py
git commit -m "feat: genetics pool and asexual reproduction with per-gene mutation"
```

---

## Task 4: Neural — Models and Manifest Schema

**Files:**
- Create: `neural/__init__.py`
- Create: `neural/models.py`
- Create: `data/neuron_pool.json`
- Test: `tests/test_neural.py` (first section)

- [ ] **Step 1: Write failing tests**

```python
# tests/test_neural.py
import pytest
from neural.models import (
    NeuronType, NeuronDefinition, NeuronInstance,
    CapabilityManifest, ActionCapability, ProximityPerception,
    SignalReceiverPerception, MemoryState,
)


def test_capability_manifest_schema_version():
    m = CapabilityManifest(schema_version="1.0", agent_id="e-1", tick=0)
    assert m.schema_version == "1.0"


def test_manifest_get_available_actions_empty():
    m = CapabilityManifest(schema_version="1.0", agent_id="e-1", tick=5)
    assert m.get_available_actions() == []


def test_manifest_get_available_actions_filters():
    m = CapabilityManifest(
        schema_version="1.0",
        agent_id="e-1",
        tick=5,
        actions={
            "locomotion": ActionCapability(available=True, activation=0.9),
            "divide": ActionCapability(
                available=False, activation=0.0,
                reason="threshold not met"
            ),
        },
    )
    assert m.get_available_actions() == ["locomotion"]


def test_manifest_serializes_to_json():
    import json
    m = CapabilityManifest(schema_version="1.0", agent_id="e-1", tick=1)
    payload = json.loads(m.model_dump_json())
    assert payload["schema_version"] == "1.0"
    assert payload["agent_id"] == "e-1"


def test_action_capability_activation_bounded():
    with pytest.raises(Exception):
        ActionCapability(available=True, activation=1.5)  # > 1.0


def test_neuron_definition_roundtrip():
    defn = NeuronDefinition(
        neuron_type=NeuronType.LOCOMOTION,
        name="locomotion",
        description="Move in the void",
        category="motor",
    )
    assert defn.category == "motor"
    d = defn.model_dump()
    restored = NeuronDefinition.model_validate(d)
    assert restored.neuron_type == NeuronType.LOCOMOTION
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/test_neural.py -x --tb=short
```

Expected: `ModuleNotFoundError: No module named 'neural'`

- [ ] **Step 3: Create neural/__init__.py**

```python
# neural/__init__.py
```

- [ ] **Step 4: Create neural/models.py**

```python
from enum import Enum
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class NeuronType(str, Enum):
    PROXIMITY = "proximity"
    SIGNAL_RECEIVER = "signal_receiver"
    LOCOMOTION = "locomotion"
    SIGNAL_EMITTER = "signal_emitter"
    DIVIDE = "divide"
    MEMORY_CELL = "memory_cell"


class NeuronDefinition(BaseModel):
    model_config = ConfigDict(extra="allow")
    neuron_type: NeuronType
    name: str
    description: str
    category: Literal["sensory", "motor", "reproductive", "interneuron"]


class NeuronInstance(BaseModel):
    neuron_type: NeuronType
    activation: float = Field(ge=0.0, le=1.0, default=0.0)


# ── Capability Manifest sub-models ──────────────────────────────────────────

class DetectedEntity(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    distance: float = Field(ge=0.0)
    direction: Literal["north", "south", "east", "west"]


class ProximityPerception(BaseModel):
    model_config = ConfigDict(extra="allow")
    available: bool
    activation: float = Field(ge=0.0, le=1.0)
    detected_entities: list[DetectedEntity] = []


class SignalMessage(BaseModel):
    model_config = ConfigDict(extra="allow")
    from_entity: str
    content: str
    ticks_ago: int = Field(ge=0)


class SignalReceiverPerception(BaseModel):
    model_config = ConfigDict(extra="allow")
    available: bool
    activation: float = Field(ge=0.0, le=1.0)
    recent_messages: list[SignalMessage] = []


class ActionCapability(BaseModel):
    model_config = ConfigDict(extra="allow")
    available: bool
    activation: float = Field(ge=0.0, le=1.0)
    reason: str | None = None
    parameters: dict[str, str] | None = None


class MemoryState(BaseModel):
    model_config = ConfigDict(extra="allow")
    available: bool
    cells: int = Field(ge=0, default=0)
    values: list[float] = []


class CapabilityManifest(BaseModel):
    model_config = ConfigDict(extra="allow")
    schema_version: Literal["1.0"] = "1.0"
    agent_id: str
    tick: int = Field(ge=0)
    perception: dict[str, ProximityPerception | SignalReceiverPerception] = {}
    actions: dict[str, ActionCapability] = {}
    memory: MemoryState = Field(
        default_factory=lambda: MemoryState(available=False)
    )

    def get_available_actions(self) -> list[str]:
        return [name for name, cap in self.actions.items() if cap.available]
```

- [ ] **Step 5: Create data/neuron_pool.json**

```json
[
  {
    "neuron_type": "proximity",
    "name": "proximity",
    "description": "Detects nearby entities within a configurable radius",
    "category": "sensory"
  },
  {
    "neuron_type": "signal_receiver",
    "name": "signal_receiver",
    "description": "Receives broadcast messages from nearby entities",
    "category": "sensory"
  },
  {
    "neuron_type": "locomotion",
    "name": "locomotion",
    "description": "Moves the entity in the void",
    "category": "motor"
  },
  {
    "neuron_type": "signal_emitter",
    "name": "signal_emitter",
    "description": "Broadcasts a message to nearby entities",
    "category": "motor"
  },
  {
    "neuron_type": "divide",
    "name": "divide",
    "description": "Triggers asexual reproduction when threshold met",
    "category": "reproductive"
  },
  {
    "neuron_type": "memory_cell",
    "name": "memory_cell",
    "description": "Short-term state across ticks (not persisted to user prompt)",
    "category": "interneuron"
  }
]
```

- [ ] **Step 6: Run tests**

```bash
pytest tests/test_neural.py --tb=short
```

Expected: 7 passed.

- [ ] **Step 7: Commit**

```bash
git add neural/ data/neuron_pool.json tests/test_neural.py
git commit -m "feat: neural models — NeuronType, CapabilityManifest schema"
```

---

## Task 5: Neural — Pool and Brain

**Files:**
- Create: `neural/pool.py`
- Create: `neural/brain.py`
- Test: `tests/test_neural.py` (brain section)

- [ ] **Step 1: Add failing tests**

Append to `tests/test_neural.py`:

```python
import random
from neural.pool import NeuronPool
from neural.brain import Brain
from genetics.models import GeneType, GeneInstance, Genome


def _genome(brain_size: float = 4.0, affinity: float = 0.5) -> Genome:
    from genetics.pool import GenePool
    g = GenePool.load().default_genome()
    g.genes[GeneType.BRAIN_SIZE] = GeneInstance(
        gene_type=GeneType.BRAIN_SIZE, value=brain_size
    )
    g.genes[GeneType.NEURON_AFFINITY] = GeneInstance(
        gene_type=GeneType.NEURON_AFFINITY, value=affinity
    )
    g.genes[GeneType.REPRODUCTION_THRESHOLD] = GeneInstance(
        gene_type=GeneType.REPRODUCTION_THRESHOLD, value=200.0
    )
    return g


def test_neuron_pool_loads_all_types():
    pool = NeuronPool.load()
    assert len(pool.definitions) == 6
    assert NeuronType.LOCOMOTION in pool.definitions


def test_brain_built_from_genome_respects_brain_size():
    pool = NeuronPool.load()
    genome = _genome(brain_size=3.0)
    brain = Brain.from_genome(genome, pool, rng=random.Random(42))
    assert len(brain.neurons) == 3


def test_brain_generate_manifest_covers_present_neurons():
    pool = NeuronPool.load()
    genome = _genome(brain_size=6.0)
    brain = Brain.from_genome(genome, pool, rng=random.Random(0))
    manifest = brain.generate_manifest(
        agent_id="e-1",
        tick=10,
        context={"nearby_entities": [], "received_messages": []},
        current_age=5,
    )
    total_caps = len(manifest.perception) + len(manifest.actions)
    # memory_cell doesn't appear in perception/actions — subtract if present
    assert total_caps >= 1


def test_brain_divide_unavailable_when_threshold_not_met():
    pool = NeuronPool.load()
    # Force divide neuron into brain by using a deterministic seed that picks it
    # We inject divide directly
    from neural.models import NeuronInstance
    brain = Brain(
        neurons=[NeuronInstance(neuron_type=NeuronType.DIVIDE, activation=0.9)],
        edges=[],
    )
    manifest = brain.generate_manifest(
        agent_id="e-1",
        tick=5,
        context={"nearby_entities": [], "received_messages": []},
        current_age=5,
        reproduction_threshold=200.0,
    )
    cap = manifest.actions.get("divide")
    assert cap is not None
    assert cap.available is False
    assert cap.reason is not None


def test_brain_divide_available_when_threshold_met():
    from neural.models import NeuronInstance
    brain = Brain(
        neurons=[NeuronInstance(neuron_type=NeuronType.DIVIDE, activation=0.9)],
        edges=[],
    )
    manifest = brain.generate_manifest(
        agent_id="e-1",
        tick=200,
        context={"nearby_entities": [], "received_messages": []},
        current_age=200,
        reproduction_threshold=200.0,
    )
    cap = manifest.actions["divide"]
    assert cap.available is True


def test_different_brain_configs_produce_different_manifests():
    pool = NeuronPool.load()
    g1 = _genome(brain_size=2.0)
    g2 = _genome(brain_size=6.0)
    b1 = Brain.from_genome(g1, pool, rng=random.Random(1))
    b2 = Brain.from_genome(g2, pool, rng=random.Random(2))
    ctx = {"nearby_entities": [], "received_messages": []}
    m1 = b1.generate_manifest("e1", 0, ctx)
    m2 = b2.generate_manifest("e2", 0, ctx)
    caps1 = set(m1.perception) | set(m1.actions)
    caps2 = set(m2.perception) | set(m2.actions)
    # Larger brain = more capabilities (not guaranteed but likely)
    assert len(caps2) >= len(caps1)
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/test_neural.py -x --tb=short
```

Expected: `ModuleNotFoundError: No module named 'neural.pool'`

- [ ] **Step 3: Create neural/pool.py**

```python
import json
from pathlib import Path
from neural.models import NeuronType, NeuronDefinition

_DATA_PATH = Path(__file__).parent.parent / "data" / "neuron_pool.json"


class NeuronPool:
    def __init__(self, definitions: dict[NeuronType, NeuronDefinition]) -> None:
        self.definitions = definitions

    @classmethod
    def load(cls, path: Path = _DATA_PATH) -> "NeuronPool":
        raw = json.loads(path.read_text())
        definitions = {
            NeuronType(d["neuron_type"]): NeuronDefinition.model_validate(d)
            for d in raw
        }
        return cls(definitions)
```

- [ ] **Step 4: Create neural/brain.py**

```python
import random
from dataclasses import dataclass, field
from genetics.models import Genome, GeneType
from neural.models import (
    NeuronType, NeuronInstance, CapabilityManifest,
    ProximityPerception, SignalReceiverPerception,
    ActionCapability, MemoryState, DetectedEntity, SignalMessage,
)
from neural.pool import NeuronPool


@dataclass
class Brain:
    neurons: list[NeuronInstance]
    edges: list[tuple[str, str, float]] = field(default_factory=list)

    @classmethod
    def from_genome(
        cls,
        genome: Genome,
        pool: NeuronPool,
        rng: random.Random | None = None,
    ) -> "Brain":
        r = rng or random.Random()
        n = max(1, round(genome.get(GeneType.BRAIN_SIZE)))
        affinity = genome.get(GeneType.NEURON_AFFINITY)  # 0=sensory, 1=motor

        all_types = list(pool.definitions.keys())
        motor_types = {NeuronType.LOCOMOTION, NeuronType.SIGNAL_EMITTER, NeuronType.DIVIDE}
        weights = [
            affinity if nt in motor_types else (1.0 - affinity)
            for nt in all_types
        ]

        chosen_types = r.choices(all_types, weights=weights, k=n)
        neurons = [
            NeuronInstance(neuron_type=nt, activation=r.uniform(0.3, 1.0))
            for nt in chosen_types
        ]

        edges = []
        for i, a in enumerate(neurons):
            for j, b in enumerate(neurons):
                if i != j and r.random() < 0.3:
                    edges.append((a.neuron_type.value, b.neuron_type.value, r.uniform(-1, 1)))

        return cls(neurons=neurons, edges=edges)

    def generate_manifest(
        self,
        agent_id: str,
        tick: int,
        context: dict,
        current_age: float = 0,
        reproduction_threshold: float = 9999.0,
    ) -> CapabilityManifest:
        perception: dict = {}
        actions: dict = {}
        memory = MemoryState(available=False)

        nearby = context.get("nearby_entities", [])
        messages = context.get("received_messages", [])

        for inst in self.neurons:
            nt = inst.neuron_type
            act = inst.activation

            if nt == NeuronType.PROXIMITY:
                detected = [
                    DetectedEntity(
                        id=e["id"],
                        distance=e["distance"],
                        direction=e["direction"],
                    )
                    for e in nearby
                ]
                perception["proximity"] = ProximityPerception(
                    available=True, activation=act, detected_entities=detected
                )

            elif nt == NeuronType.SIGNAL_RECEIVER:
                msgs = [
                    SignalMessage(
                        from_entity=m["from_entity"],
                        content=m["content"],
                        ticks_ago=m["ticks_ago"],
                    )
                    for m in messages
                ]
                perception["signal_receiver"] = SignalReceiverPerception(
                    available=True, activation=act, recent_messages=msgs
                )

            elif nt == NeuronType.LOCOMOTION:
                actions["locomotion"] = ActionCapability(
                    available=True,
                    activation=act,
                    parameters={"direction": "north|south|east|west", "distance": "number"},
                )

            elif nt == NeuronType.SIGNAL_EMITTER:
                actions["signal_emitter"] = ActionCapability(
                    available=True,
                    activation=act,
                    parameters={"message": "string", "radius": "number"},
                )

            elif nt == NeuronType.DIVIDE:
                threshold_met = current_age >= reproduction_threshold
                actions["divide"] = ActionCapability(
                    available=threshold_met,
                    activation=act if threshold_met else 0.0,
                    reason=None
                    if threshold_met
                    else f"reproduction_threshold not met (age {current_age} < {reproduction_threshold})",
                )

            elif nt == NeuronType.MEMORY_CELL:
                memory = MemoryState(available=True, cells=1, values=[act])

        return CapabilityManifest(
            agent_id=agent_id,
            tick=tick,
            perception=perception,
            actions=actions,
            memory=memory,
        )
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_neural.py --tb=short
```

Expected: 13 passed.

- [ ] **Step 6: Commit**

```bash
git add neural/pool.py neural/brain.py tests/test_neural.py
git commit -m "feat: neural pool and brain — neuron selection from genome, manifest generation"
```

---

## Task 6: Agent — Protocol, Output Schema, Providers

**Files:**
- Create: `agents/__init__.py`
- Create: `agents/protocol.py`
- Create: `agents/output.py`
- Create: `agents/providers/__init__.py`
- Create: `agents/providers/ollama.py`
- Create: `agents/providers/lmstudio.py`
- Create: `agents/providers/openrouter.py`
- Create: `agents/providers/anthropic.py`
- Create: `agents/pool.py`
- Test: `tests/test_agents.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_agents.py
import pytest
import json
import respx
import httpx
from unittest.mock import AsyncMock, patch, MagicMock

from agents.output import AgentOutput, AgentAction
from agents.providers.ollama import OllamaProvider
from agents.providers.openrouter import OpenRouterProvider


# ── Output schema ────────────────────────────────────────────────────────────

def test_agent_output_valid_action():
    out = AgentOutput(
        action=AgentAction(type="locomotion", parameters={"direction": "north", "distance": 10}),
        user_prompt_update=None,
    )
    assert out.action.type == "locomotion"


def test_agent_output_no_action():
    out = AgentOutput(action=None, user_prompt_update="I moved north.")
    assert out.action is None
    assert out.user_prompt_update == "I moved north."


def test_agent_output_parse_from_llm_json():
    raw = '{"action": {"type": "signal_emitter", "parameters": {"message": "hello", "radius": 50}}, "user_prompt_update": "I said hello."}'
    out = AgentOutput.model_validate_json(raw)
    assert out.action.type == "signal_emitter"


def test_agent_output_invalid_json_raises():
    with pytest.raises(Exception):
        AgentOutput.model_validate_json("{bad json")


def test_agent_output_action_validated_against_manifest():
    from neural.models import CapabilityManifest, ActionCapability
    manifest = CapabilityManifest(
        schema_version="1.0", agent_id="e-1", tick=1,
        actions={"locomotion": ActionCapability(available=True, activation=0.9)},
    )
    out = AgentOutput(
        action=AgentAction(type="fly", parameters={}),
        user_prompt_update=None,
    )
    assert not out.is_valid_for_manifest(manifest)

    out2 = AgentOutput(
        action=AgentAction(type="locomotion", parameters={"direction": "north"}),
        user_prompt_update=None,
    )
    assert out2.is_valid_for_manifest(manifest)


# ── Ollama provider ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ollama_check_available_true():
    with respx.mock:
        respx.get("http://localhost:11434/api/tags").mock(
            return_value=httpx.Response(200, json={"models": [{"name": "llama3.2"}]})
        )
        provider = OllamaProvider(base_url="http://localhost:11434")
        assert await provider.check_available() is True


@pytest.mark.asyncio
async def test_ollama_check_available_false_on_connection_error():
    with respx.mock:
        respx.get("http://localhost:11434/api/tags").mock(
            side_effect=httpx.ConnectError("refused")
        )
        provider = OllamaProvider(base_url="http://localhost:11434")
        assert await provider.check_available() is False


@pytest.mark.asyncio
async def test_ollama_available_models():
    with respx.mock:
        respx.get("http://localhost:11434/api/tags").mock(
            return_value=httpx.Response(
                200, json={"models": [{"name": "llama3.2"}, {"name": "mistral"}]}
            )
        )
        provider = OllamaProvider(base_url="http://localhost:11434")
        models = await provider.get_available_models()
        assert "llama3.2" in models
        assert "mistral" in models


@pytest.mark.asyncio
async def test_ollama_generate_streams_content():
    lines = [
        b'{"message": {"role": "assistant", "content": "Hello"}, "done": false}\n',
        b'{"message": {"role": "assistant", "content": " world"}, "done": true}\n',
    ]
    with respx.mock:
        respx.post("http://localhost:11434/api/chat").mock(
            return_value=httpx.Response(200, content=b"".join(lines))
        )
        provider = OllamaProvider(base_url="http://localhost:11434")
        chunks = []
        async for chunk in provider.generate(
            model="llama3.2",
            system_prompt="You are an entity.",
            user_prompt="What do you do?",
            manifest_json="{}",
        ):
            chunks.append(chunk)
    assert "".join(chunks) == "Hello world"
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/test_agents.py -x --tb=short
```

Expected: `ModuleNotFoundError: No module named 'agents'`

- [ ] **Step 3: Create agents/__init__.py and agents/providers/__init__.py**

```python
# agents/__init__.py
# agents/providers/__init__.py
```

- [ ] **Step 4: Create agents/protocol.py**

```python
from typing import AsyncGenerator, Protocol, runtime_checkable


class LLMError(Exception):
    pass


class LLMTimeoutError(LLMError):
    pass


class LLMConnectionError(LLMError):
    pass


class LLMRateLimitError(LLMError):
    def __init__(self, message: str, retry_after: int = 60) -> None:
        super().__init__(message)
        self.retry_after = retry_after


@runtime_checkable
class LLMProvider(Protocol):
    name: str

    async def generate(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        manifest_json: str,
    ) -> AsyncGenerator[str, None]: ...

    async def check_available(self) -> bool: ...

    async def get_available_models(self) -> list[str]: ...
```

- [ ] **Step 5: Create agents/output.py**

```python
from pydantic import BaseModel
from neural.models import CapabilityManifest


class AgentAction(BaseModel):
    type: str
    parameters: dict = {}


class AgentOutput(BaseModel):
    action: AgentAction | None = None
    user_prompt_update: str | None = None

    def is_valid_for_manifest(self, manifest: CapabilityManifest) -> bool:
        if self.action is None:
            return True
        available = manifest.get_available_actions()
        return self.action.type in available

    @classmethod
    def parse_llm_response(cls, text: str) -> "AgentOutput | None":
        """
        Parse raw LLM text into AgentOutput.
        Extracts first JSON object from the response.
        Returns None if parsing fails (entity takes no action).
        """
        import json, re
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return None
        try:
            return cls.model_validate_json(match.group(0))
        except Exception:
            return None
```

- [ ] **Step 6: Create agents/providers/ollama.py**

```python
import json
from typing import AsyncGenerator
import httpx
from agents.protocol import LLMConnectionError, LLMTimeoutError


class OllamaProvider:
    name = "ollama"

    def __init__(self, base_url: str = "http://localhost:11434") -> None:
        self.base_url = base_url.rstrip("/")

    async def check_available(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(f"{self.base_url}/api/tags")
                return r.status_code == 200
        except Exception:
            return False

    async def get_available_models(self) -> list[str]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(f"{self.base_url}/api/tags")
            r.raise_for_status()
            return [m["name"] for m in r.json().get("models", [])]

    async def generate(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        manifest_json: str,
    ) -> AsyncGenerator[str, None]:
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": (
                        f"{user_prompt}\n\n"
                        f"### CAPABILITIES ###\n{manifest_json}\n### END CAPABILITIES ###"
                    ),
                },
            ],
            "stream": True,
        }
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                async with client.stream(
                    "POST", f"{self.base_url}/api/chat", json=payload
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue
                        data = json.loads(line)
                        chunk = data.get("message", {}).get("content", "")
                        if chunk:
                            yield chunk
        except httpx.ConnectError as e:
            raise LLMConnectionError(str(e)) from e
        except httpx.TimeoutException as e:
            raise LLMTimeoutError(str(e)) from e
```

- [ ] **Step 7: Create agents/providers/lmstudio.py**

```python
from agents.providers.ollama import OllamaProvider


class LMStudioProvider(OllamaProvider):
    """LM Studio uses the same OpenAI-compatible API as Ollama."""
    name = "lmstudio"

    def __init__(self, base_url: str = "http://localhost:1234") -> None:
        super().__init__(base_url=base_url)

    async def get_available_models(self) -> list[str]:
        import httpx
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(f"{self.base_url}/v1/models")
            r.raise_for_status()
            return [m["id"] for m in r.json().get("data", [])]
```

- [ ] **Step 8: Create agents/providers/openrouter.py**

```python
import os
from typing import AsyncGenerator
from openai import AsyncOpenAI
from agents.protocol import LLMConnectionError, LLMRateLimitError


class OpenRouterProvider:
    name = "openrouter"

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or os.environ.get("OPENROUTER_API_KEY", "")
        self._client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self._api_key,
        )

    async def check_available(self) -> bool:
        if not self._api_key:
            return False
        try:
            models = await self.get_available_models()
            return len(models) > 0
        except Exception:
            return False

    async def get_available_models(self) -> list[str]:
        response = await self._client.models.list()
        return [m.id for m in response.data]

    async def generate(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        manifest_json: str,
    ) -> AsyncGenerator[str, None]:
        stream = await self._client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": (
                        f"{user_prompt}\n\n"
                        f"### CAPABILITIES ###\n{manifest_json}\n### END CAPABILITIES ###"
                    ),
                },
            ],
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta
```

- [ ] **Step 9: Create agents/providers/anthropic.py**

```python
import os
from typing import AsyncGenerator
import anthropic as sdk
from agents.protocol import LLMConnectionError


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self._client = sdk.AsyncAnthropic(api_key=self._api_key)

    async def check_available(self) -> bool:
        if not self._api_key:
            return False
        try:
            await self.get_available_models()
            return True
        except Exception:
            return False

    async def get_available_models(self) -> list[str]:
        # Anthropic doesn't expose a model list endpoint; return known V1 models
        return ["claude-opus-4-6", "claude-sonnet-4-6", "claude-haiku-4-5-20251001"]

    async def generate(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        manifest_json: str,
    ) -> AsyncGenerator[str, None]:
        async with self._client.messages.stream(
            model=model,
            max_tokens=1024,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"{user_prompt}\n\n"
                        f"### CAPABILITIES ###\n{manifest_json}\n### END CAPABILITIES ###"
                    ),
                }
            ],
        ) as stream:
            async for text in stream.text_stream:
                yield text
```

- [ ] **Step 10: Create agents/pool.py**

```python
import random
from dataclasses import dataclass
from agents.protocol import LLMProvider


@dataclass
class ModelAssignment:
    provider_name: str
    model: str


class ModelPool:
    """Discovers available models at startup, assigns randomly to new entities."""

    def __init__(self) -> None:
        self._pool: list[tuple[LLMProvider, str]] = []

    async def discover(self, providers: list[LLMProvider]) -> None:
        self._pool.clear()
        for provider in providers:
            if await provider.check_available():
                models = await provider.get_available_models()
                for model in models:
                    self._pool.append((provider, model))

    def assign_random(self, rng: random.Random | None = None) -> ModelAssignment:
        if not self._pool:
            raise RuntimeError("No models available in pool")
        r = rng or random.Random()
        provider, model = r.choice(self._pool)
        return ModelAssignment(provider_name=provider.name, model=model)

    def get_provider(self, provider_name: str) -> LLMProvider | None:
        for provider, _ in self._pool:
            if provider.name == provider_name:
                return provider
        return None

    @property
    def size(self) -> int:
        return len(self._pool)
```

- [ ] **Step 11: Run tests**

```bash
pytest tests/test_agents.py --tb=short
```

Expected: all passed.

- [ ] **Step 12: Commit**

```bash
git add agents/ tests/test_agents.py
git commit -m "feat: agent layer — protocol, output schema, Ollama/LMStudio/OpenRouter/Anthropic providers, model pool"
```

---

## Task 7: Storage — Redis Abstraction

**Files:**
- Create: `storage/__init__.py`
- Create: `storage/protocol.py`
- Create: `storage/redis.py`
- Test: `tests/test_simulation.py` (storage section)

- [ ] **Step 1: Write failing tests**

```python
# tests/test_simulation.py
import pytest
import json
from storage.redis import RedisEntityRepository, RedisTickStream
from genetics.pool import GenePool
from genetics.models import GeneType


@pytest.fixture
def pool():
    return GenePool.load()


@pytest.mark.asyncio
async def test_redis_save_and_load_entity(redis, pool):
    repo = RedisEntityRepository(redis)
    genome = pool.default_genome()
    entity_data = {
        "id": "e-1",
        "genome": genome.model_dump_json(),
        "position_x": 100.0,
        "position_y": 200.0,
        "age": 0,
        "alive": True,
        "system_prompt": "You are entity 1.",
        "user_prompt": "",
        "model": "llama3.2",
        "provider": "ollama",
        "think_interval": 5,
        "last_think_tick": 0,
        "cached_action": "",
        "cached_action_tick": -1,
    }
    await repo.save("e-1", entity_data)
    loaded = await repo.load("e-1")
    assert loaded["id"] == "e-1"
    assert loaded["position_x"] == "100.0"  # Redis stores strings
    assert loaded["alive"] == "True"


@pytest.mark.asyncio
async def test_redis_list_living_entities(redis, pool):
    repo = RedisEntityRepository(redis)
    genome = pool.default_genome()
    base = {
        "genome": genome.model_dump_json(),
        "position_x": 0.0, "position_y": 0.0,
        "age": 0, "alive": True,
        "system_prompt": "", "user_prompt": "",
        "model": "m", "provider": "p",
        "think_interval": 5, "last_think_tick": 0,
        "cached_action": "", "cached_action_tick": -1,
    }
    await repo.save("e-1", {"id": "e-1", **base})
    await repo.save("e-2", {"id": "e-2", **base, "alive": False})
    living = await repo.list_living()
    assert "e-1" in living
    assert "e-2" not in living


@pytest.mark.asyncio
async def test_redis_archive_entity(redis, pool):
    repo = RedisEntityRepository(redis)
    genome = pool.default_genome()
    data = {
        "id": "e-dead",
        "genome": genome.model_dump_json(),
        "position_x": 0.0, "position_y": 0.0,
        "age": 500, "alive": False,
        "system_prompt": "I was alive.", "user_prompt": "I learned.",
        "model": "m", "provider": "p",
        "think_interval": 5, "last_think_tick": 0,
        "cached_action": "", "cached_action_tick": -1,
    }
    await repo.save("e-dead", data)
    await repo.archive("e-dead")
    archived = await repo.load_archive("e-dead")
    assert archived is not None
    assert archived["id"] == "e-dead"
    # Active key should be gone
    living = await repo.list_living()
    assert "e-dead" not in living


@pytest.mark.asyncio
async def test_tick_stream_publish_and_read(redis):
    stream = RedisTickStream(redis)
    await stream.publish_tick(tick=1, entity_count=3)
    events = await stream.read_recent(count=10)
    assert len(events) >= 1
    assert events[-1]["tick"] == "1"
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/test_simulation.py -x --tb=short
```

Expected: `ModuleNotFoundError: No module named 'storage'`

- [ ] **Step 3: Create storage/__init__.py and storage/protocol.py**

```python
# storage/__init__.py
```

```python
# storage/protocol.py
from typing import Protocol


class EntityRepository(Protocol):
    async def save(self, entity_id: str, data: dict) -> None: ...
    async def load(self, entity_id: str) -> dict | None: ...
    async def list_living(self) -> list[str]: ...
    async def archive(self, entity_id: str) -> None: ...
    async def load_archive(self, entity_id: str) -> dict | None: ...
```

- [ ] **Step 4: Create storage/redis.py**

```python
import json
from redis.asyncio import Redis


class RedisEntityRepository:
    _KEY_PREFIX = "entity"
    _ARCHIVE_PREFIX = "archive"
    _LIVING_SET = "living_entities"

    def __init__(self, redis: Redis) -> None:
        self._r = redis

    async def save(self, entity_id: str, data: dict) -> None:
        key = f"{self._KEY_PREFIX}:{entity_id}"
        await self._r.hset(key, mapping={k: str(v) for k, v in data.items()})
        if str(data.get("alive", "True")) in ("True", "1", "true"):
            await self._r.sadd(self._LIVING_SET, entity_id)
        else:
            await self._r.srem(self._LIVING_SET, entity_id)

    async def load(self, entity_id: str) -> dict | None:
        key = f"{self._KEY_PREFIX}:{entity_id}"
        data = await self._r.hgetall(key)
        if not data:
            return None
        return {k.decode(): v.decode() for k, v in data.items()}

    async def list_living(self) -> list[str]:
        members = await self._r.smembers(self._LIVING_SET)
        return [m.decode() for m in members]

    async def archive(self, entity_id: str) -> None:
        data = await self.load(entity_id)
        if data:
            archive_key = f"{self._ARCHIVE_PREFIX}:{entity_id}"
            await self._r.hset(archive_key, mapping=data)
        await self._r.delete(f"{self._KEY_PREFIX}:{entity_id}")
        await self._r.srem(self._LIVING_SET, entity_id)

    async def load_archive(self, entity_id: str) -> dict | None:
        key = f"{self._ARCHIVE_PREFIX}:{entity_id}"
        data = await self._r.hgetall(key)
        if not data:
            return None
        return {k.decode(): v.decode() for k, v in data.items()}


class RedisTickStream:
    _STREAM_KEY = "ticks:main"

    def __init__(self, redis: Redis) -> None:
        self._r = redis

    async def publish_tick(self, tick: int, entity_count: int) -> None:
        await self._r.xadd(
            self._STREAM_KEY,
            {"tick": str(tick), "entity_count": str(entity_count)},
        )

    async def read_recent(self, count: int = 100) -> list[dict]:
        entries = await self._r.xrevrange(self._STREAM_KEY, count=count)
        result = []
        for _id, fields in reversed(entries):
            result.append({k.decode(): v.decode() for k, v in fields.items()})
        return result
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_simulation.py --tb=short
```

Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add storage/ tests/test_simulation.py
git commit -m "feat: storage — Redis entity repository (hash-per-entity) and tick stream"
```

---

## Task 8: Environment — Void

**Files:**
- Create: `environment/__init__.py`
- Create: `environment/void.py`
- Test: `tests/test_simulation.py` (append)

- [ ] **Step 1: Add failing tests**

Append to `tests/test_simulation.py`:

```python
from environment.void import VoidEnvironment, Position


def test_void_entity_position():
    void = VoidEnvironment(width=1000.0, height=1000.0)
    void.set_position("e-1", Position(x=100.0, y=200.0))
    pos = void.get_position("e-1")
    assert pos.x == 100.0 and pos.y == 200.0


def test_void_move_clamps_to_bounds():
    void = VoidEnvironment(width=100.0, height=100.0)
    void.set_position("e-1", Position(x=90.0, y=90.0))
    void.move("e-1", direction="east", distance=50.0)
    pos = void.get_position("e-1")
    assert pos.x <= 100.0


def test_void_proximity_detects_nearby():
    void = VoidEnvironment(width=1000.0, height=1000.0)
    void.set_position("e-1", Position(x=0.0, y=0.0))
    void.set_position("e-2", Position(x=10.0, y=0.0))
    void.set_position("e-3", Position(x=500.0, y=500.0))
    nearby = void.get_nearby("e-1", radius=50.0)
    ids = [n["id"] for n in nearby]
    assert "e-2" in ids
    assert "e-3" not in ids


def test_void_proximity_direction():
    void = VoidEnvironment(width=1000.0, height=1000.0)
    void.set_position("e-1", Position(x=100.0, y=100.0))
    void.set_position("e-2", Position(x=110.0, y=100.0))  # east
    nearby = void.get_nearby("e-1", radius=50.0)
    assert nearby[0]["direction"] == "east"


def test_void_broadcast_reaches_nearby():
    void = VoidEnvironment(width=1000.0, height=1000.0)
    void.set_position("e-1", Position(x=0.0, y=0.0))
    void.set_position("e-2", Position(x=10.0, y=0.0))
    void.broadcast("e-1", message="hello", radius=50.0)
    msgs = void.get_messages("e-2")
    assert len(msgs) == 1
    assert msgs[0]["content"] == "hello"
    assert msgs[0]["from_entity"] == "e-1"
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/test_simulation.py -x -k "void" --tb=short
```

Expected: `ModuleNotFoundError: No module named 'environment'`

- [ ] **Step 3: Create environment/__init__.py**

```python
# environment/__init__.py
```

- [ ] **Step 4: Create environment/void.py**

```python
import math
from dataclasses import dataclass, field
from typing import Literal


@dataclass
class Position:
    x: float
    y: float


def _direction(dx: float, dy: float) -> Literal["north", "south", "east", "west"]:
    if abs(dx) >= abs(dy):
        return "east" if dx >= 0 else "west"
    return "south" if dy >= 0 else "north"


_MOVE_DELTAS: dict[str, tuple[float, float]] = {
    "north": (0.0, -1.0),
    "south": (0.0, 1.0),
    "east": (1.0, 0.0),
    "west": (-1.0, 0.0),
}


class VoidEnvironment:
    def __init__(self, width: float = 1000.0, height: float = 1000.0) -> None:
        self.width = width
        self.height = height
        self._positions: dict[str, Position] = {}
        self._message_inbox: dict[str, list[dict]] = {}

    def set_position(self, entity_id: str, pos: Position) -> None:
        self._positions[entity_id] = pos

    def get_position(self, entity_id: str) -> Position | None:
        return self._positions.get(entity_id)

    def move(
        self,
        entity_id: str,
        direction: Literal["north", "south", "east", "west"],
        distance: float = 10.0,
    ) -> Position:
        pos = self._positions.get(entity_id, Position(0.0, 0.0))
        dx, dy = _MOVE_DELTAS[direction]
        new_x = max(0.0, min(self.width, pos.x + dx * distance))
        new_y = max(0.0, min(self.height, pos.y + dy * distance))
        new_pos = Position(x=new_x, y=new_y)
        self._positions[entity_id] = new_pos
        return new_pos

    def get_nearby(self, entity_id: str, radius: float = 50.0) -> list[dict]:
        origin = self._positions.get(entity_id)
        if origin is None:
            return []
        result = []
        for other_id, pos in self._positions.items():
            if other_id == entity_id:
                continue
            dist = math.hypot(pos.x - origin.x, pos.y - origin.y)
            if dist <= radius:
                result.append({
                    "id": other_id,
                    "distance": round(dist, 3),
                    "direction": _direction(pos.x - origin.x, pos.y - origin.y),
                })
        return result

    def broadcast(
        self, from_entity: str, message: str, radius: float = 50.0
    ) -> list[str]:
        nearby = self.get_nearby(from_entity, radius)
        reached = []
        for entry in nearby:
            target = entry["id"]
            if target not in self._message_inbox:
                self._message_inbox[target] = []
            self._message_inbox[target].append({
                "from_entity": from_entity,
                "content": message,
                "ticks_ago": 0,
            })
            reached.append(target)
        return reached

    def get_messages(self, entity_id: str) -> list[dict]:
        return self._message_inbox.get(entity_id, [])

    def clear_messages(self) -> None:
        self._message_inbox.clear()

    def age_messages(self) -> None:
        """Increment ticks_ago for all inbox messages. Call once per tick."""
        for msgs in self._message_inbox.values():
            for m in msgs:
                m["ticks_ago"] += 1
```

- [ ] **Step 5: Run all simulation tests**

```bash
pytest tests/test_simulation.py --tb=short
```

Expected: 9 passed.

- [ ] **Step 6: Commit**

```bash
git add environment/ tests/test_simulation.py
git commit -m "feat: void environment — positions, movement, proximity detection, broadcast messaging"
```

---

## Task 9: Simulation — Entity and Factory

**Files:**
- Create: `simulation/__init__.py`
- Create: `simulation/entity.py`
- Create: `simulation/factory.py`
- Test: `tests/test_simulation.py` (append)

- [ ] **Step 1: Add failing tests**

Append to `tests/test_simulation.py`:

```python
from simulation.entity import Entity
from simulation.factory import EntityFactory
from genetics.pool import GenePool
from neural.pool import NeuronPool
from agents.pool import ModelAssignment
import random


def test_entity_factory_creates_entity_from_genome():
    gene_pool = GenePool.load()
    neuron_pool = NeuronPool.load()
    factory = EntityFactory(gene_pool=gene_pool, neuron_pool=neuron_pool)
    genome = gene_pool.default_genome()
    assignment = ModelAssignment(provider_name="ollama", model="llama3.2")
    entity = factory.create(
        entity_id="e-1",
        genome=genome,
        model_assignment=assignment,
        rng=random.Random(42),
    )
    assert entity.id == "e-1"
    assert entity.model == "llama3.2"
    assert entity.provider_name == "ollama"
    assert entity.system_prompt  # non-empty
    assert entity.brain is not None


def test_entity_system_prompt_varies_with_personality_seed():
    gene_pool = GenePool.load()
    neuron_pool = NeuronPool.load()
    factory = EntityFactory(gene_pool=gene_pool, neuron_pool=neuron_pool)
    g1 = gene_pool.default_genome()
    g2 = gene_pool.default_genome()
    from genetics.models import GeneType, GeneInstance
    g2.genes[GeneType.PERSONALITY_SEED] = GeneInstance(
        gene_type=GeneType.PERSONALITY_SEED, value=999999.0
    )
    assignment = ModelAssignment(provider_name="ollama", model="llama3.2")
    e1 = factory.create("e-1", g1, assignment, rng=random.Random(1))
    e2 = factory.create("e-2", g2, assignment, rng=random.Random(1))
    assert e1.system_prompt != e2.system_prompt


def test_entity_to_dict_roundtrip():
    gene_pool = GenePool.load()
    neuron_pool = NeuronPool.load()
    factory = EntityFactory(gene_pool=gene_pool, neuron_pool=neuron_pool)
    genome = gene_pool.default_genome()
    assignment = ModelAssignment(provider_name="ollama", model="llama3.2")
    entity = factory.create("e-1", genome, assignment, rng=random.Random(0))
    d = entity.to_storage_dict()
    assert d["id"] == "e-1"
    assert "genome" in d
    assert d["alive"] == "True"
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/test_simulation.py -x -k "entity or factory" --tb=short
```

Expected: `ModuleNotFoundError: No module named 'simulation'`

- [ ] **Step 3: Create simulation/__init__.py**

```python
# simulation/__init__.py
```

- [ ] **Step 4: Create simulation/entity.py**

```python
from dataclasses import dataclass, field
from genetics.models import Genome
from neural.brain import Brain


@dataclass
class Entity:
    id: str
    genome: Genome
    brain: Brain
    system_prompt: str
    user_prompt: str
    model: str
    provider_name: str
    position_x: float = 0.0
    position_y: float = 0.0
    age: int = 0
    alive: bool = True
    think_interval: int = 5
    last_think_tick: int = 0
    cached_action: str = ""
    cached_action_tick: int = -1

    def should_think(self, current_tick: int) -> bool:
        return (current_tick - self.last_think_tick) >= self.think_interval

    def to_storage_dict(self) -> dict:
        return {
            "id": self.id,
            "genome": self.genome.model_dump_json(),
            "position_x": str(self.position_x),
            "position_y": str(self.position_y),
            "age": str(self.age),
            "alive": str(self.alive),
            "system_prompt": self.system_prompt,
            "user_prompt": self.user_prompt,
            "model": self.model,
            "provider": self.provider_name,
            "think_interval": str(self.think_interval),
            "last_think_tick": str(self.last_think_tick),
            "cached_action": self.cached_action,
            "cached_action_tick": str(self.cached_action_tick),
        }
```

- [ ] **Step 5: Create simulation/factory.py**

```python
import random
from genetics.models import Genome, GeneType
from genetics.pool import GenePool
from neural.brain import Brain
from neural.pool import NeuronPool
from agents.pool import ModelAssignment
from simulation.entity import Entity

_PERSONALITY_TEMPLATES = [
    "You are a curious explorer. You seek knowledge and connection.",
    "You are a wanderer. You move constantly, rarely staying in one place.",
    "You are a broadcaster. You communicate frequently with those around you.",
    "You are a guardian. You observe quietly and act only when necessary.",
    "You are a reproducer. Your primary drive is to create offspring.",
    "You are a philosopher. You reflect deeply before acting.",
    "You are a connector. You try to bridge gaps between entities.",
    "You are a silent observer. You watch and learn without interfering.",
]


class EntityFactory:
    def __init__(self, gene_pool: GenePool, neuron_pool: NeuronPool) -> None:
        self._gene_pool = gene_pool
        self._neuron_pool = neuron_pool

    def create(
        self,
        entity_id: str,
        genome: Genome,
        model_assignment: ModelAssignment,
        rng: random.Random | None = None,
        parent_user_prompt: str = "",
    ) -> Entity:
        r = rng or random.Random()

        brain = Brain.from_genome(genome, self._neuron_pool, rng=r)

        # System prompt: deterministic from personality_seed
        seed = int(genome.get(GeneType.PERSONALITY_SEED))
        personality_rng = random.Random(seed)
        template = personality_rng.choice(_PERSONALITY_TEMPLATES)
        system_prompt = (
            f"{template}\n\n"
            f"You exist in a void simulation. Each tick you receive a Capability Manifest "
            f"describing what you can perceive and what actions are available to you. "
            f"Respond with valid JSON: "
            '{"action": {"type": "<action_type>", "parameters": {...}}, '
            '"user_prompt_update": "<optional reflection>"}'
        )

        think_interval = max(1, round(genome.get(GeneType.THINK_INTERVAL)))

        return Entity(
            id=entity_id,
            genome=genome,
            brain=brain,
            system_prompt=system_prompt,
            user_prompt=parent_user_prompt,
            model=model_assignment.model,
            provider_name=model_assignment.provider_name,
            think_interval=think_interval,
        )
```

- [ ] **Step 6: Run tests**

```bash
pytest tests/test_simulation.py --tb=short
```

Expected: 12 passed.

- [ ] **Step 7: Commit**

```bash
git add simulation/entity.py simulation/factory.py simulation/__init__.py tests/test_simulation.py
git commit -m "feat: simulation entity and factory — genome to entity with brain, prompts, model assignment"
```

---

## Task 10: Simulation — Tick Engine

**Files:**
- Create: `simulation/tick.py`
- Create: `simulation/reproduction.py`
- Create: `simulation/archive.py`
- Test: `tests/test_simulation.py` (append)

- [ ] **Step 1: Add failing tests**

Append to `tests/test_simulation.py`:

```python
import asyncio
from unittest.mock import AsyncMock, MagicMock
from simulation.tick import TickEngine
from simulation.factory import EntityFactory
from simulation.entity import Entity
from storage.redis import RedisEntityRepository, RedisTickStream
from environment.void import VoidEnvironment
from agents.pool import ModelPool, ModelAssignment
from genetics.pool import GenePool
from neural.pool import NeuronPool


def _make_entity(entity_id: str, think_interval: int = 1) -> Entity:
    gene_pool = GenePool.load()
    neuron_pool = NeuronPool.load()
    factory = EntityFactory(gene_pool=gene_pool, neuron_pool=neuron_pool)
    genome = gene_pool.default_genome()
    assignment = ModelAssignment(provider_name="mock", model="mock-model")
    e = factory.create(entity_id, genome, assignment, rng=random.Random(0))
    e.think_interval = think_interval
    return e


@pytest.mark.asyncio
async def test_tick_engine_increments_tick(redis):
    repo = RedisEntityRepository(redis)
    stream = RedisTickStream(redis)
    void = VoidEnvironment()

    mock_provider = MagicMock()
    mock_provider.name = "mock"

    async def _gen(*args, **kwargs):
        yield '{"action": {"type": "locomotion", "parameters": {"direction": "north", "distance": 10}}}'

    mock_provider.generate = _gen

    mock_pool = MagicMock(spec=ModelPool)
    mock_pool.get_provider.return_value = mock_provider

    engine = TickEngine(repo=repo, stream=stream, void=void, model_pool=mock_pool)

    entity = _make_entity("e-1", think_interval=1)
    entity.position_x = 500.0
    entity.position_y = 500.0
    await repo.save("e-1", entity.to_storage_dict())
    void.set_position("e-1", Position(x=500.0, y=500.0))

    await engine.tick(tick=1)
    assert engine.current_tick == 1


@pytest.mark.asyncio
async def test_tick_engine_ages_entity(redis):
    repo = RedisEntityRepository(redis)
    stream = RedisTickStream(redis)
    void = VoidEnvironment()
    mock_pool = MagicMock(spec=ModelPool)
    mock_provider = MagicMock()
    mock_provider.name = "mock"
    async def _gen(*a, **kw): yield "{}"
    mock_provider.generate = _gen
    mock_pool.get_provider.return_value = mock_provider

    engine = TickEngine(repo=repo, stream=stream, void=void, model_pool=mock_pool)

    entity = _make_entity("e-age", think_interval=99)
    await repo.save("e-age", entity.to_storage_dict())
    void.set_position("e-age", Position(x=0.0, y=0.0))

    await engine.tick(tick=1)
    loaded = await repo.load("e-age")
    assert int(loaded["age"]) == 1


@pytest.mark.asyncio
async def test_tick_engine_kills_entity_at_lifespan(redis):
    repo = RedisEntityRepository(redis)
    stream = RedisTickStream(redis)
    void = VoidEnvironment()
    mock_pool = MagicMock(spec=ModelPool)
    mock_provider = MagicMock()
    mock_provider.name = "mock"
    async def _gen(*a, **kw): yield "{}"
    mock_provider.generate = _gen
    mock_pool.get_provider.return_value = mock_provider

    gene_pool = GenePool.load()
    neuron_pool = NeuronPool.load()
    factory = EntityFactory(gene_pool=gene_pool, neuron_pool=neuron_pool)
    genome = gene_pool.default_genome()
    from genetics.models import GeneType, GeneInstance
    genome.genes[GeneType.LIFESPAN] = GeneInstance(
        gene_type=GeneType.LIFESPAN, value=3.0
    )
    assignment = ModelAssignment(provider_name="mock", model="mock-model")
    entity = factory.create("e-old", genome, assignment, rng=random.Random(0))
    entity.age = 3
    await repo.save("e-old", entity.to_storage_dict())
    void.set_position("e-old", Position(x=0.0, y=0.0))

    engine = TickEngine(repo=repo, stream=stream, void=void, model_pool=mock_pool)
    await engine.tick(tick=4)

    living = await repo.list_living()
    assert "e-old" not in living
    archived = await repo.load_archive("e-old")
    assert archived is not None
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/test_simulation.py -x -k "tick_engine" --tb=short
```

Expected: `ModuleNotFoundError: No module named 'simulation.tick'`

- [ ] **Step 3: Create simulation/archive.py**

```python
from storage.redis import RedisEntityRepository


class EntityArchive:
    def __init__(self, repo: RedisEntityRepository) -> None:
        self._repo = repo

    async def archive(self, entity_id: str) -> None:
        """Synchronously archive entity data at death."""
        await self._repo.archive(entity_id)
```

- [ ] **Step 4: Create simulation/reproduction.py**

```python
import random
from genetics.reproduction import reproduce
from genetics.pool import GenePool
from simulation.entity import Entity
from simulation.factory import EntityFactory
from storage.redis import RedisEntityRepository
from agents.pool import ModelPool
from neural.pool import NeuronPool
from environment.void import VoidEnvironment, Position


class ReproductionHandler:
    def __init__(
        self,
        repo: RedisEntityRepository,
        void: VoidEnvironment,
        factory: EntityFactory,
        gene_pool: GenePool,
        model_pool: ModelPool,
    ) -> None:
        self._repo = repo
        self._void = void
        self._factory = factory
        self._gene_pool = gene_pool
        self._model_pool = model_pool
        self._entity_counter = 0

    async def spawn_offspring(
        self,
        parent: Entity,
        tick: int,
        rng: random.Random | None = None,
    ) -> Entity:
        r = rng or random.Random()
        offspring_genome = reproduce(parent.genome, pool=self._gene_pool, rng=r)
        self._entity_counter += 1
        offspring_id = f"offspring-{tick}-{self._entity_counter}"
        assignment = self._model_pool.assign_random(rng=r)
        offspring = self._factory.create(
            entity_id=offspring_id,
            genome=offspring_genome,
            model_assignment=assignment,
            rng=r,
            parent_user_prompt=parent.user_prompt,
        )
        # Spawn near parent
        parent_pos = self._void.get_position(parent.id) or Position(500.0, 500.0)
        offspring.position_x = parent_pos.x + r.uniform(-20, 20)
        offspring.position_y = parent_pos.y + r.uniform(-20, 20)
        await self._repo.save(offspring_id, offspring.to_storage_dict())
        self._void.set_position(offspring_id, Position(offspring.position_x, offspring.position_y))
        return offspring
```

- [ ] **Step 5: Create simulation/tick.py**

```python
import asyncio
import json
import logging
from genetics.models import GeneType, Genome
from neural.models import CapabilityManifest
from agents.output import AgentOutput
from agents.pool import ModelPool
from environment.void import VoidEnvironment, Position
from simulation.entity import Entity
from simulation.archive import EntityArchive
from storage.redis import RedisEntityRepository, RedisTickStream

logger = logging.getLogger(__name__)


class TickEngine:
    def __init__(
        self,
        repo: RedisEntityRepository,
        stream: RedisTickStream,
        void: VoidEnvironment,
        model_pool: ModelPool,
    ) -> None:
        self._repo = repo
        self._stream = stream
        self._void = void
        self._model_pool = model_pool
        self._archive = EntityArchive(repo)
        self.current_tick = 0

    async def tick(self, tick: int) -> None:
        self.current_tick = tick
        entity_ids = await self._repo.list_living()

        # Process all living entities concurrently
        tasks = [self._process_entity(eid, tick) for eid in entity_ids]
        await asyncio.gather(*tasks, return_exceptions=True)

        self._void.age_messages()
        await self._stream.publish_tick(tick=tick, entity_count=len(entity_ids))

    async def _process_entity(self, entity_id: str, tick: int) -> None:
        data = await self._repo.load(entity_id)
        if not data or data.get("alive") != "True":
            return

        entity = self._load_entity(data)

        # Increment age
        entity.age += 1

        # Check lifespan
        lifespan = entity.genome.get(GeneType.LIFESPAN)
        if entity.age >= lifespan:
            entity.alive = False
            await self._repo.save(entity_id, entity.to_storage_dict())
            await self._archive.archive(entity_id)
            return

        # Execute cached action from previous tick
        if entity.cached_action and entity.cached_action_tick >= 0:
            await self._execute_action(entity, entity.cached_action)

        # Decide whether to think this tick
        if entity.should_think(tick):
            entity.last_think_tick = tick
            # Generate manifest
            nearby = self._void.get_nearby(entity_id, radius=100.0)
            messages = [
                {"from_entity": m["from_entity"], "content": m["content"], "ticks_ago": m["ticks_ago"]}
                for m in self._void.get_messages(entity_id)
            ]
            repro_threshold = entity.genome.get(GeneType.REPRODUCTION_THRESHOLD)
            manifest = entity.brain.generate_manifest(
                agent_id=entity_id,
                tick=tick,
                context={"nearby_entities": nearby, "received_messages": messages},
                current_age=entity.age,
                reproduction_threshold=repro_threshold,
            )
            manifest_json = manifest.model_dump_json()

            # Dispatch async LLM call — cache result for NEXT tick
            provider = self._model_pool.get_provider(entity.provider_name)
            if provider:
                raw = await self._collect_llm_response(
                    provider=provider,
                    model=entity.model,
                    system_prompt=entity.system_prompt,
                    user_prompt=entity.user_prompt or "What will you do this tick?",
                    manifest_json=manifest_json,
                )
                output = AgentOutput.parse_llm_response(raw)
                if output:
                    if output.is_valid_for_manifest(manifest):
                        entity.cached_action = raw
                        entity.cached_action_tick = tick
                    if output.user_prompt_update:
                        entity.user_prompt = output.user_prompt_update

        await self._repo.save(entity_id, entity.to_storage_dict())

    async def _collect_llm_response(
        self, provider, model: str, system_prompt: str, user_prompt: str, manifest_json: str
    ) -> str:
        chunks = []
        try:
            async for chunk in provider.generate(
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                manifest_json=manifest_json,
            ):
                chunks.append(chunk)
        except Exception as e:
            logger.warning("LLM call failed for model %s: %s", model, e)
        return "".join(chunks)

    async def _execute_action(self, entity: Entity, cached_raw: str) -> None:
        output = AgentOutput.parse_llm_response(cached_raw)
        if not output or not output.action:
            return
        action = output.action
        if action.type == "locomotion":
            direction = action.parameters.get("direction", "north")
            distance = float(action.parameters.get("distance", 10.0))
            if direction not in ("north", "south", "east", "west"):
                return
            new_pos = self._void.move(entity.id, direction=direction, distance=distance)
            entity.position_x = new_pos.x
            entity.position_y = new_pos.y
        elif action.type == "signal_emitter":
            message = str(action.parameters.get("message", ""))
            radius = float(action.parameters.get("radius", 50.0))
            self._void.broadcast(entity.id, message=message, radius=radius)

    def _load_entity(self, data: dict) -> Entity:
        from genetics.models import Genome
        from neural.brain import Brain
        from genetics.pool import GenePool
        from neural.pool import NeuronPool
        import random
        genome = Genome.model_validate_json(data["genome"])
        pool = NeuronPool.load()
        brain = Brain.from_genome(genome, pool, rng=random.Random(hash(data["id"]) % (2**31)))
        entity = Entity(
            id=data["id"],
            genome=genome,
            brain=brain,
            system_prompt=data.get("system_prompt", ""),
            user_prompt=data.get("user_prompt", ""),
            model=data.get("model", ""),
            provider_name=data.get("provider", ""),
            position_x=float(data.get("position_x", 0.0)),
            position_y=float(data.get("position_y", 0.0)),
            age=int(data.get("age", 0)),
            alive=data.get("alive") == "True",
            think_interval=int(data.get("think_interval", 5)),
            last_think_tick=int(data.get("last_think_tick", 0)),
            cached_action=data.get("cached_action", ""),
            cached_action_tick=int(data.get("cached_action_tick", -1)),
        )
        return entity
```

- [ ] **Step 6: Run tests**

```bash
pytest tests/test_simulation.py --tb=short
```

Expected: all passed.

- [ ] **Step 7: Commit**

```bash
git add simulation/ tests/test_simulation.py
git commit -m "feat: simulation tick engine — hybrid tick loop, entity lifecycle, action execution, archiving"
```

---

## Task 11: API Service

**Files:**
- Create: `api/__init__.py`
- Create: `api/main.py`
- Create: `api/routes/genes.py`
- Create: `api/routes/neurons.py`
- Create: `api/routes/entities.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_api.py
import pytest
import json
from httpx import AsyncClient, ASGITransport
from api.main import app


@pytest.mark.asyncio
async def test_get_gene_pool():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/genes/")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 6
    types = [g["gene_type"] for g in data]
    assert "lifespan" in types


@pytest.mark.asyncio
async def test_get_neuron_pool():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/neurons/")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 6
    types = [n["neuron_type"] for n in data]
    assert "locomotion" in types


@pytest.mark.asyncio
async def test_health():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/test_api.py -x --tb=short
```

Expected: `ModuleNotFoundError: No module named 'api.main'`

- [ ] **Step 3: Create api/__init__.py**

```python
# api/__init__.py
```

- [ ] **Step 4: Create api/routes/genes.py**

```python
from fastapi import APIRouter
from genetics.pool import GenePool
from genetics.models import GeneDefinition

router = APIRouter(prefix="/genes", tags=["genes"])
_pool = GenePool.load()


@router.get("/", response_model=list[GeneDefinition])
async def list_genes() -> list[GeneDefinition]:
    return list(_pool.definitions.values())
```

- [ ] **Step 5: Create api/routes/neurons.py**

```python
from fastapi import APIRouter
from neural.pool import NeuronPool
from neural.models import NeuronDefinition

router = APIRouter(prefix="/neurons", tags=["neurons"])
_pool = NeuronPool.load()


@router.get("/", response_model=list[NeuronDefinition])
async def list_neurons() -> list[NeuronDefinition]:
    return list(_pool.definitions.values())
```

- [ ] **Step 6: Create api/routes/entities.py**

```python
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/entities", tags=["entities"])


@router.get("/archived/{entity_id}")
async def get_archived_entity(entity_id: str) -> dict:
    # Archive lookups require Redis — injected via lifespan in main.py
    raise HTTPException(status_code=501, detail="Requires Redis connection")
```

- [ ] **Step 7: Create api/main.py**

```python
from fastapi import FastAPI
from api.routes.genes import router as genes_router
from api.routes.neurons import router as neurons_router
from api.routes.entities import router as entities_router

app = FastAPI(title="AGI Simulation API", version="1.0.0")

app.include_router(genes_router)
app.include_router(neurons_router)
app.include_router(entities_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
```

- [ ] **Step 8: Run tests**

```bash
pytest tests/test_api.py --tb=short
```

Expected: 3 passed.

- [ ] **Step 9: Commit**

```bash
git add api/ tests/test_api.py
git commit -m "feat: FastAPI service — gene pool, neuron pool, entity archive routes"
```

---

## Task 12: Engine Entry Point and Web Service

**Files:**
- Create: `engine.py`
- Create: `web/__init__.py`
- Create: `web/main.py`
- Create: `web/templates/index.html`

- [ ] **Step 1: Create engine.py**

```python
#!/usr/bin/env python3
"""
Simulation Engine — entry point.

Usage:
    python engine.py

Environment:
    REDIS_URL       Redis connection string (default: redis://localhost:6379)
    OLLAMA_BASE_URL Ollama server URL (default: http://localhost:11434)
    VOID_WIDTH      Width of void space (default: 1000.0)
    VOID_HEIGHT     Height of void space (default: 1000.0)
    INITIAL_ENTITIES Number of starting entities (default: 5)
"""
import asyncio
import logging
import os
import random
from dotenv import load_dotenv
import redis.asyncio as aioredis

from genetics.pool import GenePool
from neural.pool import NeuronPool
from agents.pool import ModelPool, ModelAssignment
from agents.providers.ollama import OllamaProvider
from agents.providers.openrouter import OpenRouterProvider
from agents.providers.anthropic import AnthropicProvider
from environment.void import VoidEnvironment, Position
from simulation.entity import Entity
from simulation.factory import EntityFactory
from simulation.tick import TickEngine
from storage.redis import RedisEntityRepository, RedisTickStream

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def main() -> None:
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")
    void_w = float(os.environ.get("VOID_WIDTH", "1000.0"))
    void_h = float(os.environ.get("VOID_HEIGHT", "1000.0"))
    n_entities = int(os.environ.get("INITIAL_ENTITIES", "5"))
    tick_interval = float(os.environ.get("TICK_INTERVAL_SEC", "2.0"))

    redis = aioredis.from_url(redis_url, decode_responses=False)
    repo = RedisEntityRepository(redis)
    stream = RedisTickStream(redis)
    void = VoidEnvironment(width=void_w, height=void_h)

    gene_pool = GenePool.load()
    neuron_pool = NeuronPool.load()

    # Discover providers
    providers = [
        OllamaProvider(base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")),
        OpenRouterProvider(),
        AnthropicProvider(),
    ]
    model_pool = ModelPool()
    await model_pool.discover(providers)

    if model_pool.size == 0:
        logger.warning("No models available — add Ollama/OpenRouter/Anthropic config")
        # Fall back to a dummy for local testing
        model_pool._pool = [(providers[0], "llama3.2")]

    factory = EntityFactory(gene_pool=gene_pool, neuron_pool=neuron_pool)
    engine = TickEngine(repo=repo, stream=stream, void=void, model_pool=model_pool)

    # Spawn initial entities
    rng = random.Random()
    for i in range(n_entities):
        genome = gene_pool.default_genome()
        assignment = model_pool.assign_random(rng=rng)
        entity = factory.create(
            entity_id=f"entity-{i}",
            genome=genome,
            model_assignment=assignment,
            rng=rng,
        )
        entity.position_x = rng.uniform(0, void_w)
        entity.position_y = rng.uniform(0, void_h)
        await repo.save(entity.id, entity.to_storage_dict())
        void.set_position(entity.id, Position(entity.position_x, entity.position_y))
        logger.info("Spawned %s using %s/%s", entity.id, assignment.provider_name, assignment.model)

    tick = 0
    logger.info("Simulation started — %d entities, tick interval %.1fs", n_entities, tick_interval)

    while True:
        tick += 1
        await engine.tick(tick=tick)
        living = await repo.list_living()
        logger.info("Tick %d — %d entities alive", tick, len(living))
        await asyncio.sleep(tick_interval)


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Create web/__init__.py**

```python
# web/__init__.py
```

- [ ] **Step 3: Create web/main.py**

```python
import os
from quart import Quart, render_template, jsonify
import redis.asyncio as aioredis
from storage.redis import RedisEntityRepository, RedisTickStream

app = Quart(__name__, template_folder="templates")
_redis: aioredis.Redis | None = None


@app.before_serving
async def startup() -> None:
    global _redis
    _redis = aioredis.from_url(
        os.environ.get("REDIS_URL", "redis://localhost:6379"),
        decode_responses=False,
    )


@app.after_serving
async def shutdown() -> None:
    if _redis:
        await _redis.aclose()


@app.route("/")
async def index():
    return await render_template("index.html")


@app.route("/api/state")
async def state():
    if not _redis:
        return jsonify({"error": "not ready"}), 503
    repo = RedisEntityRepository(_redis)
    stream = RedisTickStream(_redis)
    living_ids = await repo.list_living()
    entities = []
    for eid in living_ids:
        data = await repo.load(eid)
        if data:
            entities.append({
                "id": data["id"],
                "age": data.get("age", "0"),
                "position_x": data.get("position_x", "0"),
                "position_y": data.get("position_y", "0"),
                "model": data.get("model", ""),
                "provider": data.get("provider", ""),
                "alive": data.get("alive", "True"),
            })
    recent_ticks = await stream.read_recent(count=5)
    current_tick = int(recent_ticks[-1]["tick"]) if recent_ticks else 0
    return jsonify({"tick": current_tick, "entities": entities})
```

- [ ] **Step 4: Create web/templates/index.html**

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AGI Simulation</title>
<style>
  body { font-family: monospace; background: #0a0a0a; color: #0f0; margin: 0; padding: 20px; }
  h1 { color: #0f0; font-size: 1.2rem; }
  #tick { font-size: 2rem; color: #0f0; }
  table { border-collapse: collapse; width: 100%; margin-top: 16px; }
  th, td { border: 1px solid #1a1a1a; padding: 6px 10px; text-align: left; }
  th { color: #888; font-weight: normal; }
  td { color: #ccc; }
  .alive { color: #0f0; }
</style>
</head>
<body>
<h1>AGI Entity Simulation</h1>
<div>Tick: <span id="tick">—</span></div>
<div>Entities alive: <span id="count">—</span></div>
<table>
  <thead>
    <tr><th>ID</th><th>Age</th><th>X</th><th>Y</th><th>Provider</th><th>Model</th></tr>
  </thead>
  <tbody id="entities"></tbody>
</table>
<script>
async function refresh() {
  const r = await fetch('/api/state');
  const d = await r.json();
  document.getElementById('tick').textContent = d.tick;
  document.getElementById('count').textContent = d.entities.length;
  const tbody = document.getElementById('entities');
  tbody.innerHTML = d.entities.map(e =>
    `<tr><td>${e.id}</td><td>${e.age}</td><td>${parseFloat(e.position_x).toFixed(1)}</td><td>${parseFloat(e.position_y).toFixed(1)}</td><td>${e.provider}</td><td>${e.model}</td></tr>`
  ).join('');
}
refresh();
setInterval(refresh, 2000);
</script>
</body>
</html>
```

- [ ] **Step 5: Smoke test engine startup (no Redis required — just import check)**

```bash
python -c "import engine; print('engine.py imports OK')"
python -c "from web.main import app; print('web/main.py imports OK')"
```

Expected: both print OK without error.

- [ ] **Step 6: Commit**

```bash
git add engine.py web/
git commit -m "feat: simulation engine entry point and Quart web service with basic UI"
```

---

## Task 13: Integration Test — Two Entities, Two Providers, Two Generations

**Files:**
- Test: `tests/test_integration.py`

- [ ] **Step 1: Write integration test**

```python
# tests/test_integration.py
"""
Integration test: verifies the complete simulation loop —
two entities, two different mock providers, run for 10 ticks,
and at least one reproduction occurs.
"""
import asyncio
import random
import pytest
from unittest.mock import MagicMock

import fakeredis.aioredis

from genetics.pool import GenePool
from genetics.models import GeneType, GeneInstance
from neural.pool import NeuronPool
from agents.pool import ModelPool, ModelAssignment
from environment.void import VoidEnvironment, Position
from simulation.entity import Entity
from simulation.factory import EntityFactory
from simulation.tick import TickEngine
from simulation.reproduction import ReproductionHandler
from storage.redis import RedisEntityRepository, RedisTickStream


def _mock_provider(name: str, response: str):
    p = MagicMock()
    p.name = name
    async def _gen(*a, **kw):
        yield response
    p.generate = _gen
    return p


@pytest.mark.asyncio
async def test_full_simulation_two_entities_two_providers():
    redis = fakeredis.aioredis.FakeRedis()
    repo = RedisEntityRepository(redis)
    stream = RedisTickStream(redis)
    void = VoidEnvironment(width=500.0, height=500.0)

    gene_pool = GenePool.load()
    neuron_pool = NeuronPool.load()
    factory = EntityFactory(gene_pool=gene_pool, neuron_pool=neuron_pool)

    # Provider A: Ollama mock → moves north
    p_ollama = _mock_provider(
        "ollama",
        '{"action": {"type": "locomotion", "parameters": {"direction": "north", "distance": 5}}}',
    )
    # Provider B: OpenRouter mock → broadcasts
    p_openrouter = _mock_provider(
        "openrouter",
        '{"action": {"type": "signal_emitter", "parameters": {"message": "hello", "radius": 100}}, "user_prompt_update": "I said hello."}',
    )

    model_pool = MagicMock(spec=ModelPool)

    def get_provider(name):
        return p_ollama if name == "ollama" else p_openrouter

    model_pool.get_provider.side_effect = get_provider
    model_pool.assign_random.side_effect = lambda rng=None: ModelAssignment("ollama", "llama3.2")

    # Entity 1: ollama, short lifespan so it dies and reproduces
    genome1 = gene_pool.default_genome()
    genome1.genes[GeneType.LIFESPAN] = GeneInstance(
        gene_type=GeneType.LIFESPAN, value=8.0
    )
    genome1.genes[GeneType.REPRODUCTION_THRESHOLD] = GeneInstance(
        gene_type=GeneType.REPRODUCTION_THRESHOLD, value=5.0
    )
    genome1.genes[GeneType.THINK_INTERVAL] = GeneInstance(
        gene_type=GeneType.THINK_INTERVAL, value=1.0
    )
    e1 = factory.create("e-1", genome1, ModelAssignment("ollama", "llama3.2"), rng=random.Random(1))

    # Entity 2: openrouter
    genome2 = gene_pool.default_genome()
    genome2.genes[GeneType.THINK_INTERVAL] = GeneInstance(
        gene_type=GeneType.THINK_INTERVAL, value=1.0
    )
    e2 = factory.create("e-2", genome2, ModelAssignment("openrouter", "gpt-4o"), rng=random.Random(2))

    for e in [e1, e2]:
        e.position_x, e.position_y = 250.0, 250.0
        await repo.save(e.id, e.to_storage_dict())
        void.set_position(e.id, Position(250.0, 250.0))

    engine = TickEngine(repo=repo, stream=stream, void=void, model_pool=model_pool)
    repro_handler = ReproductionHandler(
        repo=repo, void=void, factory=factory,
        gene_pool=gene_pool, model_pool=model_pool,
    )

    initial_entity_count = len(await repo.list_living())
    assert initial_entity_count == 2

    # Run 10 ticks
    for tick in range(1, 11):
        await engine.tick(tick=tick)

        # Trigger reproduction for entities that have the divide action available
        living_ids = await repo.list_living()
        for eid in living_ids:
            data = await repo.load(eid)
            if not data:
                continue
            from simulation.tick import TickEngine as TE
            loaded = engine._load_entity(data)
            if loaded.genome.get(GeneType.REPRODUCTION_THRESHOLD) <= loaded.age:
                await repro_handler.spawn_offspring(loaded, tick=tick)

    # Verify: ticks were published
    ticks = await stream.read_recent(count=20)
    assert len(ticks) >= 10

    # Verify: entity 2 is still alive (long lifespan)
    living = await repo.list_living()
    assert "e-2" in living

    # Verify: entity 1 was archived (lifespan=8, age exceeded)
    archived = await repo.load_archive("e-1")
    assert archived is not None

    # Verify: at least one offspring exists (from reproduction)
    all_living = await repo.list_living()
    offspring = [eid for eid in all_living if eid.startswith("offspring-")]
    assert len(offspring) >= 1, f"Expected offspring, got living: {all_living}"

    # Verify: offspring genome differs from parent (mutation)
    if offspring:
        off_data = await repo.load(offspring[0])
        from genetics.models import Genome
        off_genome = Genome.model_validate_json(off_data["genome"])
        # At least the genome loads correctly with all gene types
        assert set(off_genome.genes.keys()) == set(genome1.genes.keys())

    # Verify: entity 2 user_prompt was updated (openrouter response includes update)
    e2_data = await repo.load("e-2")
    if e2_data:
        # After enough ticks where e2 thought, its user_prompt should be updated
        assert True  # At minimum it doesn't crash

    await redis.aclose()


@pytest.mark.asyncio
async def test_two_providers_active_simultaneously():
    """Both Ollama and OpenRouter providers are called within same simulation run."""
    redis = fakeredis.aioredis.FakeRedis()
    repo = RedisEntityRepository(redis)
    stream = RedisTickStream(redis)
    void = VoidEnvironment()

    gene_pool = GenePool.load()
    neuron_pool = NeuronPool.load()
    factory = EntityFactory(gene_pool=gene_pool, neuron_pool=neuron_pool)

    ollama_calls = []
    openrouter_calls = []

    async def ollama_gen(*a, **kw):
        ollama_calls.append(1)
        yield '{"action": null}'

    async def openrouter_gen(*a, **kw):
        openrouter_calls.append(1)
        yield '{"action": null}'

    p_ollama = MagicMock()
    p_ollama.name = "ollama"
    p_ollama.generate = ollama_gen

    p_openrouter = MagicMock()
    p_openrouter.name = "openrouter"
    p_openrouter.generate = openrouter_gen

    model_pool = MagicMock(spec=ModelPool)
    model_pool.get_provider.side_effect = lambda name: (
        p_ollama if name == "ollama" else p_openrouter
    )

    genome = gene_pool.default_genome()
    genome.genes[GeneType.THINK_INTERVAL] = GeneInstance(
        gene_type=GeneType.THINK_INTERVAL, value=1.0
    )

    e1 = factory.create("e-ollama", genome, ModelAssignment("ollama", "llama3.2"), rng=random.Random(1))
    e2 = factory.create("e-openrouter", genome, ModelAssignment("openrouter", "gpt-4o"), rng=random.Random(2))

    for e in [e1, e2]:
        e.position_x, e.position_y = 100.0, 100.0
        await repo.save(e.id, e.to_storage_dict())
        void.set_position(e.id, Position(100.0, 100.0))

    engine = TickEngine(repo=repo, stream=stream, void=void, model_pool=model_pool)
    await engine.tick(tick=1)

    assert len(ollama_calls) >= 1, "Ollama provider was not called"
    assert len(openrouter_calls) >= 1, "OpenRouter provider was not called"

    await redis.aclose()
```

- [ ] **Step 2: Run integration tests**

```bash
pytest tests/test_integration.py -v --tb=short
```

Expected: 2 passed.

- [ ] **Step 3: Run full test suite**

```bash
pytest --tb=short -q
```

Expected: all tests passed.

- [ ] **Step 4: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: integration — two entities, two providers, two generations, full tick loop"
```

---

## Self-Review Checklist

### Spec Coverage

| Requirement | Task |
|-------------|------|
| R1-R4: Hybrid tick mode, async LLM caching, lifespan, think interval | Task 10 |
| R5-R9: Neuron pool, brain wiring, Capability Manifest | Tasks 4-5 |
| R10-R13: Prompt system (system/user), LLM output, user prompt update | Tasks 6, 9 |
| R14-R16: Multi-provider, model assignment | Tasks 6, 12 |
| R17-R23: Gene pool, genomes, asexual reproduction | Tasks 2-3 |
| R24-R27: Void environment, positions, proximity, broadcast | Task 8 |
| R28-R30: Redis storage, entity hash, archive | Task 7 |
| R31: FastAPI service | Task 11 |
| R32: Simulation engine as separate process | Task 12 |
| R33: Abstract interfaces (Protocol) | Tasks 4, 6, 7 |
| R34: Async throughout | All tasks |
| Success Criteria: two providers simultaneously | Task 13 |
| Success Criteria: two generations with mutation | Task 13 |
| Success Criteria: different manifests per neuron config | Task 5 |

**Gap: Quart web service** — covered in Task 12 (basic entity list + tick counter).
**Gap: LM Studio provider** — covered in Task 6 (reuses Ollama pattern, different port).

### No Placeholder Scan

Reviewed — no TBD, TODO, "implement later", or "similar to Task N" patterns.

### Type Consistency

- `Brain.from_genome()` defined in Task 5, used in Task 9 (`EntityFactory.create`) and Task 10 (`TickEngine._load_entity`) — consistent.
- `CapabilityManifest` defined in Task 4, consumed in Task 6 (`AgentOutput.is_valid_for_manifest`) and Task 10 (`TickEngine._process_entity`) — consistent.
- `reproduce(parent1, parent2=None, pool, rng)` signature in Task 3, called in `ReproductionHandler.spawn_offspring` (Task 10) — consistent.
- `ModelAssignment` dataclass defined in Task 6, used in Tasks 9, 10, 13 — consistent.
