---
title: Fix Settings and Port Inconsistencies
type: fix
status: completed
date: 2026-04-18
---

# Fix Settings and Port Inconsistencies

## Overview

Resolve inconsistencies between `shared.env` and `settings.json`, restore the custom external Ollama port (`11435`) to avoid conflicts, and dynamically inject the API base URL into frontend templates to prevent hardcoded ports from breaking when overrides are applied.

## Problem Frame

Currently, `shared.env` defines both infrastructure variables (ports, URLs) and simulation parameters (`INITIAL_ENTITIES`, `TICK_INTERVAL_SEC`, etc.). Since `engine.py` prioritizes environment variables over `settings.json`, any changes made via the API to these simulation parameters are ignored if they are also defined in `shared.env`.

Additionally, the frontend templates (`index.html`, `llm_providers.html`, etc.) hardcode the API base URL to `http://localhost:8000`. If a user overrides `API_PORT_EXTERNAL` via a local `.env` file, the frontend will fail to connect. Finally, the external Ollama port was accidentally reverted to the default `11434`, causing conflicts with the user's host hypervisor.

## Key Technical Decisions

- **Separation of Concerns**: `shared.env` will exclusively manage infrastructure (ports, internal URLs, directory paths). `settings.json` will be the sole source of truth for simulation parameters.
- **Dynamic Frontend URLs**: The `web` service (running Quart) will read `API_PORT_EXTERNAL` from its environment and inject `api_base_url` into the J2 templates, eliminating hardcoded `localhost:8000` references.
- **Port Restoration**: Update `OLLAMA_PORT_EXTERNAL` to `11435` in `shared.env` and `settings.example.json`.

## Implementation Units

- [x] **Unit 1: Prune shared.env and Restore Ollama Port**

**Goal:** Remove simulation parameters to avoid overriding `settings.json` and restore the correct Ollama external port.
**Files:**
- Modify: `shared.env`
**Approach:**
- Remove `INITIAL_ENTITIES`, `TICK_INTERVAL_SEC`, `VOID_WIDTH`, and `VOID_HEIGHT`.
- Change `OLLAMA_PORT_EXTERNAL=11434` to `OLLAMA_PORT_EXTERNAL=11435`.

- [x] **Unit 2: Update settings.example.json**

**Goal:** Align the example JSON with the new default external ports.
**Files:**
- Modify: `settings.example.json`
**Approach:**
- Update `"ollama_base_url": "http://localhost:11434"` to `"http://localhost:11435"`.

- [x] **Unit 3: Inject API Base URL in Web App**

**Goal:** Pass the correct API URL to frontend templates based on the environment configuration.
**Files:**
- Modify: `web/main.py`
**Approach:**
- In the route handlers (`/`, `/llm-providers`, `/neural`, `/prompts`), read `api_port = os.environ.get("API_PORT_EXTERNAL", "8000")`.
- Construct `api_base_url = f"http://localhost:{api_port}"`.
- Pass `api_base_url=api_base_url` as a context variable to `render_template`.

- [x] **Unit 4: Update Frontend Templates**

**Goal:** Remove hardcoded API URLs.
**Files:**
- Modify: `web/templates/index.html`
- Modify: `web/templates/llm_providers.html`
- Modify: `web/templates/neural.html`
- Modify: `web/templates/prompts.html`
**Approach:**
- Replace `const API_BASE = "http://localhost:8000";` (or similar ternary operators) with `const API_BASE = "{{ api_base_url }}";`.
