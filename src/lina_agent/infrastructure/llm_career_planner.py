import json

from pydantic import BaseModel, Field, ValidationError

from lina_agent.application.career_planner import CareerPlannerError
from lina_agent.domain.career_gap import CareerGapAnalysis
from lina_agent.domain.career_matching import CandidateDocumentProfile, RankedJobMatch
from lina_agent.domain.career_planning import CareerActionPlan, CareerPlanAction
from lina_agent.infrastructure.llm_provider import (
    LLMMessage,
    LLMProvider,
    LLMRequest,
    ProviderConfigurationError,
    ProviderExhaustedError,
    ProviderRequestError,
    ProviderResponseError,
    build_economic_router,
)

_SYSTEM_PROMPT = """你是职业行动计划节点。根据匿名化结构化技能匹配数据生成短期行动计划。
只输出 JSON，不要 Markdown。不得补造候选人经历，不得把覆盖分解释为录取概率。
每项行动的 target_skills 只能使用输入中出现的候选人技能或岗位缺口技能。
Schema: {"summary": str, "priority_actions": [{"priority": 1..3,
"target_skills": [str], "action": str, "reason": str, "deliverable": str,
"acceptance_criteria": str, "time_budget_hours": 1..80}], "interview_focus": [str]}。
priority_actions 必须为 1 到 3 项，priority 必须从 1 开始连续。"""


class CareerPlanningError(CareerPlannerError):
    """Raised when a model response cannot satisfy the career plan contract."""


class _PlanPayload(BaseModel):
    summary: str = Field(min_length=1, max_length=500)
    priority_actions: tuple[CareerPlanAction, ...] = Field(min_length=1, max_length=3)
    interview_focus: tuple[str, ...] = Field(default=(), max_length=3)


class LLMCareerPlanner:
    def __init__(self, provider: LLMProvider | None = None) -> None:
        self._provider = provider

    def create_plan(
        self,
        candidate: CandidateDocumentProfile,
        matches: tuple[RankedJobMatch, ...],
        gap_analysis: CareerGapAnalysis,
    ) -> CareerActionPlan:
        context = {
            "candidate_skills": [mention.skill for mention in candidate.skills],
            "skill_gaps": [
                {
                    "skill": gap.skill,
                    "required_by_jobs": gap.required_by_jobs,
                    "preferred_by_jobs": gap.preferred_by_jobs,
                    "priority_score": gap.priority_score,
                }
                for gap in gap_analysis.gaps
            ],
            "top_jobs": [
                {
                    "title": match.title,
                    "company": match.company,
                    "evidence_coverage_score": match.score,
                    "matched_required": [item.skill for item in match.matched_required],
                    "missing_required": [item.skill for item in match.missing_required],
                    "matched_preferred": [item.skill for item in match.matched_preferred],
                    "matched_contextual": [item.skill for item in match.matched_contextual],
                }
                for match in matches[:3]
            ],
        }
        try:
            provider = self._provider or build_economic_router()
            result = provider.complete(
                LLMRequest(
                    messages=(
                        LLMMessage(role="system", content=_SYSTEM_PROMPT),
                        LLMMessage(
                            role="user",
                            content=json.dumps(
                                context,
                                ensure_ascii=False,
                                separators=(",", ":"),
                            ),
                        ),
                    ),
                    max_tokens=1024,
                    temperature=0.1,
                    response_format="json_object",
                    reasoning_effort="none",
                )
            )
        except (
            ProviderConfigurationError,
            ProviderExhaustedError,
            ProviderRequestError,
            ProviderResponseError,
        ) as error:
            raise CareerPlanningError("模型服务暂不可用，已保留确定性分析结果。") from error
        try:
            payload = _parse_plan_payload(result.content)
        except (ValueError, ValidationError) as error:
            raise CareerPlanningError("模型未返回符合 Schema 的职业行动计划。") from error
        return CareerActionPlan(
            **payload.model_dump(),
            provider=result.provider.value,
            model=result.model,
            total_tokens=result.usage.total_tokens,
        )


def _strip_code_fence(content: str) -> str:
    stripped = content.strip()
    if stripped.startswith("```") and stripped.endswith("```"):
        lines = stripped.splitlines()
        return "\n".join(lines[1:-1]).strip()
    return stripped


def _parse_plan_payload(content: str) -> _PlanPayload:
    stripped = _strip_code_fence(content)
    decoder = json.JSONDecoder()
    for index, character in enumerate(stripped):
        if character != "{":
            continue
        try:
            value, _ = decoder.raw_decode(stripped[index:])
            return _PlanPayload.model_validate(value)
        except (ValueError, ValidationError):
            continue
    raise ValueError("没有找到符合计划 Schema 的 JSON 对象")
