---
title: Refactor Docker Compose Ports to Variables
type: refactor
status: completed
date: 2026-04-18
---

# Refactor Docker Compose Ports to Variables

## Overview

Differentiate internal and external ports for all services in `docker-compose.yml` and extract them into `shared.env`. Ensure that these variables can be overridden by a local `.env` file that is not maintained in version control.

## Problem Frame

Ports in `docker-compose.yml` are currently hardcoded, including the Ollama external port (which was previously changed to avoid conflicts). The ports should be referenced consistently across the Compose file and the application's configuration, differentiating between the port exposed to the host (external) and the port used within the container and Docker network (internal). Furthermore, the user needs to be able to override these variables via a local `.env` file.

## Key Technical Decisions

- **Extract Ports**: Move all port definitions into `shared.env`, explicitly naming them with `_PORT_EXTERNAL` and `_PORT_INTERNAL` suffixes.
- **Compose File Interpolation**: Update `docker-compose.yml` to use variable interpolation (e.g., `"${API_PORT_EXTERNAL}:${API_PORT_INTERNAL}"`) for the `ports` mapping.
- **Command Line Arguments**: Update `docker-compose.yml` command lines (for `api` and `web` services) to use the internal port variables.
- **URL Updates**: Update `OLLAMA_BASE_URL`, `REDIS_URL`, and `MONGO_URL` in `shared.env` to reference their respective internal ports.
- **Precedence Mechanism**: To allow a local `.env` to override `shared.env`, Docker Compose requires the user to specify both `env_file`s in the command (e.g., `docker compose --env-file shared.env --env-file .env up`), OR we can rely on Compose automatically reading `.env` by default, which overrides variables injected into the shell or specified in `env_file` inside services. We will define default fallback values in the compose file or simply document the requirement, but the primary task is to wire the variables correctly.
- **Service Env Files**: Include `env_file: - shared.env - .env` in the services if we want to pass both to containers, though docker-compose automatically passes `.env` values when used in interpolation. We'll use:
  ```yaml
  env_file:
    - shared.env
    - .env
  ```
  Wait, if `.env` is optional, `docker-compose` might fail if it doesn't exist. So we'll use `required: false` (in Docker Compose v2.24+) or just keep it simple. Actually, we don't strictly need to list `.env` in `env_file` for interpolation, but we should make sure the container gets the overrides. 

## Implementation Units

- [x] **Unit 1: Update shared.env with Port Variables**

**Goal:** Add internal and external port variables for all services.
**Files:**
- Modify: `shared.env`
**Approach:**
- Add variables for Redis, Mongo, API, Web, and Ollama.
  - `REDIS_PORT_EXTERNAL=6379`
  - `REDIS_PORT_INTERNAL=6379`
  - `MONGO_PORT_EXTERNAL=27017`
  - `MONGO_PORT_INTERNAL=27017`
  - `API_PORT_EXTERNAL=8000`
  - `API_PORT_INTERNAL=8000`
  - `WEB_PORT_EXTERNAL=5000`
  - `WEB_PORT_INTERNAL=5000`
  - `OLLAMA_PORT_EXTERNAL=11435`
  - `OLLAMA_PORT_INTERNAL=11434`
- Update URL variables to use the internal port variables:
  - `REDIS_URL=redis://${REDIS_PORT_INTERNAL}`
  - `MONGO_URL=mongodb://mongo:${MONGO_PORT_INTERNAL}`
  - `OLLAMA_BASE_URL=http://ollama:${OLLAMA_PORT_INTERNAL}`

- [x] **Unit 2: Update .env.example**

**Goal:** Provide an example of overriding the variables.
**Files:**
- Modify: `.env.example`
**Approach:**
- Add an example showing how to override `OLLAMA_PORT_EXTERNAL` and point out that `.env` is ignored by Git and can be used for local overrides.

- [x] **Unit 3: Update docker-compose.yml**

**Goal:** Wire `docker-compose.yml` to use the new port variables.
**Files:**
- Modify: `docker-compose.yml`
**Approach:**
- In the `ports:` sections for each service, use the pattern `"${SERVICE_PORT_EXTERNAL:-default}:${SERVICE_PORT_INTERNAL:-default}"` to provide a fallback in case `shared.env` isn't loaded into the Compose CLI's environment, ensuring the file remains valid.
- Update the `command:` overrides for `api` and `web` to use `${API_PORT_INTERNAL:-8000}` and `${WEB_PORT_INTERNAL:-5000}` respectively.
- For `env_file` within each service, keep `shared.env` and add `.env` (using the modern syntax where possible, though we'll just stick to `shared.env` to avoid "file not found" errors on older Compose versions, as Docker automatically loads `.env`).
