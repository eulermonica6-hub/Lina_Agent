import asyncio

from httpx import ASGITransport, AsyncClient

from lina_agent.config import Settings
from lina_agent.main import create_app


def test_applied_job_is_excluded_from_recommendations_and_can_be_restored() -> None:
    app = create_app(Settings(app_name="Lina Test", environment="test"))

    async def exercise() -> None:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            initial = await client.post("/opportunities/recommended", json={"limit": 6})
            applied = initial.json()["leads"][0]

            marked = await client.post(
                "/applications",
                json={
                    "source_id": applied["source_id"],
                    "external_id": applied["external_id"],
                    "company": applied["company"],
                    "title": applied["title"],
                    "source_url": applied["source_url"],
                },
            )
            after = await client.post("/opportunities/recommended", json={"limit": 6})
            applications = await client.get("/applications")
            search = await client.post(
                "/opportunities/search",
                json={
                    "companies": [applied["company"]],
                    "locations": ["上海"],
                    "max_results": 50,
                },
            )

            assert marked.status_code == 201
            assert marked.json()["external_id"] == applied["external_id"]
            assert applied["external_id"] not in {
                lead["external_id"] for lead in after.json()["leads"]
            }
            assert [item["external_id"] for item in applications.json()] == [applied["external_id"]]
            assert applied["external_id"] in {
                lead["external_id"] for lead in search.json()["leads"]
            }

            removed = await client.delete(
                f"/applications/{applied['source_id']}/{applied['external_id']}"
            )
            restored = await client.post("/opportunities/recommended", json={"limit": 6})
            missing = await client.delete(
                f"/applications/{applied['source_id']}/{applied['external_id']}"
            )

            assert removed.status_code == 204
            assert applied["external_id"] in {
                lead["external_id"] for lead in restored.json()["leads"]
            }
            assert missing.status_code == 404

    asyncio.run(exercise())
