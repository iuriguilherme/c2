import json
from pathlib import Path
from neural.models import NeuronType, NeuronDefinition

_DATA_PATH = Path(__file__).parent.parent / "data" / "neuron_pool.json"


class NeuronPool:
    def __init__(self, definitions: dict[NeuronType, NeuronDefinition]) -> None:
        self.definitions = definitions

    @classmethod
    def load(cls, path: Path = _DATA_PATH) -> "NeuronPool":
        raw = json.loads(path.read_text())
        definitions = {
            NeuronType(d["neuron_type"]): NeuronDefinition.model_validate(d)
            for d in raw
        }
        return cls(definitions)
