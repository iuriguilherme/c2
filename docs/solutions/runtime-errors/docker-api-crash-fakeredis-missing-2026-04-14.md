---
title: "Docker API crash: fakeredis missing from requirements.txt"
module: api
category: runtime-errors
tags:
  - docker
  - dependencies
  - settings
  - error-handling
  - fakeredis
  - requirements
problem_type: missing_dependency
date: 2026-04-14
severity: high
components:
  - api/main.py
  - api/routes/settings.py
  - api/routes/ollama.py
  - api/routes/openrouter.py
  - api/routes/lmstudio.py
  - web/templates/index.html
  - requirements.txt
---

# Docker API Crash: fakeredis Missing from requirements.txt

## Problem

When running the application via `docker compose up`, the web frontend at `localhost:5000` showed settings as empty and the browser console displayed `net::ERR_EMPTY_RESPONSE` for every request to `localhost:8000`. No actionable error was shown in the UI — only the generic browser message "Failed to fetch".

### Symptoms

- Web UI loads but all settings fields are empty
- Browser console shows `net::ERR_EMPTY_RESPONSE` for `GET http://localhost:8000/health`
- No error banner or status indicator in the UI
- `docker compose ps` shows all containers as "Up" (misleading)
- Backend logs show only the crash traceback, not visible from the web UI

### Misleading Signals

- All containers reported as "Up" in `docker compose ps` because the reloader process (PID 1) stayed alive even though the worker process crashed
- The web UI gave no indication that the API was unreachable — it just silently failed
- Backend route files used `except Exception: pass`, hiding the real error from logs

## Root Cause

`api/main.py` line 5 imports `fakeredis` unconditionally at the top level as a Redis fallback. However, `fakeredis` was never added to `requirements.txt`. The Docker image build succeeded (no install-time error), but the API container crashed immediately on startup with:

```
ModuleNotFoundError: No module named 'fakeredis'
```

The uvicorn reloader process (PID 1) stayed alive, so Docker reported the container as "Up" even though no HTTP server was actually listening on port 8000.

## Investigation Steps

1. **Started from the user report**: "settings are not loading in the web app when using docker and the error messages don't explain what is going on"
2. **Inspected the web UI**: Confirmed empty settings, saw `ERR_EMPTY_RESPONSE` in console
3. **Checked `docker compose ps`**: All 5 containers showed "Up" — misleading
4. **Ran `docker compose logs api --tail 50`**: Found the `ModuleNotFoundError: No module named 'fakeredis'` traceback
5. **Checked `requirements.txt`**: Confirmed `fakeredis` was absent
6. **Added `fakeredis>=2.26` to requirements.txt and rebuilt**: API started successfully, `GET /health` returned `{"status":"ok"}`

## Solution

### 1. Add missing dependency (root cause fix)

```diff
# requirements.txt
 # Storage
 redis[hiredis]>=5.2
+fakeredis>=2.26
```

### 2. Add backend logging to all route files

Replaced silent `except Exception: pass` with `logger.warning()` in `get_settings_data()` across 4 route files (`settings.py`, `ollama.py`, `openrouter.py`, `lmstudio.py`):

```python
import logging
logger = logging.getLogger(__name__)

def get_settings_data() -> dict:
    for path in (SETTINGS_FILE, SETTINGS_EXAMPLE_FILE):
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    return json.load(f)
            except Exception as exc:
                logger.warning(
                    "Failed to load settings from %s (%s: %s)",
                    path, type(exc).__name__, exc,
                )
    logger.warning(
        "No settings file found; searched %s and %s",
        SETTINGS_FILE, SETTINGS_EXAMPLE_FILE,
    )
    return {}
```

### 3. Add API connection status banner to web UI

Added a colored status bar at the top of `index.html` with three states:

- **Green (connected)**: `✓ API connected at http://localhost:8000`
- **Yellow (retrying)**: `⟳ API not reachable — retry 2/5 in 3s...`
- **Red (disconnected)**: `✗ Cannot reach API — Check: docker compose logs api`

### 4. Add actionable error messages

Created `formatApiError(url, err)` that translates browser errors into Docker-specific guidance:

```javascript
function formatApiError(url, err) {
  if (err instanceof TypeError && err.message === 'Failed to fetch') {
    return `Cannot reach API at ${url} — is the api service running? Check: docker compose ps`;
  }
  if (err.message && err.message.includes('ERR_EMPTY_RESPONSE')) {
    return `API at ${url} returned empty response — Check: docker compose logs api`;
  }
  return `Request to ${url} failed: ${err.message}`;
}
```

### 5. Add retry logic for Docker startup ordering

```javascript
const RETRY_DELAYS = [2000, 3000, 5000, 8000, 13000]; // 5 retries

async function initialConnect() {
  const ok = await checkApiHealth();
  if (!ok && retryCount < RETRY_DELAYS.length) {
    const delay = RETRY_DELAYS[retryCount];
    retryCount++;
    retryTimer = setTimeout(initialConnect, delay);
  }
}
```

Settings only load after the API health check succeeds, preventing the wall of console errors during Docker startup.

## Review Findings (Fixed)

- **XSS risk**: `loadOllamaModels()` used `innerHTML` with `formatApiError()` output — switched to `textContent` via DOM methods
- **Timer leak**: Retry timer wasn't cleared when `checkApiHealth()` detected reconnection — added `clearTimeout(retryTimer)` on success

## Prevention

### 1. Always check imports against requirements.txt

When adding a new `import` at the top of any Python file, verify the package is listed in `requirements.txt`. This is especially critical for packages used as fallbacks (like `fakeredis`) that may work in development (where installed via pip) but fail in Docker (where only `requirements.txt` is installed).

### 2. Never use bare `except: pass` in settings loading

Silent exception swallowing makes debugging impossible in containerized environments where you can't easily attach a debugger. Always log at minimum `logger.warning()` with the exception details.

### 3. Test Docker builds end-to-end

After modifying dependencies, always run `docker compose up --build` and verify the service actually responds, not just that the container is "Up". The uvicorn reloader masks crashes by keeping PID 1 alive.

### 4. Add health check endpoints

The `/health` endpoint was already present but wasn't being used by the frontend. Connecting the health check to a visible status indicator catches connectivity issues immediately.

## Related

- Commit: `e847144` — fix: Docker settings not loading
- Requirements doc: `docs/brainstorms/2026-04-13-docker-settings-errors-requirements.md`
