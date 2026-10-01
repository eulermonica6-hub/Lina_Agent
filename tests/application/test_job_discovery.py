import asyncio
from datetime import UTC, date, datetime

from lina_agent.application.job_discovery import JobDiscoveryService, JobSourceAdapter
from lina_agent.domain.job_applications import JobApplicationRecord
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
from lina_agent.infrastructure.repositories.memory import InMemoryJobApplicationRepository

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
    pool: CompanyPool = CompanyPool.DOMESTIC_MAJOR,
    locations: tuple[str, ...] = ("上海",),
    job_type: JobType = JobType.UNKNOWN,
    verification_status: JobVerificationStatus = JobVerificationStatus.LIVE,
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
        verification_status=verification_status,
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


def test_homepage_recommendations_use_two_two_two_quota_and_preferences() -> None:
    leads = (
        *(_lead(f"domestic-{index}", company=f"Domestic {index}") for index in range(4)),
        *(
            _lead(
                f"global-{index}",
                company=f"Global {index}",
                pool=CompanyPool.GLOBAL_MAJOR,
            )
            for index in range(4)
        ),
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
                preferred_companies=("Domestic 3", "Global 3"),
                recent_companies=("Focused D",),
                week_start=date(2026, 9, 28),
            )
        )
    )

    assert len(result.leads) == 6
    assert [lead.company_pool for lead in result.leads[:2]] == [CompanyPool.DOMESTIC_MAJOR] * 2
    assert [lead.company_pool for lead in result.leads[2:4]] == [CompanyPool.GLOBAL_MAJOR] * 2
    assert [lead.company_pool for lead in result.leads[4:]] == [CompanyPool.FOCUSED_AI] * 2
    assert result.leads[0].company == "Domestic 3"
    assert result.leads[2].company == "Global 3"
    assert result.leads[4].company == "Focused D"


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


def test_homepage_recommendations_rotate_between_days() -> None:
    leads = (
        tuple(_lead(f"domestic-{index}") for index in range(5))
        + tuple(_lead(f"global-{index}", pool=CompanyPool.GLOBAL_MAJOR) for index in range(5))
        + tuple(_lead(f"focused-{index}", pool=CompanyPool.FOCUSED_AI) for index in range(5))
    )
    source = JobSourceResult(
        source_id="source-a",
        status=JobSourceStatus.SUCCESS,
        fetched_at=_CAPTURED_AT,
        leads=leads,
    )
    service = JobDiscoveryService((FakeSource("source-a", source),))

    first_day = asyncio.run(
        service.recommend(JobRecommendationRequest(rotation_date=date(2026, 9, 28)))
    )
    next_day = asyncio.run(
        service.recommend(JobRecommendationRequest(rotation_date=date(2026, 9, 29)))
    )

    assert [lead.lead_id for lead in first_day.leads] != [lead.lead_id for lead in next_day.leads]
    assert [lead.company_pool for lead in next_day.leads[:2]] == [CompanyPool.DOMESTIC_MAJOR] * 2
    assert [lead.company_pool for lead in next_day.leads[2:4]] == [CompanyPool.GLOBAL_MAJOR] * 2
    assert [lead.company_pool for lead in next_day.leads[4:]] == [CompanyPool.FOCUSED_AI] * 2


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


def test_homepage_recommendations_exclude_non_live_jobs() -> None:
    source = JobSourceResult(
        source_id="source-a",
        status=JobSourceStatus.SUCCESS,
        fetched_at=_CAPTURED_AT,
        leads=(
            _lead("live"),
            _lead("closed", verification_status=JobVerificationStatus.CLOSED),
            _lead(
                "unknown",
                verification_status=JobVerificationStatus.NEEDS_REVERIFICATION,
            ),
        ),
    )
    service = JobDiscoveryService((FakeSource("source-a", source),))

    result = asyncio.run(service.recommend(JobRecommendationRequest()))

    assert [lead.lead_id for lead in result.leads] == ["live"]


def test_recommendations_exclude_applied_jobs_but_search_keeps_them() -> None:
    applied = _lead("applied", company="Applied Company")
    source = JobSourceResult(
        source_id="source-a",
        status=JobSourceStatus.SUCCESS,
        fetched_at=_CAPTURED_AT,
        leads=(applied, _lead("available", company="Available Company")),
    )
    repository = InMemoryJobApplicationRepository()
    service = JobDiscoveryService(
        (FakeSource("source-a", source),),
        application_repository=repository,
    )

    async def exercise() -> None:
        await repository.save(
            JobApplicationRecord(
                source_id=applied.source_id,
                external_id=applied.external_id,
                company=applied.company,
                title=applied.title,
                source_url=applied.source_url,
                applied_at=_CAPTURED_AT,
            )
        )
        recommendation = await service.recommend(JobRecommendationRequest())
        search = await service.search(JobSearchRequest())
        assert [lead.external_id for lead in recommendation.leads] == ["available"]
        assert {lead.external_id for lead in search.leads} == {"applied", "available"}

        assert await repository.delete(applied.application_key) is True
        assert await repository.delete(applied.application_key) is False
        restored = await service.recommend(
            JobRecommendationRequest(preferred_companies=("Applied Company",))
        )
        assert restored.leads[0].external_id == "applied"

    asyncio.run(exercise())
