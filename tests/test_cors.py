import pytest
import os
from httpx import AsyncClient, ASGITransport
from api.main import app

@pytest.mark.asyncio
async def test_cors_restricted_origin():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Simulate a CORS request from an arbitrary origin
        headers = {
            "Origin": "http://malicious.com",
            "Access-Control-Request-Method": "GET",
        }
        # Options request (preflight)
        response = await client.options("/health", headers=headers)

        # Should NOT allow the malicious origin (header should be missing)
        assert "access-control-allow-origin" not in response.headers

@pytest.mark.asyncio
async def test_cors_allowed_origin():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = {
            "Origin": "http://localhost:5000",
            "Access-Control-Request-Method": "GET",
        }
        response = await client.options("/health", headers=headers)

        assert response.headers.get("access-control-allow-origin") == "http://localhost:5000"
        assert response.headers.get("access-control-allow-credentials") == "true"
