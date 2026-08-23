import json
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from lina_agent.domain.job_parser import parse_job_constraints
from lina_agent.domain.models import EducationLevel, JobConstraints


class ExpectedJobConstraints(BaseModel):
    model_config = ConfigDict(frozen=True)

    graduation_years: set[int] = Field(default_factory=set[int])
    minimum_education: EducationLevel | None = None
    minimum_years_of_experience: float | None = Field(default=None, ge=0)
    locations: set[str] = Field(default_factory=set[str])


class JobParserEvaluationCase(BaseModel):
    model_config = ConfigDict(frozen=True)

    case_id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    expected: ExpectedJobConstraints
    expected_evidence: set[str] = Field(default_factory=set[str])


class JobParserEvaluationReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    case_count: int
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float
    exact_match_rate: float
    evidence_precision: float
    evidence_recall: float
    failed_case_ids: tuple[str, ...]


def _field_values(constraints: JobConstraints | ExpectedJobConstraints) -> tuple[object, ...]:
    return (
        constraints.graduation_years or None,
        constraints.minimum_education,
        constraints.minimum_years_of_experience,
        constraints.locations or None,
    )


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 1.0


def evaluate_job_parser(
    cases: Iterable[JobParserEvaluationCase],
) -> JobParserEvaluationReport:
    evaluation_cases = tuple(cases)
    if not evaluation_cases:
        raise ValueError("evaluation requires at least one case")

    true_positives = 0
    false_positives = 0
    false_negatives = 0
    exact_matches = 0
    evidence_true_positives = 0
    predicted_evidence_count = 0
    expected_evidence_count = 0
    failed_case_ids: list[str] = []

    for case in evaluation_cases:
        extraction = parse_job_constraints(case.description, document_id=uuid4())
        predicted_values = _field_values(extraction.constraints)
        expected_values = _field_values(case.expected)

        for predicted, expected in zip(predicted_values, expected_values, strict=True):
            if predicted == expected and expected is not None:
                true_positives += 1
            elif predicted != expected:
                false_positives += predicted is not None
                false_negatives += expected is not None

        if predicted_values == expected_values:
            exact_matches += 1
        else:
            failed_case_ids.append(case.case_id)

        predicted_evidence = {
            evidence.text
            for evidence in (
                *extraction.evidence.graduation_years,
                extraction.evidence.minimum_education,
                extraction.evidence.minimum_years_of_experience,
                *extraction.evidence.locations,
            )
            if evidence is not None
        }
        evidence_true_positives += len(predicted_evidence & case.expected_evidence)
        predicted_evidence_count += len(predicted_evidence)
        expected_evidence_count += len(case.expected_evidence)

    return JobParserEvaluationReport(
        case_count=len(evaluation_cases),
        true_positives=true_positives,
        false_positives=false_positives,
        false_negatives=false_negatives,
        precision=_ratio(true_positives, true_positives + false_positives),
        recall=_ratio(true_positives, true_positives + false_negatives),
        exact_match_rate=_ratio(exact_matches, len(evaluation_cases)),
        evidence_precision=_ratio(
            evidence_true_positives,
            predicted_evidence_count,
        ),
        evidence_recall=_ratio(evidence_true_positives, expected_evidence_count),
        failed_case_ids=tuple(failed_case_ids),
    )


def load_evaluation_cases(path: Path) -> tuple[JobParserEvaluationCase, ...]:
    payload = cast(list[dict[str, Any]], json.loads(path.read_text(encoding="utf-8")))
    return tuple(JobParserEvaluationCase.model_validate(item) for item in payload)


def main(arguments: Sequence[str] | None = None) -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Evaluate Lina's deterministic JD parser.")
    parser.add_argument("dataset", type=Path)
    parsed_arguments = parser.parse_args(arguments)
    report = evaluate_job_parser(load_evaluation_cases(parsed_arguments.dataset))
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":  # pragma: no cover
    main()
