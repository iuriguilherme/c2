import pytest
import httpx
from unittest.mock import AsyncMock, patch

from api.main import app

@pytest.mark.asyncio
async def test_get_prompts():
    mock_find = AsyncMock()
    mock_prompt = AsyncMock()
    mock_prompt.id = "12345"
    mock_prompt.name = "Test"
    mock_prompt.content = "Test content"
    mock_prompt.is_default = True

    mock_find.to_list = AsyncMock(return_value=[mock_prompt])

    with patch("storage.mongo.SystemPrompt.find_all", return_value=mock_find):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/system-prompts/")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Test"
