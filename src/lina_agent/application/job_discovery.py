from typing import Protocol

from lina_agent.domain.job_discovery import (
    CompanyPool,
    JobDiscoveryResult,
    JobLead,
    JobSearchRequest,
    JobSourceResult,
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
