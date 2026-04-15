"""
Unit and integration tests for TickEngine divide action dispatch and dead entity cleanup.
"""
import asyncio
import random
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

try:
    import fakeredis.aioredis
except ImportError:
    pytest.skip("fakeredis not available", allow_module_level=True)

from genetics import GenePool
from genetics.models import GeneType, GeneInstance
from neural.pool import NeuronPool
from agents.pool import ModelPool, ModelAssignment
from environment.void import VoidEnvironment, Position
from simulation.entity import Entity
from simulation.factory import EntityFactory
from simulation.reproduction import ReproductionHandler
from simulation.tick import TickEngine
from storage.redis import RedisEntityRepository, RedisTickStream


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_engine_fixtures(
    void_width: float = 1000.0,
    void_height: float = 1000.0,
):
    """Return (redis, repo, stream, void) — caller owns redis.aclose()."""
    redis = fakeredis.aioredis.FakeRedis()
    repo = RedisEntityRepository(redis)
    stream = RedisTickStream(redis)
    void = VoidEnvironment(width=void_width, height=void_height)
    return redis, repo, stream, void


def _silent_mock_pool() -> MagicMock:
    """ModelPool that returns a provider yielding empty JSON (no action)."""
    provider = MagicMock()
    provider.name = "mock"

    async def _gen(*a, **kw):
        yield "{}"

    provider.generate = _gen
    pool = MagicMock(spec=ModelPool)
    pool.get_provider.return_value = provider
    return pool


def _make_entity_with_genome(
    entity_id: str,
    gene_pool: GenePool,
    neuron_pool: NeuronPool,
    *,
    lifespan: float | None = None,
    reproduction_threshold: float | None = None,
    think_interval: float | None = None,
) -> Entity:
    factory = EntityFactory(gene_pool=gene_pool, neuron_pool=neuron_pool)
    genome = gene_pool.default_genome()
    if lifespan is not None:
        genome.genes[GeneType.LIFESPAN] = GeneInstance(
            gene_type=GeneType.LIFESPAN, value=lifespan
        )
    if reproduction_threshold is not None:
        genome.genes[GeneType.REPRODUCTION_THRESHOLD] = GeneInstance(
            gene_type=GeneType.REPRODUCTION_THRESHOLD, value=reproduction_threshold
        )
    if think_interval is not None:
        genome.genes[GeneType.THINK_INTERVAL] = GeneInstance(
            gene_type=GeneType.THINK_INTERVAL, value=think_interval
        )
    assignment = ModelAssignment(provider_name="mock", model="mock-model")
    return factory.create(entity_id, genome, assignment, rng=random.Random(0))


# ── Test 1: divide action → spawn_offspring called ───────────────────────────


async def test_divide_action_calls_spawn_offspring():
    """Happy path: entity with divide cached_action triggers spawn_offspring."""
    gene_pool = GenePool.load()
    neuron_pool = NeuronPool.load()

    redis, repo, stream, void = _make_engine_fixtures()

    # Build entity with a cached divide action
    entity = _make_entity_with_genome("e-div", gene_pool, neuron_pool, lifespan=100.0)
    entity.cached_action = '{"action": {"type": "divide", "parameters": {}}}'
    entity.cached_action_tick = 0
    entity.position_x = 500.0
    entity.position_y = 500.0
    await repo.save("e-div", entity.to_storage_dict())
    void.set_position("e-div", Position(500.0, 500.0))

    # Mock ReproductionHandler.spawn_offspring so we can assert it was called
    mock_repro = MagicMock(spec=ReproductionHandler)
    future = asyncio.get_event_loop().create_future()
    future.set_result(entity)  # return value doesn't matter for this test

    async def _fake_spawn(parent, tick, rng=None):
        return entity

    mock_repro.spawn_offspring = _fake_spawn

    engine = TickEngine(
        repo=repo,
        stream=stream,
        void=void,
        model_pool=_silent_mock_pool(),
        reproduction_handler=mock_repro,
        spawn_rate_cap_percent=100.0,
    )

    called = []

    # Patch spawn_offspring to track invocations
    original = mock_repro.spawn_offspring

    async def _tracking_spawn(parent, tick, rng=None):
        called.append(parent.id)
        return await original(parent, tick, rng=rng)

    mock_repro.spawn_offspring = _tracking_spawn

    await engine.tick(tick=1)
    # Give any created tasks a chance to run
    await asyncio.sleep(0)

    assert "e-div" in called, "spawn_offspring should have been called for the divide action"

    await redis.aclose()


# ── Test 1.5: spawn_rate_cap limits reproduction ──────────────────────────────

async def test_spawn_rate_cap():
    """Verify that mass reproduction respects the spawn rate cap and queues remainders."""
    gene_pool = GenePool.load()
    neuron_pool = NeuronPool.load()

    redis, repo, stream, void = _make_engine_fixtures()

    # Create 100 living entities to get a cap of 5 (5% of 100)
    for i in range(100):
        e = _make_entity_with_genome(f"e-pop-{i}", gene_pool, neuron_pool, lifespan=100.0)
        e.position_x = 500.0
        e.position_y = 500.0
        # 10 entities want to divide
        if i < 10:
            e.cached_action = '{"action": {"type": "divide", "parameters": {}}}'
            e.cached_action_tick = 0
        await repo.save(f"e-pop-{i}", e.to_storage_dict())
        void.set_position(f"e-pop-{i}", Position(500.0, 500.0))

    mock_repro = MagicMock(spec=ReproductionHandler)
    async def _fake_spawn(parent, tick, rng=None):
        return parent
    mock_repro.spawn_offspring = _fake_spawn

    called = []
    original = mock_repro.spawn_offspring
    async def _tracking_spawn(parent, tick, rng=None):
        called.append(parent.id)
        return await original(parent, tick, rng=rng)
    mock_repro.spawn_offspring = _tracking_spawn

    engine = TickEngine(
        repo=repo,
        stream=stream,
        void=void,
        model_pool=_silent_mock_pool(),
        reproduction_handler=mock_repro,
        spawn_rate_cap_percent=5.0,
    )

    # Tick 1: 10 divide actions execute. 5% cap on 100 entities = 5 spawns allowed.
    await engine.tick(tick=1)
    await asyncio.sleep(0)

    assert len(called) == 5, f"Expected exactly 5 spawns due to cap, got {len(called)}"
    assert len(engine._spawn_queue) == 5, f"Expected 5 remaining entities in queue, got {len(engine._spawn_queue)}"

    # Check they were removed from the queue
    for eid in called:
        assert eid not in engine._spawn_queue

    called.clear()

    # Tick 2: 0 new divides. Queue processes remaining 5.
    await engine.tick(tick=2)
    await asyncio.sleep(0)

    assert len(called) == 5, f"Expected exactly 5 spawns due to cap on tick 2, got {len(called)}"
    assert len(engine._spawn_queue) == 0, f"Expected queue to be empty, got {len(engine._spawn_queue)}"

    await redis.aclose()


# ── Test 2: dead entity removed from void after tick ─────────────────────────


async def test_dead_entity_removed_from_void():
    """Entity dies (age >= lifespan); after tick, void.get_nearby() excludes it."""
    gene_pool = GenePool.load()
    neuron_pool = NeuronPool.load()

    redis, repo, stream, void = _make_engine_fixtures()

    # Entity that will die on tick 1 (age 3 >= lifespan 3 after increment)
    entity = _make_entity_with_genome(
        "e-dead", gene_pool, neuron_pool, lifespan=3.0
    )
    entity.age = 3  # next tick: age becomes 4 >= lifespan 3 → dies on increment check
    entity.position_x = 100.0
    entity.position_y = 100.0
    await repo.save("e-dead", entity.to_storage_dict())
    void.set_position("e-dead", Position(100.0, 100.0))

    # Observer entity nearby
    observer = _make_entity_with_genome("e-obs", gene_pool, neuron_pool, lifespan=1000.0)
    observer.position_x = 110.0
    observer.position_y = 100.0
    await repo.save("e-obs", observer.to_storage_dict())
    void.set_position("e-obs", Position(110.0, 100.0))

    engine = TickEngine(
        repo=repo,
        stream=stream,
        void=void,
        model_pool=_silent_mock_pool(),
    )

    await engine.tick(tick=1)

    # Dead entity should no longer be in void
    nearby = void.get_nearby("e-obs", radius=500.0)
    nearby_ids = [n["id"] for n in nearby]
    assert "e-dead" not in nearby_ids, (
        "Dead entity should have been removed from VoidEnvironment"
    )
    # Observer should still be alive and present
    living = await repo.list_living()
    assert "e-obs" in living

    await redis.aclose()


# ── Test 3: divide with reproduction_handler=None → no exception ─────────────


async def test_divide_action_no_handler_no_exception():
    """Edge case: TickEngine without reproduction_handler; divide runs silently."""
    gene_pool = GenePool.load()
    neuron_pool = NeuronPool.load()

    redis, repo, stream, void = _make_engine_fixtures()

    entity = _make_entity_with_genome("e-nodiv", gene_pool, neuron_pool, lifespan=100.0)
    entity.cached_action = '{"action": {"type": "divide", "parameters": {}}}'
    entity.cached_action_tick = 0
    entity.position_x = 500.0
    entity.position_y = 500.0
    await repo.save("e-nodiv", entity.to_storage_dict())
    void.set_position("e-nodiv", Position(500.0, 500.0))

    engine = TickEngine(
        repo=repo,
        stream=stream,
        void=void,
        model_pool=_silent_mock_pool(),
        reproduction_handler=None,  # explicitly no handler
    )

    # Should not raise
    await engine.tick(tick=1)

    # Entity still alive, no offspring
    living = await repo.list_living()
    assert "e-nodiv" in living
    offspring = [eid for eid in living if eid.startswith("offspring-")]
    assert len(offspring) == 0, "No offspring should be created without a handler"

    await redis.aclose()


# ── Test 4: Integration — two-generation via TickEngine.tick() ───────────────


async def test_integration_two_generation_via_tick():
    """
    Full integration: parent reaches reproduction threshold, divide action is
    dispatched from TickEngine.tick(), offspring appears in repo.list_living()
    on the subsequent tick.
    """
    gene_pool = GenePool.load()
    neuron_pool = NeuronPool.load()

    redis, repo, stream, void = _make_engine_fixtures()

    factory = EntityFactory(gene_pool=gene_pool, neuron_pool=neuron_pool)
    model_pool = MagicMock(spec=ModelPool)
    model_pool.assign_random.return_value = ModelAssignment("mock", "mock-model")

    # Provider responds with a divide action every time
    provider = MagicMock()
    provider.name = "mock"

    async def _gen(*a, **kw):
        yield '{"action": {"type": "divide", "parameters": {}}}'

    provider.generate = _gen
    model_pool.get_provider.return_value = provider

    reproduction_handler = ReproductionHandler(
        repo=repo,
        void=void,
        factory=factory,
        gene_pool=gene_pool,
        model_pool=model_pool,
    )

    engine = TickEngine(
        repo=repo,
        stream=stream,
        void=void,
        model_pool=model_pool,
        reproduction_handler=reproduction_handler,
        spawn_rate_cap_percent=100.0,
    )

    # Parent entity — think every tick, reproduction_threshold=1 so divide is
    # immediately available (current_age >= threshold after the first increment)
    parent = _make_entity_with_genome(
        "parent-1",
        gene_pool,
        neuron_pool,
        lifespan=50.0,
        reproduction_threshold=1.0,
        think_interval=1.0,
    )
    parent.position_x = 500.0
    parent.position_y = 500.0
    # Pre-seed a divide action so tick 1 executes it regardless of brain wiring
    parent.cached_action = '{"action": {"type": "divide", "parameters": {}}}'
    parent.cached_action_tick = 0
    await repo.save("parent-1", parent.to_storage_dict())
    void.set_position("parent-1", Position(500.0, 500.0))

    # Tick 1: execute pre-seeded divide → spawn_offspring scheduled
    # asyncio.sleep(0) yields to let the create_task complete
    await engine.tick(tick=1)
    await asyncio.sleep(0)

    living = await repo.list_living()
    offspring_ids = [eid for eid in living if eid.startswith("offspring-")]
    assert len(offspring_ids) >= 1, (
        f"Expected at least one offspring in living entities, got: {living}"
    )

    # Offspring should have a valid genome with all gene types
    off_data = await repo.load(offspring_ids[0])
    from genetics.models import Genome
    off_genome = Genome.model_validate_json(off_data["genome"])
    assert set(off_genome.genes.keys()) == set(parent.genome.genes.keys())

    await redis.aclose()
