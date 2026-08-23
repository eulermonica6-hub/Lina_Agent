import re
from collections.abc import Iterable
from uuid import UUID

from lina_agent.domain.models import (
    EducationLevel,
    JobConstraintEvidence,
    JobConstraintExtraction,
    JobConstraints,
    SourceEvidence,
)

_GRADUATION_PATTERN = re.compile(r"(?P<years>20\d{2}(?:\s*[、,，/或和]\s*20\d{2})*)\s*届")
_EDUCATION_PATTERN = re.compile(r"(?P<level>高中|大专|本科|硕士|博士)(?:及以上|以上)(?:学历)?")
_EXPERIENCE_PATTERN = re.compile(
    r"(?P<years>\d+(?:\.\d+)?)\s*年(?:及以上|以上)?(?:相关)?(?:工作)?经验"
)
_LOCATION_PATTERN = re.compile(r"工作地点\s*[:：]\s*(?P<locations>[^。；;\n]+)")
_YEAR_PATTERN = re.compile(r"20\d{2}")
_LOCATION_SEPARATOR = re.compile(r"[、,，/]")
_PREFERENCE_SUFFIX = re.compile(r"^\s*(?:[，,:：]\s*)?(?:者)?优先(?:考虑)?")
_PREFERENCE_PREFIX = re.compile(r"(?:优先(?:考虑)?(?:具有|具备)?)\s*[:：]?\s*$")
_CLAUSE_SEPARATOR = re.compile(r"[，,。；;\uFF01\uFF1F!?\n]")
_NATURAL_LOCATION_PAIR = re.compile(
    r"^(?:北京|上海|广州|深圳|杭州|南京|苏州|成都|重庆|武汉|西安|天津|长沙|郑州|青岛)"
    r"[和或]"
    r"(?:北京|上海|广州|深圳|杭州|南京|苏州|成都|重庆|武汉|西安|天津|长沙|郑州|青岛)$"
)

_EDUCATION_LEVELS = {
    "高中": EducationLevel.HIGH_SCHOOL,
    "大专": EducationLevel.ASSOCIATE,
    "本科": EducationLevel.BACHELOR,
    "硕士": EducationLevel.MASTER,
    "博士": EducationLevel.DOCTORATE,
}


def _evidence(document_id: UUID, description: str, match: re.Match[str]) -> SourceEvidence:
    return SourceEvidence(
        document_id=document_id,
        text=match.group(),
        start_offset=match.start(),
        end_offset=match.end(),
    )


def _graduation_years(matches: Iterable[re.Match[str]]) -> set[int]:
    return {
        int(year.group())
        for match in matches
        for year in _YEAR_PATTERN.finditer(match.group("years"))
    }


def _is_preferred(match: re.Match[str], description: str) -> bool:
    preceding_clause = _CLAUSE_SEPARATOR.split(description[: match.start()])[-1]
    return (
        _PREFERENCE_SUFFIX.match(description[match.end() :]) is not None
        or _PREFERENCE_PREFIX.search(preceding_clause) is not None
    )


def _first_required_match(pattern: re.Pattern[str], description: str) -> re.Match[str] | None:
    return next(
        (match for match in pattern.finditer(description) if not _is_preferred(match, description)),
        None,
    )


def parse_job_constraints(description: str, document_id: UUID) -> JobConstraintExtraction:
    graduation_matches = tuple(
        match
        for match in _GRADUATION_PATTERN.finditer(description)
        if not _is_preferred(match, description)
    )
    education_match = _first_required_match(_EDUCATION_PATTERN, description)
    experience_match = _first_required_match(_EXPERIENCE_PATTERN, description)
    location_matches = tuple(_LOCATION_PATTERN.finditer(description))
    location_values = tuple(
        location.strip()
        for match in location_matches
        for location in _LOCATION_SEPARATOR.split(match.group("locations"))
        if location.strip()
    )
    has_ambiguous_locations = any(
        _NATURAL_LOCATION_PAIR.fullmatch(location) is not None for location in location_values
    )

    locations: set[str] = set() if has_ambiguous_locations else set(location_values)
    constraints = JobConstraints(
        graduation_years=_graduation_years(graduation_matches),
        minimum_education=(
            _EDUCATION_LEVELS[education_match.group("level")]
            if education_match is not None
            else None
        ),
        minimum_years_of_experience=(
            float(experience_match.group("years")) if experience_match is not None else None
        ),
        locations=locations,
    )
    evidence = JobConstraintEvidence(
        graduation_years=tuple(
            _evidence(document_id, description, match) for match in graduation_matches
        ),
        minimum_education=(
            _evidence(document_id, description, education_match)
            if education_match is not None
            else None
        ),
        minimum_years_of_experience=(
            _evidence(document_id, description, experience_match)
            if experience_match is not None
            else None
        ),
        locations=tuple(_evidence(document_id, description, match) for match in location_matches),
    )
    warnings: list[str] = []
    if has_ambiguous_locations:
        warnings.append("工作地点包含未可靠拆分的并列表达，请人工确认。")
    if not any((graduation_matches, education_match, experience_match, location_matches)):
        warnings.append("未识别到明确的毕业年份、学历、经验或工作地点约束，请人工确认。")
    return JobConstraintExtraction(
        constraints=constraints,
        evidence=evidence,
        warnings=tuple(warnings),
    )
