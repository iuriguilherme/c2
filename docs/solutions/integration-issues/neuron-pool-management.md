---
title: Neuron Pool Management Integration
date: 2026-04-16
category: integration-issues
tags:
  - neuron-pool
  - api
  - settings
  - json-persistence
---

# Neuron Pool Management Integration

## Problem Frame
The simulation backend had support for `NeuronPool` and `Brain` logic, but no interface was available to manage the neuron pool (`data/neuron_pool.json`). Adding or removing neuron types required manual file edits, and the simulation provided no visual feedback on available neurons during entity creation.

## Root Cause
A gap between backend logic (which was fully implemented) and the frontend UI. The neuron pool was loaded once at startup and treated as read-only by the API, with no endpoints provided for modification.

## Solution

### 1. Persistent API Endpoints
Added `POST` and `DELETE` endpoints to `api/routes/neurons.py` that modify the `NeuronPool` in memory and persist changes back to `data/neuron_pool.json`.

```python
# api/routes/neurons.py
def save_pool(pool: NeuronPool):
    data = [defn.model_dump() for defn in pool.definitions.values()]
    with open(_DATA_PATH, "w") as f:
        json.dump(data, f, indent=2)

@router.post("/", response_model=NeuronDefinition)
async def add_or_update_neuron(neuron: NeuronDefinition):
    _pool.definitions[neuron.neuron_type] = neuron
    save_pool(_pool)
    return neuron
```

### 2. Centralized Settings UI
Added a management section to `web/templates/settings.html` to allow CRUD operations on neurons.

```javascript
async function saveNeuron() {
  const r = await fetch(`${API_URL}/neurons/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ neuron_type, name, description, category })
  });
  if (r.ok) loadNeuronPool();
}
```

### 3. Simulation Visibility
Updated `web/templates/index.html` to fetch and display the current neuron pool in the "Add Configured Entity" panel.

## Prevention Tip
When implementing backend "pools" or "registries" (genes, neurons, models), always ensure a corresponding management API and UI visibility are planned to avoid "black box" behavior where features exist but are inaccessible.

## Cross-References
- Brainstorm: `docs/brainstorms/archive/2026-04-16-neuron-pool-management-requirements.md`
- Plan: `docs/plans/archive/2026-04-16-003-feat-neuron-pool-management-plan.md`
