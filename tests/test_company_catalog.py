import asyncio

from httpx import ASGITransport, AsyncClient, Response

from lina_agent.config import Settings
from lina_agent.domain.weekly_monitoring import CompanyPool
from lina_agent.infrastructure.job_sources.registry import MONITORED_JOB_SOURCES
from lina_agent.main import create_app


def _request(path: str) -> Response:
    app = create_app(Settings(app_name="Lina Test", environment="test"))

    async def send() -> Response:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get(path)

    return asyncio.run(send())


def test_company_catalog_balances_anchor_and_focused_ai_pools() -> None:
    anchor = tuple(source for source in MONITORED_JOB_SOURCES if source.pool is CompanyPool.ANCHOR)
    focused = tuple(
        source for source in MONITORED_JOB_SOURCES if source.pool is CompanyPool.FOCUSED_AI
    )

    assert len(anchor) == 10
    assert len(focused) == 22
    assert {source.company for source in focused} == {
        "MiniMax",
        "Garena",
        "Baseten",
        "Cohere",
        "Fireworks AI",
        "Anyscale",
        "LlamaIndex",
        "Pinecone",
        "Weaviate",
        "ElevenLabs",
        "LangChain",
        "Together AI",
        "Sierra",
        "Scale AI",
        "Lambda",
        "Cartesia",
        "Harvey",
        "Vapi",
        "WRITER",
        "Unstructured",
        "Glean",
        "Arize AI",
    }
    assert all(source.regions for source in MONITORED_JOB_SOURCES)
    assert all(source.why_watch for source in MONITORED_JOB_SOURCES)


def test_company_api_filters_focused_ai_pool() -> None:
    response = _request("/companies?pool=focused_ai")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 22
    assert all(company["pool"] == "focused_ai" for company in payload)
    assert {company["company"] for company in payload} >= {
        "Baseten",
        "LlamaIndex",
        "Weaviate",
    }
