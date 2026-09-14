import re
from dataclasses import dataclass
from uuid import UUID

from pydantic import Field

from lina_agent.domain.documents import IngestedDocument
from lina_agent.domain.job_catalog import CatalogJob
from lina_agent.domain.models import DomainModel, SourceEvidence


@dataclass(frozen=True)
class SkillTerm:
    name: str
    aliases: tuple[str, ...]


SKILL_TAXONOMY = (
    SkillTerm("Agent", ("AI Agent", "智能体", "Agent")),
    SkillTerm("Multi-Agent", ("Multi-Agent", "Multi Agent", "多智能体")),
    SkillTerm("RAG", ("检索增强生成", "RAG")),
    SkillTerm("LLM", ("大语言模型", "大模型", "LLMs", "LLM")),
    SkillTerm("LangChain", ("LangChain",)),
    SkillTerm("LangGraph", ("LangGraph",)),
    SkillTerm("Dify", ("Dify",)),
    SkillTerm("AutoGen", ("AutoGen",)),
    SkillTerm("MCP", ("Model Context Protocol", "MCP")),
    SkillTerm("Tool Calling", ("Function Calling", "Tool Calling", "工具调用")),
    SkillTerm("Prompt Engineering", ("Prompt Engineering", "提示词工程", "Prompt")),
    SkillTerm("Fine-tuning", ("Fine-tuning", "Fine Tuning", "微调")),
    SkillTerm("Knowledge Graph", ("Knowledge Graph", "知识图谱")),
    SkillTerm("Vector Database", ("Vector Database", "向量数据库", "向量库")),
    SkillTerm("Python", ("Python",)),
    SkillTerm("SQL", ("PostgreSQL", "MySQL", "SQL")),
    SkillTerm("FastAPI", ("FastAPI",)),
    SkillTerm("Pydantic", ("Pydantic",)),
    SkillTerm(
        "REST API", ("RESTful API", "REST API", "HTTP / API", "HTTP API", "APIs", "API 接口")
    ),
    SkillTerm("Docker", ("Docker",)),
    SkillTerm("Git", ("GitHub", "Git")),
    SkillTerm("Linux", ("Linux",)),
    SkillTerm("PyTorch", ("PyTorch",)),
    SkillTerm("TensorFlow", ("TensorFlow",)),
    SkillTerm("Transformers", ("Transformers",)),
    SkillTerm("Pandas", ("Pandas",)),
    SkillTerm("NumPy", ("NumPy",)),
    SkillTerm("SciPy", ("SciPy",)),
    SkillTerm("XGBoost", ("XGBoost",)),
    SkillTerm("NLP", ("自然语言处理", "NLP")),
    SkillTerm("Computer Vision", ("Computer Vision", "计算机视觉", "CV")),
    SkillTerm("Machine Learning", ("Machine Learning", "机器学习")),
    SkillTerm("Deep Learning", ("Deep Learning", "深度学习")),
    SkillTerm("Java", ("Java",)),
    SkillTerm("C++", ("C++",)),
    SkillTerm("Redis", ("Redis",)),
    SkillTerm("MongoDB", ("MongoDB",)),
    SkillTerm("Elasticsearch", ("Elasticsearch",)),
    SkillTerm("Data Analysis", ("Data Analysis", "数据分析")),
)
_PREFERRED = re.compile(r"优先|加分|preferred", re.IGNORECASE)


class SkillMention(DomainModel):
    skill: str = Field(min_length=1)
    evidence: tuple[SourceEvidence, ...] = Field(min_length=1)


class CandidateDocumentProfile(DomainModel):
    document_id: UUID
    source_name: str = Field(min_length=1)
    skills: tuple[SkillMention, ...] = ()


class JobSkillProfile(DomainModel):
    required: tuple[SkillMention, ...] = ()
    preferred: tuple[SkillMention, ...] = ()
    contextual: tuple[SkillMention, ...] = ()


class EvidenceMatch(DomainModel):
    skill: str = Field(min_length=1)
    candidate_evidence: SourceEvidence
    job_evidence: SourceEvidence


class MatchWeights(DomainModel):
    required: float = Field(default=0.7, ge=0)
    preferred: float = Field(default=0.2, ge=0)
    contextual: float = Field(default=0.1, ge=0)


class DecisionSignals(DomainModel):
    hard_compatibility: float | None = Field(default=None, ge=0, le=1)
    direction_alignment: float | None = Field(default=None, ge=0, le=1)
    explanations: tuple[str, ...] = ()


class DecisionWeights(DomainModel):
    skill: float = Field(default=0.3, ge=0)
    hard: float = Field(default=0.2, ge=0)
    direction: float = Field(default=0.5, ge=0)


class RankedJobMatch(DomainModel):
    catalog_number: int = Field(ge=1)
    title: str = Field(min_length=1)
    company: str = Field(min_length=1)
    source_url: str | None = None
    score: float = Field(ge=0, le=100)
    skill_score: float = Field(default=0, ge=0, le=100)
    hard_compatibility: float | None = Field(default=None, ge=0, le=1)
    direction_alignment: float | None = Field(default=None, ge=0, le=1)
    decision_explanations: tuple[str, ...] = ()
    required_coverage: float | None = Field(default=None, ge=0, le=1)
    preferred_coverage: float | None = Field(default=None, ge=0, le=1)
    contextual_coverage: float | None = Field(default=None, ge=0, le=1)
    matched_required: tuple[EvidenceMatch, ...] = ()
    missing_required: tuple[SkillMention, ...] = ()
    matched_preferred: tuple[EvidenceMatch, ...] = ()
    missing_preferred: tuple[SkillMention, ...] = ()
    matched_contextual: tuple[EvidenceMatch, ...] = ()


def extract_candidate_profile(document: IngestedDocument) -> CandidateDocumentProfile:
    evidence = tuple(
        SourceEvidence(
            document_id=document.id,
            text=block.text,
            start_offset=block.start_offset,
            end_offset=block.end_offset,
        )
        for block in document.blocks
    )
    return CandidateDocumentProfile(
        document_id=document.id,
        source_name=document.source_name,
        skills=_extract_skill_mentions(evidence),
    )


def extract_job_skill_profile(job: CatalogJob) -> JobSkillProfile:
    required_evidence = tuple(
        evidence for evidence in job.requirements if _PREFERRED.search(evidence.text) is None
    )
    preferred_evidence = tuple(
        evidence for evidence in job.requirements if _PREFERRED.search(evidence.text) is not None
    )
    required = _extract_skill_mentions(required_evidence)
    required_names = {mention.skill for mention in required}
    preferred = tuple(
        mention
        for mention in _extract_skill_mentions(preferred_evidence)
        if mention.skill not in required_names
    )
    claimed_names = required_names | {mention.skill for mention in preferred}
    contextual = tuple(
        mention
        for mention in _extract_skill_mentions(job.responsibilities)
        if mention.skill not in claimed_names
    )
    return JobSkillProfile(required=required, preferred=preferred, contextual=contextual)


def score_job_match(
    candidate: CandidateDocumentProfile,
    job: CatalogJob,
    skills: JobSkillProfile,
    weights: MatchWeights | None = None,
    decision_signals: DecisionSignals | None = None,
    decision_weights: DecisionWeights | None = None,
) -> RankedJobMatch:
    active_weights = weights or MatchWeights()
    candidate_by_skill = {mention.skill: mention for mention in candidate.skills}
    matched_required, missing_required = _partition_matches(candidate_by_skill, skills.required)
    matched_preferred, missing_preferred = _partition_matches(candidate_by_skill, skills.preferred)
    matched_contextual, _ = _partition_matches(candidate_by_skill, skills.contextual)

    required_coverage = _coverage(len(matched_required), len(skills.required))
    preferred_coverage = _coverage(len(matched_preferred), len(skills.preferred))
    contextual_coverage = _coverage(len(matched_contextual), len(skills.contextual))
    weighted = tuple(
        (coverage, weight)
        for coverage, weight in (
            (required_coverage, active_weights.required),
            (preferred_coverage, active_weights.preferred),
            (contextual_coverage, active_weights.contextual),
        )
        if coverage is not None and weight > 0
    )
    skill_score = (
        round(
            sum(coverage * weight for coverage, weight in weighted)
            / sum(weight for _, weight in weighted)
            * 100,
            1,
        )
        if weighted
        else 0.0
    )
    score = _decision_score(skill_score, decision_signals, decision_weights)
    return RankedJobMatch(
        catalog_number=job.catalog_number,
        title=job.title,
        company=job.company,
        source_url=job.source_url,
        score=score,
        skill_score=skill_score,
        hard_compatibility=(
            decision_signals.hard_compatibility if decision_signals is not None else None
        ),
        direction_alignment=(
            decision_signals.direction_alignment if decision_signals is not None else None
        ),
        decision_explanations=(decision_signals.explanations if decision_signals else ()),
        required_coverage=required_coverage,
        preferred_coverage=preferred_coverage,
        contextual_coverage=contextual_coverage,
        matched_required=matched_required,
        missing_required=missing_required,
        matched_preferred=matched_preferred,
        missing_preferred=missing_preferred,
        matched_contextual=matched_contextual,
    )


def _decision_score(
    skill_score: float,
    signals: DecisionSignals | None,
    weights: DecisionWeights | None,
) -> float:
    if signals is None:
        return skill_score
    active_weights = weights or DecisionWeights()
    components = [(skill_score / 100, active_weights.skill)]
    if signals.hard_compatibility is not None:
        components.append((signals.hard_compatibility, active_weights.hard))
    if signals.direction_alignment is not None:
        components.append((signals.direction_alignment, active_weights.direction))
    weighted = tuple((value, weight) for value, weight in components if weight > 0)
    if not weighted:
        return 0.0
    return round(
        sum(value * weight for value, weight in weighted)
        / sum(weight for _, weight in weighted)
        * 100,
        1,
    )


def _extract_skill_mentions(evidence_items: tuple[SourceEvidence, ...]) -> tuple[SkillMention, ...]:
    mentions: list[SkillMention] = []
    for term in SKILL_TAXONOMY:
        hits: list[SourceEvidence] = []
        for evidence in evidence_items:
            match = next(
                (
                    match
                    for alias in term.aliases
                    if (match := _alias_pattern(alias).search(evidence.text)) is not None
                ),
                None,
            )
            if match is not None:
                hits.append(
                    SourceEvidence(
                        document_id=evidence.document_id,
                        text=match.group(),
                        start_offset=evidence.start_offset + match.start(),
                        end_offset=evidence.start_offset + match.end(),
                    )
                )
        if hits:
            mentions.append(SkillMention(skill=term.name, evidence=tuple(hits[:3])))
    return tuple(mentions)


def _alias_pattern(alias: str) -> re.Pattern[str]:
    left_boundary = r"(?<![A-Za-z0-9])" if alias[0].isascii() and alias[0].isalnum() else ""
    right_boundary = r"(?![A-Za-z0-9])" if alias[-1].isascii() and alias[-1].isalnum() else ""
    return re.compile(f"{left_boundary}{re.escape(alias)}{right_boundary}", re.IGNORECASE)


def _partition_matches(
    candidate_by_skill: dict[str, SkillMention],
    job_mentions: tuple[SkillMention, ...],
) -> tuple[tuple[EvidenceMatch, ...], tuple[SkillMention, ...]]:
    matched = tuple(
        EvidenceMatch(
            skill=job_mention.skill,
            candidate_evidence=candidate_by_skill[job_mention.skill].evidence[0],
            job_evidence=job_mention.evidence[0],
        )
        for job_mention in job_mentions
        if job_mention.skill in candidate_by_skill
    )
    missing = tuple(
        job_mention for job_mention in job_mentions if job_mention.skill not in candidate_by_skill
    )
    return matched, missing


def _coverage(matched: int, total: int) -> float | None:
    return matched / total if total else None
