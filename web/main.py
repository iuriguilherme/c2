import os
from quart import Quart, render_template, jsonify
import redis.asyncio as aioredis
from storage.redis import RedisEntityRepository, RedisTickStream

app = Quart(__name__, template_folder="templates")
_redis: aioredis.Redis | None = None


@app.before_serving
async def startup() -> None:
    global _redis
    _redis = aioredis.from_url(
        os.environ.get("REDIS_URL", "redis://localhost:6379"),
        decode_responses=False,
    )


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
    entities = []
    for eid in living_ids:
        data = await repo.load(eid)
        if data:
            entities.append({
                "id": data["id"],
                "age": data.get("age", "0"),
                "position_x": data.get("position_x", "0"),
                "position_y": data.get("position_y", "0"),
                "model": data.get("model", ""),
                "provider": data.get("provider", ""),
                "alive": data.get("alive", "True"),
            })
    recent_ticks = await stream.read_recent(count=5)
    current_tick = int(recent_ticks[-1]["tick"]) if recent_ticks else 0
    return jsonify({"tick": current_tick, "entities": entities})
