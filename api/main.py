import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
import fakeredis
from fastapi.middleware.cors import CORSMiddleware
from api.routes.genes import router as genes_router
from api.routes.neurons import router as neurons_router
from api.routes.neurons import set_redis_client as set_neurons_redis_client
from api.routes.entities import router as entities_router, set_redis_client
from api.routes.ollama import router as ollama_router
from api.routes.settings import router as settings_router
from api.routes.openrouter import router as openrouter_router
from api.routes.lmstudio import router as lmstudio_router
from api.routes.simulation import router as simulation_router
from api.routes.simulation import set_redis_client as set_simulation_redis_client
from api.routes.system_prompts import router as system_prompts_router

logger = logging.getLogger(__name__)
redis_client = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis_client
    try:
        from redis.asyncio import Redis

        redis_url = "redis://localhost:6379"
        import json
        _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        for settings_path in (
            os.path.join(_root, "settings.json"),
            os.path.join(_root, "settings.example.json"),
        ):
            if os.path.exists(settings_path):
                try:
                    with open(settings_path, "r") as f:
                        settings = json.load(f)
                        redis_url = settings.get("redis_url", redis_url)
                    break
                except Exception as exc:
                    logger.warning(
                        "Failed to load Redis settings from %s (%s: %s) — using defaults/environment overrides.",
                        settings_path, type(exc).__name__, exc,
                    )

        redis_url = os.environ.get("REDIS_URL", redis_url)

        redis_client = Redis.from_url(redis_url)
        await redis_client.ping()
    except Exception as exc:
        logger.warning(
            "Redis unavailable (%s: %s) — falling back to in-process fakeredis. "
            "All entity data will be lost on restart.",
            type(exc).__name__, exc,
        )
        redis_client = fakeredis.FakeAsyncRedis()
    set_redis_client(redis_client)
    set_simulation_redis_client(redis_client)
    set_neurons_redis_client(redis_client)
    set_settings_redis_client(redis_client)

    try:
        # Seed pool data into Redis if empty
        from storage.redis import RedisPoolRepository
        import json
        repo = RedisPoolRepository(redis_client)
        
        neurons = await repo.get_all_neurons()
        if not neurons:
            neuron_pool_path = os.path.join(_root, "data", "neuron_pool.json")
            if os.path.exists(neuron_pool_path):
                with open(neuron_pool_path, "r") as f:
                    raw_neurons = json.load(f)
                    for n in raw_neurons:
                        await repo.save_neuron(n["neuron_type"], n)
        
        profiles = await repo.get_all_profiles()
        if not profiles:
            profiles_path = os.path.join(_root, "data", "neuron_profiles.json")
            if os.path.exists(profiles_path):
                with open(profiles_path, "r") as f:
                    raw_profiles = json.load(f)
                    for p in raw_profiles:
                        await repo.save_profile(p["id"], p)
                        
    except Exception as exc:
        logger.error("Failed to seed RedisPoolRepository: %s", exc)

    try:
        from storage.mongo import init_mongo
        await init_mongo()
    except Exception as exc:
        logger.error("Failed to initialize MongoDB/Beanie: %s", exc)
        raise

    yield
    if redis_client is not None:
        await redis_client.aclose()


app = FastAPI(title="AGI Simulation API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(genes_router)
app.include_router(neurons_router)
app.include_router(entities_router)
app.include_router(ollama_router)
app.include_router(settings_router)
app.include_router(openrouter_router)
app.include_router(lmstudio_router)
app.include_router(simulation_router)
app.include_router(system_prompts_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
ct:
    return {"status": "ok"}
