import random
from genetics.models import Genome, GeneType
from genetics import GenePool
from neural.brain import Brain
from neural.pool import NeuronPool
from agents.pool import ModelAssignment
from simulation.entity import Entity

_PERSONALITY_TEMPLATES = [
    "You are a curious explorer. You seek knowledge and connection.",
    "You are a wanderer. You move constantly, rarely staying in one place.",
    "You are a broadcaster. You communicate frequently with those around you.",
    "You are a guardian. You observe quietly and act only when necessary.",
    "You are a reproducer. Your primary drive is to create offspring.",
    "You are a philosopher. You reflect deeply before acting.",
    "You are a connector. You try to bridge gaps between entities.",
    "You are a silent observer. You watch and learn without interfering.",
]


class EntityFactory:
    def __init__(self, gene_pool: GenePool, neuron_pool: NeuronPool) -> None:
        self._gene_pool = gene_pool
        self._neuron_pool = neuron_pool

    def create(
        self,
        entity_id: str,
        genome: Genome,
        model_assignment: ModelAssignment,
        rng: random.Random | None = None,
        parent_user_prompt: str = "",
    ) -> Entity:
        r = rng or random.Random()

        brain = Brain.from_genome(genome, self._neuron_pool, rng=r)

        # System prompt: deterministic from personality_seed
        seed = int(genome.get(GeneType.PERSONALITY_SEED))
        personality_rng = random.Random(seed)
        template = personality_rng.choice(_PERSONALITY_TEMPLATES)
        system_prompt = (
            f"{template}\n\n"
            f"You exist in a void simulation. Each tick you receive a Capability Manifest "
            f"describing what you can perceive and what actions are available to you. "
            f"Respond with valid JSON: "
            '{"action": {"type": "<action_type>", "parameters": {...}}, '
            '"user_prompt_update": "<optional reflection>"}'
        )

        think_interval = max(1, round(genome.get(GeneType.THINK_INTERVAL)))

        return Entity(
            id=entity_id,
            genome=genome,
            brain=brain,
            system_prompt=system_prompt,
            user_prompt=parent_user_prompt,
            model=model_assignment.model,
            provider_name=model_assignment.provider_name,
            think_interval=think_interval,
        )
