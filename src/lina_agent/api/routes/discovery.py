from datetime import UTC, date, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from lina_agent.api.dependencies import (
    get_conversational_assistant,
    get_job_recommendation_service,
    get_job_search_service,
)
from lina_agent.application.conversational_assistant import (
    AssistantResponse,
    ConversationalAssistantService,
)
from lina_agent.application.job_discovery import JobDiscoveryService
from lina_agent.domain.job_discovery import (
    JobDiscoveryResult,
    JobLead,
    JobRecommendationRequest,
    JobSearchRequest,
)

router = APIRouter(tags=["job discovery"])

JobSearchService = Annotated[JobDiscoveryService, Depends(get_job_search_service)]
JobRecommendationService = Annotated[
    JobDiscoveryService,
    Depends(get_job_recommendation_service),
]
ConversationalAssistant = Annotated[
    ConversationalAssistantService,
    Depends(get_conversational_assistant),
]


class OpportunitySnapshot(BaseModel):
    opportunity_id: str = Field(min_length=1)
    company: str = Field(min_length=1)
    title: str = Field(min_length=1)
    location: str = Field(min_length=1)
    direction: str = Field(min_length=1)
    source_url: str = Field(pattern=r"^https://")
    last_verified_at: date
    verification_status: Literal["live"]
    highlights: tuple[str, ...]


class OpportunityFeed(BaseModel):
    data_as_of: date
    freshness: Literal["live_and_verified", "verified_recommendations"]
    last_checked_at: datetime
    source_note: str
    opportunities: tuple[OpportunitySnapshot, ...]


class AssistantMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


def _to_opportunity(lead: JobLead) -> OpportunitySnapshot:
    return OpportunitySnapshot(
        opportunity_id=lead.external_id,
        company=lead.company,
        title=lead.title,
        location="、".join(lead.locations),
        direction=lead.direction,
        source_url=lead.source_url,
        last_verified_at=lead.captured_at.date(),
        verification_status="live",
        highlights=lead.highlights,
    )


@router.get("/opportunities", response_model=OpportunityFeed)
async def list_opportunities(service: JobRecommendationService) -> OpportunityFeed:
    result = await service.recommend(JobRecommendationRequest())
    successful_sources = tuple(
        source for source in result.sources if source.status.value == "success"
    )
    latest_source_time = max(
        (source.fetched_at for source in successful_sources),
        default=max(
            (lead.captured_at for lead in result.leads),
            default=datetime.now(UTC),
        ),
    )
    data_as_of = latest_source_time.date()
    freshness = (
        "live_and_verified"
        if any(source.source_id == "nvidia-careers" for source in successful_sources)
        else "verified_recommendations"
    )
    return OpportunityFeed(
        data_as_of=data_as_of,
        freshness=freshness,
        last_checked_at=latest_source_time,
        source_note=(
            "已合并 NVIDIA 官方实时岗位与经复核快照；申请前仍应打开官方链接确认。"
            if freshness == "live_and_verified"
            else "当前仅有经复核快照；申请前仍应打开官方链接确认。"
        ),
        opportunities=tuple(_to_opportunity(lead) for lead in result.leads),
    )


@router.post("/opportunities/search", response_model=JobDiscoveryResult)
async def search_opportunities(
    request: JobSearchRequest,
    service: JobSearchService,
) -> JobDiscoveryResult:
    return await service.search(request)


@router.post("/opportunities/recommended", response_model=JobDiscoveryResult)
async def recommend_opportunities(
    request: JobRecommendationRequest,
    service: JobRecommendationService,
) -> JobDiscoveryResult:
    return await service.recommend(request)


@router.post("/assistant/messages", response_model=AssistantResponse)
async def create_assistant_message(
    request: AssistantMessageRequest,
    assistant: ConversationalAssistant,
) -> AssistantResponse:
    return await assistant.respond(request.message)
