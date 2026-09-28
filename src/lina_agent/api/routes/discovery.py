from datetime import date
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from lina_agent.application.job_discovery import JobDiscoveryService
from lina_agent.domain.job_discovery import (
    JobDiscoveryResult,
    JobLead,
    JobSearchRequest,
)
from lina_agent.domain.weekly_monitoring import MonitoredJobSource
from lina_agent.infrastructure.job_sources.registry import MONITORED_JOB_SOURCES
from lina_agent.infrastructure.job_sources.verified_snapshot import (
    VerifiedSnapshotJobSource,
)

router = APIRouter(tags=["job discovery"])
_discovery_service = JobDiscoveryService((VerifiedSnapshotJobSource(),))


class OpportunitySnapshot(BaseModel):
    opportunity_id: str = Field(min_length=1)
    company: str = Field(min_length=1)
    title: str = Field(min_length=1)
    location: str = Field(min_length=1)
    direction: str = Field(min_length=1)
    source_url: str = Field(pattern=r"^https://")
    last_verified_at: date
    verification_status: Literal["needs_reverification"]
    highlights: tuple[str, ...]


class OpportunityFeed(BaseModel):
    data_as_of: date
    freshness: Literal["historical_snapshot"]
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
        verification_status="needs_reverification",
        highlights=lead.highlights,
    )


@router.get("/opportunities", response_model=OpportunityFeed)
async def list_opportunities() -> OpportunityFeed:
    result = await _discovery_service.search(JobSearchRequest())
    data_as_of = max(lead.captured_at.date() for lead in result.leads)
    return OpportunityFeed(
        data_as_of=data_as_of,
        freshness="historical_snapshot",
        source_note="官方页面人工核验快照，不代表当前仍在招聘；申请前请打开官网重新确认。",
        opportunities=tuple(_to_opportunity(lead) for lead in result.leads),
    )


@router.post("/opportunities/search", response_model=JobDiscoveryResult)
async def search_opportunities(request: JobSearchRequest) -> JobDiscoveryResult:
    return await _discovery_service.search(request)


@router.get("/monitoring/sources", response_model=tuple[MonitoredJobSource, ...])
async def list_monitoring_sources() -> tuple[MonitoredJobSource, ...]:
    return MONITORED_JOB_SOURCES


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
            answer="我已加载官方页面人工核验快照。它们不是实时岗位，请先打开官网确认仍在招聘，再上传简历进行匹配。",
            suggested_action="view_opportunities",
        )
    return AssistantMessageResponse(
        answer="当前对话是类型化预览，可帮你查看岗位快照或定位简历匹配入口；尚未联网自主搜索，也没有多轮记忆。",
        suggested_action="none",
    )
