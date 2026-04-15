import pytest
from httpx import AsyncClient, ASGITransport
from api.main import app


@pytest.mark.asyncio
async def test_health():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_get_gene_pool():
    # Wrap test logic inside lifespan context manager to run lifespan events
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        async with app.router.lifespan_context(app):
            r = await client.get("/genes/")
            assert r.status_code == 200
            data = r.json()
            assert len(data) == 7
            types = [g["gene_type"] for g in data]
            assert "lifespan" in types


@pytest.mark.asyncio
async def test_get_neuron_pool():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        async with app.router.lifespan_context(app):
            r = await client.get("/neurons/")
            assert r.status_code == 200
            data = r.json()
            assert len(data) == 7
    types = [n["neuron_type"] for n in data]
    assert "locomotion" in types


@pytest.mark.asyncio
async def test_get_gene_by_type():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        async with app.router.lifespan_context(app):
            r = await client.get("/genes/lifespan")
            assert r.status_code == 200
            assert r.json()["gene_type"] == "lifespan"


@pytest.mark.asyncio
async def test_get_gene_not_found():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        async with app.router.lifespan_context(app):
            r = await client.get("/genes/nonexistent")
            assert r.status_code == 404
