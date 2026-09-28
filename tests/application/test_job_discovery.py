import asyncio
from datetime import UTC, date, datetime

from lina_agent.application.job_discovery import JobDiscoveryService, JobSourceAdapter
from lina_agent.domain.job_discovery import (
    JobDiscoveryResult,
    JobLead,
    JobRecommendationRequest,
    JobSearchRequest,
    JobSourceResult,
    JobSourceStatus,
    JobType,
    JobVerificationStatus,
)
from lina_agent.domain.weekly_monitoring import CompanyPool

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
    pool: CompanyPool = CompanyPool.ANCHOR,
    locations: tuple[str, ...] = ("上海",),
    job_type: JobType = JobType.UNKNOWN,
) -> JobLead:
    return JobLead(
        lead_id=lead_id,
        deduplication_key=deduplication_key or lead_id,
        source_id="official-snapshot",
        external_id=lead_id,
        company=company,
        title="Agent Intern",
        locations=locations,
        direction="Agent / LLM 应用",
        source_url=f"https://example.com/{lead_id}",
        captured_at=_CAPTURED_AT,
        verification_status=JobVerificationStatus.NEEDS_REVERIFICATION,
        highlights=("Agent", "Python"),
        company_pool=pool,
        job_type=job_type,
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


def test_discovery_interleaves_anchor_and_focused_ai_leads() -> None:
    source = JobSourceResult(
        source_id="source-a",
        status=JobSourceStatus.SUCCESS,
        fetched_at=_CAPTURED_AT,
        leads=(
            _lead("anchor-one"),
            _lead("anchor-two"),
            _lead("focused-one", pool=CompanyPool.FOCUSED_AI),
            _lead("focused-two", pool=CompanyPool.FOCUSED_AI),
        ),
    )
    service = JobDiscoveryService((FakeSource("source-a", source),))

    result = asyncio.run(service.search(JobSearchRequest(max_results=4)))

    assert [lead.lead_id for lead in result.leads] == [
        "anchor-one",
        "focused-one",
        "anchor-two",
        "focused-two",
    ]


def test_homepage_recommendations_use_six_three_quota_and_preferences() -> None:
    leads = (
        *(_lead(f"anchor-{index}", company=f"Anchor {index}") for index in range(8)),
        _lead("focused-a", company="Focused A", pool=CompanyPool.FOCUSED_AI),
        _lead("focused-b", company="Focused B", pool=CompanyPool.FOCUSED_AI),
        _lead("focused-c", company="Focused C", pool=CompanyPool.FOCUSED_AI),
        _lead("focused-d", company="Focused D", pool=CompanyPool.FOCUSED_AI),
    )
    source = JobSourceResult(
        source_id="source-a",
        status=JobSourceStatus.SUCCESS,
        fetched_at=_CAPTURED_AT,
        leads=leads,
    )
    service = JobDiscoveryService((FakeSource("source-a", source),))

    result = asyncio.run(
        service.recommend(
            JobRecommendationRequest(
                preferred_companies=("Anchor 7",),
                recent_companies=("Focused D",),
                week_start=date(2026, 9, 28),
            )
        )
    )

    assert len(result.leads) == 9
    assert [lead.company_pool for lead in result.leads[:6]] == [CompanyPool.ANCHOR] * 6
    assert [lead.company_pool for lead in result.leads[6:]] == [CompanyPool.FOCUSED_AI] * 3
    assert result.leads[0].company == "Anchor 7"
    assert result.leads[6].company == "Focused D"


def test_homepage_recommendations_fill_missing_pool_capacity() -> None:
    source = JobSourceResult(
        source_id="source-a",
        status=JobSourceStatus.SUCCESS,
        fetched_at=_CAPTURED_AT,
        leads=(
            _lead("anchor-one"),
            _lead("focused-one", pool=CompanyPool.FOCUSED_AI),
        ),
    )
    service = JobDiscoveryService((FakeSource("source-a", source),))

    result = asyncio.run(service.recommend(JobRecommendationRequest()))

    assert len(result.leads) == 2


def test_homepage_recommendations_rotate_between_weeks() -> None:
    leads = tuple(_lead(f"anchor-{index}") for index in range(8)) + tuple(
        _lead(f"focused-{index}", pool=CompanyPool.FOCUSED_AI) for index in range(5)
    )
    source = JobSourceResult(
        source_id="source-a",
        status=JobSourceStatus.SUCCESS,
        fetched_at=_CAPTURED_AT,
        leads=leads,
    )
    service = JobDiscoveryService((FakeSource("source-a", source),))

    first_week = asyncio.run(
        service.recommend(JobRecommendationRequest(week_start=date(2026, 9, 28)))
    )
    next_week = asyncio.run(
        service.recommend(JobRecommendationRequest(week_start=date(2026, 10, 5)))
    )

    assert [lead.lead_id for lead in first_week.leads] != [lead.lead_id for lead in next_week.leads]
    assert [lead.company_pool for lead in next_week.leads[:6]] == [CompanyPool.ANCHOR] * 6
    assert [lead.company_pool for lead in next_week.leads[6:]] == [CompanyPool.FOCUSED_AI] * 3


def test_homepage_recommendations_prioritize_location_and_early_career() -> None:
    source = JobSourceResult(
        source_id="source-a",
        status=JobSourceStatus.SUCCESS,
        fetched_at=_CAPTURED_AT,
        leads=(
            _lead("beijing-full-time", locations=("北京",), job_type=JobType.FULL_TIME),
            _lead("shanghai-intern", job_type=JobType.INTERNSHIP),
            _lead(
                "remote-campus",
                locations=("远程",),
                job_type=JobType.CAMPUS,
                pool=CompanyPool.FOCUSED_AI,
            ),
        ),
    )
    service = JobDiscoveryService((FakeSource("source-a", source),))

    result = asyncio.run(
        service.recommend(
            JobRecommendationRequest(
                preferred_locations=("上海", "远程"),
                preferred_job_types=(JobType.INTERNSHIP, JobType.CAMPUS),
            )
        )
    )

    assert result.leads[0].lead_id == "shanghai-intern"
    assert result.leads[1].lead_id == "beijing-full-time"
    assert result.leads[2].lead_id == "remote-campus"
