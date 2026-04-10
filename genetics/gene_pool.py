"""Gene pool implementation - catalog of gene definitions.

The gene pool is loaded from data/gene_pool.json at startup and defines
the valid ranges, defaults, and mutation parameters for all gene types.
"""

import json
from pathlib import Path
from genetics.models import GeneType, GeneDefinition, GeneInstance, Genome

_DATA_PATH = Path(__file__).parent.parent / "data" / "gene_pool.json"


class GenePool:
    """Catalog of gene definitions loaded from JSON.

    The gene pool is read-only at runtime and defines:
    - Valid ranges (min_value, max_value) for each gene type
    - Default values for initial entity creation
    - Mutation parameters (rate and standard deviation)
    - Dominance defaults for V2 sexual reproduction

    Example:
        pool = GenePool.load()
        default_genome = pool.default_genome()
        lifespan_def = pool.definitions[GeneType.LIFESPAN]
    """

    def __init__(self, definitions: dict[GeneType, GeneDefinition]) -> None:
        """Initialize with gene definitions.

        Args:
            definitions: Mapping from GeneType to GeneDefinition.
        """
        self.definitions = definitions

    @classmethod
    def load(cls, path: Path | None = None) -> "GenePool":
        """Load gene pool from JSON file.

        Args:
            path: Path to gene pool JSON file. Defaults to data/gene_pool.json.

        Returns:
            Initialized GenePool with all definitions loaded.

        Raises:
            FileNotFoundError: If the gene pool JSON file is not found.
            ValueError: If the JSON contains invalid gene definitions.
        """
        path = path or _DATA_PATH
        raw = json.loads(path.read_text(encoding="utf-8"))
        definitions = {
            GeneType(d["gene_type"]): GeneDefinition.model_validate(d)
            for d in raw
        }
        return cls(definitions)

    def default_genome(self) -> Genome:
        """Create a genome with all genes at their default values.

        Creates GeneInstance objects for each gene type using the
        default_value and dominance_default from the definitions.

        Returns:
            A new Genome with default gene instances.
        """
        genes = {
            gt: GeneInstance(
                gene_type=gt,
                value=defn.default_value,
                dominance=defn.dominance_default,
            )
            for gt, defn in self.definitions.items()
        }
        return Genome(genes=genes)

    def create_gene_instance(
        self,
        gene_type: GeneType,
        value: float | None = None,
        dominance: float | None = None,
    ) -> GeneInstance:
        """Create a gene instance with optional custom values.

        Args:
            gene_type: The type of gene to create.
            value: Custom value (defaults to definition's default_value).
            dominance: Custom dominance (defaults to definition's dominance_default).

        Returns:
            A new GeneInstance, clamped to valid [min, max] range.
        """
        defn = self.definitions[gene_type]
        actual_value = value if value is not None else defn.default_value
        actual_dominance = dominance if dominance is not None else defn.dominance_default

        # Clamp to valid range
        actual_value = max(defn.min_value, min(defn.max_value, actual_value))
        actual_dominance = max(0.0, min(1.0, actual_dominance))

        return GeneInstance(
            gene_type=gene_type,
            value=actual_value,
            dominance=actual_dominance,
        )


def load_gene_pool(path: Path | None = None) -> GenePool:
    """Convenience function to load the gene pool.

    Args:
        path: Optional custom path to gene pool JSON.

    Returns:
        Loaded GenePool instance.
    """
    return GenePool.load(path)
