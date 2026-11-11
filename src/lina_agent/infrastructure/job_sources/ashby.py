"""Live Ashby job-board source (Notion, Linear, Persona, ...).

Ashby serves a company's public board as a single JSON document
(``{"jobs": [...], "apiVersion": ...}``). Each fresh board is the current
truth: closed or unlisted postings disappear from the default listing, and a
changed description changes ``content_fingerprint``. Unreadable boards are
reported as a failure, never as an empty result.

Unlike the single-company ``NvidiaWorkdayJobSource``, this adapter is
parameterized per organization so one class can serve several Ashby boards.
"""

import json
import re
from collections.abc import Callable
from datetime import UTC, datetime
from hashlib import sha256
from html import unescape
from html.parser import HTMLParser
from typing import ClassVar

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from lina_agent.domain.job_discovery import (
    CompanyPool,
    JobLead,
    JobSearchRequest,
    JobSourceResult,
    JobSourceStatus,
    JobType,
    JobVerificationStatus,
)

_BOARD_URL = "https://api.ashbyhq.com/posting-api/job-board/"
_PUBLIC_BASE_URL = "https://jobs.ashbyhq.com"


class _AshbySecondaryLocation(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    location: str = ""


class _AshbyPosting(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = ""
    title: str = Field(min_length=1)
    employment_type: str = Field(alias="employmentType", default="")
    location: str = ""
    secondary_locations: tuple[_AshbySecondaryLocation, ...] = Field(
        alias="secondaryLocations",
        default=(),
    )
    published_at: datetime | None = Field(alias="publishedAt", default=None)
    is_listed: bool = Field(alias="isListed", default=True)
    job_url: str | None = Field(alias="jobUrl", default=None)
    apply_url: str | None = Field(alias="applyUrl", default=None)
    description_html: str = Field(alias="descriptionHtml", default="")
    description_plain: str = Field(alias="descriptionPlain", default="")


class _AshbyBoard(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    jobs: tuple[_AshbyPosting, ...]


class _DescriptionParser(HTMLParser):
    _BLOCK_TAGS: ClassVar[set[str]] = {"br", "li", "p", "ul", "div", "h1", "h2", "h3", "h4"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        del attrs
        if tag in self._BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


class AshbyJobSource:
    def __init__(
        self,
        *,
        source_id: str,
        company: str,
        org: str,
        pool: CompanyPool = CompanyPool.GLOBAL_MAJOR,
        transport: httpx.AsyncBaseTransport | None = None,
        clock: Callable[[], datetime] | None = None,
        detail_limit: int = 50,
    ) -> None:
        self.source_id = source_id
        self._company = company
        self._org = org
        self._pool = pool
        self._transport = transport
        self._clock = clock or (lambda: datetime.now(UTC))
        self._detail_limit = max(1, min(50, detail_limit))

    async def search(self, request: JobSearchRequest) -> JobSourceResult:
        if not _supports_request(self._company, request):
            return self._result(JobSourceStatus.SUCCESS)

        try:
            async with httpx.AsyncClient(
                transport=self._transport,
                timeout=25,
                headers={"User-Agent": "Lina-Career-Agent/official-job-source"},
            ) as client:
                response = await client.get(f"{_BOARD_URL}{self._org}")
        except httpx.HTTPError:
            return self._result(JobSourceStatus.FAILED, "network_error")

        error_result = self._http_error_result(response)
        if error_result is not None:
            return error_result

        try:
            board = _AshbyBoard.model_validate(response.json())
        except (ValueError, ValidationError):
            return self._result(JobSourceStatus.STRUCTURE_CHANGED, "invalid_ashby_payload")

        listed = [posting for posting in board.jobs if posting.is_listed]
        listed.sort(
            key=lambda item: item.published_at or datetime.min.replace(tzinfo=UTC), reverse=True
        )
        leads = tuple(
            self._to_lead(posting)
            for posting in listed[: self._detail_limit]
            if self._description(posting)
        )
        matched = tuple(lead for lead in leads if _matches(lead, request))
        return self._result(JobSourceStatus.SUCCESS, leads=matched)

    def _to_lead(self, posting: _AshbyPosting) -> JobLead:
        title = posting.title
        company = self._company
        locations = _locations(posting)
        job_type = _job_type(title, posting.employment_type)
        direction = _direction(title)
        external_id = (
            posting.id or sha256(f"{company}:{title}:{''.join(locations)}".encode()).hexdigest()
        )
        description = self._description(posting)
        source_url = posting.job_url or posting.apply_url or f"{_PUBLIC_BASE_URL}/{self._org}"
        return JobLead(
            lead_id=f"{self.source_id}:{external_id}",
            deduplication_key=f"{company.casefold()}:{title.casefold()}:{'|'.join(locations)}",
            source_id=self.source_id,
            external_id=external_id,
            company=company,
            company_pool=self._pool,
            title=title,
            job_type=job_type,
            locations=locations,
            direction=direction,
            source_url=source_url,
            captured_at=self._clock(),
            verification_status=JobVerificationStatus.LIVE,
            highlights=_highlights(title),
            normalized_description=description,
            content_fingerprint=_content_fingerprint(
                title=title,
                company=company,
                locations=locations,
                job_type=job_type,
                direction=direction,
                description=description,
                source_url=source_url,
            ),
        )

    @staticmethod
    def _description(posting: _AshbyPosting) -> str:
        return unescape(
            posting.description_plain or _html_to_text(posting.description_html)
        ).strip()

    def _http_error_result(self, response: httpx.Response) -> JobSourceResult | None:
        if response.status_code == 429:
            return self._result(JobSourceStatus.RATE_LIMITED, "http_429")
        if response.status_code in {401, 403}:
            return self._result(
                JobSourceStatus.BLOCKED,
                f"http_{response.status_code}",
            )
        if response.status_code >= 400:
            return self._result(JobSourceStatus.FAILED, f"http_{response.status_code}")
        return None

    def _result(
        self,
        status: JobSourceStatus,
        error_code: str | None = None,
        *,
        leads: tuple[JobLead, ...] = (),
    ) -> JobSourceResult:
        return JobSourceResult(
            source_id=self.source_id,
            status=status,
            fetched_at=self._clock(),
            leads=leads,
            error_code=error_code,
        )


def _supports_request(company: str, request: JobSearchRequest) -> bool:
    companies = {value.casefold() for value in request.companies}
    return not companies or company.casefold() in companies


def _matches(lead: JobLead, request: JobSearchRequest) -> bool:
    if request.query is not None:
        searchable = " ".join(
            (
                lead.company,
                lead.title,
                lead.direction,
                *lead.locations,
                *lead.highlights,
            )
        ).casefold()
        if request.query.casefold() not in searchable:
            return False
    locations = {value.casefold() for value in request.locations}
    lead_locations = {value.casefold() for value in lead.locations}
    return (not locations or bool(locations & lead_locations)) and (
        not request.job_types or lead.job_type in request.job_types
    )


def _locations(posting: _AshbyPosting) -> tuple[str, ...]:
    raw_parts = [posting.location, *(item.location for item in posting.secondary_locations)]
    parts = tuple(value.strip() for value in raw_parts if value and value.strip())
    if not parts:
        return ("全球",)
    if any("remote" in value.casefold() for value in parts):
        parts = (*parts, "全球")
    return parts


def _job_type(title: str, employment_type: str) -> JobType:
    field = employment_type.casefold()
    if "intern" in field:
        return JobType.INTERNSHIP
    combined = f"{field} {title}".casefold()
    if "new college grad" in combined or "new graduate" in combined:
        return JobType.CAMPUS
    if "full" in field or "permanent" in field:
        return JobType.FULL_TIME
    return JobType.UNKNOWN


def _direction(title: str) -> str:
    normalized = title.casefold()
    if re.search(r"\bai\b|\bllm\b", normalized) or any(
        term in normalized for term in ("machine learning", "deep learning", "agent")
    ):
        return "AI / Machine Learning"
    if any(
        term in normalized
        for term in ("software", "engineer", "backend", "frontend", "full stack", "infrastructure")
    ):
        return "Software Engineering"
    if any(term in normalized for term in ("product", "design")):
        return "Product & Design"
    if "data" in normalized:
        return "Data"
    return "Technology"


def _highlights(title: str) -> tuple[str, ...]:
    normalized = title.casefold()
    return tuple(
        label
        for keyword, label in (
            ("ai", "AI"),
            ("llm", "LLM"),
            ("machine learning", "Machine Learning"),
            ("deep learning", "Deep Learning"),
            ("agent", "Agent"),
            ("software", "Software Engineering"),
            ("backend", "Backend"),
            ("frontend", "Frontend"),
            ("full stack", "Full Stack"),
            ("infrastructure", "Infrastructure"),
            ("data", "Data"),
            ("product", "Product"),
            ("design", "Design"),
            ("research", "Research"),
        )
        if keyword in normalized
    )


def _html_to_text(value: str) -> str:
    parser = _DescriptionParser()
    parser.feed(unescape(value))
    parser.close()
    return " ".join("".join(parser.parts).split())


def _content_fingerprint(
    *,
    title: str,
    company: str,
    locations: tuple[str, ...],
    job_type: JobType,
    direction: str,
    description: str,
    source_url: str,
) -> str:
    payload = json.dumps(
        {
            "title": title,
            "company": company,
            "locations": locations,
            "job_type": job_type,
            "direction": direction,
            "description": description,
            "source_url": source_url,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(payload.encode("utf-8")).hexdigest()
