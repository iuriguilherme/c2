#!/usr/bin/env python3
"""
Simulation Engine — entry point.

Usage:
    python engine.py

Environment:
    REDIS_URL           Redis connection string (default: redis://localhost:6379)
    OLLAMA_BASE_URL     Ollama server URL (default: http://localhost:11434)
    VOID_WIDTH          Width of void space (default: 1000.0)
    VOID_HEIGHT         Height of void space (default: 1000.0)
    INITIAL_ENTITIES    Number of starting entities (default: 5)
    TICK_INTERVAL_SEC   Seconds between ticks (default: 2.0)
"""
import asyncio
import logging
import os
import random
from dotenv import load_dotenv
import redis.asyncio as aioredis

from genetics import GenePool
from neural.pool import NeuronPool
from agents.pool import ModelPool
from agents.providers.ollama import OllamaProvider
from agents.providers.openrouter import OpenRouterProvider
from agents.providers.anthropic import AnthropicProvider
from agents.providers.lmstudio import LMStudioProvider
from environment.void import VoidEnvironment, Position
from simulation.factory import EntityFactory
from simulation.reproduction import ReproductionHandler
from simulation.tick import TickEngine
from storage.redis import RedisEntityRepository, RedisTickStream

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def main() -> None:
    import json
    _root = os.path.dirname(os.path.abspath(__file__))
    settings = {}
    for settings_path in (
        os.path.join(_root, "settings.json"),
        os.path.join(_root, "settings.example.json"),
    ):
        if os.path.exists(settings_path):
            try:
                with open(settings_path, "r") as f:
                    settings = json.load(f)
                break
            except Exception as e:
                logger.error(f"Failed to read {settings_path}: {e}")

    # Fallback order: os.environ overrides -> settings.json -> hardcoded defaults
    redis_url = os.environ.get("REDIS_URL", settings.get("redis_url", "redis://localhost:6379"))
    void_w = float(os.environ.get("VOID_WIDTH", settings.get("void_width", 1000.0)))
    void_h = float(os.environ.get("VOID_HEIGHT", settings.get("void_height", 1000.0)))
    n_entities = int(os.environ.get("INITIAL_ENTITIES", settings.get("initial_entities", 5)))
    tick_interval = float(os.environ.get("TICK_INTERVAL_SEC", settings.get("tick_interval_sec", 2.0)))
    ollama_base_url = os.environ.get("OLLAMA_BASE_URL", settings.get("ollama_base_url", "http://localhost:11434"))
    lmstudio_base_url = os.environ.get("LMSTUDIO_BASE_URL", settings.get("lmstudio_base_url", "http://localhost:1234"))
    allowed_providers = settings.get("allowed_providers", ["ollama", "openrouter", "lmstudio", "anthropic"])

    redis = aioredis.from_url(redis_url, decode_responses=False)
    repo = RedisEntityRepository(redis)
    stream = RedisTickStream(redis)
    void = VoidEnvironment(width=void_w, height=void_h)

    gene_pool = GenePool.load()
    neuron_pool = NeuronPool.load()

    all_providers = [
        OllamaProvider(base_url=ollama_base_url),
        OpenRouterProvider(),
        LMStudioProvider(base_url=lmstudio_base_url),
        AnthropicProvider(),
    ]
    providers = [p for p in all_providers if p.name in allowed_providers]
    model_pool = ModelPool()
    await model_pool.discover(providers)

    if model_pool.size == 0:
        fallback_added = False
        for provider_name in allowed_providers:
            if provider_name == "ollama":
                default_settings = settings.get("ollama_default_model", {"text": "llama3.2"})
                default_model = default_settings.get("text", "llama3.2") if isinstance(default_settings, dict) else default_settings
                logger.warning(f"No models available — using Ollama with {default_model} as fallback")
                p = next(p for p in all_providers if p.name == "ollama")
                model_pool._pool.append((p, default_model))
                fallback_added = True
                break
            elif provider_name == "openrouter":
                default_settings = settings.get("openrouter_default_model", {"text": "openai/gpt-4o-mini"})
                default_model = default_settings.get("text", "openai/gpt-4o-mini") if isinstance(default_settings, dict) else default_settings
                logger.warning(f"No models available — using OpenRouter with {default_model} as fallback")
                p = next(p for p in all_providers if p.name == "openrouter")
                model_pool._pool.append((p, default_model))
                fallback_added = True
                break
            elif provider_name == "lmstudio":
                default_settings = settings.get("lmstudio_default_model", {"text": "llama-3"})
                default_model = default_settings.get("text", "llama-3") if isinstance(default_settings, dict) else default_settings
                logger.warning(f"No models available — using LM Studio with {default_model} as fallback")
                p = next(p for p in all_providers if p.name == "lmstudio")
                model_pool._pool.append((p, default_model))
                fallback_added = True
                break

        if not fallback_added:
            logger.warning("No models available and no viable fallback found — using Ollama with llama3.2")
            p = next(p for p in all_providers if p.name == "ollama")
            model_pool._pool.append((p, "llama3.2"))

    factory = EntityFactory(gene_pool=gene_pool, neuron_pool=neuron_pool)
    reproduction_handler = ReproductionHandler(
        repo=repo,
        void=void,
        factory=factory,
        gene_pool=gene_pool,
        model_pool=model_pool,
    )
    engine = TickEngine(
        repo=repo,
        stream=stream,
        void=void,
        model_pool=model_pool,
        neuron_pool=neuron_pool,
        reproduction_handler=reproduction_handler,
    )

    rng = random.Random()
    for i in range(n_entities):
        genome = gene_pool.default_genome()
        assignment = model_pool.assign_random(rng=rng)
        entity = factory.create(
            entity_id=f"entity-{i}",
            genome=genome,
            model_assignment=assignment,
            rng=rng,
        )
        entity.position_x = rng.uniform(0, void_w)
        entity.position_y = rng.uniform(0, void_h)
        await repo.save(entity.id, entity.to_storage_dict())
        void.set_position(entity.id, Position(entity.position_x, entity.position_y))
        logger.info(
            "Spawned %s using %s/%s", entity.id, assignment.provider_name, assignment.model
        )

    tick = 0
    logger.info(
        "Simulation started — %d entities, tick interval %.1fs", n_entities, tick_interval
    )

    while True:
        tick += 1
        await engine.tick(tick=tick)
        living = await repo.list_living()
        logger.info("Tick %d — %d entities alive", tick, len(living))
        await asyncio.sleep(tick_interval)


if __name__ == "__main__":
    asyncio.run(main())
