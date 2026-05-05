import pytest
from httpx import ASGITransport, AsyncClient

from server.main import build_app


@pytest.mark.asyncio
async def test_health_returns_ok():
    app = build_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert "version" in body
