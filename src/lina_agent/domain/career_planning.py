from pydantic import Field

from lina_agent.domain.models import DomainModel


class CareerPlanAction(DomainModel):
    priority: int = Field(ge=1, le=3)
    target_skills: tuple[str, ...] = Field(min_length=1, max_length=3)
    action: str = Field(min_length=1, max_length=200)
    reason: str = Field(min_length=1, max_length=300)
    deliverable: str = Field(min_length=1, max_length=200)
    acceptance_criteria: str = Field(min_length=1, max_length=300)
    time_budget_hours: int = Field(ge=1, le=80)


class CareerActionPlan(DomainModel):
    summary: str = Field(min_length=1, max_length=500)
    priority_actions: tuple[CareerPlanAction, ...] = Field(min_length=1, max_length=3)
    interview_focus: tuple[str, ...] = Field(default=(), max_length=3)
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    total_tokens: int = Field(ge=0)
