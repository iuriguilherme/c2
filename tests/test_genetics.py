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
