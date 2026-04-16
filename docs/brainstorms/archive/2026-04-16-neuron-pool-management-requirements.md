---
date: 2026-04-16
topic: neuron-pool-management
---

# Neuron Pool Management

## Problem Frame
The simulation had backend support for a "Neuron Pool" (`data/neuron_pool.json`) and entity brains, but no user interface existed to manage the pool. Users could not add, update, or remove neuron definitions without manually editing JSON files, and there was no visual confirmation in the simulation that specific neurons were available.

## Requirements
- R1. API endpoints to list, add/update, and delete neurons in the pool.
- R2. Persistent storage of neuron definitions back to `data/neuron_pool.json`.
- R3. A management UI in the Settings page to view and edit the neuron pool.
- R4. Visibility of available neurons in the entity configuration panel on the main simulation page.

## Success Criteria
- [x] Neurons can be added/deleted via the Settings UI.
- [x] Changes persist across server restarts (saved to disk).
- [x] The "Add Configured Entity" panel accurately reflects the current state of the neuron pool.

## Scope Boundaries
- Visualizing the internal neural network wiring of individual entities (deferred).
- Complex neuron parameter configuration beyond type, name, category, and description (deferred).

## Key Decisions
- **Persistence**: Decided to update the existing `data/neuron_pool.json` directly from the API router to maintain simplicity for V1.
- **UI Integration**: Added the management tools to the existing `settings.html` rather than a new page to keep simulation settings centralized.

## Next Steps
- [x] Implement API extensions.
- [x] Implement Settings UI.
- [x] Implement visibility in Config Panel.
- [x] Archive documents.
