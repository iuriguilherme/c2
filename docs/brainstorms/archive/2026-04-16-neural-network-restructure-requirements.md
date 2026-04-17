---
date: 2026-04-16
topic: neural-network-restructure
---

# Neural Network Restructure & Neuron Profiles

## Problem Frame
The current neural system is fragmented and lacks a cohesive way to manage entity "brains" beyond random genetic assignment. A "Neuron Pool" management tool was implemented without clear purpose, allowing arbitrary text descriptions that have no engine-level logic. Entities often spawn without functional networks because the "Add Configured Entity" tool does not properly utilize the neuron pool or genetic information. Settings for neurons are currently buried in general provider settings, causing UI noise.

## Requirements

### R1. Dedicated Neural Management Page
- Move neuron-related configuration from `settings.html` to a new `neural.html`.
- Centralize all Neuron Pool and Neuron Profile management in this dedicated view.

### R2. Neuron Profiles (Templates)
- **Definition**: A named set of neurons (e.g., "Standard Scout") from the global Neuron Pool.
- **Storage**: Save profiles to `data/neuron_profiles.json`.
- **Default Profile**: Designate one profile as the system default for random spawns.
- **Usage**: Manual spawn tools must allow selecting a profile via dropdown.

### R3. Evolution-Aligned Spawning
- **Genetic Link**: Ensure `BRAIN_SIZE` and `NEURON_AFFINITY` genes interact with selected profiles or the global pool during spawning.
- **Random Spawning**: Random entities must use the "Default Profile" as their genetic baseline, allowing mutation to vary the final brain.
- **Manual Spawning**: Forced assignment of a profile should bypass or heavily weight random selection to ensure a functional network.

### R4. Remove Arbitrary "Add Neuron" UI
- Remove the text-based "Add/Update Neuron" form that allows creating non-functional types.
- The Neuron Pool should only contain types supported by the simulation engine (`neural/brain.py`).
- (Long-term: New neurons should emerge from evolution/interaction, not manual text input).

## Success Criteria
- [ ] A dedicated `/neural` route exists with a functional UI.
- [ ] Neuron Profiles can be created, saved, and set as default.
- [ ] Manual entity spawn successfully assigns the selected Neuron Profile.
- [ ] Randomly spawned entities always have a valid initial neural network based on the default profile.

## Scope Boundaries
- **Deferred**: Real-time "emergence" of brand new neuron types from LLM interactions (research needed).
- **Out of Scope**: Brain visualization preview (moved to Ideation).

## Key Decisions
- **Profile Persistence**: Use a dedicated JSON file (`data/neuron_profiles.json`) for user-defined templates.
- **UI Decoupling**: Provider/Model settings stay in `settings.html`; Biological/Neural settings move to `neural.html`.

## Next Steps
- `→ /ce:plan` for implementation of the Neural page and Profile system.
- `→ docs/ideation/2026-04-16-evolutionary-neuron-emergence.md` to document the vision for neurons appearing through interaction.
