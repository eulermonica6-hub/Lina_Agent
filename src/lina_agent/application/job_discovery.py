from typing import Protocol

from lina_agent.domain.job_discovery import (
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

        return JobDiscoveryResult(
            sources=source_results,
            leads=tuple(unique_leads.values())[: request.max_results],
        )
