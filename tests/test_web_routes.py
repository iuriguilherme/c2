import pytest
from web.main import app


@pytest.mark.asyncio
async def test_index():
    client = app.test_client()
    response = await client.get("/")
    assert response.status_code == 200
    text = await response.get_data()
    assert b"AGI Entity Simulation" in text
    assert b"Tick:" in text


@pytest.mark.asyncio
async def test_settings():
    client = app.test_client()
    response = await client.get("/settings")
    assert response.status_code == 200
    text = await response.get_data()
    assert b"AGI Entity Simulation Settings" in text
    assert b"Global Settings" in text
