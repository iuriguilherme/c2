from dataclasses import dataclass, field
from genetics.models import Genome
from neural.brain import Brain


@dataclass
class Entity:
    id: str
    genome: Genome
    brain: Brain
    system_prompt: str
    user_prompt: str
    model: str
    provider_name: str
    position_x: float = 0.0
    position_y: float = 0.0
    age: int = 0
    alive: bool = True
    think_interval: int = 5
    last_think_tick: int = 0
    cached_action: str = ""
    cached_action_tick: int = -1
    last_manifest: str = ""
    last_activations: str = ""
    last_llm_exchange: str = ""

    def should_think(self, current_tick: int) -> bool:
        return (current_tick - self.last_think_tick) >= self.think_interval

    def to_storage_dict(self) -> dict:
        return {
            "id": self.id,
            "genome": self.genome.model_dump_json(),
            "position_x": str(self.position_x),
            "position_y": str(self.position_y),
            "age": str(self.age),
            "alive": str(self.alive),
            "system_prompt": self.system_prompt,
            "user_prompt": self.user_prompt,
            "model": self.model,
            "provider": self.provider_name,
            "think_interval": str(self.think_interval),
            "last_think_tick": str(self.last_think_tick),
            "cached_action": self.cached_action,
            "cached_action_tick": str(self.cached_action_tick),
            "last_manifest": self.last_manifest,
            "last_activations": self.last_activations,
            "last_llm_exchange": self.last_llm_exchange,
        }
