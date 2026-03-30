import pytest
import random

# ── Storage ──────────────────────────────────────────────────────────────────

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
    assert loaded["position_x"] == "100.0"
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
    living = await repo.list_living()
    assert "e-dead" not in living


@pytest.mark.asyncio
async def test_tick_stream_publish_and_read(redis):
    stream = RedisTickStream(redis)
    await stream.publish_tick(tick=1, entity_count=3)
    events = await stream.read_recent(count=10)
    assert len(events) >= 1
    assert events[-1]["tick"] == "1"


# ── Void Environment ─────────────────────────────────────────────────────────

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


# ── Entity and Factory ───────────────────────────────────────────────────────

from simulation.entity import Entity
from simulation.factory import EntityFactory
from agents.pool import ModelAssignment
from neural.pool import NeuronPool


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
    assert entity.system_prompt
    assert entity.brain is not None


def test_entity_system_prompt_varies_with_personality_seed():
    gene_pool = GenePool.load()
    neuron_pool = NeuronPool.load()
    factory = EntityFactory(gene_pool=gene_pool, neuron_pool=neuron_pool)
    g1 = gene_pool.default_genome()
    g2 = gene_pool.default_genome()
    from genetics.models import GeneInstance
    g2.genes[GeneType.PERSONALITY_SEED] = GeneInstance(
        gene_type=GeneType.PERSONALITY_SEED, value=999999.0
    )
    assignment = ModelAssignment(provider_name="ollama", model="llama3.2")
    e1 = factory.create("e-1", g1, assignment, rng=random.Random(1))
    e2 = factory.create("e-2", g2, assignment, rng=random.Random(1))
    assert e1.system_prompt != e2.system_prompt


def test_entity_to_storage_dict_roundtrip():
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


def test_entity_should_think():
    gene_pool = GenePool.load()
    neuron_pool = NeuronPool.load()
    factory = EntityFactory(gene_pool=gene_pool, neuron_pool=neuron_pool)
    genome = gene_pool.default_genome()
    from genetics.models import GeneInstance
    genome.genes[GeneType.THINK_INTERVAL] = GeneInstance(
        gene_type=GeneType.THINK_INTERVAL, value=5.0
    )
    assignment = ModelAssignment(provider_name="ollama", model="llama3.2")
    entity = factory.create("e-1", genome, assignment, rng=random.Random(0))
    entity.last_think_tick = 0

    assert entity.should_think(5) is True   # interval elapsed
    assert entity.should_think(3) is False  # interval not elapsed
