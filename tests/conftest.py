"""Pytest configuration and shared fixtures."""

import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import random
import pytest
try:
    import fakeredis.aioredis
    HAS_FAKEREDIS = True
except ImportError:
    HAS_FAKEREDIS = False

from genetics.gene_pool import GenePool
from genetics.models import GeneType, GeneInstance, Genome


@pytest.fixture(autouse=True)
async def mongo(monkeypatch):
    from unittest.mock import AsyncMock, patch

    # Since beanie + mongomock_motor is failing deep inside beanie internals with list_collection_names,
    # let's mock beanie completely out for tests that don't specifically test DB functionality.

    with patch("storage.mongo.init_mongo", new_callable=AsyncMock) as mock_init:

        # We also need to mock SystemPrompt if tests use it.
        # For simplicity, we just mock the find().to_list() chain
        mock_find = AsyncMock()
        mock_find.to_list = AsyncMock(return_value=[])

        with patch("storage.mongo.SystemPrompt.find", return_value=mock_find):
            with patch("storage.mongo.SystemPrompt.find_all", return_value=mock_find):
                yield mock_init

@pytest.fixture
async def redis():
    """Provide a fake Redis instance for testing."""
    if not HAS_FAKEREDIS:
        pytest.skip("fakeredis not available")
    r = fakeredis.aioredis.FakeRedis()
    yield r
    await r.aclose()


# =============================================================================
# Genetics Fixtures
# =============================================================================

@pytest.fixture
def gene_pool():
    """Provide the default gene pool loaded from data/gene_pool.json."""
    return GenePool.load()


@pytest.fixture
def default_genome(gene_pool):
    """Provide a default genome from the gene pool."""
    return gene_pool.default_genome()


@pytest.fixture
def seeded_rng():
    """Provide a seeded random.Random instance for deterministic tests.

    Usage:
        def test_something(seeded_rng):
            # This will always produce the same sequence
            offspring = reproduce(parent, rng=seeded_rng)
    """
    return random.Random(42)


@pytest.fixture
def deterministic_rng():
    """Provide a fresh seeded RNG that can be reset between uses.

    This fixture returns a Random instance seeded with a known value.
    For tests requiring multiple independent RNGs, use seeded_rng instead.
    """
    return random.Random(12345)


@pytest.fixture
def mock_gene_pool(tmp_path):
    """Create a temporary gene pool with controlled mutation rates.

    This is useful for tests that need specific mutation parameters.
    """
    import json

    gene_data = [
        {
            "gene_type": "lifespan",
            "description": "Test lifespan with zero mutation",
            "min_value": 1.0,
            "max_value": 1000.0,
            "default_value": 100.0,
            "mutation_rate": 0.0,  # Never mutate
            "mutation_std": 0.0,
            "dominance_default": 0.5,
        },
        {
            "gene_type": "brain_size",
            "description": "Test brain size with high mutation",
            "min_value": 1.0,
            "max_value": 10.0,
            "default_value": 5.0,
            "mutation_rate": 1.0,  # Always mutate
            "mutation_std": 0.5,
            "dominance_default": 0.5,
        },
        {
            "gene_type": "neuron_affinity",
            "description": "Test affinity",
            "min_value": 0.0,
            "max_value": 1.0,
            "default_value": 0.5,
            "mutation_rate": 0.5,
            "mutation_std": 0.1,
            "dominance_default": 0.5,
        },
        {
            "gene_type": "personality_seed",
            "description": "Test personality",
            "min_value": 0.0,
            "max_value": 1000000.0,
            "default_value": 1000.0,
            "mutation_rate": 0.1,
            "mutation_std": 100.0,
            "dominance_default": 0.5,
        },
        {
            "gene_type": "think_interval",
            "description": "Test think interval",
            "min_value": 1.0,
            "max_value": 100.0,
            "default_value": 5.0,
            "mutation_rate": 0.2,
            "mutation_std": 1.0,
            "dominance_default": 0.5,
        },
        {
            "gene_type": "reproduction_threshold",
            "description": "Test reproduction threshold",
            "min_value": 10.0,
            "max_value": 500.0,
            "default_value": 50.0,
            "mutation_rate": 0.15,
            "mutation_std": 5.0,
            "dominance_default": 0.5,
        },
    ]

    gene_file = tmp_path / "test_gene_pool.json"
    gene_file.write_text(json.dumps(gene_data))

    return GenePool.load(path=gene_file)


@pytest.fixture
def custom_genome(gene_pool):
    """Provide a genome with custom gene values for testing.

    Returns a function that creates genomes with specified values.
    """
    def make_genome(**gene_values):
        genes = {}
        for gt in GeneType:
            defn = gene_pool.definitions[gt]
            value = gene_values.get(gt.value, defn.default_value)
            # Clamp to valid range
            value = max(defn.min_value, min(defn.max_value, value))
            genes[gt] = GeneInstance(
                gene_type=gt,
                value=value,
                dominance=defn.dominance_default,
            )
        return Genome(genes=genes)

    return make_genome
