import asyncio
import tomllib
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient, Response

from lina_agent.config import Settings
from lina_agent.domain.weekly_monitoring import CompanyPool
from lina_agent.infrastructure.job_sources.registry import (
    MONITORED_JOB_SOURCES,
    load_company_catalog,
)
from lina_agent.main import create_app

PROJECT_ROOT = Path(__file__).parents[1]


def _request(path: str) -> Response:
    app = create_app(Settings(app_name="Lina Test", environment="test"))

    async def send() -> Response:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get(path)

    return asyncio.run(send())


def test_company_catalog_balances_major_and_focused_ai_pools() -> None:
    domestic = tuple(
        source for source in MONITORED_JOB_SOURCES if source.pool is CompanyPool.DOMESTIC_MAJOR
    )
    global_major = tuple(
        source for source in MONITORED_JOB_SOURCES if source.pool is CompanyPool.GLOBAL_MAJOR
    )
    focused = tuple(
        source for source in MONITORED_JOB_SOURCES if source.pool is CompanyPool.FOCUSED_AI
    )

    assert {source.company for source in domestic} == {
        "腾讯",
        "字节跳动",
        "阿里巴巴",
        "蚂蚁集团",
        "小红书",
    }
    assert {source.company for source in global_major} == {
        "Microsoft",
        "Amazon",
        "Meltwater",
        "Apple",
        "NVIDIA",
    }
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


def test_company_catalog_toml_is_the_reviewable_source_of_truth() -> None:
    catalog_path = (
        PROJECT_ROOT
        / "src"
        / "lina_agent"
        / "infrastructure"
        / "job_sources"
        / "company_catalog.toml"
    )
    catalog = tomllib.loads(catalog_path.read_text(encoding="utf-8"))

    assert catalog["schema_version"] == 1
    assert len(catalog["companies"]) == len(MONITORED_JOB_SOURCES) == 32
    assert [item["source_id"] for item in catalog["companies"]] == [
        source.source_id for source in MONITORED_JOB_SOURCES
    ]
    assert len({source.company.casefold() for source in MONITORED_JOB_SOURCES}) == 32


@pytest.mark.parametrize(
    ("catalog", "message"),
    [
        ("schema_version = 2\ncompanies = []", "schema version"),
        (
            """
            schema_version = 1
            [[companies]]
            source_id = "duplicate"
            company = "Company A"
            url = "https://example.com/a"
            keywords = ["AI"]
            [[companies]]
            source_id = "duplicate"
            company = "Company B"
            url = "https://example.com/b"
            keywords = ["AI"]
            """,
            "source_id",
        ),
        (
            """
            schema_version = 1
            [[companies]]
            source_id = "company-a"
            company = "Same Company"
            url = "https://example.com/a"
            keywords = ["AI"]
            [[companies]]
            source_id = "company-b"
            company = "same company"
            url = "https://example.com/b"
            keywords = ["AI"]
            """,
            "company names",
        ),
    ],
)
def test_company_catalog_rejects_invalid_metadata(catalog: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        load_company_catalog(catalog)


def test_internal_company_catalog_is_not_exposed_publicly() -> None:
    response = _request("/companies?pool=focused_ai")
    monitoring = _request("/monitoring/sources")

    assert response.status_code == 404
    assert monitoring.status_code == 404
