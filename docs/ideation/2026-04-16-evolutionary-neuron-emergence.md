---
date: 2026-04-16
topic: evolutionary-neuron-emergence
---

# Evolutionary Neuron Emergence

## Vision
New neuron types should not be manually "typed into a form" by the user. Instead, they should emerge from the simulation itself. As entities interact, communicate, and evolve, the genetic system should eventually be able to "discover" or "unlock" new functional capabilities.

## Mechanism Ideas
- **Latent Capability Activation**: The engine contains code for "Potential" neurons that are only accessible if specific genetic thresholds or environmental conditions are met.
- **Interaction-Driven Discovery**: If two entities exchange a specific pattern of signals consistently, a "Signal Protocol" neuron might be added to the global pool for future generations.
- **LLM Synthesis**: Use a "Supervising Agent" to observe entity logs. If the supervisor detects a repeating pattern of complex behavior that isn't captured by current neurons, it proposes a new `NeuronDefinition` to the global pool.

## Constraints
- Must remain grounded in the Python simulation engine logic.
- Avoid "magic" English-to-Code translation unless a robust sandbox/interpreter is built.

## Status
Ideation only. This document captures the long-term goal to prevent re-implementation of arbitrary UI forms.
