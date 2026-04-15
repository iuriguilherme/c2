#!/usr/bin/env python3
"""
Simulation Engine — entry point.

Usage:
    python engine.py

Environment:
    REDIS_URL                   Redis connection string (default: redis://localhost:6379)
    OLLAMA_BASE_URL             Ollama server URL (default: http://localhost:11434)
    VOID_WIDTH                  Width of void space (default: 1000.0)
    VOID_HEIGHT                 Height of void space (default: 1000.0)
    INITIAL_ENTITIES            Number of starting entities (default: 5)
    TICK_INTERVAL_SEC           Seconds between ticks (default: 2.0)
    SPAWN_RATE_CAP_PERCENT      Max offspring spawned per tick as % of population (0-100, default: 5.0)
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
    spawn_rate_cap_percent = float(os.environ.get("SPAWN_RATE_CAP_PERCENT", settings.get("spawn_rate_cap_percent", 5.0)))
    ollama_base_url = os.environ.get("OLLAMA_BASE_URL", settings.get("ollama_base_url", "http://localhost:11434"))
    lmstudio_base_url = os.environ.get("LMSTUDIO_BASE_URL", settings.get("lmstudio_base_url", "http://localhost:1234"))
    allowed_providers = settings.get("allowed_providers", ["ollama", "openrouter", "lmstudio", "anthropic"])

    try:
        from storage.mongo import init_mongo
        await init_mongo()
    except Exception as exc:
        logger.error(f"Failed to initialize MongoDB/Beanie: {exc}")

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
    await model_pool.discover(providers, settings=settings)

    if model_pool.size == 0:
        logger.error("No models configured. Please check settings.json.")
        raise RuntimeError("No models configured in settings. Please configure allowed models or a default model for at least one allowed provider.")

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
        spawn_rate_cap_percent=spawn_rate_cap_percent,
    )

    rng = random.Random()

    async def _spawn_initial():
        from storage.mongo import SystemPrompt

        # Pre-fetch default prompts
        default_prompts = await SystemPrompt.find({"is_default": True}).to_list()

        for i in range(n_entities):
            genome = gene_pool.default_genome()
            assignment = model_pool.assign_random(rng=rng)

            sys_prompt = ""
            if default_prompts:
                p = rng.choice(default_prompts)
                sys_prompt = (
                    f"{p.content}\n\n"
                    f"You exist in a void simulation. Each tick you receive a Capability Manifest "
                    f"describing what you can perceive and what actions are available to you. "
                    f"Respond with valid JSON: "
                    '{"action": {"type": "<action_type>", "parameters": {...}}, '
                    '"user_prompt_update": "<optional reflection>"}'
                )

            entity = factory.create(
                entity_id=f"entity-{i}",
                genome=genome,
                model_assignment=assignment,
                rng=rng,
                system_prompt=sys_prompt
            )
            entity.position_x = rng.uniform(0, void_w)
            entity.position_y = rng.uniform(0, void_h)
            await repo.save(entity.id, entity.to_storage_dict())
            void.set_position(entity.id, Position(entity.position_x, entity.position_y))
            logger.info(
                "Spawned %s using %s/%s", entity.id, assignment.provider_name, assignment.model
            )

    await _spawn_initial()

    tick = 0
    logger.info(
        "Simulation started — %d entities, tick interval %.1fs", n_entities, tick_interval
    )

    while True:
        command = await redis.get("simulation:command")
        if command and command.decode() == "reset":
            logger.info("Resetting simulation state...")
            await redis.delete("simulation:command")

            # Clear all relevant data
            await redis.delete("living_entities")
            await redis.delete("ticks:main")

            keys_to_delete = []
            async for key in redis.scan_iter("entity:*"):
                keys_to_delete.append(key)
            async for key in redis.scan_iter("archive:*"):
                keys_to_delete.append(key)
            if keys_to_delete:
                await redis.delete(*keys_to_delete)

            void._positions.clear()
            void._message_inbox.clear()
            tick = 0
            engine.current_tick = 0

            await _spawn_initial()
            logger.info("Simulation reset complete.")
            continue

        tick += 1
        await engine.tick(tick=tick)
        living = await repo.list_living()
        logger.info("Tick %d — %d entities alive", tick, len(living))
        await asyncio.sleep(tick_interval)


if __name__ == "__main__":
    asyncio.run(main())
