---
title: Docker Environment Priority Chain — Missing env Checks in entities.py and Entry Points
date: 2026-04-18
category: integration-issues
module: devops
problem_type: integration_issue
component: development_workflow
severity: high
symptoms:
  - LLM provider URLs resolve to localhost inside Docker containers, making them unreachable
  - api/routes/entities.py ignores OLLAMA_BASE_URL and LMSTUDIO_BASE_URL set in shared.env
  - Services started outside Docker do not load shared.env baseline configuration
  - settings.json contained redis_url, ollama_base_url, api_base_url duplicating shared.env
root_cause: config_error
resolution_type: code_fix
tags:
  - docker
  - environment-variables
  - configuration
  - dotenv
  - settings
  - ollama
  - lmstudio
---

# Docker Environment Priority Chain — Missing env Checks in entities.py and Entry Points

## Problem

After the Docker environment refactor established `shared.env` as the infrastructure config baseline, `api/routes/entities.py` still read provider URLs directly from `settings.json`, bypassing `OLLAMA_BASE_URL` and `LMSTUDIO_BASE_URL`. Additionally, `api/main.py` and `web/main.py` had no `load_dotenv` calls, so running outside Docker never populated those env vars from `shared.env`.

## Symptoms

- LLM provider calls routed to `http://localhost:11434` (or `:1234`) inside Docker containers, which cannot reach the host
- `OLLAMA_BASE_URL` and `LMSTUDIO_BASE_URL` set in `shared.env` had no effect on entity-creation code paths
- Running outside Docker, env vars from `shared.env` were never populated — only `.env` was loaded, and only in `engine.py`
- `settings.json` contained `redis_url`, `ollama_base_url`, and `api_base_url` duplicating `shared.env`, creating two competing sources of truth for infrastructure config

## What Didn't Work

- The Docker environment refactor correctly introduced the `env > settings > default` pattern in `engine.py`, `api/routes/ollama.py`, and `api/routes/lmstudio.py`, but did not audit every file that instantiates providers — `api/routes/entities.py` was missed (session history: this file was authored in a GitHub Copilot PR, commit `c72addc`, outside the Claude Code workflow and not reviewed for env consistency)
- `api/main.py` and `web/main.py` had no `load_dotenv` call at all; non-Docker invocations relied on the shell environment having vars pre-set
- `api_base_url` in `settings.json` was already dead code (`web/main.py` derives the URL from `API_PORT_EXTERNAL`, see `web/main.py:46-47`), but its presence implied it was still in use and obscured the actual source of truth

## Solution

**Entry points — load `shared.env` as baseline, `.env` as local override:**

```python
# engine.py, api/main.py, web/main.py — add before any os.environ.get() calls
from dotenv import load_dotenv
load_dotenv("shared.env")          # infra baseline; won't override vars Docker already set
load_dotenv(".env", override=True) # developer-local overrides win over shared.env
```

**`api/routes/entities.py` — apply the standard precedence chain:**

```python
# BEFORE (bypasses env vars entirely):
OllamaProvider(base_url=settings.get("ollama_base_url", "http://localhost:11434"))
LMStudioProvider(base_url=settings.get("lmstudio_base_url", "http://localhost:1234"))

# AFTER (consistent with engine.py and other route files):
OllamaProvider(
    base_url=os.environ.get(
        "OLLAMA_BASE_URL",
        settings.get("ollama_base_url", "http://localhost:11434")
    )
)
LMStudioProvider(
    base_url=os.environ.get(
        "LMSTUDIO_BASE_URL",
        settings.get("lmstudio_base_url", "http://localhost:1234")
    )
)
```

**`settings.json` — remove infra URL keys, keep only host-only entries:**

Removed `redis_url`, `ollama_base_url`, `api_base_url` — defined authoritatively in `shared.env`.

Keep `lmstudio_base_url` — LM Studio is a host-only desktop app with no Docker Compose service entry. The general rule is: infrastructure URLs for services with a Compose entry belong in `shared.env`; URLs for host-only tools with no Compose entry may stay in `settings.json` until added as a service.

## Why This Works

`load_dotenv` does not override variables already present in the environment, so calling `load_dotenv("shared.env")` in entry points is safe under Docker (where `shared.env` values are injected by Compose as real env vars before Python starts — the call is effectively a no-op). The `.env` load with `override=True` runs second, letting developer-local values take precedence without affecting Docker. The `os.environ.get > settings.get > hardcoded` chain ensures Docker-supplied URLs are always preferred over values baked into `settings.json`. Removing infra URLs from `settings.json` eliminates the ambiguity of two places supplying a URL with no clear winner.

**Caveat — outside Docker:** `shared.env` uses `${VAR}` interpolation (e.g., `OLLAMA_BASE_URL=http://ollama:${OLLAMA_PORT_INTERNAL}`) that Docker Compose expands but `python-dotenv` does not. Outside Docker, `load_dotenv("shared.env")` sets these as literal unexpanded strings AND Docker-internal hostnames (`ollama`, `redis`) which are unreachable from the host. A `.env` file with host-accessible overrides (e.g., `OLLAMA_BASE_URL=http://localhost:11434`) is required for non-Docker execution. The `load_dotenv(".env", override=True)` call applies these overrides correctly.

## Prevention

- When introducing a configuration precedence pattern across a codebase, search all files for the affected config keys before closing — a search for `settings.get("ollama_base_url"` would have caught the missed file immediately
- In code review: any `settings.get` call for a key that exists in `shared.env` is a bug; `os.environ.get` must be the first lookup
- Keep `settings.json` strictly for runtime simulation parameters (agent counts, tick rates, model names). Infrastructure endpoints belong exclusively in `shared.env` or `.env`
- The three entry points (`engine.py`, `api/main.py`, `web/main.py`) must call `load_dotenv("shared.env")` then `load_dotenv(".env", override=True)` before any `os.environ.get` calls; route files (e.g., `api/routes/entities.py`) do not need this since they run within the same process after the entry point has already populated the environment. Use `Path(__file__).parent / "shared.env"` if invocation from a non-root working directory is possible.
- Add startup logging of resolved provider URLs so misconfiguration surfaces on launch rather than at first LLM call

## Related Issues

- `docs/solutions/refactors/docker-environment-refactor-2026-04-18.md` — predecessor refactor that established `shared.env` as infra config baseline; this fix documents incomplete application of that refactor in code
- `docs/solutions/runtime-errors/docker-api-crash-fakeredis-missing-2026-04-14.md` — related Docker startup failures with similar route-level `settings.json` reads for LLM URLs
