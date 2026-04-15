from enum import Enum
from pydantic import BaseModel, Field, model_validator


class GeneType(str, Enum):
    LIFESPAN = "lifespan"
    BRAIN_SIZE = "brain_size"
    NEURON_AFFINITY = "neuron_affinity"
    PERSONALITY_SEED = "personality_seed"
    THINK_INTERVAL = "think_interval"
    REPRODUCTION_THRESHOLD = "reproduction_threshold"
    COGNITIVE_CLARITY = "cognitive_clarity"


class GeneDefinition(BaseModel):
    gene_type: GeneType
    description: str
    min_value: float
    max_value: float
    default_value: float
    mutation_rate: float = Field(ge=0.0, le=1.0)
    mutation_std: float = Field(ge=0.0)
    dominance_default: float = Field(ge=0.0, le=1.0, default=0.5)

    @model_validator(mode="after")
    def default_in_range(self) -> "GeneDefinition":
        if not (self.min_value <= self.default_value <= self.max_value):
            raise ValueError(
                f"default_value {self.default_value} not in "
                f"[{self.min_value}, {self.max_value}]"
            )
        return self


class GeneInstance(BaseModel):
    gene_type: GeneType
    value: float
    dominance: float = Field(ge=0.0, le=1.0, default=0.5)


class Genome(BaseModel):
    genes: dict[GeneType, GeneInstance]

    def get(self, gene_type: GeneType) -> float:
        """Return the numeric value of a gene."""
        return self.genes[gene_type].value
