---
title: "Neural Network Architecture & Profiles Overhaul"
date: 2026-04-16
category: best-practices
tags:
  - architecture
  - neural-network
  - ui-decoupling
  - genetics
---

# Neural Network Architecture & Profiles Overhaul

## Problem Frame
The simulation had accumulated severe technical debt in the neural network layer. The UI was providing a form to add arbitrary "Neurons" via textual description, saving them to `neuron_pool.json`. However, the Python engine (`neural/brain.py`) could only execute logic for a hardcoded enum of `NeuronType`s. New neurons created in the UI had no functional code backing them, meaning they appeared in the pool but did nothing.

Additionally, entity spawning was creating "brains" randomly from the pool, leading to entities with unviable neural topologies (e.g., all motor neurons, no sensory neurons). Finally, there was no feedback loop for the LLM to write back to its own brain, and the genetic `COGNITIVE_CLARITY` trait was planned but never implemented.

## Root Cause
- **UI/Engine Mismatch**: Building UI forms to add configuration data (neurons) without ensuring the backend engine can dynamically execute logic for them. Arbitrary natural language descriptions do not magically compile into Python simulation logic.
- **Fragmented Scope**: Settings for deeply integrated biological traits (neurons) were mixed into the general provider/LLM settings page (`settings.html`).

## Solution

### 1. UI Decoupling and Strict Typing
Removed the arbitrary text-input form for neurons. The `NeuronPool` is now strictly constrained by the engine's `NeuronType` Enum. The neural management UI was moved to a dedicated `/neural` route (`web/templates/neural.html`) to separate biological configurations from LLM provider settings.

### 2. Neuron Profiles (Spawn Templates)
Introduced `NeuronProfile`s to guarantee viable brains at spawn time. A profile is a named template (e.g., "Default Profile") defining exactly which `NeuronType`s and `ActivationFunction`s should be assigned to a new entity.

### 3. Brain Evaluation & Reproduction
Implemented a true forward pass in `Brain.evaluate()`. It aggregates sensory signals (e.g., from `proximity` or `cortex_input_receiver`), multiplies them by edge weights, and applies a clamped activation function (Tanh, Sigmoid, ReLU). Implemented `Brain.reproduce()` to clone and mutate the network topology across generations.

### 4. Cognitive Feedback & Degradation
- **`cortex_input_receiver`**: A new sensory neuron type that allows the LLM to emit an action (`cortex_write`) to feed a numeric signal back into its brain for the next evaluation cycle.
- **`COGNITIVE_CLARITY`**: A new gene that actively modifies the JSON formatting of the `neural_system_prompt` (the Capability Manifest). High clarity results in clean, indented JSON; low clarity results in minified or heavily scrambled strings, testing the LLM's robustness to noisy perception.

## Prevention Tip
**Do not build CRUD UI for deeply integrated engine logic without a code-generation or interpreter strategy.** If the simulation engine requires a Python class to handle a specific neuron behavior, the UI should not let users type a natural language description and pretend it is functional. Use strict Enums and profiles to manage configurations of *existing* engine features instead.

## Cross-References
- Brainstorm: `docs/brainstorms/2026-04-16-neural-network-restructure-requirements.md`
- Plan: `docs/plans/2026-04-16-005-feat-neural-network-overhaul-and-profiles-plan.md`
- Code: `neural/brain.py`, `simulation/tick.py`
