"""Tests for the /entities/archived/{entity_id} endpoint and AnthropicProvider models."""

import httpx
import pytest

try:
    import fakeredis.aioredis
except ImportError:
    pytest.skip("fakeredis not available", allow_module_level=True)

from api.main import app
from api.routes.entities import get_redis
from agents.providers.anthropic import AnthropicProvider
from storage.redis import RedisEntityRepository


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


async def test_get_archived_entity_found(override_redis):
    """Happy path: returns 200 with entity dict when archive entry exists."""
    repo = RedisEntityRepository(override_redis)
    entity_data = {"id": "ent-001", "alive": "False", "tick_born": "1"}
    # Archive directly: save then archive
    await repo.save("ent-001", {**entity_data, "alive": "False"})
    await repo.archive("ent-001")

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/entities/archived/ent-001")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "ent-001"


async def test_get_archived_entity_not_found(override_redis):
    """Error path: returns 404 when no archive entry exists for unknown id."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/entities/archived/unknown-999")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


async def test_anthropic_provider_no_invalid_model_id():
    """Verify get_available_models() does not contain 'claude-opus-4-6'."""
    provider = AnthropicProvider(api_key="dummy")
    models = await provider.get_available_models()
    assert "claude-opus-4-6" not in models
    # Confirm valid IDs are present
    assert "claude-opus-4-5" in models
    assert "claude-sonnet-4-6" in models

async def test_get_entity_found(override_redis):
    """Happy path: returns 200 with entity dict when entity exists."""
    repo = RedisEntityRepository(override_redis)
    entity_data = {"id": "ent-002", "alive": "True", "tick_born": "1", "age": "5"}
    await repo.save("ent-002", entity_data)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/entities/ent-002")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "ent-002"
    assert body["age"] == "5"

async def test_get_entity_not_found(override_redis):
    """Error path: returns 404 when entity doesn't exist."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/entities/nonexistent-123")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()

async def test_add_entity_random(override_redis):
    """Happy path: test spawning a fully random entity."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/entities/", json={})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "entity_id" in body

    # Verify entity was saved to redis
    repo = RedisEntityRepository(override_redis)
    data = await repo.load(body["entity_id"])
    assert data is not None
    assert data["id"] == body["entity_id"]

async def test_add_entity_configured(override_redis):
    """Happy path: test spawning an entity with overridden genes."""
    payload = {
        "brain_size": 9.5,
        "lifespan": 500.0,
        "think_interval": 10.0,
    }
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/entities/", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"

    # Check that gene values are respected
    repo = RedisEntityRepository(override_redis)
    data = await repo.load(body["entity_id"])
    assert data is not None

    import json
    genome_data = json.loads(data["genome"])
    genes = genome_data.get("genes", {})

    assert genes.get("brain_size", {}).get("value") == 9.5
    assert genes.get("lifespan", {}).get("value") == 500.0
    assert genes.get("think_interval", {}).get("value") == 10.0


@pytest.mark.asyncio
async def test_update_user_prompt(override_redis):
    """Test updating the user prompt of an entity."""
    repo = RedisEntityRepository(override_redis)
    entity_id = "test-entity-123"
    await repo.save(entity_id, {
        "id": entity_id,
        "user_prompt": "old prompt",
        "alive": "True",
    })

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.patch(f"/entities/{entity_id}/user_prompt", json={"user_prompt": "new prompt"})

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"

    entity_data = await repo.load(entity_id)
    assert entity_data["user_prompt"] == "new prompt"


@pytest.mark.asyncio
async def test_update_user_prompt_not_found(override_redis):
    """Test updating user prompt for a non-existent entity."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.patch("/entities/non-existent-entity/user_prompt", json={"user_prompt": "new prompt"})

    assert response.status_code == 404
    assert response.json()["detail"] == "Entity not found"


@pytest.mark.asyncio
async def test_delete_entity(override_redis):
    """Test deleting (archiving) an entity."""
    repo = RedisEntityRepository(override_redis)
    entity_id = "test-entity-delete"
    await repo.save(entity_id, {
        "id": entity_id,
        "alive": "True",
        "some_data": "data"
    })

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.delete(f"/entities/{entity_id}")

    assert response.status_code == 200
    assert "destroyed" in response.json()["message"]

    # It should not be active anymore
    entity_data = await repo.load(entity_id)
    assert entity_data is None

    # It should be in the archive and marked as not alive
    archived_data = await repo.load_archive(entity_id)
    assert archived_data is not None
    assert archived_data["alive"] == "False"


@pytest.mark.asyncio
async def test_delete_entity_not_found(override_redis):
    """Test deleting a non-existent entity."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.delete("/entities/non-existent-entity")

    assert response.status_code == 404
    assert response.json()["detail"] == "Entity not found"
