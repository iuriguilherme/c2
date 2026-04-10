import pytest
from neural.models import (
    NeuronType, NeuronDefinition, NeuronInstance,
    CapabilityManifest, ActionCapability, ProximityPerception,
    SignalReceiverPerception, MemoryState,
)


def test_capability_manifest_schema_version():
    m = CapabilityManifest(schema_version="1.0", agent_id="e-1", tick=0)
    assert m.schema_version == "1.0"


def test_manifest_get_available_actions_empty():
    m = CapabilityManifest(schema_version="1.0", agent_id="e-1", tick=5)
    assert m.get_available_actions() == []


def test_manifest_get_available_actions_filters():
    m = CapabilityManifest(
        schema_version="1.0",
        agent_id="e-1",
        tick=5,
        actions={
            "locomotion": ActionCapability(available=True, activation=0.9),
            "divide": ActionCapability(
                available=False, activation=0.0,
                reason="threshold not met"
            ),
        },
    )
    assert m.get_available_actions() == ["locomotion"]


def test_manifest_serializes_to_json():
    import json
    m = CapabilityManifest(schema_version="1.0", agent_id="e-1", tick=1)
    payload = json.loads(m.model_dump_json())
    assert payload["schema_version"] == "1.0"
    assert payload["agent_id"] == "e-1"


def test_action_capability_activation_bounded():
    with pytest.raises(Exception):
        ActionCapability(available=True, activation=1.5)  # > 1.0


def test_neuron_definition_roundtrip():
    defn = NeuronDefinition(
        neuron_type=NeuronType.LOCOMOTION,
        name="locomotion",
        description="Move in the void",
        category="motor",
    )
    assert defn.category == "motor"
    d = defn.model_dump()
    restored = NeuronDefinition.model_validate(d)
    assert restored.neuron_type == NeuronType.LOCOMOTION


# ── Pool and Brain ────────────────────────────────────────────────────────────

import random
from neural.pool import NeuronPool
from neural.brain import Brain
from genetics.models import GeneType, GeneInstance, Genome


def _genome(brain_size: float = 4.0, affinity: float = 0.5) -> Genome:
    from genetics import GenePool
    g = GenePool.load().default_genome()
    g.genes[GeneType.BRAIN_SIZE] = GeneInstance(
        gene_type=GeneType.BRAIN_SIZE, value=brain_size
    )
    g.genes[GeneType.NEURON_AFFINITY] = GeneInstance(
        gene_type=GeneType.NEURON_AFFINITY, value=affinity
    )
    g.genes[GeneType.REPRODUCTION_THRESHOLD] = GeneInstance(
        gene_type=GeneType.REPRODUCTION_THRESHOLD, value=200.0
    )
    return g


def test_neuron_pool_loads_all_types():
    pool = NeuronPool.load()
    assert len(pool.definitions) == 6
    assert NeuronType.LOCOMOTION in pool.definitions


def test_brain_built_from_genome_respects_brain_size():
    pool = NeuronPool.load()
    genome = _genome(brain_size=3.0)
    brain = Brain.from_genome(genome, pool, rng=random.Random(42))
    assert len(brain.neurons) == 3


def test_brain_generate_manifest_covers_present_neurons():
    pool = NeuronPool.load()
    genome = _genome(brain_size=6.0)
    brain = Brain.from_genome(genome, pool, rng=random.Random(0))
    manifest = brain.generate_manifest(
        agent_id="e-1",
        tick=10,
        context={"nearby_entities": [], "received_messages": []},
        current_age=5,
    )
    total_caps = len(manifest.perception) + len(manifest.actions)
    assert total_caps >= 1


def test_brain_divide_unavailable_when_threshold_not_met():
    pool = NeuronPool.load()
    brain = Brain(
        neurons=[NeuronInstance(neuron_type=NeuronType.DIVIDE, activation=0.9)],
        edges=[],
    )
    manifest = brain.generate_manifest(
        agent_id="e-1",
        tick=5,
        context={"nearby_entities": [], "received_messages": []},
        current_age=5,
        reproduction_threshold=200.0,
    )
    cap = manifest.actions.get("divide")
    assert cap is not None
    assert cap.available is False
    assert cap.reason is not None


def test_brain_divide_available_when_threshold_met():
    brain = Brain(
        neurons=[NeuronInstance(neuron_type=NeuronType.DIVIDE, activation=0.9)],
        edges=[],
    )
    manifest = brain.generate_manifest(
        agent_id="e-1",
        tick=200,
        context={"nearby_entities": [], "received_messages": []},
        current_age=200,
        reproduction_threshold=200.0,
    )
    cap = manifest.actions["divide"]
    assert cap.available is True


def test_different_brain_configs_produce_different_manifests():
    pool = NeuronPool.load()
    g1 = _genome(brain_size=2.0)
    g2 = _genome(brain_size=6.0)
    b1 = Brain.from_genome(g1, pool, rng=random.Random(1))
    b2 = Brain.from_genome(g2, pool, rng=random.Random(2))
    ctx = {"nearby_entities": [], "received_messages": []}
    m1 = b1.generate_manifest("e1", 0, ctx)
    m2 = b2.generate_manifest("e2", 0, ctx)
    caps1 = set(m1.perception) | set(m1.actions)
    caps2 = set(m2.perception) | set(m2.actions)
    assert len(caps2) >= len(caps1)
