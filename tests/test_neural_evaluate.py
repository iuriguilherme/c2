import math
from neural.models import NeuronType, NeuronInstance, ActivationFunction
from neural.brain import Brain

def test_brain_evaluate_tanh():
    n1 = NeuronInstance(neuron_type=NeuronType.PROXIMITY, activation=0.5)
    n2 = NeuronInstance(neuron_type=NeuronType.LOCOMOTION, activation=0.2)
    edges = [(NeuronType.PROXIMITY.value, NeuronType.LOCOMOTION.value, 1.0)]
    brain = Brain(neurons=[n1, n2], edges=edges, activation_function=ActivationFunction.TANH)

    brain.evaluate()

    # n1 output = tanh(0.5)
    expected_n1_raw = math.tanh(0.5)
    expected_n1_clamped = (expected_n1_raw + 1.0) / 2.0

    # n2 output = tanh(0.2 + n1.activation * 1.0)
    # The actual code uses `source_inst.activation` BEFORE it's updated because we look it up in self.neurons dynamically during the loop? No, the loop goes over self.neurons but reads .activation. Wait, let's trace:
    # Actually, new_activations is calculated based on current .activation, then applied later. So n1's old activation is 0.5.
    expected_n2_raw = math.tanh(0.2 + 0.5 * 1.0)
    expected_n2_clamped = (expected_n2_raw + 1.0) / 2.0

    assert math.isclose(brain.neurons[0].activation, expected_n1_clamped)
    assert math.isclose(brain.neurons[1].activation, expected_n2_clamped)
