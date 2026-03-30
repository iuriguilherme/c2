import random
from genetics.models import GeneType, GeneInstance, Genome
from genetics.pool import GenePool


def reproduce(
    parent1: Genome,
    parent2: Genome | None = None,
    pool: GenePool | None = None,
    rng: random.Random | None = None,
) -> Genome:
    """
    Create an offspring genome.

    V1: asexual only — parent2 is ignored (interface forward-compatible for V2).
    Each gene mutates independently with probability = mutation_rate.
    Mutated value = clamp(current + gauss(0, mutation_std), min, max).
    """
    if pool is None:
        pool = GenePool.load()
    r = rng or random.Random()

    new_genes: dict[GeneType, GeneInstance] = {}
    for gt, inst in parent1.genes.items():
        defn = pool.definitions[gt]
        value = inst.value
        if r.random() < defn.mutation_rate:
            delta = r.gauss(0, defn.mutation_std)
            value = max(defn.min_value, min(defn.max_value, value + delta))
        new_genes[gt] = GeneInstance(
            gene_type=gt,
            value=value,
            dominance=inst.dominance,
        )
    return Genome(genes=new_genes)
