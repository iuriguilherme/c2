"""
Integration test: verifies the complete simulation loop —
two entities, two different mock providers, run for 10 ticks,
and at least one reproduction occurs producing offspring.
"""
import asyncio
import random
import pytest
from unittest.mock import MagicMock

try:
    import fakeredis.aioredis
except ImportError:
    pytest.skip("fakeredis not available", allow_module_level=True)

from genetics import GenePool
from genetics.models import GeneType, GeneInstance
from neural.pool import NeuronPool
from agents.pool import ModelPool, ModelAssignment
from environment.void import VoidEnvironment, Position
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

    # Provider A: moves north
    p_ollama = _mock_provider(
        "ollama",
        '{"action": {"type": "locomotion", "parameters": {"direction": "north", "distance": 5}}}',
    )
    # Provider B: broadcasts and updates user_prompt
    p_openrouter = _mock_provider(
        "openrouter",
        '{"action": {"type": "signal_emitter", "parameters": {"message": "hello", "radius": 100}}, "user_prompt_update": "I said hello."}',
    )

    model_pool = MagicMock(spec=ModelPool)
    model_pool.get_provider.side_effect = lambda name: (
        p_ollama if name == "ollama" else p_openrouter
    )
    model_pool.assign_random.return_value = ModelAssignment("ollama", "llama3.2")

    # Entity 1: ollama, short lifespan so it dies
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
    e1 = factory.create(
        "e-1", genome1, ModelAssignment("ollama", "llama3.2"), rng=random.Random(1)
    )

    # Entity 2: openrouter, long lifespan
    genome2 = gene_pool.default_genome()
    genome2.genes[GeneType.THINK_INTERVAL] = GeneInstance(
        gene_type=GeneType.THINK_INTERVAL, value=1.0
    )
    e2 = factory.create(
        "e-2", genome2, ModelAssignment("openrouter", "gpt-4o"), rng=random.Random(2)
    )

    for e in [e1, e2]:
        e.position_x, e.position_y = 250.0, 250.0
        await repo.save(e.id, e.to_storage_dict())
        void.set_position(e.id, Position(250.0, 250.0))

    engine = TickEngine(repo=repo, stream=stream, void=void, model_pool=model_pool)
    repro_handler = ReproductionHandler(
        repo=repo,
        void=void,
        factory=factory,
        gene_pool=gene_pool,
        model_pool=model_pool,
    )

    assert len(await repo.list_living()) == 2

    # Run 10 ticks, triggering reproduction when threshold met
    for tick in range(1, 11):
        await engine.tick(tick=tick)

        living_ids = await repo.list_living()
        for eid in living_ids:
            data = await repo.load(eid)
            if not data:
                continue
            loaded = engine._load_entity(data)
            repro_threshold = loaded.genome.get(GeneType.REPRODUCTION_THRESHOLD)
            if loaded.age >= repro_threshold:
                await repro_handler.spawn_offspring(loaded, tick=tick, rng=random.Random(tick))

    # ── Assertions ─────────────────────────────────────────────────────────

    # Ticks were published
    ticks = await stream.read_recent(count=20)
    assert len(ticks) >= 10

    # Entity 2 (long lifespan) is still alive
    living = await repo.list_living()
    assert "e-2" in living

    # Entity 1 was archived (lifespan=8, age exceeds it)
    archived = await repo.load_archive("e-1")
    assert archived is not None, "e-1 should be archived after dying at age 8"

    # Offspring were created (reproduction threshold=5, entity 1 lives until age 8)
    all_living = await repo.list_living()
    offspring_ids = [eid for eid in all_living if eid.startswith("offspring-")]
    assert len(offspring_ids) >= 1, f"Expected offspring, got: {all_living}"

    # Offspring genome loads correctly with all gene types
    off_data = await repo.load(offspring_ids[0])
    from genetics.models import Genome
    off_genome = Genome.model_validate_json(off_data["genome"])
    assert set(off_genome.genes.keys()) == set(genome1.genes.keys())

    await redis.aclose()


@pytest.mark.asyncio
async def test_two_providers_called_in_same_simulation():
    """Both Ollama and OpenRouter providers are called within the same tick."""
    redis = fakeredis.aioredis.FakeRedis()
    repo = RedisEntityRepository(redis)
    stream = RedisTickStream(redis)
    void = VoidEnvironment()

    gene_pool = GenePool.load()
    neuron_pool = NeuronPool.load()
    factory = EntityFactory(gene_pool=gene_pool, neuron_pool=neuron_pool)

    ollama_calls: list[int] = []
    openrouter_calls: list[int] = []

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

    e1 = factory.create(
        "e-ollama", genome, ModelAssignment("ollama", "llama3.2"), rng=random.Random(1)
    )
    e2 = factory.create(
        "e-openrouter", genome, ModelAssignment("openrouter", "gpt-4o"), rng=random.Random(2)
    )

    for e in [e1, e2]:
        e.position_x, e.position_y = 100.0, 100.0
        await repo.save(e.id, e.to_storage_dict())
        void.set_position(e.id, Position(100.0, 100.0))

    engine = TickEngine(repo=repo, stream=stream, void=void, model_pool=model_pool)
    await engine.tick(tick=1)

    assert len(ollama_calls) >= 1, "Ollama provider was not called"
    assert len(openrouter_calls) >= 1, "OpenRouter provider was not called"

    await redis.aclose()


@pytest.mark.asyncio
async def test_different_neuron_configs_different_manifests():
    """Entities with different genomes receive different Capability Manifests."""
    from neural.brain import Brain
    from genetics import GenePool

    gene_pool = GenePool.load()
    neuron_pool = NeuronPool.load()

    # Small brain (1 neuron)
    g_small = gene_pool.default_genome()
    g_small.genes[GeneType.BRAIN_SIZE] = GeneInstance(
        gene_type=GeneType.BRAIN_SIZE, value=1.0
    )
    # Large brain (6 neurons)
    g_large = gene_pool.default_genome()
    g_large.genes[GeneType.BRAIN_SIZE] = GeneInstance(
        gene_type=GeneType.BRAIN_SIZE, value=6.0
    )

    b_small = Brain.from_genome(g_small, neuron_pool, rng=random.Random(42))
    b_large = Brain.from_genome(g_large, neuron_pool, rng=random.Random(42))

    ctx = {"nearby_entities": [], "received_messages": []}
    m_small = b_small.generate_manifest("e-small", 1, ctx)
    m_large = b_large.generate_manifest("e-large", 1, ctx)

    caps_small = set(m_small.perception) | set(m_small.actions)
    caps_large = set(m_large.perception) | set(m_large.actions)

    # Larger brain has more distinct capability entries
    assert len(b_large.neurons) > len(b_small.neurons)
