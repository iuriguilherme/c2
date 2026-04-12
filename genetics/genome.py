"""Genome implementation - collection of genes forming an entity's DNA.

The genome is the complete set of heritable traits for an entity.
This module provides the Genome class and related utilities.
"""

import random
from genetics.models import GeneType, GeneInstance, Genome as GenomeModel
from genetics.gene_pool import GenePool


class GenomeManager:
    """Manager for genome operations including mutation and reproduction.

    This class wraps the Pydantic Genome model and adds methods for
    genetic operations like mutation and reproduction.
    """

    def __init__(self, genome: GenomeModel, pool: GenePool | None = None):
        """Initialize with a genome model.

        Args:
            genome: The underlying Genome Pydantic model.
            pool: Optional GenePool for mutation parameters.
        """
        self._genome = genome
        self._pool = pool or GenePool.load()

    @property
    def genome(self) -> GenomeModel:
        """Access the underlying genome model."""
        return self._genome

    def get(self, gene_type: GeneType) -> float:
        """Get the value of a specific gene.

        Args:
            gene_type: The type of gene to retrieve.

        Returns:
            The gene's value as a float.
        """
        return self._genome.get(gene_type)

    def mutate(self, rng: random.Random | None = None) -> "GenomeManager":
        """Create a mutated copy of this genome.

        Each gene mutates independently with probability = mutation_rate
        from its definition. Mutation amount follows Gaussian distribution
        with std = mutation_std.

        Args:
            rng: Optional random.Random instance for deterministic testing.

        Returns:
            A new GenomeManager with potentially mutated genes.
        """
        r = rng or random.Random()
        new_genes: dict[GeneType, GeneInstance] = {}

        for gt, inst in self._genome.genes.items():
            defn = self._pool.definitions[gt]
            value = inst.value

            # Apply mutation with probability = mutation_rate
            if r.random() < defn.mutation_rate:
                delta = r.gauss(0, defn.mutation_std)
                value = max(defn.min_value, min(defn.max_value, value + delta))

            new_genes[gt] = GeneInstance(
                gene_type=gt,
                value=value,
                dominance=inst.dominance,
            )

        return GenomeManager(GenomeModel(genes=new_genes), self._pool)

    def reproduce(self, parent2: GenomeModel | None = None) -> GenomeModel:
        """Create offspring genome.

        V1: Asexual reproduction - returns mutated copy of self.
        V2: If parent2 is provided, uses dominance-based selection.

        Args:
            parent2: Optional second parent for sexual reproduction (V2).

        Returns:
            A new Genome for the offspring.
        """
        if parent2 is None:
            # V1: Asexual - just mutate self
            return self.mutate().genome
        else:
            # V2: Sexual reproduction - dominance-based selection
            return self._sexual_reproduction(parent2)

    def _sexual_reproduction(self, parent2: GenomeModel) -> GenomeModel:
        """V2: Create offspring via sexual reproduction.

        For each gene, selects from parent1 or parent2 based on dominance.
        The gene with higher dominance value wins, then mutation is applied.

        Args:
            parent2: The second parent's genome.

        Returns:
            A new Genome combining genes from both parents.
        """
        import random

        r = random.Random()
        new_genes: dict[GeneType, GeneInstance] = {}

        for gt in self._genome.genes:
            p1_inst = self._genome.genes[gt]
            p2_inst = parent2.genes[gt]

            # Select gene with higher dominance
            if p1_inst.dominance >= p2_inst.dominance:
                selected = p1_inst
            else:
                selected = p2_inst

            # Copy selected gene and apply mutation
            defn = self._pool.definitions[gt]
            value = selected.value
            if r.random() < defn.mutation_rate:
                delta = r.gauss(0, defn.mutation_std)
                value = max(defn.min_value, min(defn.max_value, value + delta))

            new_genes[gt] = GeneInstance(
                gene_type=gt,
                value=value,
                dominance=selected.dominance,
            )

        return GenomeModel(genes=new_genes)


def create_genome(
    gene_values: dict[GeneType, float] | None = None,
    pool: GenePool | None = None,
) -> GenomeModel:
    """Create a new genome with specified or default gene values.

    Args:
        gene_values: Optional mapping of gene types to values.
        pool: Optional GenePool for constraints.

    Returns:
        A new Genome with the specified values (or defaults).
    """
    pool = pool or GenePool.load()

    if gene_values is None:
        return pool.default_genome()

    genes: dict[GeneType, GeneInstance] = {}
    for gt, value in gene_values.items():
        defn = pool.definitions.get(gt)
        if defn:
            # Clamp to valid range
            value = max(defn.min_value, min(defn.max_value, value))
            genes[gt] = GeneInstance(
                gene_type=gt,
                value=value,
                dominance=defn.dominance_default,
            )

    return GenomeModel(genes=genes)
