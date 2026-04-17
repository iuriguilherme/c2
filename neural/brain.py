import math
import random
from dataclasses import dataclass, field
from genetics.models import Genome, GeneType
from neural.models import (
    NeuronType, NeuronInstance, CapabilityManifest,
    ProximityPerception, SignalReceiverPerception,
    ActionCapability, MemoryState, DetectedEntity, SignalMessage,
    ActivationFunction
)
from neural.pool import NeuronPool


@dataclass
class Brain:
    neurons: list[NeuronInstance]
    edges: list[tuple[str, str, float]] = field(default_factory=list)
    activation_function: ActivationFunction = ActivationFunction.TANH
    parent_brain_state: dict | None = None

    @classmethod
    def from_genome(
        cls,
        genome: Genome,
        pool: NeuronPool,
        rng: random.Random | None = None,
        profile: dict | None = None,
    ) -> "Brain":
        r = rng or random.Random()
        n = max(1, round(genome.get(GeneType.BRAIN_SIZE)))
        affinity = genome.get(GeneType.NEURON_AFFINITY)  # 0=sensory, 1=motor

        if profile:
            all_types = profile.get("neurons", [])
            act_func_str = profile.get("activation_function", ActivationFunction.TANH.value)
            act_func = ActivationFunction(act_func_str)
        else:
            all_types = list(pool.definitions.keys())
            act_func = ActivationFunction.TANH

        motor_types = {NeuronType.LOCOMOTION, NeuronType.SIGNAL_EMITTER, NeuronType.DIVIDE}
        weights = [
            affinity if nt in motor_types else (1.0 - affinity)
            for nt in all_types
        ]

        chosen_types = []
        if all_types:
            n_unique = min(n, len(all_types))
            chosen_set = set()
            while len(chosen_set) < n_unique:
                chosen_set.add(r.choices(all_types, weights=weights, k=1)[0])
            chosen_types = list(chosen_set)
        
        neurons = [
            NeuronInstance(neuron_type=nt, activation=r.uniform(0.3, 1.0))
            for nt in chosen_types
        ]

        edges = []
        for i, a in enumerate(neurons):
            for j, b in enumerate(neurons):
                if i != j and r.random() < 0.3:
                    edges.append((a.neuron_type.value, b.neuron_type.value, r.uniform(-1, 1)))

        return cls(neurons=neurons, edges=edges, activation_function=act_func)

    def evaluate(self, incoming_signals: dict[str, float]) -> None:
        new_activations = {}
        current_acts = {n.neuron_type.value: n.activation for n in self.neurons}
        
        for inst in self.neurons:
            nt = inst.neuron_type.value
            s = incoming_signals.get(nt, 0.0)
            
            for edge in self.edges:
                src, dst, weight = edge
                if dst == nt:
                    s += weight * current_acts.get(src, 0.0)
            
            if self.activation_function == ActivationFunction.TANH:
                val = math.tanh(s)
                val = max(0.0, min(1.0, val))
            elif self.activation_function == ActivationFunction.SIGMOID:
                try:
                    val = 1.0 / (1.0 + math.exp(-s))
                except OverflowError:
                    val = 0.0 if s < 0 else 1.0
            elif self.activation_function == ActivationFunction.RELU:
                val = max(0.0, min(1.0, s))
            else:
                val = max(0.0, min(1.0, s))
                
            new_activations[nt] = val

        for inst in self.neurons:
            inst.activation = new_activations[inst.neuron_type.value]

    def reproduce(self, genome: Genome, pool: NeuronPool, rng: random.Random | None = None) -> "Brain":
        r = rng or random.Random()
        
        new_neurons = [NeuronInstance(neuron_type=n.neuron_type, activation=0.0) for n in self.neurons]
        new_edges = list(self.edges)
        
        target_size = max(1, round(genome.get(GeneType.BRAIN_SIZE)))
        current_size = len(new_neurons)
        
        all_types = list(pool.definitions.keys())
        
        if current_size < target_size:
            nt = r.choice(all_types)
            if not any(n.neuron_type == nt for n in new_neurons):
                new_neurons.append(NeuronInstance(neuron_type=nt, activation=0.0))
        elif current_size > target_size and len(new_neurons) > 1:
            idx = r.randrange(len(new_neurons))
            removed_nt = new_neurons[idx].neuron_type.value
            new_neurons.pop(idx)
            new_edges = [e for e in new_edges if e[0] != removed_nt and e[1] != removed_nt]
            
        for i in range(len(new_edges)):
            if r.random() < 0.2:
                src, dst, weight = new_edges[i]
                weight += r.uniform(-0.1, 0.1)
                weight = max(-1.0, min(1.0, weight))
                new_edges[i] = (src, dst, weight)
                
        parent_state = {
            "neurons": [{"type": n.neuron_type.value, "activation": n.activation} for n in self.neurons],
            "edges": self.edges,
            "activation_function": self.activation_function.value
        }
                
        return Brain(
            neurons=new_neurons,
            edges=new_edges,
            activation_function=self.activation_function,
            parent_brain_state=parent_state
        )

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
