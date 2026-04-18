---
title: Docker Environment Variable and Port Management Refactor
category: refactor
date: 2026-04-18
module: devops
tags: [docker, environment, configuration, orchestration]
problem_type: architectural_drift
---

# Docker Environment Variable and Port Management Refactor

## Problem Symptom

1.  **Redundancy**:Identical `environment` blocks were repeated across multiple services (`api`, `web`, `engine`) in `docker-compose.yml`.
2.  **Hardcoded Ports**: Ports were hardcoded in `docker-compose.yml` and frontend HTML templates, making it difficult to avoid conflicts with host services (like hypervisor-bound Ollama).
3.  **Settings Inconsistency**: Mixing simulation parameters (e.g., `TICK_INTERVAL_SEC`) with infrastructure config in environment variables caused `engine.py` to prioritize environment values over `settings.json`, effectively disabling API-driven configuration updates.
4.  **No Override Mechanism**: No clear way to provide local, non-versioned configuration overrides for developers.

## Root Cause Analysis

- The project lacked a version-controlled source of truth for baseline infrastructure configuration.
- The separation of concerns between **infrastructure** (orchestration, discovery) and **application state** (simulation parameters) was not enforced at the configuration level.
- Frontend templates relied on hardcoded `localhost:8000` URLs, breaking when the API port was mapped differently on the host.

## Working Solution

### 1. Unified Infrastructure Config (`shared.env`)
Created `shared.env` to store version-controlled baseline infrastructure settings. This file is explicitly excluded from the `.*` gitignore rule.

```ini
# shared.env
REDIS_PORT_EXTERNAL=6379
REDIS_PORT_INTERNAL=6379
# ... other ports
API_PORT_EXTERNAL=8000
# URLs derived from ports
REDIS_URL=redis://redis:${REDIS_PORT_INTERNAL}
OLLAMA_BASE_URL=http://ollama:${OLLAMA_PORT_INTERNAL}
```

### 2. Robust Docker Orchestration
Refactored `docker-compose.yml` to utilize `env_file` with override priority and variable interpolation with fallbacks.

```yaml
# docker-compose.yml
services:
  api:
    ports:
      - "${API_PORT_EXTERNAL:-8000}:${API_PORT_INTERNAL:-8000}"
    env_file:
      - shared.env # Versioned baseline
      - .env       # Local overrides (last wins)
```

### 3. Dynamic Frontend URLs
Updated the Quart `web` service to dynamically inject the API URL into templates based on the `API_PORT_EXTERNAL` environment variable.

```python
# web/main.py
@app.route("/")
async def index():
    api_port = os.environ.get("API_PORT_EXTERNAL", "8000")
    api_base_url = f"http://localhost:{api_port}"
    return await render_template("index.html", api_base_url=api_base_url)
```

Templates now use `const API_BASE = "{{ api_base_url }}";`.

### 4. Settings Source of Truth
Removed simulation parameters from environment variables in `shared.env`. This ensures `engine.py` falls back to `settings.json` (managed via the API/UI) when environment variables are absent, restoring the functionality of the settings management UI.

## Prevention Strategies

- **Use `shared.env` for Infra only**: Only store configuration required for service discovery and orchestration in environment files.
- **Keep Application Config in JSON**: Continue using `settings.json` for domain-specific parameters that need to be mutable at runtime via the API.
- **Avoid Hardcoding in Templates**: Always inject environment-dependent URLs into frontends from the backend server.
- **Interpolation Fallbacks**: Always provide `:-default` fallbacks in `docker-compose.yml` to maintain file validity when environment files are missing or incomplete.
