import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from httpx import ASGITransport, AsyncClient

from lina_agent.config import Settings
from lina_agent.domain.job_changes import JobCaptureBatch, JobChangeEvent, JobChangeKind
from lina_agent.main import create_app

_NOW = datetime(2026, 9, 30, 10, 0, tzinfo=UTC)


def _event(
    batch: JobCaptureBatch,
    external_id: str,
    kind: JobChangeKind,
    occurred_at: datetime,
) -> JobChangeEvent:
    return JobChangeEvent(
        batch_id=batch.batch_id,
        source_id="nvidia-careers",
        external_id=external_id,
        kind=kind,
        occurred_at=occurred_at,
        previous_fingerprint="a" * 64 if kind is not JobChangeKind.NEW else None,
        current_fingerprint="b" * 64 if kind is not JobChangeKind.CLOSED else None,
        title=f"Role {external_id}",
        source_url=f"https://example.com/{external_id}",
    )


def test_inbox_api_filters_and_persists_independent_flags() -> None:
    app = create_app(Settings(app_name="Lina Test", environment="test"))
    batch = JobCaptureBatch(
        source_id="nvidia-careers",
        captured_at=_NOW,
        job_count=2,
    )
    older = _event(batch, "JR1", JobChangeKind.NEW, _NOW)
    newer = _event(batch, "JR2", JobChangeKind.UPDATED, _NOW + timedelta(minutes=1))

    async def exercise() -> None:
        await app.state.job_change_repository.save_capture(batch, (), (older, newer))
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            default = await client.get("/inbox/events")
            assert default.status_code == 200
            assert [item["event_id"] for item in default.json()] == [
                str(newer.event_id),
                str(older.event_id),
            ]
            assert "previous_fingerprint" not in default.text
            assert await app.state.job_change_repository.get_inbox_state(older.event_id) is None

            updated = await client.patch(
                f"/inbox/events/{older.event_id}",
                json={"saved": True, "compare_later": True},
            )
            assert updated.status_code == 200
            assert updated.json()["saved"] is True
            assert updated.json()["compare_later"] is True

            ignored = await client.patch(
                f"/inbox/events/{older.event_id}",
                json={"ignored": True},
            )
            assert ignored.json()["saved"] is True
            assert ignored.json()["compare_later"] is True
            assert ignored.json()["ignored"] is True

            assert len((await client.get("/inbox/events?status=unhandled")).json()) == 1
            assert len((await client.get("/inbox/events?status=saved")).json()) == 1
            assert len((await client.get("/inbox/events?status=ignored")).json()) == 1
            assert len((await client.get("/inbox/events?status=compare_later")).json()) == 1
            filtered = await client.get("/inbox/events?status=all&kind=updated")
            assert [item["external_id"] for item in filtered.json()] == ["JR2"]

    asyncio.run(exercise())


def test_inbox_api_rejects_empty_updates_and_unknown_events() -> None:
    app = create_app(Settings(app_name="Lina Test", environment="test"))

    async def exercise() -> None:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            empty = await client.patch(f"/inbox/events/{uuid4()}", json={})
            missing = await client.patch(
                f"/inbox/events/{uuid4()}",
                json={"saved": True},
            )
            assert empty.status_code == 422
            assert missing.status_code == 404

    asyncio.run(exercise())
