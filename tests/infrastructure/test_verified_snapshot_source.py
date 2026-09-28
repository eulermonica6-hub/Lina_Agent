import asyncio

from lina_agent.domain.job_discovery import JobSearchRequest, JobSourceStatus, JobType
from lina_agent.infrastructure.job_sources.verified_snapshot import VerifiedSnapshotJobSource


def test_snapshot_source_filters_query_company_and_location() -> None:
    source = VerifiedSnapshotJobSource()
    request = JobSearchRequest(
        query="agent",
        companies=("MiniMax", "小红书"),
        locations=("上海",),
        job_types=(JobType.INTERNSHIP, JobType.CAMPUS),
    )

    result = asyncio.run(source.search(request))

    assert result.status is JobSourceStatus.SUCCESS
    assert len(result.leads) == 4
    assert {lead.company for lead in result.leads} == {"MiniMax", "小红书"}
    assert all("上海" in lead.locations for lead in result.leads)


def test_snapshot_source_returns_successful_empty_result() -> None:
    source = VerifiedSnapshotJobSource()

    result = asyncio.run(source.search(JobSearchRequest(query="quantum biology")))
    wrong_location = asyncio.run(source.search(JobSearchRequest(locations=("北京",))))

    assert result.status is JobSourceStatus.SUCCESS
    assert result.leads == ()
    assert result.error_code is None
    assert wrong_location.status is JobSourceStatus.SUCCESS
    assert wrong_location.leads == ()


def test_snapshot_source_matches_highlights_case_insensitively() -> None:
    source = VerifiedSnapshotJobSource()

    result = asyncio.run(source.search(JobSearchRequest(query="CUDA")))

    assert [lead.company for lead in result.leads] == ["NVIDIA"]
