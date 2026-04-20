import pytest
from httpx import AsyncClient, ASGITransport
import fakeredis.aioredis
from api.main import app
from api.routes.neurons import get_redis

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


@pytest.mark.asyncio
async def test_health():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_get_gene_pool():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/genes/")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 7
    types = [g["gene_type"] for g in data]
    assert "lifespan" in types


@pytest.mark.asyncio
async def test_get_neuron_pool(override_redis):
    # Seed fake redis with JSON
    import json, os
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    from storage.redis import RedisPoolRepository
    repo = RedisPoolRepository(override_redis)
    with open(os.path.join(_root, "data", "neuron_pool.json"), "r") as f:
        raw = json.load(f)
        for n in raw:
            await repo.save_neuron(n["neuron_type"], n)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/neurons/")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 7
    types = [n["neuron_type"] for n in data]
    assert "locomotion" in types


@pytest.mark.asyncio
async def test_get_gene_by_type():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/genes/lifespan")
    assert r.status_code == 200
    assert r.json()["gene_type"] == "lifespan"


@pytest.mark.asyncio
async def test_get_gene_not_found():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/genes/nonexistent")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_post_profile_sets_default_and_unsets_others(override_redis):
    from storage.redis import RedisPoolRepository

    repo = RedisPoolRepository(override_redis)

    # Seed two existing profiles, both non-default initially
    profiles_seed = [
        {
            "id": "profile-a",
            "name": "Profile A",
            "description": "First profile",
            "neurons": ["locomotion"],
            "activation_function": "tanh",
            "is_default": True,
        },
        {
            "id": "profile-b",
            "name": "Profile B",
            "description": "Second profile",
            "neurons": ["proximity"],
            "activation_function": "tanh",
            "is_default": False,
        },
    ]
    for p in profiles_seed:
        await repo.save_profile(p["id"], p)

    # Post a new profile that should become the default
    new_profile = {
        "id": "profile-c",
        "name": "Profile C",
        "description": "New default profile",
        "neurons": ["signal_receiver"],
        "activation_function": "sigmoid",
        "is_default": True,
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/neurons/profiles", json=new_profile)

    assert r.status_code == 200
    assert r.json()["id"] == "profile-c"
    assert r.json()["is_default"] is True

    # Verify that only profile-c is default; profile-a (previously default) is now False
    all_profiles = await repo.get_all_profiles()
    assert all_profiles["profile-c"]["is_default"] is True
    assert all_profiles["profile-a"]["is_default"] is False
    assert all_profiles["profile-b"]["is_default"] is False
