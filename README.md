# AGI

[![Conventional Code](https://img.shields.io/badge/code-conventional%20🏭-red?style=for-the-badge)](https://github.com/zwbao/certified-organic-code)

**A**gent-driven  
**G**enetic-simulated  
**I**ndividual-organisms  

A simulation where individual entities evolve genetically, perceive their environment through a neural capability system, and make decisions via LLM reasoning.

## What it does

Each entity has three interacting layers:

- **Genetic** — heritable traits (lifespan, brain size, think interval, personality seed) that mutate across asexual reproduction
- **Neural** — a brain wired from a neuron pool using predefined Neuron Profiles. It evaluates sensory signals to compute outputs via bounded activation functions, generating a Capability Manifest each tick that describes available perceptions and actions. Genetic `COGNITIVE_CLARITY` determines how well the LLM interprets this manifest.
- **Agent** — an LLM (Anthropic, Ollama, OpenRouter, or LM Studio) reads the manifest and returns a JSON action

The world runs on a hybrid tick engine: world state advances synchronously every tick, while LLM calls happen asynchronously and are cached for the next tick.

## Running

### With Docker

```bash
docker-compose up
```

Services: Redis, FastAPI API (`:8000`), Quart web UI (`:5000`), simulation engine.

### Without Docker

```bash
pip install -e ".[dev]"
# Start Redis separately, then:
python engine.py          # simulation engine
uvicorn api.main:app      # REST API
hypercorn web.main:app    # web UI
```

Copy `.env.example` to `.env` and set `REDIS_URL` and any provider API keys.

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `REDIS_URL` | `redis://localhost:6379` | Redis connection string |
| `ANTHROPIC_API_KEY` | — | Anthropic API key |
| `OPENROUTER_API_KEY` | — | OpenRouter API key |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `INITIAL_ENTITIES` | `5` | Number of entities at simulation start |
| `TICK_INTERVAL_SEC` | `2.0` | Seconds between ticks |
| `VOID_WIDTH` / `VOID_HEIGHT` | `1000.0` | Void coordinate space dimensions |

## Tests

```bash
pytest
```

113 tests. Requires no external services (fakeredis used automatically).

## Architecture

See [`docs/solutions/best-practices/agi-entity-simulation-v1-architecture-2026-04-11.md`](docs/solutions/best-practices/agi-entity-simulation-v1-architecture-2026-04-11.md) for detailed design decisions, key patterns, and code examples.

## License

AGPLv3 — see [LICENSE](./LICENSE)

    Copyright (C) 2026  Iuri Guilherme
