---
date: 2026-04-13
topic: docker-settings-errors
---

# Fix Unhelpful Error Messages When Settings Fail to Load in Docker

## Problem Frame

When running the web app via Docker, the frontend cannot reach the API service on port 8000. Every settings-related fetch fails with `net::ERR_EMPTY_RESPONSE`. The user sees:

- "Error: Failed to fetch" next to save buttons
- "Error loading models: Failed to fetch" in the Ollama table
- Empty/missing settings data with no explanation

The current error messages don't tell the user **what** failed, **why**, or **what to check**. The only way to investigate is to open the browser console, where you find a wall of identical red `ERR_EMPTY_RESPONSE` errors — still without actionable guidance.

On the backend, `get_settings_data()` in every route file silently swallows exceptions (`except Exception: pass`), so even server-side logs provide no clues.

## Requirements

- R1. **Visible API connection status** — The web UI should clearly indicate whether it can reach the API service, rather than silently showing empty data.

- R2. **Actionable error messages** — When a settings load or save fails, the error shown in the UI should include the URL that was called and a hint about what to check (e.g., "Cannot reach API at http://localhost:8000 — is the api service running?").

- R3. **Backend error logging** — The `get_settings_data()` functions in route files should log when settings fail to load instead of silently returning empty dicts.

- R4. **Retry on initial load** — When the web page loads before the API is ready (common with Docker Compose startup ordering), the settings loaders should retry a few times before showing an error.

## Success Criteria

- When the API is unreachable, the user can tell immediately from the web UI without opening the browser console
- Error messages name the failing URL and suggest what to check
- Backend logs show when and why settings file loading fails
- If the API starts a few seconds after the web frontend, settings eventually load automatically

## Scope Boundaries

- Do NOT refactor settings into a centralized module (that's a separate improvement)
- Do NOT change `.gitignore` or Docker volume mounts
- Do NOT change the settings file format or structure
- Do NOT add new API endpoints

## Next Steps

→ `/ce:plan` for structured implementation planning
