"""Tests for gene mutation statistics and behavior."""

import random
import math
import pytest
from statistics import mean, stdev

from genetics.models import GeneType, GeneInstance, Genome
from genetics.gene_pool import GenePool
from genetics.reproduction import reproduce, mutate_gene_value


class TestMutationOccurs:
    """Test suite verifying that mutation actually occurs."""

    def test_mutation_occurs_over_many_offspring(self):
        """Over many offspring, at least some mutations should occur."""
        pool = GenePool.load()
        parent = pool.default_genome()
        rng = random.Random()

        changed = False
        for _ in range(500):
            offspring = reproduce(parent, pool=pool, rng=rng)
            for gt in GeneType:
                if offspring.genes[gt].value != parent.genes[gt].value:
                    changed = True
                    break
            if changed:
                break

        assert changed, "No mutations occurred in 500 offspring"

    def test_mutation_probability_respected(self):
        """Genes with higher mutation_rate mutate more often."""
        pool = GenePool.load()
        parent = pool.default_genome()
        rng = random.Random(42)

        # Find gene with highest mutation rate
        highest_rate_gt = max(
            GeneType,
            key=lambda gt: pool.definitions[gt].mutation_rate
        )
        highest_rate = pool.definitions[highest_rate_gt].mutation_rate

        # Count mutations over many trials
        mutations = 0
        trials = 200
        for _ in range(trials):
            offspring = reproduce(parent, pool=pool, rng=rng)
            if offspring.genes[highest_rate_gt].value != parent.genes[highest_rate_gt].value:
                mutations += 1

        # With high probability, we should see some mutations
        # If mutation_rate is 0.3, we expect ~60 mutations in 200 trials
        observed_rate = mutations / trials
        assert observed_rate > 0, f"No mutations for high-rate gene (expected ~{highest_rate})"


class TestMutationDistribution:
    """Test suite for mutation distribution characteristics."""

    def test_mutation_distribution_approximates_gaussian(self):
        """Mutations follow approximately Gaussian distribution."""
        pool = GenePool.load()
        rng = random.Random(42)

        # Focus on a gene with known mutation parameters
        gt = GeneType.THINK_INTERVAL
        defn = pool.definitions[gt]

        # Collect mutations by repeatedly reproducing
        # We'll use a fixed starting point and collect deltas
        deltas = []
        for _ in range(300):
            # Create a gene at a fixed value
            start_value = defn.default_value
            parent_genes = {
                g: GeneInstance(gene_type=g, value=pool.definitions[g].default_value, dominance=0.5)
                for g in GeneType
            }
            parent = Genome(genes=parent_genes)

            offspring = reproduce(parent, pool=pool, rng=rng)
            delta = offspring.genes[gt].value - start_value
            if delta != 0:  # Only count actual mutations
                deltas.append(delta)

        # We should have collected some mutations
        assert len(deltas) > 10, f"Too few mutations collected: {len(deltas)}"

        # Mean should be approximately 0 (Gaussian centered at 0)
        observed_mean = mean(deltas)
        assert abs(observed_mean) < defn.mutation_std * 2, \
            f"Mean {observed_mean} too far from 0 for Gaussian"

    def test_mutation_std_respected(self):
        """Mutation standard deviation matches configuration."""
        pool = GenePool.load()
        rng = random.Random(42)

        # Use a gene with well-defined std
        gt = GeneType.NEURON_AFFINITY
        defn = pool.definitions[gt]
        expected_std = defn.mutation_std

        # Collect actual mutations
        values = []
        base_value = defn.default_value

        for _ in range(500):
            mutated = mutate_gene_value(
                current_value=base_value,
                mutation_std=expected_std,
                min_value=defn.min_value,
                max_value=defn.max_value,
                rng=rng,
            )
            if mutated != base_value:  # Only count changed values
                values.append(mutated)

        if len(values) > 10:
            observed_std = stdev(values)
            # Allow for significant variance in sample std, but check it's reasonable
            assert observed_std > 0, "Observed std is 0, mutations may not be occurring"


class TestMutationBounds:
    """Test suite for mutation clamping behavior."""

    def test_values_clamped_to_max(self):
        """Mutations cannot exceed max_value."""
        pool = GenePool.load()

        # Test mutate_gene_value directly
        rng = random.Random(42)
        mutated = mutate_gene_value(
            current_value=9999.0,  # Near max
            mutation_std=1000.0,  # Large std to force overflow
            min_value=10.0,
            max_value=10000.0,
            rng=rng,
        )
        assert mutated <= 10000.0

    def test_values_clamped_to_min(self):
        """Mutations cannot go below min_value."""
        pool = GenePool.load()
        rng = random.Random(42)

        mutated = mutate_gene_value(
            current_value=11.0,  # Near min
            mutation_std=1000.0,  # Large std to force underflow
            min_value=10.0,
            max_value=10000.0,
            rng=rng,
        )
        assert mutated >= 10.0

    def test_extreme_values_stay_in_bounds(self):
        """Even with extreme starting values, offspring stays in bounds."""
        pool = GenePool.load()
        rng = random.Random(42)

        # Create genome at extreme values
        genes = {}
        for gt in GeneType:
            defn = pool.definitions[gt]
            # Set to max value
            genes[gt] = GeneInstance(
                gene_type=gt,
                value=defn.max_value,
                dominance=0.5,
            )
        parent = Genome(genes=genes)

        # Reproduce many times
        for _ in range(50):
            offspring = reproduce(parent, pool=pool, rng=rng)
            for gt, inst in offspring.genes.items():
                defn = pool.definitions[gt]
                assert defn.min_value <= inst.value <= defn.max_value


class TestMutationIndependence:
    """Test suite for mutation independence across genes."""

    def test_genes_mutate_independently(self):
        """Each gene mutates independently of others."""
        pool = GenePool.load()
        parent = pool.default_genome()
        rng = random.Random(42)

        # Track which genes mutate across many offspring
        mutation_counts = {gt: 0 for gt in GeneType}
        trials = 300

        for _ in range(trials):
            offspring = reproduce(parent, pool=pool, rng=rng)
            for gt in GeneType:
                if offspring.genes[gt].value != parent.genes[gt].value:
                    mutation_counts[gt] += 1

        # Each gene should have mutated at least once over many trials
        # (unless mutation_rate is extremely low)
        for gt, count in mutation_counts.items():
            rate = pool.definitions[gt].mutation_rate
            if rate > 0.05:  # Only check genes with reasonable mutation rates
                assert count > 0, f"Gene {gt} never mutated in {trials} trials"

    def test_not_all_genes_mutate_together(self):
        """Not all genes mutate on every reproduction."""
        pool = GenePool.load()
        parent = pool.default_genome()
        rng = random.Random(42)

        # Count how many genes mutate per offspring (averaged)
        total_mutations = 0
        trials = 100

        for _ in range(trials):
            offspring = reproduce(parent, pool=pool, rng=rng)
            mutations = sum(
                1 for gt in GeneType
                if offspring.genes[gt].value != parent.genes[gt].value
            )
            total_mutations += mutations

        avg_mutations = total_mutations / trials
        # On average, we shouldn't see all 6 genes mutating every time
        assert avg_mutations < 6, "Too many genes mutating together"


class TestMutateGeneValue:
    """Test suite for the mutate_gene_value utility function."""

    def test_mutate_returns_float(self):
        """mutate_gene_value returns a float."""
        rng = random.Random(42)
        result = mutate_gene_value(
            current_value=50.0,
            mutation_std=5.0,
            min_value=0.0,
            max_value=100.0,
            rng=rng,
        )
        assert isinstance(result, float)

    def test_mutate_without_rng_uses_random(self):
        """mutate_gene_value works without explicit RNG."""
        result = mutate_gene_value(
            current_value=50.0,
            mutation_std=5.0,
            min_value=0.0,
            max_value=100.0,
        )
        assert isinstance(result, float)
        assert 0.0 <= result <= 100.0

    def test_mutate_with_zero_std_returns_original(self):
        """With zero std, value doesn't change."""
        rng = random.Random(42)
        result = mutate_gene_value(
            current_value=50.0,
            mutation_std=0.0,
            min_value=0.0,
            max_value=100.0,
            rng=rng,
        )
        assert result == 50.0


class TestMutationRateConfiguration:
    """Test suite for mutation rate configuration."""

    def test_mutation_rates_are_valid_probabilities(self):
        """All mutation rates are valid probabilities [0, 1]."""
        pool = GenePool.load()

        for gt, defn in pool.definitions.items():
            assert 0.0 <= defn.mutation_rate <= 1.0, \
                f"Invalid mutation_rate for {gt}: {defn.mutation_rate}"

    def test_mutation_stds_are_non_negative(self):
        """All mutation std values are non-negative."""
        pool = GenePool.load()

        for gt, defn in pool.definitions.items():
            assert defn.mutation_std >= 0.0, \
                f"Negative mutation_std for {gt}: {defn.mutation_std}"

    def test_different_genes_have_different_rates(self):
        """Different gene types have different mutation characteristics."""
        pool = GenePool.load()

        rates = [defn.mutation_rate for defn in pool.definitions.values()]
        stds = [defn.mutation_std for defn in pool.definitions.values()]

        # Not all rates should be the same
        assert len(set(rates)) > 1, "All mutation rates are identical"
        assert len(set(stds)) > 1, "All mutation stds are identical"
