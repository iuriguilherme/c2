"""Tests for the /entities/archived/{entity_id} endpoint and AnthropicProvider models."""

import fakeredis.aioredis
import httpx
import pytest

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
