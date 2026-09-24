import pytest

from lina_agent.domain.career_matching import (
    CandidateAvailabilityConfirmation,
    CandidateDirectionPreferenceConfirmation,
    ConstraintStatus,
    DecisionSignals,
    DecisionWeights,
    MatchWeights,
    extract_candidate_profile,
    extract_decision_signals,
    extract_job_skill_profile,
    score_job_match,
)
from lina_agent.domain.job_catalog import CatalogJob, parse_job_catalog
from lina_agent.infrastructure.document_loader import LocalDocumentLoader


def _job_from(markdown: str) -> CatalogJob:
    document = LocalDocumentLoader().load_bytes("jobs.md", markdown.encode())
    return parse_job_catalog(document)[0]


def test_extracts_canonical_candidate_skills_with_precise_evidence() -> None:
    document = LocalDocumentLoader().load_bytes(
        "resume.txt",
        "Agentic 不是独立命中\nPython、RAG、多智能体、C++、GitHub、API 接口与数据分析".encode(),
    )

    profile = extract_candidate_profile(document)

    names = {mention.skill for mention in profile.skills}
    assert {"Python", "RAG", "Multi-Agent", "C++", "Git", "REST API", "Data Analysis"} <= names
    python = next(mention for mention in profile.skills if mention.skill == "Python")
    evidence = python.evidence[0]
    assert document.text[evidence.start_offset : evidence.end_offset] == "Python"

    boundary_profile = extract_candidate_profile(
        LocalDocumentLoader().load_bytes("boundary.txt", b"Agentic architecture")
    )
    assert "Agent" not in {mention.skill for mention in boundary_profile.skills}

    alias_profile = extract_candidate_profile(
        LocalDocumentLoader().load_bytes("aliases.txt", b"LLMs and HTTP API")
    )
    assert {mention.skill for mention in alias_profile.skills} == {"LLM", "REST API"}


def test_classifies_requirements_and_scores_evidence_coverage() -> None:
    candidate_document = LocalDocumentLoader().load_bytes(
        "resume.txt", "使用 Python 构建 RAG 系统".encode()
    )
    job = _job_from(
        """### 1. Agent 工程师 | 甲公司
**岗位职责**
- 使用 Agent 编排 RAG
**任职要求**
- 熟悉 Python 与 LangGraph
- RAG 经验优先
- Python 项目经验优先
"""
    )
    candidate = extract_candidate_profile(candidate_document)

    job_skills = extract_job_skill_profile(job)
    result = score_job_match(candidate, job, job_skills)

    assert {item.skill for item in job_skills.required} == {"Python", "LangGraph"}
    assert {item.skill for item in job_skills.preferred} == {"RAG"}
    assert {item.skill for item in job_skills.contextual} == {"Agent"}
    assert result.required_coverage == 0.5
    assert result.preferred_coverage == 1.0
    assert result.contextual_coverage == 0.0
    assert result.score == 55.0
    assert result.skill_score == 55.0
    assert [item.skill for item in result.matched_required] == ["Python"]
    assert [item.skill for item in result.missing_required] == ["LangGraph"]
    assert [item.skill for item in result.matched_preferred] == ["RAG"]
    assert result.matched_contextual == ()

    calibrated = score_job_match(
        candidate,
        job,
        job_skills,
        MatchWeights(required=0.5, preferred=0.5, contextual=0),
    )
    assert calibrated.score == 75.0

    combined = score_job_match(
        candidate,
        job,
        job_skills,
        decision_signals=DecisionSignals(
            hard_compatibility=1,
            direction_alignment=0.8,
            explanations=("硬条件兼容", "方向高度匹配"),
        ),
        decision_weights=DecisionWeights(skill=0.3, hard=0.2, direction=0.5),
    )
    assert combined.skill_score == 55.0
    assert combined.score == 76.5
    assert combined.decision_explanations == ("硬条件兼容", "方向高度匹配")

    direction_only = score_job_match(
        candidate,
        job,
        job_skills,
        decision_signals=DecisionSignals(direction_alignment=1),
        decision_weights=DecisionWeights(skill=0, hard=0, direction=1),
    )
    assert direction_only.score == 100

    no_active_component = score_job_match(
        candidate,
        job,
        job_skills,
        decision_signals=DecisionSignals(),
        decision_weights=DecisionWeights(skill=0, hard=0, direction=0),
    )
    assert no_active_component.score == 0

    hard_rejected = score_job_match(
        candidate,
        job,
        job_skills,
        decision_signals=DecisionSignals(hard_compatibility=0, direction_alignment=1),
    )
    assert hard_rejected.score == 0


def test_returns_zero_when_job_contains_no_taxonomy_skills() -> None:
    candidate = extract_candidate_profile(LocalDocumentLoader().load_bytes("resume.txt", b"Python"))
    job = _job_from("### 1. 综合岗位 | 甲公司\n**任职要求**\n- 沟通能力强")

    result = score_job_match(candidate, job, extract_job_skill_profile(job))

    assert result.score == 0
    assert result.required_coverage is None
    assert result.preferred_coverage is None
    assert result.contextual_coverage is None


def test_extracts_evidence_backed_decision_signals_without_assuming_unknowns() -> None:
    loader = LocalDocumentLoader()
    resume = loader.load_bytes(
        "resume.txt",
        "2027 届硕士，期望地点上海。目标方向：AI Agent 与大模型应用。".encode(),
    )
    job = _job_from(
        """### 1. Agent 实习生 | 甲公司
**基本信息**
- 工作地点：上海
- 每周到岗 4 天，连续实习 3 个月
**任职要求**
- 2026、2027 届本科及以上学历
**岗位职责**
- 开发 AI Agent 与大模型应用
"""
    )

    extraction = extract_decision_signals(resume, job)

    assert extraction.signals.hard_compatibility == 1
    assert extraction.signals.direction_alignment == 1
    assert {item.name: item.status for item in extraction.hard_constraints} == {
        "graduation_year": ConstraintStatus.MET,
        "education": ConstraintStatus.MET,
        "location": ConstraintStatus.MET,
        "weekly_days": ConstraintStatus.UNKNOWN,
        "duration_months": ConstraintStatus.UNKNOWN,
    }
    assert extraction.directions[0].name == "agent_llm_application"
    for item in (*extraction.hard_constraints, *extraction.directions):
        for evidence in (*item.candidate_evidence, *item.job_evidence):
            source = resume if evidence.document_id == resume.id else None
            if source is None:
                assert evidence.text in job.raw_text
            else:
                assert source.text[evidence.start_offset : evidence.end_offset] == evidence.text

    availability = extract_decision_signals(
        loader.load_bytes("availability.txt", "每周实习 5 天，可连续实习 2 个月".encode()),
        job,
    )
    statuses = {item.name: item.status for item in availability.hard_constraints}
    assert statuses["weekly_days"] is ConstraintStatus.MET
    assert statuses["duration_months"] is ConstraintStatus.UNMET


@pytest.mark.parametrize(
    ("candidate_availability", "job_requirement", "expected_status"),
    [
        ("可连续实习至少一年", "至少 1 年", ConstraintStatus.MET),
        ("可连续实习 4 个月", "连续 3-4 个月", ConstraintStatus.MET),
        ("可连续实习 2 个月", "至少持续实习 3 个月", ConstraintStatus.UNMET),
        ("可连续实习 6 个月", "连续实习 3 至 6 个月", ConstraintStatus.MET),
    ],
)
def test_normalizes_internship_duration_ranges(
    candidate_availability: str,
    job_requirement: str,
    expected_status: ConstraintStatus,
) -> None:
    loader = LocalDocumentLoader()
    resume = loader.load_bytes("resume.txt", candidate_availability.encode())
    job = _job_from(
        f"""### 1. 实习岗位 | 甲公司
**基本信息**
- {job_requirement}
"""
    )

    extraction = extract_decision_signals(resume, job)

    duration = next(item for item in extraction.hard_constraints if item.name == "duration_months")
    assert duration.status is expected_status


def test_matches_graduation_onward_and_bare_catalog_location() -> None:
    loader = LocalDocumentLoader()
    resume = loader.load_bytes(
        "resume.txt",
        "期望城市：上海；预计毕业：2028 年".encode(),
    )
    job = _job_from(
        """### 1. 实习岗位 | 甲公司
**基本信息**
- 上海；2027 届及以后在读
"""
    )

    extraction = extract_decision_signals(resume, job)

    statuses = {item.name: item.status for item in extraction.hard_constraints}
    assert statuses == {
        "graduation_year": ConstraintStatus.MET,
        "location": ConstraintStatus.MET,
    }


def test_keeps_only_the_candidate_evidence_used_for_constraint_comparison() -> None:
    loader = LocalDocumentLoader()
    resume = loader.load_bytes("resume.txt", "最高学历硕士；此前获得本科学历".encode())
    job = _job_from(
        """### 1. 实习岗位 | 甲公司
**基本信息**
- 本科及以上学历
"""
    )

    extraction = extract_decision_signals(resume, job)

    education = next(item for item in extraction.hard_constraints if item.name == "education")
    assert education.status is ConstraintStatus.MET
    assert tuple(item.text for item in education.candidate_evidence) == ("硕士",)


def test_applies_confirmed_availability_without_fabricating_document_evidence() -> None:
    loader = LocalDocumentLoader()
    resume = loader.load_bytes("resume.txt", "Python 项目".encode())
    job = _job_from(
        """### 1. 实习岗位 | 甲公司
**基本信息**
- 每周 4 天；连续 3 个月
"""
    )

    unknown = extract_decision_signals(resume, job)
    confirmed = extract_decision_signals(
        resume,
        job,
        availability=CandidateAvailabilityConfirmation(
            weekly_days=5,
            duration_months=2,
        ),
    )

    assert {item.name: item.status for item in unknown.hard_constraints} == {
        "weekly_days": ConstraintStatus.UNKNOWN,
        "duration_months": ConstraintStatus.UNKNOWN,
    }
    confirmed_items = {item.name: item for item in confirmed.hard_constraints}
    assert confirmed_items["weekly_days"].status is ConstraintStatus.MET
    assert confirmed_items["duration_months"].status is ConstraintStatus.UNMET
    assert confirmed_items["weekly_days"].candidate_evidence == ()
    assert confirmed_items["weekly_days"].candidate_confirmation is not None
    assert confirmed_items["weekly_days"].candidate_confirmation.value == 5
    assert confirmed_items["weekly_days"].candidate_confirmation.source == "user_confirmation"
    assert confirmed.signals.hard_compatibility == 0
    assert confirmed.warnings == ()


def test_applies_confirmed_direction_preferences_without_fabricating_evidence() -> None:
    loader = LocalDocumentLoader()
    resume = loader.load_bytes("resume.txt", "目标方向：AI Agent 与大模型应用".encode())
    preferences = CandidateDirectionPreferenceConfirmation(
        agent_llm_application=1.0,
        ai_infrastructure=0.8,
        machine_learning=0.6,
        fullstack_ai_testing=0.0,
        risk_modeling=0.0,
    )
    platform_job = _job_from(
        """### 1. Agent 研发实习生-AI Infra | 甲公司
**岗位职责**
- 参与 AI Agent 和智能运维平台建设
"""
    )
    testing_job = _job_from(
        """### 1. CUDA Full Stack 与 AI 测试开发实习生 | 乙公司
**岗位职责**
- 开发 AI Agent 功能并执行 AI 应用自动化测试
"""
    )

    platform = extract_decision_signals(
        resume,
        platform_job,
        direction_preferences=preferences,
    )
    testing = extract_decision_signals(
        resume,
        testing_job,
        direction_preferences=preferences,
    )

    assert platform.signals.direction_alignment == 0.9
    assert testing.signals.direction_alignment == 0.5
    testing_items = {item.name: item for item in testing.directions}
    confirmation = testing_items["fullstack_ai_testing"].candidate_confirmation
    assert confirmation is not None
    assert confirmation.score == 0
    assert confirmation.source == "user_confirmation"
    assert testing_items["fullstack_ai_testing"].candidate_evidence == ()


def test_recognizes_test_automation_as_fullstack_ai_testing_direction() -> None:
    loader = LocalDocumentLoader()
    resume = loader.load_bytes("resume.txt", b"Python")
    job = _job_from(
        """### 1. Software Engineering Intern - AI Tools | 甲公司
**岗位职责**
- 为硬件工程开发测试自动化工具和前后端功能
"""
    )

    extraction = extract_decision_signals(
        resume,
        job,
        direction_preferences=CandidateDirectionPreferenceConfirmation(fullstack_ai_testing=0.0),
    )

    assert extraction.signals.direction_alignment == 0
    assert extraction.directions[0].name == "fullstack_ai_testing"
    assert extraction.directions[0].status == "unmet"


def test_matches_any_supported_job_location() -> None:
    loader = LocalDocumentLoader()
    resume = loader.load_bytes("resume.txt", "期望城市：上海".encode())
    job = _job_from(
        """### 1. Agent 研究实习生 | 甲公司
**基本信息**
- 北京、上海、杭州
"""
    )

    extraction = extract_decision_signals(resume, job)

    location = next(item for item in extraction.hard_constraints if item.name == "location")
    assert location.status == "met"
    assert [item.text for item in location.job_evidence] == ["北京", "上海", "杭州"]


def test_ignores_preferred_availability_as_hard_constraint() -> None:
    loader = LocalDocumentLoader()
    resume = loader.load_bytes("resume.txt", b"Python")
    job = _job_from(
        """### 1. Agent 实习生 | 甲公司
**基本信息**
- 每周 4 天以上；能实习 6 个月以上者优先
"""
    )

    extraction = extract_decision_signals(
        resume,
        job,
        availability=CandidateAvailabilityConfirmation(weekly_days=5, duration_months=12),
    )

    assert [item.name for item in extraction.hard_constraints] == ["weekly_days"]


def test_extracts_not_less_than_availability_requirements() -> None:
    loader = LocalDocumentLoader()
    resume = loader.load_bytes("resume.txt", b"Python")
    job = _job_from(
        """### 1. 模型评测实习生 | 甲公司
**基本信息**
- 每周不少于 4 天；实习不少于 4 个月
"""
    )

    extraction = extract_decision_signals(
        resume,
        job,
        availability=CandidateAvailabilityConfirmation(weekly_days=5, duration_months=12),
    )

    items = {item.name: item for item in extraction.hard_constraints}
    assert items["weekly_days"].status == "met"
    assert items["duration_months"].status == "met"


def test_applies_confirmed_ai_product_preference() -> None:
    loader = LocalDocumentLoader()
    resume = loader.load_bytes("resume.txt", b"Python")
    job = _job_from(
        """### 1. AI 社区产品培训生 | 甲公司
**岗位职责**
- 以 AI Native 方式建设社区产品
"""
    )

    extraction = extract_decision_signals(
        resume,
        job,
        direction_preferences=CandidateDirectionPreferenceConfirmation(ai_product=0.6),
    )

    assert extraction.signals.direction_alignment == 0.6
    assert extraction.directions[0].name == "ai_product"


def test_recognizes_model_evaluation_as_machine_learning_direction() -> None:
    loader = LocalDocumentLoader()
    resume = loader.load_bytes("resume.txt", b"Python")
    job = _job_from(
        """### 1. 大模型算法评测实习生 | 甲公司
**岗位职责**
- 建设模型评测系统并指导模型训练
"""
    )

    extraction = extract_decision_signals(
        resume,
        job,
        direction_preferences=CandidateDirectionPreferenceConfirmation(machine_learning=0.7),
    )

    assert extraction.signals.direction_alignment == 0.7
    assert extraction.directions[0].name == "machine_learning"


def test_classifies_tensorrt_inference_as_ai_infrastructure_not_testing() -> None:
    loader = LocalDocumentLoader()
    resume = loader.load_bytes("resume.txt", b"Python")
    job = _job_from(
        """### 1. AI Computing Software Development Intern | 甲公司
**岗位职责**
- 使用 TensorRT 优化 LLM 推理和 GPU 计算性能
- 使用 CUDA 开发深度学习算子
"""
    )

    extraction = extract_decision_signals(
        resume,
        job,
        direction_preferences=CandidateDirectionPreferenceConfirmation(
            ai_infrastructure=0.8,
            machine_learning=0.7,
            fullstack_ai_testing=0.0,
        ),
    )

    assert extraction.signals.direction_alignment == 0.75
    assert {item.name for item in extraction.directions} == {
        "ai_infrastructure",
        "machine_learning",
    }
