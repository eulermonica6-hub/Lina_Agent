from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from lina_agent.api.dependencies import (
    get_job_recommendation_service,
    get_job_search_service,
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
    freshness: Literal["verified_recommendations"]
    source_note: str
    opportunities: tuple[OpportunitySnapshot, ...]


class AssistantMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class AssistantMessageResponse(BaseModel):
    answer: str
    mode: Literal["typed_preview"] = "typed_preview"
    suggested_action: Literal["view_opportunities", "upload_resume", "none"]


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
    data_as_of = max(lead.captured_at.date() for lead in result.leads)
    return OpportunityFeed(
        data_as_of=data_as_of,
        freshness="verified_recommendations",
        source_note="2026-09-28 已复核官方详情与投递入口；申请前仍应再次确认。",
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


@router.post("/assistant/messages", response_model=AssistantMessageResponse)
async def create_assistant_message(
    request: AssistantMessageRequest,
) -> AssistantMessageResponse:
    normalized = request.message.casefold()
    if any(keyword in normalized for keyword in ("简历", "resume", "匹配")):
        return AssistantMessageResponse(
            answer=(
                "可以。打开“简历匹配”区域上传 TXT、Markdown 或 DOCX 简历，"
                "我会用当前岗位快照做证据化初筛。"
            ),
            suggested_action="upload_resume",
        )
    if any(keyword in normalized for keyword in ("岗位", "实习", "工作", "job", "agent")):
        return AssistantMessageResponse(
            answer=(
                "我已加载 2026-09-28 复核过详情和投递入口的岗位。"
                "申请前仍建议再次打开官网确认，也可以上传简历进行匹配。"
            ),
            suggested_action="view_opportunities",
        )
    return AssistantMessageResponse(
        answer="当前对话是类型化预览，可帮你查看岗位快照或定位简历匹配入口；尚未联网自主搜索，也没有多轮记忆。",
        suggested_action="none",
    )
