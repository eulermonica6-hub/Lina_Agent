import asyncio
from datetime import UTC, datetime

from lina_agent.application.conversational_assistant import (
    AssistantAction,
    AssistantMode,
    AssistantTool,
    ConversationalAssistantService,
)
from lina_agent.application.job_discovery import JobDiscoveryService, JobSourceAdapter
from lina_agent.application.job_inbox import JobInboxService
from lina_agent.domain.job_changes import JobCaptureBatch, JobChangeEvent, JobChangeKind
from lina_agent.domain.job_discovery import (
    CompanyPool,
    JobLead,
    JobSearchRequest,
    JobSourceResult,
    JobSourceStatus,
    JobType,
    JobVerificationStatus,
)
from lina_agent.infrastructure.repositories.memory import InMemoryJobChangeRepository

_NOW = datetime(2026, 10, 1, tzinfo=UTC)


class FakeSource(JobSourceAdapter):
    source_id = "fake-official"

    def __init__(self, leads: tuple[JobLead, ...]) -> None:
        self._leads = leads
        self.requests: list[JobSearchRequest] = []

    async def search(self, request: JobSearchRequest) -> JobSourceResult:
        self.requests.append(request)
        return JobSourceResult(
            source_id=self.source_id,
            status=JobSourceStatus.SUCCESS,
            fetched_at=_NOW,
            leads=self._leads,
        )


def _lead(
    external_id: str,
    company: str,
    pool: CompanyPool,
    direction: str = "Agent",
) -> JobLead:
    return JobLead(
        lead_id=f"fake:{external_id}",
        deduplication_key=f"{company}:{external_id}",
        source_id="fake-official",
        external_id=external_id,
        company=company,
        company_pool=pool,
        title=f"{direction} Intern",
        job_type=JobType.INTERNSHIP,
        locations=("上海",),
        direction=direction,
        source_url=f"https://example.com/{external_id}",
        captured_at=_NOW,
        verification_status=JobVerificationStatus.LIVE,
        highlights=("Python", direction),
    )


def _assistant(
    leads: tuple[JobLead, ...] | None = None,
) -> tuple[ConversationalAssistantService, FakeSource, InMemoryJobChangeRepository]:
    source = FakeSource(
        leads
        or (
            _lead("domestic", "字节跳动", CompanyPool.DOMESTIC_MAJOR),
            _lead("global", "NVIDIA", CompanyPool.GLOBAL_MAJOR, "CUDA"),
        )
    )
    discovery = JobDiscoveryService((source,))
    repository = InMemoryJobChangeRepository()
    return (
        ConversationalAssistantService(
            discovery,
            discovery,
            JobInboxService(repository, clock=lambda: _NOW),
            company_names=("字节跳动", "NVIDIA"),
        ),
        source,
        repository,
    )


def test_assistant_searches_jobs_with_structured_preferences_and_sources() -> None:
    assistant, source, _ = _assistant()

    response = asyncio.run(assistant.respond("帮我找 NVIDIA 上海 Agent 实习"))

    assert response.mode is AssistantMode.TOOL_EXECUTION
    assert response.tool is AssistantTool.JOB_SEARCH
    assert response.suggested_action is AssistantAction.VIEW_OPPORTUNITIES
    assert response.missing_fields == ()
    assert len(response.opportunities) == 2
    assert all(item.source_status == "success" for item in response.opportunities)
    assert all(item.source_url.startswith("https://") for item in response.opportunities)
    request = source.requests[0]
    assert request.query == "Agent"
    assert request.companies == ("NVIDIA",)
    assert request.locations == ("上海",)
    assert request.job_types == (JobType.INTERNSHIP,)


def test_assistant_asks_for_missing_search_preferences_without_calling_tool() -> None:
    assistant, source, _ = _assistant()

    response = asyncio.run(assistant.respond("帮我找岗位"))

    assert response.mode is AssistantMode.CLARIFICATION
    assert response.tool is AssistantTool.JOB_SEARCH
    assert response.missing_fields == ("location", "job_type", "direction")
    assert "地点" in response.answer
    assert source.requests == []


def test_assistant_queries_unhandled_inbox_events() -> None:
    assistant, _, repository = _assistant()
    batch = JobCaptureBatch(source_id="nvidia-careers", captured_at=_NOW, job_count=1)
    event = JobChangeEvent(
        batch_id=batch.batch_id,
        source_id="nvidia-careers",
        external_id="JR1",
        kind=JobChangeKind.NEW,
        occurred_at=_NOW,
        current_fingerprint="a" * 64,
        title="AI Infra Intern",
        source_url="https://example.com/JR1",
    )
    asyncio.run(repository.save_capture(batch, (), (event,)))

    response = asyncio.run(assistant.respond("今天有什么新增岗位动态?"))

    assert response.mode is AssistantMode.TOOL_EXECUTION
    assert response.tool is AssistantTool.INBOX_QUERY
    assert response.suggested_action is AssistantAction.VIEW_INBOX
    assert [item.event_id for item in response.inbox_items] == [event.event_id]


def test_assistant_compares_two_verified_jobs_and_preserves_unknowns() -> None:
    assistant, _, _ = _assistant()

    response = asyncio.run(assistant.respond("比较这两个岗位"))

    assert response.mode is AssistantMode.TOOL_EXECUTION
    assert response.tool is AssistantTool.JOB_COMPARE
    assert len(response.opportunities) == 2
    assert "unknown" in response.answer
    assert "字节跳动" in response.answer
    assert "NVIDIA" in response.answer


def test_assistant_compares_explicit_companies_and_clarifies_one_company() -> None:
    assistant, source, _ = _assistant()

    explicit = asyncio.run(assistant.respond("比较 NVIDIA 和字节跳动岗位"))
    incomplete = asyncio.run(assistant.respond("比较 NVIDIA 岗位"))

    assert [item.company for item in explicit.opportunities] == ["NVIDIA", "字节跳动"]
    assert source.requests[0].companies == ("NVIDIA", "字节跳动")
    assert incomplete.mode is AssistantMode.CLARIFICATION
    assert incomplete.missing_fields == ("comparison_jobs",)


def test_assistant_clarifies_comparison_when_fewer_than_two_jobs_exist() -> None:
    assistant, _, _ = _assistant((_lead("only", "NVIDIA", CompanyPool.GLOBAL_MAJOR),))

    response = asyncio.run(assistant.respond("比较岗位"))

    assert response.mode is AssistantMode.CLARIFICATION
    assert response.missing_fields == ("comparison_jobs",)
    assert len(response.opportunities) == 1


def test_assistant_routes_resume_and_explains_available_tools() -> None:
    assistant, _, _ = _assistant()

    resume = asyncio.run(assistant.respond("怎么上传简历匹配?"))
    greeting = asyncio.run(assistant.respond("你好"))

    assert resume.mode is AssistantMode.GUIDANCE
    assert resume.suggested_action is AssistantAction.UPLOAD_RESUME
    assert greeting.mode is AssistantMode.GUIDANCE
    assert "搜索岗位" in greeting.answer
