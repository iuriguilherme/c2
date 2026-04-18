---
title: Refactor Docker Compose Environment Variables
type: refactor
status: completed
date: 2026-04-18
---

# Refactor Docker Compose Environment Variables

## Overview

Move hardcoded environment variables out of `docker-compose.yml` and consolidate them into a single, version-controlled source of truth (`shared.env`). This reduces repetition and ensures consistent configuration across all containers.

## Problem Frame

The `docker-compose.yml` currently repeats identical `environment` block definitions for `REDIS_URL`, `MONGO_URL`, and `OLLAMA_BASE_URL` across `api`, `web`, and `engine` services. It also hardcodes `engine`-specific variables. Additionally, `OLLAMA_MODELS_DIR` is currently in `.env.example` but should be moved to the shared file since it doesn't contain sensitive information.

## Key Technical Decisions

- **File Naming**: Create `shared.env`. This avoids the `.*` match in `.gitignore` while communicating its purpose.
- **Variable Consolidation**: All non-sensitive operational environment variables move to `shared.env`.
- **Top-Level `env_file`**: Utilize Docker Compose's top-level `env_file` directive (supported in v2.24+) to ensure Compose itself can interpolate `OLLAMA_MODELS_DIR` for volume mounts, alongside using `env_file: shared.env` in individual services to inject variables into containers.

## Implementation Units

- [x] **Unit 1: Create shared environment file**

**Goal:** Establish the single source of truth for non-sensitive configuration.
**Files:**
- Create: `shared.env`
**Approach:**
- Populate with variables currently in `docker-compose.yml`:
  - `REDIS_URL=redis://redis:6379`
  - `MONGO_URL=mongodb://mongo:27017`
  - `OLLAMA_BASE_URL=http://ollama:11434` (Note: Update port to internal `11434` instead of `11435`)
  - `INITIAL_ENTITIES=5`
  - `TICK_INTERVAL_SEC=2.0`
  - `VOID_WIDTH=1000.0`
  - `VOID_HEIGHT=1000.0`
- Move `OLLAMA_MODELS_DIR=./ollama_models` from `.env.example` to `shared.env`.

- [x] **Unit 2: Clean up .env.example**

**Goal:** Remove redundant variables from the `.env` template.
**Files:**
- Modify: `.env.example`
**Approach:**
- Remove the `OLLAMA_MODELS_DIR` declaration and its comment.

- [x] **Unit 3: Update docker-compose.yml**

**Goal:** Wire all services to use `shared.env` and remove hardcoded environment blocks.
**Files:**
- Modify: `docker-compose.yml`
**Approach:**
- Add `env_file: - shared.env` at the root/top-level of the file to support compose-time interpolation (like `${OLLAMA_MODELS_DIR}`).
- Replace all `environment` sections in `api`, `web`, and `engine` services with `env_file: shared.env`.
- Keep the `ollama` service's `volumes` interpolation as-is (`${OLLAMA_MODELS_DIR:-./ollama/models}:/root/.ollama/models`), which will now resolve via the top-level `env_file`.

## System-Wide Impact

- **Docker Compose compatibility**: Requires `docker-compose` version 2.24 or newer for the top-level `env_file` directive. If an older version is used, developers might need to append `--env-file shared.env` to their commands.
- **Port Mapping**: Fixing `OLLAMA_BASE_URL` to point to the correct internal port (`11434`) prevents potential connection issues within the Docker network.
