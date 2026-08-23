import json
from pathlib import Path

import pytest

from lina_agent.domain.models import EducationLevel
from lina_agent.evaluation.job_parser import (
    ExpectedJobConstraints,
    JobParserEvaluationCase,
    evaluate_job_parser,
    load_evaluation_cases,
    main,
)

FIXTURES = Path(__file__).parents[1] / "fixtures"


def test_evaluate_job_parser_reports_field_and_case_metrics() -> None:
    cases = (
        JobParserEvaluationCase(
            case_id="supported",
            description="工作地点：上海。要求 2027 届本科及以上学历。",
            expected=ExpectedJobConstraints(
                graduation_years={2027},
                minimum_education=EducationLevel.BACHELOR,
                locations={"上海"},
            ),
            expected_evidence={"2027 届", "本科及以上学历", "工作地点：上海"},
        ),
        JobParserEvaluationCase(
            case_id="unsupported",
            description="Base 地在杭州，面向 2026 年毕业生，本科起。",
            expected=ExpectedJobConstraints(
                graduation_years={2026},
                minimum_education=EducationLevel.BACHELOR,
                locations={"杭州"},
            ),
            expected_evidence={"2026 年毕业生", "本科起", "Base 地在杭州"},
        ),
    )

    report = evaluate_job_parser(cases)

    assert report.case_count == 2
    assert report.true_positives == 3
    assert report.false_positives == 0
    assert report.false_negatives == 3
    assert report.precision == 1.0
    assert report.recall == 0.5
    assert report.exact_match_rate == 0.5
    assert report.evidence_precision == 1.0
    assert report.evidence_recall == 0.5
    assert report.failed_case_ids == ("unsupported",)


def test_job_parser_evaluation_fixture_records_current_baseline() -> None:
    cases = load_evaluation_cases(FIXTURES / "job_parser_evaluation.json")

    report = evaluate_job_parser(cases)

    assert report.case_count == 6
    assert report.precision == 1.0
    assert report.recall == 0.625
    assert report.exact_match_rate == 0.5
    assert report.evidence_precision == 1.0
    assert report.evidence_recall == 0.625
    assert report.failed_case_ids == (
        "base-and-graduation-variant",
        "labelled-requirements-variant",
        "education-choice-variant",
    )


def test_job_parser_evaluation_cli_outputs_json(
    capsys: pytest.CaptureFixture[str],
) -> None:
    main([str(FIXTURES / "job_parser_evaluation.json")])

    payload = json.loads(capsys.readouterr().out)

    assert payload["case_count"] == 6
    assert payload["recall"] == 0.625


def test_job_parser_evaluation_rejects_empty_dataset() -> None:
    with pytest.raises(ValueError, match="at least one case"):
        evaluate_job_parser(())
