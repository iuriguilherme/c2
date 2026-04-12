import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
import fakeredis
from fastapi.middleware.cors import CORSMiddleware
from api.routes.genes import router as genes_router
from api.routes.neurons import router as neurons_router
from api.routes.entities import router as entities_router, set_redis_client
from api.routes.ollama import router as ollama_router

logger = logging.getLogger(__name__)
redis_client = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis_client
    try:
        from redis.asyncio import Redis

        redis_url = "redis://localhost:6379"
        import json
        settings_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "settings.json")
        if os.path.exists(settings_path):
            try:
                with open(settings_path, "r") as f:
                    settings = json.load(f)
                    redis_url = settings.get("redis_url", redis_url)
            except Exception:
                pass

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


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
