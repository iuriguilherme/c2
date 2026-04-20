import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from httpx import AsyncClient, ASGITransport

_TEST_ALLOWED_ORIGINS = ["http://localhost:5000", "http://127.0.0.1:5000"]


def _make_test_app(allowed_origins):
    """Return a minimal FastAPI app with CORSMiddleware configured for testing."""
    test_app = FastAPI()
    test_app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @test_app.get("/health")
    async def health():
        return {"status": "ok"}

    return test_app


@pytest.mark.asyncio
async def test_cors_restricted_origin():
    app = _make_test_app(_TEST_ALLOWED_ORIGINS)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Simulate a CORS preflight from a disallowed origin
        headers = {
            "Origin": "http://malicious.com",
            "Access-Control-Request-Method": "GET",
        }
        response = await client.options("/health", headers=headers)

        # Should NOT allow the malicious origin (header should be absent)
        assert "access-control-allow-origin" not in response.headers


@pytest.mark.asyncio
async def test_cors_allowed_origin():
    app = _make_test_app(_TEST_ALLOWED_ORIGINS)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = {
            "Origin": "http://localhost:5000",
            "Access-Control-Request-Method": "GET",
        }
        response = await client.options("/health", headers=headers)

        assert response.headers.get("access-control-allow-origin") == "http://localhost:5000"
        assert response.headers.get("access-control-allow-credentials") == "true"
