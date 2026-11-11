import asyncio
from datetime import UTC, datetime
from typing import Any

import httpx

from lina_agent.domain.job_discovery import (
    CompanyPool,
    JobSearchRequest,
    JobSourceStatus,
    JobType,
)
from lina_agent.infrastructure.job_sources.ashby import AshbyJobSource

_NOW = datetime(2026, 9, 30, 8, 0, tzinfo=UTC)

_BOARD: dict[str, Any] = {
    "jobs": [
        {
            "id": "a0000000-0000-0000-0000-000000000001",
            "title": "AI Engineer Intern",
            "employmentType": "Intern",
            "location": "San Francisco, California, United States",
            "secondaryLocations": [],
            "publishedAt": "2026-09-29T00:00:00.000Z",
            "isListed": True,
            "jobUrl": "https://jobs.ashbyhq.com/notion/a0000000-0000-0000-0000-000000000001",
            "applyUrl": None,
            "descriptionHtml": "<p>Build AI systems.</p><ul><li>Python</li><li>LLM</li></ul>",
            "descriptionPlain": "Build AI systems.\n- Python\n- LLM",
        },
        {
            "id": "a0000000-0000-0000-0000-000000000002",
            "title": "Software Engineer",
            "employmentType": "FullTime",
            "location": "Remote",
            "secondaryLocations": [],
            "publishedAt": "2026-09-28T00:00:00.000Z",
            "isListed": True,
            "jobUrl": "https://jobs.ashbyhq.com/notion/a0000000-0000-0000-0000-000000000002",
            "applyUrl": None,
            "descriptionHtml": "<p>Scale the backend.</p>",
            "descriptionPlain": "Scale the backend.",
        },
        {
            "id": "a0000000-0000-0000-0000-000000000003",
            "title": "Product Designer",
            "employmentType": "FullTime",
            "location": "New York",
            "secondaryLocations": [],
            "publishedAt": "2026-09-30T00:00:00.000Z",
            "isListed": False,
            "jobUrl": "https://jobs.ashbyhq.com/notion/a0000000-0000-0000-0000-000000000003",
            "applyUrl": None,
            "descriptionHtml": "<p>Design the product.</p>",
            "descriptionPlain": "Design the product.",
        },
        {
            "id": "a0000000-0000-0000-0000-000000000004",
            "title": "Research Scientist",
            "employmentType": "FullTime",
            "location": "Remote",
            "secondaryLocations": [{"location": "Shanghai"}],
            "publishedAt": "2026-09-27T00:00:00.000Z",
            "isListed": True,
            "jobUrl": "https://jobs.ashbyhq.com/notion/a0000000-0000-0000-0000-000000000004",
            "applyUrl": None,
            "descriptionHtml": "<p>Advance machine learning research.</p>",
            "descriptionPlain": "Advance machine learning research.",
        },
    ]
}


def _source(
    *,
    board: dict[str, Any] | None = None,
    status_code: int = 200,
) -> tuple[AshbyJobSource, list[str]]:
    """Build an Ashby source backed by a mock board, and a list of requested paths."""
    payload = _BOARD if board is None else board
    requested: list[str] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requested.append(request.url.path)
        return httpx.Response(status_code, json=payload, request=request)

    source = AshbyJobSource(
        source_id="notion-careers",
        company="Notion",
        org="notion",
        transport=httpx.MockTransport(respond),
        clock=lambda: _NOW,
    )
    return source, requested


def test_ashby_source_maps_listed_jobs_to_leads() -> None:
    source, requested = _source()

    result = asyncio.run(source.search(JobSearchRequest(max_results=20)))

    assert result.status is JobSourceStatus.SUCCESS
    assert result.error_code is None
    assert requested == ["/posting-api/job-board/notion"]
    assert {lead.external_id for lead in result.leads} == {
        "a0000000-0000-0000-0000-000000000001",
        "a0000000-0000-0000-0000-000000000002",
        "a0000000-0000-0000-0000-000000000004",
    }
    intern = next(lead for lead in result.leads if lead.title == "AI Engineer Intern")
    assert intern.job_type is JobType.INTERNSHIP
    assert intern.company == "Notion"
    assert intern.company_pool is CompanyPool.GLOBAL_MAJOR
    assert intern.verification_status.value == "live"
    assert intern.normalized_description.startswith("Build AI systems.")
    assert "<" not in intern.normalized_description
    assert intern.content_fingerprint is not None
    assert len(intern.content_fingerprint) == 64
    assert "AI" in intern.highlights


def test_ashby_source_maps_secondary_and_remote_locations() -> None:
    source, _ = _source()

    result = asyncio.run(source.search(JobSearchRequest(max_results=20)))

    remote = next(lead for lead in result.leads if lead.title == "Software Engineer")
    assert "全球" in remote.locations
    scientist = next(lead for lead in result.leads if lead.title == "Research Scientist")
    assert "Shanghai" in scientist.locations
    assert "全球" in scientist.locations


def test_ashby_source_filters_by_query_location_and_job_type() -> None:
    source, _ = _source()

    by_query = asyncio.run(source.search(JobSearchRequest(query="scientist", max_results=20)))
    assert {lead.title for lead in by_query.leads} == {"Research Scientist"}

    by_location = asyncio.run(
        source.search(JobSearchRequest(locations=("Shanghai",), max_results=20))
    )
    assert {lead.title for lead in by_location.leads} == {"Research Scientist"}

    by_type = asyncio.run(
        source.search(JobSearchRequest(job_types=(JobType.INTERNSHIP,), max_results=20))
    )
    assert {lead.title for lead in by_type.leads} == {"AI Engineer Intern"}


def test_ashby_source_skips_unsupported_company_without_network() -> None:
    source, requested = _source()

    result = asyncio.run(source.search(JobSearchRequest(companies=("Stripe",), max_results=20)))

    assert result.status is JobSourceStatus.SUCCESS
    assert result.leads == ()
    assert requested == []


def test_ashby_source_reports_http_and_schema_failures() -> None:
    source, _ = _source(status_code=503)
    result = asyncio.run(source.search(JobSearchRequest(max_results=20)))
    assert result.status is JobSourceStatus.FAILED
    assert result.error_code == "http_503"

    source, _ = _source(board={"unexpected": "shape"})
    result = asyncio.run(source.search(JobSearchRequest(max_results=20)))
    assert result.status is JobSourceStatus.STRUCTURE_CHANGED
    assert result.error_code == "invalid_ashby_payload"
