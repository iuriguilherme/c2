import json
from pathlib import Path
from genetics.models import GeneType, GeneDefinition, GeneInstance, Genome

_DATA_PATH = Path(__file__).parent.parent / "data" / "gene_pool.json"


class GenePool:
    def __init__(self, definitions: dict[GeneType, GeneDefinition]) -> None:
        self.definitions = definitions

    @classmethod
    def load(cls, path: Path = _DATA_PATH) -> "GenePool":
        raw = json.loads(path.read_text())
        definitions = {
            GeneType(d["gene_type"]): GeneDefinition.model_validate(d)
            for d in raw
        }
        return cls(definitions)

    def default_genome(self) -> Genome:
        genes = {
            gt: GeneInstance(
                gene_type=gt,
                value=defn.default_value,
                dominance=defn.dominance_default,
            )
            for gt, defn in self.definitions.items()
        }
        return Genome(genes=genes)
