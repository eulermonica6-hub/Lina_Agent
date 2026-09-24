from uuid import uuid4

import pytest

from lina_agent.domain.career_gap import (
    GapPriority,
    PlanReviewStatus,
    analyze_career_gaps,
    build_skill_evidence_plan,
    review_action_plan,
)
from lina_agent.domain.career_matching import (
    CandidateDocumentProfile,
    EvidenceMatch,
    RankedJobMatch,
    SkillMention,
)
from lina_agent.domain.career_planning import CareerActionPlan, CareerPlanAction
from lina_agent.domain.models import SourceEvidence

DOCUMENT_ID = uuid4()


def _evidence(text: str, offset: int) -> SourceEvidence:
    return SourceEvidence(
        document_id=DOCUMENT_ID,
        text=text,
        start_offset=offset,
        end_offset=offset + len(text),
    )


def _mention(skill: str, offset: int) -> SkillMention:
    return SkillMention(skill=skill, evidence=(_evidence(skill, offset),))


def _match(
    number: int,
    *,
    missing_required: tuple[SkillMention, ...] = (),
    missing_preferred: tuple[SkillMention, ...] = (),
    matched: tuple[EvidenceMatch, ...] = (),
) -> RankedJobMatch:
    return RankedJobMatch(
        catalog_number=number,
        title=f"岗位 {number}",
        company="测试公司",
        score=50,
        missing_required=missing_required,
        missing_preferred=missing_preferred,
        matched_required=matched,
    )


def _action(
    priority: int,
    target_skill: str,
    action: str,
) -> CareerPlanAction:
    return CareerPlanAction(
        priority=priority,
        target_skills=(target_skill,),
        action=action,
        reason="岗位证据要求",
        deliverable="可复现项目",
        acceptance_criteria="测试通过并附说明",
        time_budget_hours=8,
    )


def test_aggregates_required_preferred_gaps_and_evidence_strengths() -> None:
    python_candidate = _evidence("Python", 100)
    python_job = _evidence("Python", 200)
    python_match = EvidenceMatch(
        skill="Python",
        candidate_evidence=python_candidate,
        job_evidence=python_job,
    )
    repeated_required = _mention("LangGraph", 0)
    preferred_medium = _mention("Docker", 20)
    preferred_low = _mention("Redis", 40)
    matches = (
        _match(
            1,
            missing_required=(repeated_required,),
            missing_preferred=(preferred_medium, preferred_low),
            matched=(python_match,),
        ),
        _match(
            2,
            missing_required=(repeated_required,),
            missing_preferred=(preferred_medium,),
            matched=(python_match,),
        ),
        _match(3, missing_preferred=(preferred_medium,)),
    )

    analysis = analyze_career_gaps(matches)

    assert analysis.analyzed_jobs == 3
    assert [gap.skill for gap in analysis.gaps] == ["LangGraph", "Docker", "Redis"]
    assert [gap.priority for gap in analysis.gaps] == [
        GapPriority.HIGH,
        GapPriority.MEDIUM,
        GapPriority.LOW,
    ]
    assert analysis.gaps[0].affected_catalog_numbers == (1, 2)
    assert len(analysis.gaps[0].job_evidence) == 1
    assert analysis.strengths[0].skill == "Python"
    assert analysis.strengths[0].covered_jobs == 2


def test_review_accepts_contiguous_evidence_backed_plan() -> None:
    candidate = CandidateDocumentProfile(
        document_id=DOCUMENT_ID,
        source_name="resume.txt",
        skills=(_mention("Python", 100),),
    )
    analysis = analyze_career_gaps((_match(1, missing_required=(_mention("LangGraph", 0),)),))
    plan = CareerActionPlan(
        summary="补齐编排缺口",
        priority_actions=(
            _action(1, "LangGraph", "完成编排项目"),
            _action(2, "Python", "整理工程证据"),
        ),
        provider="groq",
        model="test",
        total_tokens=20,
    )

    review = review_action_plan(plan, candidate, analysis)

    assert review.status is PlanReviewStatus.VERIFIED
    assert review.issues == ()
    assert review.verified_target_skills == ("LangGraph", "Python")


def test_review_rejects_priority_duplicate_and_unknown_skill() -> None:
    candidate = CandidateDocumentProfile(
        document_id=DOCUMENT_ID,
        source_name="resume.txt",
        skills=(_mention("Python", 100),),
    )
    analysis = analyze_career_gaps((_match(1, missing_required=(_mention("LangGraph", 0),)),))
    plan = CareerActionPlan(
        summary="不合格计划",
        priority_actions=(
            _action(2, "LangGraph", "重复行动"),
            _action(3, "Kubernetes", "重复行动"),
        ),
        provider="groq",
        model="test",
        total_tokens=20,
    )

    review = review_action_plan(plan, candidate, analysis)

    assert review.status is PlanReviewStatus.REJECTED
    assert len(review.issues) == 3
    assert review.verified_target_skills == ("LangGraph",)


def test_builds_deterministic_evidence_plan_for_nvidia_skill_gap() -> None:
    target = _match(
        6,
        missing_required=(
            _mention("PyTorch", 0),
            _mention("C++", 20),
            _mention("CUDA", 40),
            _mention("Deep Learning", 60),
        ),
    )

    plan = build_skill_evidence_plan(target)

    assert [action.priority for action in plan.priority_actions] == [1, 2, 3]
    assert [action.target_skills for action in plan.priority_actions] == [
        ("PyTorch",),
        ("C++",),
        ("CUDA",),
    ]
    assert "推理" in plan.priority_actions[0].deliverable
    assert "基准" in plan.priority_actions[2].acceptance_criteria
    assert plan.provider == "deterministic"
    assert plan.total_tokens == 0
    review = review_action_plan(
        plan,
        CandidateDocumentProfile(document_id=DOCUMENT_ID, source_name="resume.txt"),
        analyze_career_gaps((target,)),
    )
    assert review.status is PlanReviewStatus.VERIFIED
    assert review.verified_target_skills == ("PyTorch", "C++", "CUDA")


def test_rejects_skill_evidence_plan_when_target_has_no_required_gap() -> None:
    with pytest.raises(ValueError, match="没有待补齐"):
        build_skill_evidence_plan(_match(1))
