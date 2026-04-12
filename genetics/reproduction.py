"""Reproduction module - creating offspring genomes.

This module provides the core reproduction logic for the simulation.
V1 supports asexual reproduction (division with mutation).
V2 will add sexual reproduction (dominance-based gene selection).

The reproduction interface accepts parent1 and optional parent2 for
forward compatibility with V2 sexual reproduction.
"""

import random
from genetics.models import GeneType, GeneInstance, Genome
from genetics.gene_pool import GenePool


def reproduce(
    parent1: Genome,
    parent2: Genome | None = None,
    pool: GenePool | None = None,
    rng: random.Random | None = None,
) -> Genome:
    """Create an offspring genome.

    V1: Asexual only - parent2 is ignored (interface is forward-compatible for V2).
    Each gene mutates independently with probability = mutation_rate.
    Mutated value = clamp(current + gauss(0, mutation_std), min, max).

    V2 (future): If parent2 is provided, uses dominance-based gene selection
    before applying mutation.

    Args:
        parent1: The primary parent's genome (required).
        parent2: Optional second parent for sexual reproduction (V2).
        pool: GenePool for mutation parameters. Loads default if not provided.
        rng: Optional random.Random instance for deterministic testing.

    Returns:
        A new Genome for the offspring entity.

    Example:
        pool = GenePool.load()
        parent = pool.default_genome()

        # V1: Asexual reproduction
        offspring = reproduce(parent, pool=pool)

        # Access offspring's genes
        lifespan = offspring.get(GeneType.LIFESPAN)
    """
    if pool is None:
        pool = GenePool.load()
    r = rng or random.Random()

    # V1: Asexual - copy parent1 and apply mutation
    # V2: If parent2 present, would apply dominance-based selection first
    new_genes: dict[GeneType, GeneInstance] = {}

    for gt, inst in parent1.genes.items():
        defn = pool.definitions[gt]
        value = inst.value
        dominance = inst.dominance

        # V2: If parent2 present, apply dominance-based selection
        if parent2 is not None and gt in parent2.genes:
            p2_inst = parent2.genes[gt]
            # Select gene with higher dominance
            if p2_inst.dominance > dominance:
                value = p2_inst.value
                dominance = p2_inst.dominance

        # Apply mutation with probability = mutation_rate
        if r.random() < defn.mutation_rate:
            delta = r.gauss(0, defn.mutation_std)
            value = max(defn.min_value, min(defn.max_value, value + delta))

        new_genes[gt] = GeneInstance(
            gene_type=gt,
            value=value,
            dominance=dominance,
        )

    return Genome(genes=new_genes)


def asexual_reproduction(
    parent: Genome,
    pool: GenePool | None = None,
    rng: random.Random | None = None,
) -> Genome:
    """Create offspring via asexual reproduction (division with mutation).

    This is a convenience wrapper around reproduce() that explicitly
    ensures asexual reproduction by not accepting a second parent.

    Args:
        parent: The parent's genome.
        pool: GenePool for mutation parameters.
        rng: Optional random.Random instance for deterministic testing.

    Returns:
        A new Genome for the offspring entity.
    """
    return reproduce(parent, parent2=None, pool=pool, rng=rng)


def calculate_mutation_probability(
    gene_type: GeneType,
    pool: GenePool,
) -> float:
    """Get the mutation probability for a gene type.

    Args:
        gene_type: The type of gene.
        pool: GenePool containing the definitions.

    Returns:
        Mutation probability (0.0-1.0) for the gene type.
    """
    return pool.definitions[gene_type].mutation_rate


def mutate_gene_value(
    current_value: float,
    mutation_std: float,
    min_value: float,
    max_value: float,
    rng: random.Random | None = None,
) -> float:
    """Apply mutation to a gene value.

    Args:
        current_value: The current gene value.
        mutation_std: Standard deviation for Gaussian mutation.
        min_value: Minimum allowed value (clamping).
        max_value: Maximum allowed value (clamping).
        rng: Optional random.Random instance.

    Returns:
        The mutated value, clamped to [min_value, max_value].
    """
    r = rng or random.Random()
    delta = r.gauss(0, mutation_std)
    return max(min_value, min(max_value, current_value + delta))
