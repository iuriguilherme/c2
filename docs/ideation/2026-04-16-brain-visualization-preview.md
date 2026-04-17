---
date: 2026-04-16
topic: brain-visualization
---

# Brain Visualization & Live Preview

## Concept
Provide a real-time visual representation of an entity's neural network. Since each entity develops a unique brain through mutation and evolution, this visualization helps users understand why specific entities behave the way they do (e.g., why an entity is more prone to locomotion vs signaling).

## Potential Features
- **Node-Link Diagram**: Show neurons as nodes and connections (edges) as lines.
- **Activation Highlights**: Pulse or change color of nodes when they fire during a simulation tick.
- **Weight Thickness**: Represent the strength of genetic edges through line thickness.
- **Preview Mode**: In the entity creation/profile management screen, show a "typical" wiring for a chosen Neuron Profile.

## Implementation Ideas
- Use D3.js or a canvas-based graph library in the web frontend.
- Fetch `last_activations` and `edges` from the entity state in Redis.
- Toggle visibility of the "Brain View" in the Entity Details side panel.

## Status
Deferred. Documenting here to separate product exploration from immediate restructuring tasks.
