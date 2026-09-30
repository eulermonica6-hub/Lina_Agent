import json
import re
from collections.abc import Callable
from datetime import UTC, datetime
from hashlib import sha256
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

_SOURCE_ID = "nvidia-careers"
_API_URL = "https://nvidia.wd5.myworkdayjobs.com/wday/cxs/nvidia/NVIDIAExternalCareerSite/jobs"
_DETAIL_API_BASE_URL = (
    "https://nvidia.wd5.myworkdayjobs.com/wday/cxs/nvidia/NVIDIAExternalCareerSite"
)
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


class _WorkdayPostingInfo(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    title: str = Field(min_length=1)
    job_description: str = Field(alias="jobDescription", min_length=1)
    location: str = Field(min_length=1)
    posted_on: str = Field(alias="postedOn", min_length=1)
    start_date: str = Field(alias="startDate", min_length=1)
    time_type: str = Field(alias="timeType", min_length=1)
    job_req_id: str = Field(alias="jobReqId", min_length=1)


class _WorkdayDetailResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    job_posting_info: _WorkdayPostingInfo = Field(alias="jobPostingInfo")


class _DescriptionParser(HTMLParser):
    _BLOCK_TAGS: ClassVar[set[str]] = {"br", "li", "p", "ul"}

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
            self.parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._BLOCK_TAGS:
            self.parts.append(" ")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


class NvidiaWorkdayJobSource:
    source_id = _SOURCE_ID

    def __init__(
        self,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        clock: Callable[[], datetime] | None = None,
        page_size: int = 20,
        full_capture: bool = False,
    ) -> None:
        self._transport = transport
        self._clock = clock or (lambda: datetime.now(UTC))
        self._page_size = min(20, max(1, page_size))
        self._full_capture = full_capture

    async def search(self, request: JobSearchRequest) -> JobSourceResult:
        if not _supports_request(request):
            return self._result(JobSourceStatus.SUCCESS)

        search_text = "Shanghai"
        if request.query is not None and not self._full_capture:
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
                while self._full_capture or len(leads) < request.max_results:
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
                        detail_response = await client.get(
                            f"{_DETAIL_API_BASE_URL}{posting.external_path}"
                        )
                        detail_error = self._http_error_result(detail_response)
                        if detail_error is not None:
                            return self._result(
                                JobSourceStatus.PARTIAL,
                                f"detail_{detail_error.error_code}",
                                leads=tuple(leads),
                            )
                        try:
                            detail = _WorkdayDetailResponse.model_validate(
                                detail_response.json()
                            ).job_posting_info
                        except (ValueError, ValidationError):
                            return self._result(
                                JobSourceStatus.STRUCTURE_CHANGED,
                                "invalid_workday_detail",
                                leads=tuple(leads),
                            )
                        lead = _to_lead(posting, detail, self._clock())
                        matches_request = (
                            "上海" in lead.locations
                            if self._full_capture
                            else _matches(lead, request)
                        )
                        if lead.external_id in seen_ids or not matches_request:
                            continue
                        seen_ids.add(lead.external_id)
                        leads.append(lead)
                        if not self._full_capture and len(leads) >= request.max_results:
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


def _to_lead(
    posting: _WorkdayPosting,
    detail: _WorkdayPostingInfo,
    captured_at: datetime,
) -> JobLead:
    external_id = detail.job_req_id
    locations = _locations(posting, detail)
    direction = _direction(detail.title)
    normalized_description = _normalize_description(detail.job_description)
    content_fingerprint = _content_fingerprint(
        title=detail.title,
        locations=locations,
        job_type=_job_type(detail.title),
        direction=direction,
        description=normalized_description,
        start_date=detail.start_date,
        time_type=detail.time_type,
    )
    return JobLead(
        lead_id=f"{_SOURCE_ID}:{external_id}",
        deduplication_key=f"nvidia:{detail.title.casefold()}:{'|'.join(locations)}",
        source_id=_SOURCE_ID,
        external_id=external_id,
        company="NVIDIA",
        company_pool=CompanyPool.GLOBAL_MAJOR,
        title=detail.title,
        job_type=_job_type(detail.title),
        locations=locations,
        direction=direction,
        source_url=f"{_PUBLIC_BASE_URL}{posting.external_path}",
        captured_at=captured_at,
        verification_status=JobVerificationStatus.LIVE,
        highlights=_highlights(detail.title, detail.posted_on),
        normalized_description=normalized_description,
        content_fingerprint=content_fingerprint,
    )


def _locations(
    posting: _WorkdayPosting,
    detail: _WorkdayPostingInfo,
) -> tuple[str, ...]:
    path = posting.external_path.casefold()
    if "china-shanghai" in path:
        return ("上海",)
    if "china-beijing" in path:
        return ("北京", "上海") if "locations" in posting.locations_text.casefold() else ("北京",)
    return tuple(part.strip() for part in detail.location.split(";") if part.strip())


def _normalize_description(description_html: str) -> str:
    parser = _DescriptionParser()
    parser.feed(description_html)
    parser.close()
    return " ".join("".join(parser.parts).split())


def _content_fingerprint(
    *,
    title: str,
    locations: tuple[str, ...],
    job_type: JobType,
    direction: str,
    description: str,
    start_date: str,
    time_type: str,
) -> str:
    payload = json.dumps(
        {
            "title": title,
            "locations": locations,
            "job_type": job_type,
            "direction": direction,
            "description": description,
            "start_date": start_date,
            "time_type": time_type,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(payload.encode("utf-8")).hexdigest()


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
