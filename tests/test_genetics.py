import pytest
from genetics.models import GeneType, GeneDefinition, GeneInstance, Genome


def test_gene_instance_serialization():
    inst = GeneInstance(gene_type=GeneType.LIFESPAN, value=500.0, dominance=0.5)
    d = inst.model_dump()
    assert d["gene_type"] == "lifespan"
    assert d["value"] == 500.0
    restored = GeneInstance.model_validate(d)
    assert restored.gene_type == GeneType.LIFESPAN


def test_genome_contains_all_v1_genes():
    genes = {
        gt: GeneInstance(gene_type=gt, value=1.0, dominance=0.5)
        for gt in GeneType
    }
    genome = Genome(genes=genes)
    assert len(genome.genes) == 6  # V1 has 6 gene types


def test_gene_definition_validation():
    defn = GeneDefinition(
        gene_type=GeneType.LIFESPAN,
        description="Max age in ticks",
        min_value=10.0,
        max_value=10000.0,
        default_value=500.0,
        mutation_rate=0.1,
        mutation_std=50.0,
        dominance_default=0.5,
    )
    assert defn.min_value < defn.default_value < defn.max_value


def test_gene_definition_rejects_out_of_range_default():
    with pytest.raises(Exception):
        GeneDefinition(
            gene_type=GeneType.LIFESPAN,
            description="bad",
            min_value=10.0,
            max_value=100.0,
            default_value=500.0,  # out of range
            mutation_rate=0.1,
            mutation_std=10.0,
        )


# ── Pool and reproduction ────────────────────────────────────────────────────

import random
from genetics import GenePool
from genetics.reproduction import reproduce


def test_gene_pool_loads_all_definitions():
    pool = GenePool.load()
    assert len(pool.definitions) == 6
    assert GeneType.LIFESPAN in pool.definitions


def test_gene_pool_default_genome_has_all_genes():
    pool = GenePool.load()
    genome = pool.default_genome()
    for gt in GeneType:
        assert gt in genome.genes


def test_reproduce_asexual_returns_genome():
    pool = GenePool.load()
    parent = pool.default_genome()
    offspring = reproduce(parent, pool=pool)
    assert isinstance(offspring, Genome)
    assert set(offspring.genes.keys()) == set(parent.genes.keys())


def test_reproduce_accepts_none_parent2():
    pool = GenePool.load()
    parent = pool.default_genome()
    offspring = reproduce(parent, parent2=None, pool=pool)
    assert offspring is not parent


def test_reproduce_mutation_changes_values_statistically():
    """Over 200 offspring, at least one gene should differ from parent."""
    pool = GenePool.load()
    parent = pool.default_genome()
    changed = False
    for _ in range(200):
        offspring = reproduce(parent, pool=pool)
        for gt in GeneType:
            if offspring.genes[gt].value != parent.genes[gt].value:
                changed = True
                break
        if changed:
            break
    assert changed, "No mutations occurred in 200 offspring — mutation_rate too low?"


def test_reproduce_values_stay_in_bounds():
    pool = GenePool.load()
    parent = pool.default_genome()
    for _ in range(50):
        offspring = reproduce(parent, pool=pool)
        for gt, inst in offspring.genes.items():
            defn = pool.definitions[gt]
            assert defn.min_value <= inst.value <= defn.max_value
