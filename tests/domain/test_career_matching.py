from lina_agent.domain.career_matching import (
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
