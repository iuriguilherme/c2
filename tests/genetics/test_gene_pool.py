"""Tests for gene pool loading and default genome creation."""

import json
import pytest
from pathlib import Path

from genetics.models import GeneType, GeneDefinition, GeneInstance, Genome
from genetics.gene_pool import GenePool, load_gene_pool


class TestGenePoolLoading:
    """Test suite for GenePool loading and initialization."""

    def test_gene_pool_loads_from_default_path(self):
        """Gene pool loads from data/gene_pool.json by default."""
        pool = GenePool.load()
        assert len(pool.definitions) == 6
        assert all(gt in pool.definitions for gt in GeneType)

    def test_gene_pool_contains_all_v1_genes(self):
        """V1 gene pool contains exactly 6 gene types."""
        pool = GenePool.load()
        expected_types = {
            GeneType.LIFESPAN,
            GeneType.BRAIN_SIZE,
            GeneType.NEURON_AFFINITY,
            GeneType.PERSONALITY_SEED,
            GeneType.THINK_INTERVAL,
            GeneType.REPRODUCTION_THRESHOLD,
        }
        assert set(pool.definitions.keys()) == expected_types

    def test_gene_pool_loads_from_custom_path(self, tmp_path):
        """Gene pool can load from a custom file path."""
        # Create a minimal gene pool JSON
        gene_data = [
            {
                "gene_type": "lifespan",
                "description": "Test lifespan",
                "min_value": 1.0,
                "max_value": 100.0,
                "default_value": 50.0,
                "mutation_rate": 0.1,
                "mutation_std": 5.0,
                "dominance_default": 0.5,
            }
        ]
        gene_file = tmp_path / "test_gene_pool.json"
        gene_file.write_text(json.dumps(gene_data))

        pool = GenePool.load(path=gene_file)
        assert len(pool.definitions) == 1
        assert GeneType.LIFESPAN in pool.definitions

    def test_gene_pool_loads_valid_definitions(self):
        """Loaded definitions have correct Pydantic validation."""
        pool = GenePool.load()

        for gt, defn in pool.definitions.items():
            assert isinstance(defn, GeneDefinition)
            assert defn.gene_type == gt
            assert defn.min_value < defn.max_value
            assert defn.min_value <= defn.default_value <= defn.max_value
            assert 0.0 <= defn.mutation_rate <= 1.0
            assert defn.mutation_std >= 0.0
            assert 0.0 <= defn.dominance_default <= 1.0

    def test_gene_pool_rejects_missing_file(self):
        """Loading from non-existent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            GenePool.load(path=Path("/nonexistent/path.json"))


class TestDefaultGenome:
    """Test suite for default genome creation."""

    def test_default_genome_has_all_genes(self):
        """Default genome contains all gene types."""
        pool = GenePool.load()
        genome = pool.default_genome()

        assert len(genome.genes) == 6
        for gt in GeneType:
            assert gt in genome.genes

    def test_default_genome_uses_default_values(self):
        """Default genome uses values from gene definitions."""
        pool = GenePool.load()
        genome = pool.default_genome()

        for gt, inst in genome.genes.items():
            defn = pool.definitions[gt]
            assert inst.value == defn.default_value
            assert inst.dominance == defn.dominance_default

    def test_default_genome_is_independent(self):
        """Multiple default genomes are independent objects."""
        pool = GenePool.load()
        genome1 = pool.default_genome()
        genome2 = pool.default_genome()

        assert genome1 is not genome2
        assert genome1.genes is not genome2.genes

    def test_default_genome_is_valid_genome(self):
        """Default genome is a valid Genome instance."""
        pool = GenePool.load()
        genome = pool.default_genome()

        assert isinstance(genome, Genome)
        assert all(isinstance(inst, GeneInstance) for inst in genome.genes.values())


class TestCreateGeneInstance:
    """Test suite for creating individual gene instances."""

    def test_create_with_defaults(self):
        """Can create gene instance using pool defaults."""
        pool = GenePool.load()
        inst = pool.create_gene_instance(GeneType.LIFESPAN)

        defn = pool.definitions[GeneType.LIFESPAN]
        assert inst.value == defn.default_value
        assert inst.dominance == defn.dominance_default

    def test_create_with_custom_values(self):
        """Can create gene instance with custom values."""
        pool = GenePool.load()
        inst = pool.create_gene_instance(
            GeneType.LIFESPAN,
            value=750.0,
            dominance=0.8,
        )

        assert inst.value == 750.0
        assert inst.dominance == 0.8

    def test_create_clamps_to_valid_range(self):
        """Custom values are clamped to gene definition limits."""
        pool = GenePool.load()
        defn = pool.definitions[GeneType.LIFESPAN]

        # Test clamping above max
        inst_high = pool.create_gene_instance(
            GeneType.LIFESPAN,
            value=defn.max_value + 1000,
        )
        assert inst_high.value == defn.max_value

        # Test clamping below min
        inst_low = pool.create_gene_instance(
            GeneType.LIFESPAN,
            value=defn.min_value - 10,
        )
        assert inst_low.value == defn.min_value

    def test_create_clamps_dominance(self):
        """Dominance values are clamped to [0.0, 1.0]."""
        pool = GenePool.load()

        inst_high = pool.create_gene_instance(
            GeneType.LIFESPAN,
            dominance=1.5,
        )
        assert inst_high.dominance == 1.0

        inst_low = pool.create_gene_instance(
            GeneType.LIFESPAN,
            dominance=-0.5,
        )
        assert inst_low.dominance == 0.0


class TestLoadGenePoolConvenience:
    """Test suite for the load_gene_pool convenience function."""

    def test_load_gene_pool_returns_gene_pool(self):
        """load_gene_pool() returns a GenePool instance."""
        pool = load_gene_pool()
        assert isinstance(pool, GenePool)
        assert len(pool.definitions) == 6
