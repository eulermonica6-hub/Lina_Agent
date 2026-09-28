import asyncio
from datetime import UTC, datetime

from lina_agent.application.job_discovery import JobDiscoveryService, JobSourceAdapter
from lina_agent.domain.job_discovery import (
    JobDiscoveryResult,
    JobLead,
    JobSearchRequest,
    JobSourceResult,
    JobSourceStatus,
    JobVerificationStatus,
)

_CAPTURED_AT = datetime(2026, 9, 14, tzinfo=UTC)


class FakeSource(JobSourceAdapter):
    def __init__(self, source_id: str, result: JobSourceResult) -> None:
        self.source_id = source_id
        self._result = result

    async def search(self, request: JobSearchRequest) -> JobSourceResult:
        return self._result


def _lead(
    lead_id: str,
    company: str = "MiniMax",
    deduplication_key: str | None = None,
) -> JobLead:
    return JobLead(
        lead_id=lead_id,
        deduplication_key=deduplication_key or lead_id,
        source_id="official-snapshot",
        external_id=lead_id,
        company=company,
        title="Agent Intern",
        locations=("上海",),
        direction="Agent / LLM 应用",
        source_url=f"https://example.com/{lead_id}",
        captured_at=_CAPTURED_AT,
        verification_status=JobVerificationStatus.NEEDS_REVERIFICATION,
        highlights=("Agent", "Python"),
    )


def test_discovery_deduplicates_leads_and_preserves_source_statuses() -> None:
    duplicate = _lead("same")
    success = JobSourceResult(
        source_id="source-a",
        status=JobSourceStatus.SUCCESS,
        fetched_at=_CAPTURED_AT,
        leads=(duplicate, _lead("unique")),
    )
    partial = JobSourceResult(
        source_id="source-b",
        status=JobSourceStatus.PARTIAL,
        fetched_at=_CAPTURED_AT,
        leads=(_lead("same-from-second-source", deduplication_key="same"),),
        error_code="page_two_timeout",
    )
    service = JobDiscoveryService(
        (FakeSource("source-a", success), FakeSource("source-b", partial))
    )

    result = asyncio.run(service.search(JobSearchRequest(max_results=10)))

    assert isinstance(result, JobDiscoveryResult)
    assert [lead.lead_id for lead in result.leads] == ["same", "unique"]
    assert [source.status for source in result.sources] == [
        JobSourceStatus.SUCCESS,
        JobSourceStatus.PARTIAL,
    ]
    assert result.sources[1].error_code == "page_two_timeout"


def test_discovery_applies_global_limit_after_deduplication() -> None:
    source = JobSourceResult(
        source_id="source-a",
        status=JobSourceStatus.SUCCESS,
        fetched_at=_CAPTURED_AT,
        leads=(_lead("one"), _lead("two")),
    )
    service = JobDiscoveryService((FakeSource("source-a", source),))

    result = asyncio.run(service.search(JobSearchRequest(max_results=1)))

    assert [lead.lead_id for lead in result.leads] == ["one"]
