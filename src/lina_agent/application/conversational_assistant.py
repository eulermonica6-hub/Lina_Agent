from enum import StrEnum

from pydantic import Field

from lina_agent.application.job_discovery import JobDiscoveryService
from lina_agent.application.job_inbox import JobInboxFilter, JobInboxService
from lina_agent.domain.job_changes import JobChangeKind, JobInboxItem
from lina_agent.domain.job_discovery import (
    JobLead,
    JobRecommendationRequest,
    JobSearchRequest,
    JobSourceResult,
    JobType,
)
from lina_agent.domain.models import DomainModel


class AssistantMode(StrEnum):
    TOOL_EXECUTION = "tool_execution"
    CLARIFICATION = "clarification"
    GUIDANCE = "guidance"


class AssistantAction(StrEnum):
    VIEW_OPPORTUNITIES = "view_opportunities"
    VIEW_INBOX = "view_inbox"
    UPLOAD_RESUME = "upload_resume"
    NONE = "none"


class AssistantTool(StrEnum):
    JOB_SEARCH = "job_search"
    INBOX_QUERY = "inbox_query"
    JOB_COMPARE = "job_compare"


class AssistantOpportunity(DomainModel):
    external_id: str = Field(min_length=1)
    company: str = Field(min_length=1)
    title: str = Field(min_length=1)
    locations: tuple[str, ...]
    direction: str = Field(min_length=1)
    source_url: str = Field(pattern=r"^https://")
    source_id: str = Field(min_length=1)
    source_status: str = Field(min_length=1)
    highlights: tuple[str, ...] = ()


class AssistantResponse(DomainModel):
    answer: str = Field(min_length=1)
    mode: AssistantMode
    suggested_action: AssistantAction = AssistantAction.NONE
    tool: AssistantTool | None = None
    missing_fields: tuple[str, ...] = ()
    opportunities: tuple[AssistantOpportunity, ...] = ()
    inbox_items: tuple[JobInboxItem, ...] = ()


_LOCATION_ALIASES = {
    "上海": "上海",
    "北京": "北京",
    "深圳": "深圳",
    "杭州": "杭州",
    "广州": "广州",
    "成都": "成都",
    "远程": "远程",
    "remote": "远程",
}
_DIRECTION_ALIASES = {
    "agent": "Agent",
    "大模型": "大模型",
    "llm": "LLM",
    "rag": "RAG",
    "cuda": "CUDA",
    "算法": "算法",
    "搜索": "搜索",
    "推荐": "推荐",
    "数据": "数据",
    "ai": "AI",
}
_JOB_TYPE_ALIASES = {
    "实习": JobType.INTERNSHIP,
    "intern": JobType.INTERNSHIP,
    "校招": JobType.CAMPUS,
    "应届": JobType.CAMPUS,
    "new grad": JobType.CAMPUS,
    "全职": JobType.FULL_TIME,
    "社招": JobType.FULL_TIME,
    "full time": JobType.FULL_TIME,
}


class ConversationalAssistantService:
    def __init__(
        self,
        search_service: JobDiscoveryService,
        recommendation_service: JobDiscoveryService,
        inbox_service: JobInboxService,
        *,
        company_names: tuple[str, ...] = (),
    ) -> None:
        self._search = search_service
        self._recommendations = recommendation_service
        self._inbox = inbox_service
        self._company_names = tuple(sorted(company_names, key=len, reverse=True))

    async def respond(self, message: str) -> AssistantResponse:
        normalized = message.casefold().strip()
        if _contains_any(normalized, ("简历", "resume", "匹配")):
            return AssistantResponse(
                answer="可以。请上传 TXT、Markdown 或 DOCX 简历，我会用当前岗位做证据化初筛。",
                mode=AssistantMode.GUIDANCE,
                suggested_action=AssistantAction.UPLOAD_RESUME,
            )
        if _contains_any(normalized, ("动态", "新增", "更新", "关闭", "重开", "inbox")):
            return await self._query_inbox(normalized)
        if _contains_any(normalized, ("比较", "对比", "区别", "compare")):
            return await self._compare_jobs(normalized)
        if _contains_any(normalized, ("岗位", "职位", "实习", "工作", "job", "agent")):
            return await self._search_jobs(message, normalized)
        return AssistantResponse(
            answer="我可以搜索岗位、查看岗位动态、比较岗位，或带你进入简历匹配。",
            mode=AssistantMode.GUIDANCE,
        )

    async def _search_jobs(self, message: str, normalized: str) -> AssistantResponse:
        locations = _extract_values(normalized, _LOCATION_ALIASES)
        job_types = _extract_values(normalized, _JOB_TYPE_ALIASES)
        directions = _extract_values(normalized, _DIRECTION_ALIASES)
        missing = tuple(
            field
            for field, values in (
                ("location", locations),
                ("job_type", job_types),
                ("direction", directions),
            )
            if not values
        )
        if missing:
            labels = {
                "location": "地点 (如上海或远程)",
                "job_type": "岗位类型 (实习、校招或全职)",
                "direction": "目标方向 (如 Agent、RAG 或 CUDA)",
            }
            return AssistantResponse(
                answer="请补充" + "、".join(labels[field] for field in missing) + "。",
                mode=AssistantMode.CLARIFICATION,
                tool=AssistantTool.JOB_SEARCH,
                missing_fields=missing,
            )

        companies = tuple(
            company for company in self._company_names if company.casefold() in normalized
        )
        query = str(directions[0])
        result = await self._search.search(
            JobSearchRequest(
                query=query,
                companies=companies,
                locations=tuple(str(value) for value in locations),
                job_types=tuple(job_types),
                max_results=10,
            )
        )
        opportunities = _opportunities(result.leads[:5], result.sources)
        healthy_sources = sum(source.status.value == "success" for source in result.sources)
        return AssistantResponse(
            answer=(
                f"我按“{message}”调用了岗位搜索，找到 {len(result.leads)} 条结果；"
                f"当前 {healthy_sources}/{len(result.sources)} 个来源成功。"
                "以下结果保留官方链接，申请前请再次确认。"
            ),
            mode=AssistantMode.TOOL_EXECUTION,
            suggested_action=AssistantAction.VIEW_OPPORTUNITIES,
            tool=AssistantTool.JOB_SEARCH,
            opportunities=opportunities,
        )

    async def _query_inbox(self, normalized: str) -> AssistantResponse:
        kind = next(
            (
                kind
                for token, kind in (
                    ("新增", JobChangeKind.NEW),
                    ("更新", JobChangeKind.UPDATED),
                    ("关闭", JobChangeKind.CLOSED),
                    ("重开", JobChangeKind.REOPENED),
                )
                if token in normalized
            ),
            None,
        )
        items = await self._inbox.list_items(
            kind=kind,
            state_filter=JobInboxFilter.UNHANDLED,
        )
        return AssistantResponse(
            answer=f"当前有 {len(items)} 条未处理岗位动态。",
            mode=AssistantMode.TOOL_EXECUTION,
            suggested_action=AssistantAction.VIEW_INBOX,
            tool=AssistantTool.INBOX_QUERY,
            inbox_items=items[:5],
        )

    async def _compare_jobs(self, normalized: str) -> AssistantResponse:
        companies = tuple(
            company for company in self._company_names if company.casefold() in normalized
        )
        if len(companies) == 1:
            return AssistantResponse(
                answer="请再提供一个要比较的公司或岗位。",
                mode=AssistantMode.CLARIFICATION,
                tool=AssistantTool.JOB_COMPARE,
                missing_fields=("comparison_jobs",),
            )
        if len(companies) >= 2:
            result = await self._search.search(
                JobSearchRequest(companies=companies[:2], max_results=20)
            )
            selected = tuple(
                next((lead for lead in result.leads if lead.company == company), None)
                for company in companies[:2]
            )
            leads = tuple(lead for lead in selected if lead is not None)
        else:
            result = await self._recommendations.recommend(JobRecommendationRequest(limit=2))
            leads = result.leads
        opportunities = _opportunities(leads, result.sources)
        if len(opportunities) < 2:
            return AssistantResponse(
                answer="当前不足两个可比较的已复核岗位，请先搜索或等待更多岗位。",
                mode=AssistantMode.CLARIFICATION,
                tool=AssistantTool.JOB_COMPARE,
                missing_fields=("comparison_jobs",),
                opportunities=opportunities,
            )
        first, second = opportunities
        return AssistantResponse(
            answer=(
                f"{first.company} 的“{first.title}”方向是 {first.direction}，地点为"
                f"{'、'.join(first.locations)}；{second.company} 的“{second.title}”方向是"
                f" {second.direction}，地点为{'、'.join(second.locations)}。"
                "两者都来自已复核官方链接，未声明条件保持 unknown。"
            ),
            mode=AssistantMode.TOOL_EXECUTION,
            suggested_action=AssistantAction.VIEW_OPPORTUNITIES,
            tool=AssistantTool.JOB_COMPARE,
            opportunities=opportunities,
        )


def _contains_any(value: str, tokens: tuple[str, ...]) -> bool:
    return any(token in value for token in tokens)


def _extract_values[ValueT](value: str, aliases: dict[str, ValueT]) -> tuple[ValueT, ...]:
    return tuple(dict.fromkeys(mapped for token, mapped in aliases.items() if token in value))


def _opportunities(
    leads: tuple[JobLead, ...],
    sources: tuple[JobSourceResult, ...],
) -> tuple[AssistantOpportunity, ...]:
    statuses = {source.source_id: source.status.value for source in sources}
    return tuple(
        AssistantOpportunity(
            external_id=lead.external_id,
            company=lead.company,
            title=lead.title,
            locations=lead.locations,
            direction=lead.direction,
            source_url=lead.source_url,
            source_id=lead.source_id,
            source_status=statuses.get(lead.source_id, "unknown"),
            highlights=lead.highlights,
        )
        for lead in leads
    )
