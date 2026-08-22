import asyncio

from httpx import ASGITransport, AsyncClient, Response

from lina_agent.config import Settings
from lina_agent.main import create_app


def test_health_check_reports_service_metadata() -> None:
    app = create_app(Settings(app_name="Lina Test", environment="test"))

    async def request_health() -> Response:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get("/health")

    response = asyncio.run(request_health())

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "Lina Test",
        "version": "0.1.0",
    }
