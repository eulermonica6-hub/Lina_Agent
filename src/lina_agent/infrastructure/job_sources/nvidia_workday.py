import re
from collections.abc import Callable
from datetime import UTC, datetime

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

_SOURCE_ID = "nvidia-careers"
_API_URL = "https://nvidia.wd5.myworkdayjobs.com/wday/cxs/nvidia/NVIDIAExternalCareerSite/jobs"
_PUBLIC_BASE_URL = "https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite"


class _WorkdayPosting(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    title: str = Field(min_length=1)
    external_path: str = Field(alias="externalPath", pattern=r"^/job/")
    locations_text: str = Field(alias="locationsText", min_length=1)
    posted_on: str = Field(alias="postedOn", min_length=1)
    bullet_fields: tuple[str, ...] = Field(alias="bulletFields", min_length=1)


class _WorkdayResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    total: int = Field(ge=0)
    job_postings: tuple[_WorkdayPosting, ...] = Field(alias="jobPostings")


class NvidiaWorkdayJobSource:
    source_id = _SOURCE_ID

    def __init__(
        self,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        clock: Callable[[], datetime] | None = None,
        page_size: int = 20,
    ) -> None:
        self._transport = transport
        self._clock = clock or (lambda: datetime.now(UTC))
        self._page_size = min(20, max(1, page_size))

    async def search(self, request: JobSearchRequest) -> JobSourceResult:
        if not _supports_request(request):
            return self._result(JobSourceStatus.SUCCESS)

        search_text = "Shanghai"
        if request.query is not None:
            search_text = f"{search_text} {request.query}"

        leads: list[JobLead] = []
        seen_ids: set[str] = set()
        offset = 0
        try:
            async with httpx.AsyncClient(
                transport=self._transport,
                timeout=20,
                headers={"User-Agent": "Lina-Career-Agent/official-job-source"},
            ) as client:
                while len(leads) < request.max_results:
                    response = await client.post(
                        _API_URL,
                        json={
                            "appliedFacets": {},
                            "limit": self._page_size,
                            "offset": offset,
                            "searchText": search_text,
                        },
                    )
                    error_result = self._http_error_result(response)
                    if error_result is not None:
                        return error_result
                    try:
                        payload = _WorkdayResponse.model_validate(response.json())
                    except (ValueError, ValidationError):
                        return self._result(
                            JobSourceStatus.STRUCTURE_CHANGED,
                            "invalid_workday_payload",
                        )

                    if not payload.job_postings:
                        break
                    for posting in payload.job_postings:
                        lead = _to_lead(posting, self._clock())
                        if lead.external_id in seen_ids or not _matches(lead, request):
                            continue
                        seen_ids.add(lead.external_id)
                        leads.append(lead)
                        if len(leads) >= request.max_results:
                            break
                    offset += len(payload.job_postings)
                    if offset >= payload.total:
                        break
        except httpx.HTTPError:
            return self._result(JobSourceStatus.FAILED, "network_error")

        return self._result(JobSourceStatus.SUCCESS, leads=tuple(leads))

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


def _supports_request(request: JobSearchRequest) -> bool:
    companies = {company.casefold() for company in request.companies}
    if companies and "nvidia" not in companies:
        return False
    requested_locations = {location.casefold() for location in request.locations}
    return not requested_locations or bool(
        requested_locations & {"上海", "shanghai", "china", "中国", "china, shanghai"}
    )


def _to_lead(posting: _WorkdayPosting, captured_at: datetime) -> JobLead:
    external_id = posting.bullet_fields[0]
    locations = _locations(posting)
    direction = _direction(posting.title)
    return JobLead(
        lead_id=f"{_SOURCE_ID}:{external_id}",
        deduplication_key=f"nvidia:{posting.title.casefold()}:{'|'.join(locations)}",
        source_id=_SOURCE_ID,
        external_id=external_id,
        company="NVIDIA",
        company_pool=CompanyPool.GLOBAL_MAJOR,
        title=posting.title,
        job_type=_job_type(posting.title),
        locations=locations,
        direction=direction,
        source_url=f"{_PUBLIC_BASE_URL}{posting.external_path}",
        captured_at=captured_at,
        verification_status=JobVerificationStatus.LIVE,
        highlights=_highlights(posting.title, posting.posted_on),
    )


def _locations(posting: _WorkdayPosting) -> tuple[str, ...]:
    path = posting.external_path.casefold()
    if "china-shanghai" in path:
        return ("上海",)
    if "china-beijing" in path:
        return ("北京",)
    return tuple(part.strip() for part in posting.locations_text.split(";") if part.strip())


def _job_type(title: str) -> JobType:
    normalized = title.casefold()
    if "intern" in normalized:
        return JobType.INTERNSHIP
    if "new college grad" in normalized or "new college graduate" in normalized:
        return JobType.CAMPUS
    return JobType.FULL_TIME


def _direction(title: str) -> str:
    normalized = title.casefold()
    if re.search(r"\bai\b", normalized) or any(
        term in normalized for term in ("deep learning", "machine learning")
    ):
        return "AI / Machine Learning"
    if "gpu" in normalized or "cuda" in normalized or "soc" in normalized:
        return "GPU / CUDA"
    if "software" in normalized:
        return "Software Engineering"
    return "Technology Engineering"


def _highlights(title: str, posted_on: str) -> tuple[str, ...]:
    normalized = title.casefold()
    labels = ["AI"] if re.search(r"\bai\b", normalized) else []
    labels.extend(
        label
        for keyword, label in (
            ("deep learning", "Deep Learning"),
            ("machine learning", "Machine Learning"),
            ("gpu", "GPU"),
            ("cuda", "CUDA"),
            ("soc", "SoC"),
            ("software", "Software Engineering"),
            ("test", "Test Development"),
        )
        if keyword in normalized
    )
    return (*labels, posted_on)


def _matches(lead: JobLead, request: JobSearchRequest) -> bool:
    if "上海" not in lead.locations:
        return False
    if request.query is not None:
        searchable = " ".join(
            (lead.title, lead.direction, *lead.locations, *lead.highlights)
        ).casefold()
        if request.query.casefold() not in searchable:
            return False
    return not request.job_types or lead.job_type in request.job_types
