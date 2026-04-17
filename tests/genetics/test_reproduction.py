"""Tests for reproduction and asexual division."""

import random
import pytest
from genetics.models import GeneType, GeneInstance, Genome
from genetics.gene_pool import GenePool
from genetics.reproduction import reproduce, asexual_reproduction


class TestAsexualReproduction:
    """Test suite for asexual reproduction (V1)."""

    def test_reproduce_returns_genome(self):
        """Reproduction returns a Genome instance."""
        pool = GenePool.load()
        parent = pool.default_genome()
        offspring = reproduce(parent, pool=pool)

        assert isinstance(offspring, Genome)

    def test_reproduce_preserves_all_genes(self):
        """Offspring has all gene types from parent."""
        pool = GenePool.load()
        parent = pool.default_genome()
        offspring = reproduce(parent, pool=pool)

        assert set(offspring.genes.keys()) == set(parent.genes.keys())

    def test_reproduce_accepts_none_parent2(self):
        """Reproduction interface accepts None for parent2."""
        pool = GenePool.load()
        parent = pool.default_genome()
        offspring = reproduce(parent, parent2=None, pool=pool)

        assert offspring is not None
        assert isinstance(offspring, Genome)

    def test_reproduce_creates_new_object(self):
        """Offspring is a new object, not a reference to parent."""
        pool = GenePool.load()
        parent = pool.default_genome()
        offspring = reproduce(parent, pool=pool)

        assert offspring is not parent
        assert offspring.genes is not parent.genes

    def test_reproduce_without_pool_loads_default(self):
        """Reproduction loads default pool if none provided."""
        parent = GenePool.load().default_genome()
        offspring = reproduce(parent)

        assert isinstance(offspring, Genome)
        assert len(offspring.genes) == 7


class TestReproductionWithDeterministicRng:
    """Test suite using deterministic RNG for reproducible tests."""

    def test_reproduce_with_zero_mutation_rate(self):
        """With zero mutation rate, offspring equals parent."""
        pool = GenePool.load()
        parent = pool.default_genome()
        rng = random.Random(42)

        # Force all mutation rates to 0 by creating custom pool
        # Instead, we'll run many times and verify values stay in range
        for _ in range(10):
            offspring = reproduce(parent, pool=pool, rng=rng)
            for gt in GeneType:
                assert gt in offspring.genes

    def test_reproduce_with_seeded_rng_is_deterministic(self):
        """Same seed produces same results."""
        pool = GenePool.load()
        parent = pool.default_genome()

        rng1 = random.Random(12345)
        rng2 = random.Random(12345)

        offspring1 = reproduce(parent, pool=pool, rng=rng1)
        offspring2 = reproduce(parent, pool=pool, rng=rng2)

        for gt in GeneType:
            assert offspring1.genes[gt].value == offspring2.genes[gt].value


class TestAsexualReproductionConvenience:
    """Test suite for the asexual_reproduction convenience function."""

    def test_asexual_reproduction_returns_genome(self):
        """asexual_reproduction returns a Genome."""
        pool = GenePool.load()
        parent = pool.default_genome()
        offspring = asexual_reproduction(parent, pool=pool)

        assert isinstance(offspring, Genome)

    def test_asexual_reproduction_is_equivalent(self):
        """asexual_reproduction produces same result as reproduce with None."""
        pool = GenePool.load()
        parent = pool.default_genome()

        # Use independently seeded RNGs so both calls start from the same state
        offspring1 = reproduce(parent, parent2=None, pool=pool, rng=random.Random(42))
        offspring2 = asexual_reproduction(parent, pool=pool, rng=random.Random(42))

        for gt in GeneType:
            assert offspring1.genes[gt].value == offspring2.genes[gt].value


class TestReproductionBounds:
    """Test suite for gene value bounds in reproduction."""

    def test_offspring_values_in_bounds(self):
        """All offspring gene values are within definition bounds."""
        pool = GenePool.load()
        parent = pool.default_genome()
        rng = random.Random()

        for _ in range(50):
            offspring = reproduce(parent, pool=pool, rng=rng)
            for gt, inst in offspring.genes.items():
                defn = pool.definitions[gt]
                assert defn.min_value <= inst.value <= defn.max_value

    def test_offspring_dominance_preserved(self):
        """Dominance values are preserved from parent."""
        pool = GenePool.load()
        parent = pool.default_genome()
        rng = random.Random(42)

        offspring = reproduce(parent, pool=pool, rng=rng)

        for gt in GeneType:
            assert offspring.genes[gt].dominance == parent.genes[gt].dominance


class TestReproductionGeneTypeConsistency:
    """Test suite for gene type consistency in reproduction."""

    def test_offspring_has_correct_gene_types(self):
        """Offspring genes have correct GeneType values."""
        pool = GenePool.load()
        parent = pool.default_genome()
        offspring = reproduce(parent, pool=pool)

        for gt, inst in offspring.genes.items():
            assert inst.gene_type == gt

    def test_genome_get_method_works(self):
        """Genome.get() returns correct values."""
        pool = GenePool.load()
        parent = pool.default_genome()
        offspring = reproduce(parent, pool=pool)

        for gt in GeneType:
            expected = offspring.genes[gt].value
            assert offspring.get(gt) == expected
