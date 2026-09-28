import hashlib
from datetime import date, timedelta
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

    async def search(self, request: JobSearchRequest) -> JobDiscoveryResult:
        source_results = tuple([await source.search(request) for source in self._sources])
        unique_leads: dict[str, JobLead] = {}
        for source_result in source_results:
            for lead in source_result.leads:
                unique_leads.setdefault(lead.deduplication_key, lead)

        ordered_leads = tuple(unique_leads.values())
        anchor_leads = tuple(
            lead for lead in ordered_leads if lead.company_pool is CompanyPool.ANCHOR
        )
        focused_leads = tuple(
            lead for lead in ordered_leads if lead.company_pool is CompanyPool.FOCUSED_AI
        )
        balanced_leads = tuple(
            lead
            for index in range(max(len(anchor_leads), len(focused_leads)))
            for lead in (
                anchor_leads[index] if index < len(anchor_leads) else None,
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
        week_start = request.week_start or (date.today() - timedelta(days=date.today().weekday()))
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
                f"{week_start.isoformat()}:{lead.lead_id}".encode()
            ).hexdigest()
            return -score, rotation

        anchor = sorted(
            (lead for lead in eligible_leads if lead.company_pool is CompanyPool.ANCHOR),
            key=ranking_key,
        )
        focused = sorted(
            (lead for lead in eligible_leads if lead.company_pool is CompanyPool.FOCUSED_AI),
            key=ranking_key,
        )
        selected = [*anchor[:6], *focused[:3]]
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
