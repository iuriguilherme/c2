import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch

from api.main import app


def _make_mock_prompt(pid="507f1f77bcf86cd799439011", name="Test", content="Test content", is_default=True):
    mock_prompt = MagicMock()
    mock_prompt.id = pid
    mock_prompt.name = name
    mock_prompt.content = content
    mock_prompt.is_default = is_default
    mock_prompt.save = AsyncMock()
    mock_prompt.delete = AsyncMock()
    return mock_prompt


@pytest.mark.asyncio
async def test_get_prompts():
    mock_find = AsyncMock()
    mock_prompt = _make_mock_prompt()
    mock_find.to_list = AsyncMock(return_value=[mock_prompt])

    with patch("storage.mongo.SystemPrompt.find_all", return_value=mock_find):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/system-prompts/")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Test"


@pytest.mark.asyncio
async def test_create_system_prompt():
    mock_prompt = _make_mock_prompt()
    mock_prompt.insert = AsyncMock()

    with patch("api.routes.system_prompts.SystemPrompt") as MockSystemPrompt:
        MockSystemPrompt.return_value = mock_prompt
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/system-prompts/",
                json={"name": "Test", "content": "Test content", "is_default": True},
            )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test"
    assert data["content"] == "Test content"


@pytest.mark.asyncio
async def test_update_system_prompt():
    pid = "507f1f77bcf86cd799439011"
    mock_prompt = _make_mock_prompt(pid=pid)

    with patch("api.routes.system_prompts.SystemPrompt") as MockSystemPrompt:
        MockSystemPrompt.get = AsyncMock(return_value=mock_prompt)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.patch(
                f"/system-prompts/{pid}",
                json={"name": "Updated Name"},
            )

    assert response.status_code == 200
    mock_prompt.save.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_system_prompt_not_found():
    pid = "507f1f77bcf86cd799439011"

    with patch("api.routes.system_prompts.SystemPrompt") as MockSystemPrompt:
        MockSystemPrompt.get = AsyncMock(return_value=None)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.patch(f"/system-prompts/{pid}", json={"name": "x"})

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_update_system_prompt_invalid_id():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.patch("/system-prompts/not-a-valid-id", json={"name": "x"})

    assert response.status_code == 400
    assert "invalid" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_delete_system_prompt():
    pid = "507f1f77bcf86cd799439011"
    mock_prompt = _make_mock_prompt(pid=pid)

    with patch("api.routes.system_prompts.SystemPrompt") as MockSystemPrompt:
        MockSystemPrompt.get = AsyncMock(return_value=mock_prompt)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.delete(f"/system-prompts/{pid}")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    mock_prompt.delete.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_system_prompt_not_found():
    pid = "507f1f77bcf86cd799439011"

    with patch("api.routes.system_prompts.SystemPrompt") as MockSystemPrompt:
        MockSystemPrompt.get = AsyncMock(return_value=None)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.delete(f"/system-prompts/{pid}")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_delete_system_prompt_invalid_id():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.delete("/system-prompts/not-a-valid-id")

    assert response.status_code == 400
    assert "invalid" in response.json()["detail"].lower()
