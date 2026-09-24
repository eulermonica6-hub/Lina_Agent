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
        "version": "0.2.23",
    }


def test_root_serves_mvp_workbench() -> None:
    app = create_app(Settings(app_name="Lina Test", environment="test"))

    async def request_root() -> Response:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get("/")

    response = asyncio.run(request_root())

    assert response.status_code == 200
    assert "Lina 求职决策台" in response.text
    assert 'class="brand-version">v0.2.23</span>' in response.text
    assert "{{APP_VERSION}}" not in response.text
    assert "从描述提取硬条件" in response.text
    assert "开始新一轮" in response.text
    assert 'href="/assets/styles.css?v=6"' in response.text
    assert 'src="/assets/app.js?v=5"' in response.text
