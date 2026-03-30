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
