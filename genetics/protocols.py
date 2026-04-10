"""Genetic layer protocols defining module boundaries.

This module defines Protocol interfaces for the genetic layer, following
the design decision to use typing.Protocol over ABCs for better async support
and future extensibility (including potential Rust extensions).
"""

from typing import Protocol, runtime_checkable
from genetics.models import GeneType


@runtime_checkable
class Gene(Protocol):
    """Gene Protocol - individual heritable trait.

    Gene instances carry:
    - gene_type: The type of gene (maps to GeneType enum)
    - value: Numeric value of the trait
    - dominance: Dominance value (0.0-1.0) for V2 sexual reproduction
    - mutation_rate: Probability of mutation (0.0-1.0)
    - mutation_std: Standard deviation for Gaussian mutation

    Note: dominance is carried even in V1 asexual reproduction for forward
    compatibility with V2 sexual reproduction.
    """

    gene_type: GeneType
    value: float
    dominance: float
    mutation_rate: float
    mutation_std: float

    def mutate(self, rng=None) -> "Gene":
        """Return a new Gene with potentially mutated value.

        Each gene mutates independently with probability = mutation_rate.
        Mutation amount = random.gauss(0, mutation_std), clamped to [min, max].

        Args:
            rng: Optional random.Random instance for deterministic testing.

        Returns:
            A new Gene instance (may be mutated or unchanged).
        """
        ...


@runtime_checkable
class Genome(Protocol):
    """Genome Protocol - collection of genes forming an entity's DNA.

    The genome is the complete set of heritable traits for an entity.
    V1 supports asexual reproduction (division with mutation).
    V2 will add sexual reproduction (dominance-based gene selection).
    """

    genes: dict[GeneType, Gene]

    def get(self, gene_type: GeneType) -> float:
        """Return the numeric value of a specific gene.

        Args:
            gene_type: The type of gene to retrieve.

        Returns:
            The gene's value as a float.
        """
        ...

    def reproduce(self, parent2: "Genome | None" = None) -> "Genome":
        """Create offspring genome.

        V1: parent2 is None (asexual) - returns mutated copy of self.
        V2: parent2 may be provided - uses dominance-based gene selection.

        Args:
            parent2: Optional second parent for sexual reproduction (V2).

        Returns:
            A new Genome for the offspring entity.
        """
        ...


@runtime_checkable
class GenePoolProtocol(Protocol):
    """GenePool Protocol - catalog of gene definitions.

    The gene pool is a read-only catalog loaded at startup from data/gene_pool.json.
    It defines the constraints and defaults for all gene types in the simulation.
    """

    definitions: dict[GeneType, "GeneDefinition"]

    def default_genome(self) -> Genome:
        """Create a genome with all genes at their default values.

        Returns:
            A new Genome with default gene instances.
        """
        ...
