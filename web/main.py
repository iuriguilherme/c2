import os
from quart import Quart, render_template, jsonify
import redis.asyncio as aioredis
from storage.redis import RedisEntityRepository, RedisTickStream

app = Quart(__name__, template_folder="templates")
_redis: aioredis.Redis | None = None


@app.before_serving
async def startup() -> None:
    global _redis

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
            except Exception:
                app.logger.exception(
                    "Failed to load Redis settings from %s; falling back to defaults",
                    settings_path,
                )

    redis_url = os.environ.get("REDIS_URL", redis_url)

    _redis = aioredis.from_url(redis_url, decode_responses=False)


@app.after_serving
async def shutdown() -> None:
    if _redis:
        await _redis.aclose()


@app.route("/")
async def index():
    return await render_template("index.html")


@app.route("/api/state")
async def state():
    if not _redis:
        return jsonify({"error": "not ready"}), 503
    repo = RedisEntityRepository(_redis)
    stream = RedisTickStream(_redis)
    living_ids = await repo.list_living()
    raw_entities = await repo.load_many(living_ids)
    entities = [
        {
            "id": data["id"],
            "age": data.get("age", "0"),
            "position_x": data.get("position_x", "0"),
            "position_y": data.get("position_y", "0"),
            "model": data.get("model", ""),
            "provider": data.get("provider", ""),
            "alive": data.get("alive", "True"),
        }
        for data in raw_entities
    ]
    recent_ticks = await stream.read_recent(count=5)
    current_tick = int(recent_ticks[-1]["tick"]) if recent_ticks else 0
    return jsonify({"tick": current_tick, "entities": entities})
