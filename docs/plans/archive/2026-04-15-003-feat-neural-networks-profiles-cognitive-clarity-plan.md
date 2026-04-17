# AGI Entity Simulation — Neural Network Architectures, Profiles, and Cognitive Clarity

## 1. Problem Statement
Currently, entities lack a functional neural network capable of evaluation, forward passing, or interpreting inputs to dynamically influence their state. The connection between the "brain" and the LLM (the "spirit") is missing functional feedback loops and evolutionary mechanisms.

## 2. Requirements

### 2.1 Neural Network Evaluation
- Implement forward pass evaluation logic (`evaluate()`) in `Brain`.
- Support multiple `ActivationFunction`s (e.g., Tanh, Sigmoid, ReLU).
- Neurons must compute output activations based on existing edges and incoming source states.
- Normalization or clamping must safely integrate bounded signals `[0.0, 1.0]`.

### 2.2 LLM Feedback Loop (The "Cortex")
- Add a new `cortex_input_receiver` sensory neuron.
- Allow the LLM agent to emit an action to send a numerical signal `[-1.0, 1.0]` back to this specific neuron, influencing subsequent brain evaluations.

### 2.3 System Prompt Overhaul
- Split the monolithic `system_prompt` into components:
  1. `base_system_prompt` (genetic personality)
  2. `neural_system_prompt` (current snapshot of brain state)
  3. `learned_system_prompt` (historical behavior/insights)
- Expose the combined `system_prompt` property for agent execution.

### 2.4 Cognitive Clarity Gene
- Introduce `COGNITIVE_CLARITY`, a new genetic trait bounding `[0.0, 1.0]`.
- Modify tick generation so the format of the `neural_system_prompt` depends on this gene:
  - `> 0.8`: Clean, perfectly-formatted JSON (High clarity).
  - `> 0.4`: Minified/standard JSON (Moderate clarity).
  - `< 0.4`: Scrambled/noisy text representation of the JSON (Low clarity).

### 2.5 Neuron Profiles & Redis Storage
- Migrate gene and neuron definitions away from `data/*.json` files directly to Redis. Use the files only for system bootstrap/seeding if Redis is empty.
- Create `NeuronProfile` configurations to restrict spawned entities to specific sets of neurons and activation functions.
- Update UI `settings.html` (or create `neurons.html`) to allow adding and managing these profiles.
- Ensure the Spawn UI leverages the profiles dynamically.

### 2.6 Brain Inheritance & Evolution
- `Brain`s must reproduce across generations rather than defaulting to completely random structures.
- Implement `Brain.reproduce()`: clone the parent's neurons, edges, and activation function.
- Support mutation: add/drop neurons depending on `brain_size` drift, and stochastic modification of edge weights.
- Offspring must save a snapshot of the parent's terminal brain state to their `parent_brain_state` field.

## 3. Architecture & Implementation Plan

### Phase 1: Storage and Schema
- Expand `neural/models.py` with `ActivationFunction`, `CORTEX_INPUT_RECEIVER`, and `NeuronProfile`.
- Add `COGNITIVE_CLARITY` to `GeneType` and update `data/gene_pool.json`.
- Add `RedisPoolRepository` to `storage/redis.py` to persist definition data.
- Modify `api/main.py` lifespan to seed missing data into Redis.

### Phase 2: Engine Modifications
- Split `Entity.system_prompt` properties.
- Fix bounds mapping and add the logic to push `cortex_input_receiver` values in `tick.py`.
- Apply `should_think()` logic to evaluate cognitive clarity formatting.

### Phase 3: Brain Execution & Reproduction
- Implement `Brain.evaluate()` using the given `activation_function`.
- Add `Brain.reproduce()`.
- Ensure `ReproductionHandler` captures the JSON state of the parent's brain to populate `parent_brain_state`.

### Phase 4: UI & API Integration
- Implement `api/routes/neurons.py` endpoints for Profiles.
- Refactor `index.html` dropdown and create `neurons.html`.

## 4. Verification
- `pytest` coverage for `cortex_input_receiver` bounds testing.
- Integration tests for Redis Pool seeding.
- Playwright verification for frontend Neuron settings visibility.
