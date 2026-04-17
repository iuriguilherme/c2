from enum import Enum
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class NeuronType(str, Enum):
    PROXIMITY = "proximity"
    SIGNAL_RECEIVER = "signal_receiver"
    LOCOMOTION = "locomotion"
    SIGNAL_EMITTER = "signal_emitter"
    DIVIDE = "divide"
    MEMORY_CELL = "memory_cell"
    CORTEX_INPUT_RECEIVER = "cortex_input_receiver"


class ActivationFunction(str, Enum):
    TANH = "tanh"
    SIGMOID = "sigmoid"
    RELU = "relu"


class NeuronDefinition(BaseModel):
    model_config = ConfigDict(extra="allow")
    neuron_type: NeuronType
    name: str
    description: str
    category: Literal["sensory", "motor", "reproductive", "interneuron"]


class NeuronProfile(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    name: str
    description: str
    neurons: list[NeuronType]
    activation_function: ActivationFunction = ActivationFunction.TANH
    is_default: bool = False


class NeuronInstance(BaseModel):
    neuron_type: NeuronType
    activation: float = Field(ge=0.0, le=1.0, default=0.0)


# ── Capability Manifest sub-models ──────────────────────────────────────────

class DetectedEntity(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    distance: float = Field(ge=0.0)
    direction: Literal["north", "south", "east", "west"]


class ProximityPerception(BaseModel):
    model_config = ConfigDict(extra="allow")
    available: bool
    activation: float = Field(ge=0.0, le=1.0)
    detected_entities: list[DetectedEntity] = []


class SignalMessage(BaseModel):
    model_config = ConfigDict(extra="allow")
    from_entity: str
    content: str
    ticks_ago: int = Field(ge=0)


class SignalReceiverPerception(BaseModel):
    model_config = ConfigDict(extra="allow")
    available: bool
    activation: float = Field(ge=0.0, le=1.0)
    recent_messages: list[SignalMessage] = []


class ActionCapability(BaseModel):
    model_config = ConfigDict(extra="allow")
    available: bool
    activation: float = Field(ge=0.0, le=1.0)
    reason: str | None = None
    parameters: dict[str, str] | None = None


class MemoryState(BaseModel):
    model_config = ConfigDict(extra="allow")
    available: bool
    cells: int = Field(ge=0, default=0)
    values: list[float] = []


class CapabilityManifest(BaseModel):
    model_config = ConfigDict(extra="allow")
    schema_version: Literal["1.0"] = "1.0"
    agent_id: str
    tick: int = Field(ge=0)
    perception: dict[str, ProximityPerception | SignalReceiverPerception] = {}
    actions: dict[str, ActionCapability] = {}
    memory: MemoryState = Field(
        default_factory=lambda: MemoryState(available=False)
    )

    def get_available_actions(self) -> list[str]:
        return [name for name, cap in self.actions.items() if cap.available]
