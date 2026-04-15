import httpx
import pytest
try:
    import fakeredis.aioredis
except ImportError:
    pytest.skip("fakeredis not available", allow_module_level=True)

from api.main import app
from api.routes.simulation import get_redis

@pytest.fixture
async def fake_redis():
    r = fakeredis.aioredis.FakeRedis()
    yield r
    await r.aclose()

@pytest.fixture
def override_redis(fake_redis):
    app.dependency_overrides[get_redis] = lambda: fake_redis
    yield fake_redis
    app.dependency_overrides.pop(get_redis, None)

async def test_reset_simulation_endpoint(override_redis):
    """Happy path: test that the reset endpoint sets the simulation:command key."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/simulation/reset")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"

    # Verify redis key was set
    val = await override_redis.get("simulation:command")
    assert val.decode() == "reset"
