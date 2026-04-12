"""Genetic layer - Heritable traits, mutation, and reproduction.

The genetics module provides:
- GeneType: Enumeration of available gene types
- GeneDefinition: Schema for gene constraints and defaults
- GeneInstance: Individual gene with value and dominance
- Genome: Complete set of genes for an entity
- GenePool: Catalog of gene definitions loaded from JSON
- reproduce: Function for creating offspring genomes

Example:
    from genetics import GenePool, reproduce, GeneType

    # Load gene pool
    pool = GenePool.load()

    # Create default genome
    parent = pool.default_genome()

    # Asexual reproduction with mutation
    offspring = reproduce(parent, pool=pool)

    # Access gene values
    lifespan = offspring.get(GeneType.LIFESPAN)
"""

# Models
from genetics.models import GeneType, GeneDefinition, GeneInstance, Genome

# Protocols (for interface contracts)
from genetics.protocols import Gene, Genome as GenomeProtocol, GenePoolProtocol

# Gene pool and genome management
from genetics.gene_pool import GenePool, load_gene_pool
from genetics.genome import GenomeManager, create_genome

# Reproduction function
from genetics.reproduction import reproduce

__all__ = [
    # Models
    "GeneType",
    "GeneDefinition",
    "GeneInstance",
    "Genome",
    # Protocols
    "Gene",
    "GenomeProtocol",
    "GenePoolProtocol",
    # Gene pool
    "GenePool",
    "load_gene_pool",
    # Genome
    "GenomeManager",
    "create_genome",
    # Reproduction
    "reproduce",
]
