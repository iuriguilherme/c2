import math
import random
from dataclasses import dataclass, field
from genetics.models import Genome, GeneType
from neural.models import (
    NeuronType, NeuronInstance, CapabilityManifest,
    ProximityPerception, SignalReceiverPerception,
    ActionCapability, MemoryState, DetectedEntity, SignalMessage,
    ActivationFunction,
)
from neural.pool import NeuronPool


@dataclass
class Brain:
    neurons: list[NeuronInstance]
    edges: list[tuple[str, str, float]] = field(default_factory=list)
    activation_function: ActivationFunction = ActivationFunction.TANH

    def evaluate(self) -> None:
        """
        Performs a forward pass of the neural network.
        Update neuron activations based on incoming edges.
        """
        new_activations = {}
        for inst in self.neurons:
            nt_val = inst.neuron_type.value

            # Sum inputs from all incoming edges
            total_input = inst.activation  # Self-activation or external input from environment
            for source_nt, target_nt, weight in self.edges:
                if target_nt == nt_val:
                    # Find the source neuron activation
                    source_inst = next((n for n in self.neurons if n.neuron_type.value == source_nt), None)
                    if source_inst:
                        total_input += source_inst.activation * weight

            # Apply activation function
            if self.activation_function == ActivationFunction.TANH:
                new_activations[nt_val] = math.tanh(total_input)
            elif self.activation_function == ActivationFunction.SIGMOID:
                new_activations[nt_val] = 1 / (1 + math.exp(-total_input))
            elif self.activation_function == ActivationFunction.RELU:
                new_activations[nt_val] = max(0.0, total_input)
            else:
                new_activations[nt_val] = total_input

        # Update activations and clamp to [0, 1] if needed by NeuronInstance schema
        for inst in self.neurons:
            nt_val = inst.neuron_type.value
            if nt_val in new_activations:
                # Assuming activation bounds are 0.0 to 1.0 based on NeuronInstance Field(ge=0.0, le=1.0)
                # Tanh goes from -1 to 1. If we clamp or normalize to 0-1, we should be careful.
                # Let's map [-1, 1] to [0, 1] for Tanh if needed, or just clamp.
                # Since ReLU can be > 1, we clamp to 1.0.
                # Let's use max(0.0, min(1.0, val)) to be safe with the pydantic model.
                raw_val = new_activations[nt_val]

                # If tanh, it's [-1, 1], let's map to [0, 1] so it fits activation bounds: (tanh(x) + 1) / 2
                if self.activation_function == ActivationFunction.TANH:
                    raw_val = (raw_val + 1.0) / 2.0

                clamped_val = max(0.0, min(1.0, raw_val))
                inst.activation = clamped_val

    @classmethod
    def reproduce(
        cls,
        parent_brain: "Brain",
        genome: Genome,
        pool: NeuronPool,
        rng: random.Random | None = None,
        activation_functions: list[ActivationFunction] | None = None,
    ) -> "Brain":
        r = rng or random.Random()

        # Clone parent's neurons and edges
        neurons = [NeuronInstance(neuron_type=n.neuron_type, activation=n.activation) for n in parent_brain.neurons]
        edges = list(parent_brain.edges)

        n = max(1, round(genome.get(GeneType.BRAIN_SIZE)))

        all_types = list(pool.definitions.keys())

        # Determine if we need to add or remove neurons to match the new brain size
        if len(neurons) < n:
            # Need to add neurons
            affinity = genome.get(GeneType.NEURON_AFFINITY)
            motor_types = {NeuronType.LOCOMOTION, NeuronType.SIGNAL_EMITTER, NeuronType.DIVIDE}
            weights = [
                affinity if nt in motor_types else (1.0 - affinity)
                for nt in all_types
            ]
            num_to_add = n - len(neurons)
            chosen_types = r.choices(all_types, weights=weights, k=num_to_add)
            for nt in chosen_types:
                neurons.append(NeuronInstance(neuron_type=nt, activation=r.uniform(0.3, 1.0)))
        elif len(neurons) > n:
            # Remove random neurons to match size
            r.shuffle(neurons)
            neurons = neurons[:n]

        # Cleanup dangling edges
        current_nt_vals = {n.neuron_type.value for n in neurons}
        edges = [e for e in edges if e[0] in current_nt_vals and e[1] in current_nt_vals]

        # Mutate edges slightly
        # 10% chance to add a new edge, 10% chance to remove an edge, 10% chance to mutate a weight
        if r.random() < 0.1 and len(neurons) >= 2:
            a = r.choice(neurons).neuron_type.value
            b = r.choice(neurons).neuron_type.value
            if a != b:
                edges.append((a, b, r.uniform(-1, 1)))

        if r.random() < 0.1 and edges:
            edges.pop(r.randrange(len(edges)))

        if r.random() < 0.1 and edges:
            idx = r.randrange(len(edges))
            e = edges[idx]
            # Mutate weight slightly
            edges[idx] = (e[0], e[1], max(-1.0, min(1.0, e[2] + r.uniform(-0.2, 0.2))))

        # Determine activation function: high chance to inherit, small chance to mutate if multiples allowed
        activation_functions = activation_functions or [ActivationFunction.TANH]
        act_func = parent_brain.activation_function
        if r.random() < 0.05 and activation_functions:
            act_func = r.choice(activation_functions)

        return cls(neurons=neurons, edges=edges, activation_function=act_func)

    @classmethod
    def from_genome(
        cls,
        genome: Genome,
        pool: NeuronPool,
        rng: random.Random | None = None,
        activation_functions: list[ActivationFunction] | None = None,
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

        activation_functions = activation_functions or [ActivationFunction.TANH]
        act_func = r.choice(activation_functions)

        return cls(neurons=neurons, edges=edges, activation_function=act_func)

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

            elif nt == NeuronType.CORTEX_INPUT_RECEIVER:
                actions["cortex_input_receiver"] = ActionCapability(
                    available=True,
                    activation=act,
                    parameters={"input_value": "number (-1.0 to 1.0)"},
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
