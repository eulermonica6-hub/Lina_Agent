import hashlib
from datetime import date
from typing import Protocol

from lina_agent.domain.job_discovery import (
    CompanyPool,
    JobDiscoveryResult,
    JobLead,
    JobRecommendationRequest,
    JobSearchRequest,
    JobSourceResult,
    JobVerificationStatus,
)


class JobSourceAdapter(Protocol):
    source_id: str

    async def search(self, request: JobSearchRequest) -> JobSourceResult: ...


class JobDiscoveryService:
    def __init__(self, sources: tuple[JobSourceAdapter, ...]) -> None:
        self._sources = sources

    @property
    def source_ids(self) -> tuple[str, ...]:
        return tuple(source.source_id for source in self._sources)

    async def search(self, request: JobSearchRequest) -> JobDiscoveryResult:
        source_results = tuple([await source.search(request) for source in self._sources])
        unique_leads: dict[str, JobLead] = {}
        for source_result in source_results:
            for lead in source_result.leads:
                unique_leads.setdefault(lead.deduplication_key, lead)

        ordered_leads = tuple(unique_leads.values())
        major_leads = tuple(
            lead for lead in ordered_leads if lead.company_pool is not CompanyPool.FOCUSED_AI
        )
        focused_leads = tuple(
            lead for lead in ordered_leads if lead.company_pool is CompanyPool.FOCUSED_AI
        )
        balanced_leads = tuple(
            lead
            for index in range(max(len(major_leads), len(focused_leads)))
            for lead in (
                major_leads[index] if index < len(major_leads) else None,
                focused_leads[index] if index < len(focused_leads) else None,
            )
            if lead is not None
        )
        return JobDiscoveryResult(
            sources=source_results,
            leads=balanced_leads[: request.max_results],
        )

    async def recommend(self, request: JobRecommendationRequest) -> JobDiscoveryResult:
        discovery = await self.search(JobSearchRequest(max_results=100))
        eligible_leads = tuple(
            lead
            for lead in discovery.leads
            if lead.verification_status is JobVerificationStatus.LIVE
        )
        rotation_date = request.rotation_date or request.week_start or date.today()
        preferred_companies = {value.casefold() for value in request.preferred_companies}
        recent_companies = {value.casefold() for value in request.recent_companies}
        preferred_directions = tuple(value.casefold() for value in request.preferred_directions)
        preferred_locations = {value.casefold() for value in request.preferred_locations}

        def ranking_key(lead: JobLead) -> tuple[int, str]:
            score = 0
            if lead.company.casefold() in preferred_companies:
                score += 100
            if lead.company.casefold() in recent_companies:
                score += 50
            searchable = " ".join((lead.direction, *lead.highlights)).casefold()
            score += 20 * sum(direction in searchable for direction in preferred_directions)
            lead_locations = {location.casefold() for location in lead.locations}
            if preferred_locations & lead_locations:
                score += 30
            if lead.job_type in request.preferred_job_types:
                score += 30
            rotation = hashlib.sha256(
                f"{rotation_date.isoformat()}:{lead.lead_id}".encode()
            ).hexdigest()
            return -score, rotation

        domestic_major = sorted(
            (
                lead
                for lead in eligible_leads
                if lead.company_pool in {CompanyPool.ANCHOR, CompanyPool.DOMESTIC_MAJOR}
            ),
            key=ranking_key,
        )
        global_major = sorted(
            (lead for lead in eligible_leads if lead.company_pool is CompanyPool.GLOBAL_MAJOR),
            key=ranking_key,
        )
        focused = sorted(
            (lead for lead in eligible_leads if lead.company_pool is CompanyPool.FOCUSED_AI),
            key=ranking_key,
        )
        base_quota, remainder = divmod(request.limit, 3)
        domestic_quota = base_quota + int(remainder >= 1)
        global_quota = base_quota + int(remainder >= 2)
        focused_quota = base_quota
        selected = [
            *domestic_major[:domestic_quota],
            *global_major[:global_quota],
            *focused[:focused_quota],
        ]
        selected_ids = {lead.lead_id for lead in selected}
        remaining = sorted(
            (lead for lead in eligible_leads if lead.lead_id not in selected_ids),
            key=ranking_key,
        )
        selected.extend(remaining[: max(0, request.limit - len(selected))])
        return JobDiscoveryResult(
            sources=discovery.sources,
            leads=tuple(selected[: request.limit]),
        )
