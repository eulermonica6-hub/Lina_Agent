import json

from pydantic import BaseModel, Field, ValidationError

from lina_agent.domain.career_matching import CandidateDocumentProfile, RankedJobMatch
from lina_agent.domain.career_planning import CareerActionPlan, CareerPlanAction
from lina_agent.infrastructure.llm_provider import LLMMessage, LLMProvider, LLMRequest

_SYSTEM_PROMPT = """你是职业行动计划节点。根据匿名化结构化技能匹配数据生成短期行动计划。
只输出 JSON，不要 Markdown。不得补造候选人经历，不得把覆盖分解释为录取概率。
Schema: {"summary": str, "priority_actions": [{"priority": 1..3, "action": str,
"reason": str}], "interview_focus": [str]}。priority_actions 必须为 1 到 3 项。"""


class CareerPlanningError(ValueError):
    """Raised when a model response cannot satisfy the career plan contract."""


class _PlanPayload(BaseModel):
    summary: str = Field(min_length=1, max_length=500)
    priority_actions: tuple[CareerPlanAction, ...] = Field(min_length=1, max_length=3)
    interview_focus: tuple[str, ...] = Field(default=(), max_length=3)


class LLMCareerPlanner:
    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    def create_plan(
        self,
        candidate: CandidateDocumentProfile,
        matches: tuple[RankedJobMatch, ...],
    ) -> CareerActionPlan:
        context = {
            "candidate_skills": [mention.skill for mention in candidate.skills],
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
        result = self._provider.complete(
            LLMRequest(
                messages=(
                    LLMMessage(role="system", content=_SYSTEM_PROMPT),
                    LLMMessage(
                        role="user",
                        content=json.dumps(context, ensure_ascii=False, separators=(",", ":")),
                    ),
                ),
                max_tokens=768,
                temperature=0.1,
            )
        )
        try:
            payload = _PlanPayload.model_validate_json(_strip_code_fence(result.content))
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
