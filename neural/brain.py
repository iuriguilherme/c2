import random
from dataclasses import dataclass, field
from genetics.models import Genome, GeneType
from neural.models import (
    NeuronType, NeuronInstance, CapabilityManifest,
    ProximityPerception, SignalReceiverPerception,
    ActionCapability, MemoryState, DetectedEntity, SignalMessage,
)
from neural.pool import NeuronPool


@dataclass
class Brain:
    neurons: list[NeuronInstance]
    edges: list[tuple[str, str, float]] = field(default_factory=list)

    @classmethod
    def from_genome(
        cls,
        genome: Genome,
        pool: NeuronPool,
        rng: random.Random | None = None,
    ) -> "Brain":
        r = rng or random.Random()
        n = max(1, round(genome.get(GeneType.BRAIN_SIZE)))
        affinity = genome.get(GeneType.NEURON_AFFINITY)  # 0=sensory, 1=motor

        all_types = list(pool.definitions.keys())
        motor_types = {NeuronType.LOCOMOTION, NeuronType.SIGNAL_EMITTER, NeuronType.DIVIDE}
        weights = [
            affinity if nt in motor_types else (1.0 - affinity)
            for nt in all_types
        ]

        chosen_types = r.choices(all_types, weights=weights, k=n)
        neurons = [
            NeuronInstance(neuron_type=nt, activation=r.uniform(0.3, 1.0))
            for nt in chosen_types
        ]

        edges = []
        for i, a in enumerate(neurons):
            for j, b in enumerate(neurons):
                if i != j and r.random() < 0.3:
                    edges.append((a.neuron_type.value, b.neuron_type.value, r.uniform(-1, 1)))

        return cls(neurons=neurons, edges=edges)

    def generate_manifest(
        self,
        agent_id: str,
        tick: int,
        context: dict,
        current_age: float = 0,
        reproduction_threshold: float = 9999.0,
    ) -> CapabilityManifest:
        perception: dict = {}
        actions: dict = {}
        memory = MemoryState(available=False)

        nearby = context.get("nearby_entities", [])
        messages = context.get("received_messages", [])

        for inst in self.neurons:
            nt = inst.neuron_type
            act = inst.activation

            if nt == NeuronType.PROXIMITY:
                detected = [
                    DetectedEntity(
                        id=e["id"],
                        distance=e["distance"],
                        direction=e["direction"],
                    )
                    for e in nearby
                ]
                perception["proximity"] = ProximityPerception(
                    available=True, activation=act, detected_entities=detected
                )

            elif nt == NeuronType.SIGNAL_RECEIVER:
                msgs = [
                    SignalMessage(
                        from_entity=m["from_entity"],
                        content=m["content"],
                        ticks_ago=m["ticks_ago"],
                    )
                    for m in messages
                ]
                perception["signal_receiver"] = SignalReceiverPerception(
                    available=True, activation=act, recent_messages=msgs
                )

            elif nt == NeuronType.LOCOMOTION:
                actions["locomotion"] = ActionCapability(
                    available=True,
                    activation=act,
                    parameters={"direction": "north|south|east|west", "distance": "number"},
                )

            elif nt == NeuronType.SIGNAL_EMITTER:
                actions["signal_emitter"] = ActionCapability(
                    available=True,
                    activation=act,
                    parameters={"message": "string", "radius": "number"},
                )

            elif nt == NeuronType.DIVIDE:
                threshold_met = current_age >= reproduction_threshold
                actions["divide"] = ActionCapability(
                    available=threshold_met,
                    activation=act if threshold_met else 0.0,
                    reason=None
                    if threshold_met
                    else f"reproduction_threshold not met (age {current_age} < {reproduction_threshold})",
                )

            elif nt == NeuronType.MEMORY_CELL:
                memory = MemoryState(available=True, cells=1, values=[act])

        return CapabilityManifest(
            agent_id=agent_id,
            tick=tick,
            perception=perception,
            actions=actions,
            memory=memory,
        )
