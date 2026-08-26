from lina_agent.domain.career_matching import (
    extract_candidate_profile,
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
    assert [item.skill for item in result.matched_required] == ["Python"]
    assert [item.skill for item in result.missing_required] == ["LangGraph"]
    assert [item.skill for item in result.matched_preferred] == ["RAG"]
    assert result.matched_contextual == ()


def test_returns_zero_when_job_contains_no_taxonomy_skills() -> None:
    candidate = extract_candidate_profile(LocalDocumentLoader().load_bytes("resume.txt", b"Python"))
    job = _job_from("### 1. 综合岗位 | 甲公司\n**任职要求**\n- 沟通能力强")

    result = score_job_match(candidate, job, extract_job_skill_profile(job))

    assert result.score == 0
    assert result.required_coverage is None
    assert result.preferred_coverage is None
    assert result.contextual_coverage is None
