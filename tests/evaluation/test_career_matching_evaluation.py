import json
from pathlib import Path
from typing import Literal
from uuid import uuid4

import pytest

from lina_agent.domain.career_matching import DecisionWeights, MatchWeights
from lina_agent.domain.models import SourceEvidence
from lina_agent.evaluation.career_matching import (
    MatchingAblation,
    calibrate_match_weights,
    citation_is_valid,
    evaluate_ablations,
    evaluate_automatic_decision_signals,
    evaluate_automatic_decision_suite,
    evaluate_career_matching,
    load_gold_dataset,
    main,
)
from lina_agent.infrastructure.document_loader import LocalDocumentLoader


def _write_dataset(tmp_path: Path) -> Path:
    (tmp_path / "resume.md").write_text("Python RAG", encoding="utf-8")
    (tmp_path / "jobs.md").write_text(
        """### 1. 平台岗位 | [COMPANY_A]
**岗位职责**
- Agent 开发
**任职要求**
- Python
- RAG 优先
### 2. 算法岗位 | [COMPANY_B]
**任职要求**
- Python 与 LangGraph
""",
        encoding="utf-8",
    )
    dataset = {
        "dataset_version": "test-v1",
        "resume": "resume.md",
        "job_catalog": "jobs.md",
        "gold_ranking": [1, 2],
        "annotation_policy": "test",
        "jobs": [
            {
                "catalog_number": 1,
                "required": ["Python"],
                "preferred": ["RAG"],
                "contextual": ["Agent"],
                "candidate_supported": ["Python", "RAG"],
                "hard_compatibility": 1.0,
                "direction_alignment": 1.0,
                "decision_notes": ["兼容且方向匹配"],
                "hard_constraint_labels": [
                    {
                        "name": "location",
                        "status": "met",
                        "candidate_evidence": ["期望城市：上海"],
                        "job_evidence": ["上海"],
                    }
                ],
                "review_status": "reviewed",
            },
            {
                "catalog_number": 2,
                "required": ["LangGraph", "Python"],
                "preferred": [],
                "contextual": [],
                "candidate_supported": ["Python"],
                "hard_compatibility": 0.0,
                "direction_alignment": 0.0,
                "decision_notes": ["硬条件不兼容"],
                "review_status": "reviewed",
            },
        ],
    }
    path = tmp_path / "gold.json"
    path.write_text(json.dumps(dataset, ensure_ascii=False), encoding="utf-8")
    return path


def test_evaluates_skills_citations_and_ranking(tmp_path: Path) -> None:
    report = evaluate_career_matching(_write_dataset(tmp_path))

    assert report.skill_precision == 1.0
    assert report.skill_recall == 1.0
    assert report.skill_exact_match_rate == 1.0
    assert report.match_precision == 1.0
    assert report.match_recall == 1.0
    assert report.match_exact_match_rate == 1.0
    assert report.citation_count == 7
    assert report.citation_validity_rate == 1.0
    assert report.citation_support_rate == 1.0
    assert report.predicted_ranking == (1, 2)
    assert report.top_1_accuracy == 1.0
    assert report.pairwise_accuracy == 1.0
    assert report.ablation is MatchingAblation.SKILL_ONLY
    assert report.decision_weights is None


def test_ablation_combines_hard_constraints_and_direction(tmp_path: Path) -> None:
    report = evaluate_ablations(_write_dataset(tmp_path))

    assert report.skill_only.predicted_ranking == (1, 2)
    assert report.hard_skill.predicted_ranking == (1, 2)
    assert report.hard_direction_skill.predicted_ranking == (1, 2)
    assert report.hard_skill.decision_weights is not None
    assert report.hard_skill.decision_weights.direction == 0
    assert report.hard_direction_skill.decision_weights == DecisionWeights(
        skill=0.3,
        hard=0.2,
        direction=0.5,
    )


def test_evaluates_automatic_signals_separately_from_gold_injection(tmp_path: Path) -> None:
    dataset_path = _write_dataset(tmp_path)
    payload = json.loads(dataset_path.read_text(encoding="utf-8"))
    (dataset_path.parent / "resume.md").write_text(
        "Python RAG\n期望城市：上海",
        encoding="utf-8",
    )
    (dataset_path.parent / "jobs.md").write_text(
        """### 1. 平台岗位 | [COMPANY_A]
**基本信息**
- 上海
**岗位职责**
- Agent 开发
**任职要求**
- Python
- RAG 优先
### 2. 算法岗位 | [COMPANY_B]
**任职要求**
- Python 与 LangGraph
""",
        encoding="utf-8",
    )
    payload["jobs"][0]["hard_constraint_labels"][0]["candidate_evidence"] = ["期望城市：上海"]
    dataset_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    report = evaluate_automatic_decision_signals(dataset_path)

    assert report.job_count == 2
    assert report.hard_signal_coverage == 0.5
    assert report.hard_signal_mae == 0
    assert report.direction_signal_coverage == 0
    assert report.direction_signal_mae is None
    assert report.hard_item_count == 1
    assert report.hard_item_known_rate == 1
    assert report.hard_item_status_accuracy == 1
    assert report.hard_evidence_precision == 1
    assert report.hard_evidence_recall == 1
    assert report.hard_evidence_validity_rate == 1
    assert report.predicted_ranking == (1, 2)
    assert report.job_breakdown[0].catalog_number == 1
    assert report.job_breakdown[0].hard_compatibility == 1
    assert report.job_breakdown[0].gold_hard_compatibility == 1
    assert report.ranking_inversions == ()


def test_automatic_signals_report_ranking_inversions(tmp_path: Path) -> None:
    dataset_path = _write_dataset(tmp_path)
    payload = json.loads(dataset_path.read_text(encoding="utf-8"))
    payload["gold_ranking"] = [2, 1]
    dataset_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    report = evaluate_automatic_decision_signals(dataset_path)

    assert report.predicted_ranking == (1, 2)
    assert report.ranking_inversions[0].gold_preferred == 2
    assert report.ranking_inversions[0].predicted_preferred == 1


def test_ranking_metrics_skip_gold_ties(tmp_path: Path) -> None:
    dataset_path = _write_dataset(tmp_path)
    payload = json.loads(dataset_path.read_text(encoding="utf-8"))
    payload["gold_ranking"] = [2, 1]
    payload["ranking_ties"] = [[1, 2]]
    dataset_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    report = evaluate_automatic_decision_signals(dataset_path)

    assert report.pairwise_accuracy == 1
    assert report.top_1_accuracy == 1
    assert report.ranking_inversions == ()


def test_automatic_signals_use_dataset_candidate_availability(tmp_path: Path) -> None:
    dataset_path = _write_dataset(tmp_path)
    payload = json.loads(dataset_path.read_text(encoding="utf-8"))
    payload["candidate_availability"] = {"weekly_days": 5, "duration_months": 12}
    payload["jobs"][0]["hard_constraint_labels"] = [
        {
            "name": "weekly_days",
            "status": "met",
            "candidate_evidence": [],
            "job_evidence": ["每周 5 天"],
        },
        {
            "name": "duration_months",
            "status": "met",
            "candidate_evidence": [],
            "job_evidence": ["至少 1 年"],
        },
    ]
    (dataset_path.parent / "jobs.md").write_text(
        """### 1. 平台岗位 | [COMPANY_A]
**基本信息**
- 每周 5 天；至少 1 年
### 2. 算法岗位 | [COMPANY_B]
**任职要求**
- Python 与 LangGraph
""",
        encoding="utf-8",
    )
    dataset_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    report = evaluate_automatic_decision_signals(dataset_path)

    assert report.hard_item_count == 2
    assert report.hard_item_known_rate == 1
    assert report.hard_item_status_accuracy == 1
    assert report.unknown_hard_constraint_count == 0
    assert report.hard_evidence_precision == 1
    assert report.hard_evidence_recall == 1


def test_automatic_signals_use_dataset_direction_preferences(tmp_path: Path) -> None:
    dataset_path = _write_dataset(tmp_path)
    payload = json.loads(dataset_path.read_text(encoding="utf-8"))
    payload["candidate_direction_preferences"] = {
        "agent_llm_application": 1.0,
        "ai_infrastructure": 0.8,
    }
    payload["jobs"][0]["direction_alignment"] = 0.9
    (dataset_path.parent / "jobs.md").write_text(
        """### 1. Agent 平台岗位-AI Infra | [COMPANY_A]
**岗位职责**
- 参与 AI Agent 与智能运维平台建设
### 2. 算法岗位 | [COMPANY_B]
**任职要求**
- Python 与 LangGraph
""",
        encoding="utf-8",
    )
    dataset_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    report = evaluate_automatic_decision_signals(dataset_path)

    breakdown = next(item for item in report.job_breakdown if item.catalog_number == 1)
    assert breakdown.direction_alignment == 0.9
    assert breakdown.gold_direction_alignment == 0.9


def test_automatic_signal_suite_reports_macro_worst_case_and_direction_coverage(
    tmp_path: Path,
) -> None:
    (tmp_path / "first").mkdir()
    (tmp_path / "second").mkdir()
    first_path = _write_dataset(tmp_path / "first")
    second_path = _write_dataset(tmp_path / "second")
    first_payload = json.loads(first_path.read_text(encoding="utf-8"))
    first_payload["candidate_direction_preferences"] = {"agent_llm_application": 1.0}
    first_payload["jobs"][0]["direction_alignment"] = 1.0
    first_path.write_text(json.dumps(first_payload), encoding="utf-8")
    second_payload = json.loads(second_path.read_text(encoding="utf-8"))
    second_payload["gold_ranking"] = [2, 1]
    second_payload["candidate_direction_preferences"] = {"machine_learning": 0.7}
    second_payload["jobs"][0]["direction_alignment"] = 0.7
    (second_path.parent / "jobs.md").write_text(
        """### 1. Machine Learning 平台岗位 | [COMPANY_A]
**岗位职责**
- 机器学习模型开发
**任职要求**
- Python
### 2. 算法岗位 | [COMPANY_B]
**任职要求**
- Python 与 LangGraph
""",
        encoding="utf-8",
    )
    second_path.write_text(json.dumps(second_payload), encoding="utf-8")
    manifest_path = tmp_path / "suite.json"
    manifest_path.write_text(
        json.dumps(
            {
                "suite_version": "test-suite-v1",
                "datasets": ["first/gold.json", "second/gold.json"],
            }
        ),
        encoding="utf-8",
    )

    report = evaluate_automatic_decision_suite(manifest_path)

    assert report.dataset_count == 2
    assert report.total_job_count == 4
    assert report.covered_direction_families == (
        "agent_llm_application",
        "machine_learning",
    )
    assert report.direction_family_coverage == 0.4
    assert report.macro_direction_signal_coverage == 0.5
    assert report.minimum_direction_signal_coverage == 0.5
    assert report.macro_top_1_accuracy == 0.5
    assert report.macro_pairwise_accuracy == 0.5
    assert report.minimum_pairwise_accuracy == 0.0
    assert [item.dataset_version for item in report.datasets] == ["test-v1", "test-v1"]


def test_rejects_duplicate_datasets_in_automatic_signal_suite(tmp_path: Path) -> None:
    manifest_path = tmp_path / "suite.json"
    manifest_path.write_text(
        json.dumps(
            {
                "suite_version": "test-suite-v1",
                "datasets": ["gold.json", "gold.json"],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="must be unique"):
        evaluate_automatic_decision_suite(manifest_path)


def test_automatic_signal_suite_cli_outputs_stability_metrics(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_dataset(tmp_path)
    manifest_path = tmp_path / "suite.json"
    manifest_path.write_text(
        json.dumps({"suite_version": "test-suite-v1", "datasets": ["gold.json"]}),
        encoding="utf-8",
    )

    main([str(manifest_path), "--auto-signal-suite"])
    payload = json.loads(capsys.readouterr().out)

    assert payload["dataset_count"] == 1
    assert payload["minimum_pairwise_accuracy"] == 1


def test_calibrates_weights_and_cli_outputs_json(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    dataset_path = _write_dataset(tmp_path)

    calibration = calibrate_match_weights(dataset_path)
    main([str(dataset_path), "--calibrate"])
    payload = json.loads(capsys.readouterr().out)

    assert calibration.evaluated_weight_sets == 20
    assert calibration.calibrated.pairwise_accuracy == 1.0
    assert payload["baseline"]["weights"] == {
        "required": 0.7,
        "preferred": 0.2,
        "contextual": 0.1,
    }


def test_ablation_cli_outputs_all_variants(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    dataset_path = _write_dataset(tmp_path)

    main([str(dataset_path), "--ablate"])
    payload = json.loads(capsys.readouterr().out)

    assert set(payload) == {"skill_only", "hard_skill", "hard_direction_skill"}


def test_automatic_signal_cli_outputs_extraction_metrics(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    dataset_path = _write_dataset(tmp_path)

    main([str(dataset_path), "--auto-signals"])
    payload = json.loads(capsys.readouterr().out)

    assert payload["hard_signal_coverage"] == 0
    assert payload["direction_signal_coverage"] == 0


def test_default_cli_outputs_skill_only_report(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    dataset_path = _write_dataset(tmp_path)

    main([str(dataset_path)])
    payload = json.loads(capsys.readouterr().out)

    assert payload["ablation"] == "skill-only"


def test_cli_rejects_calibration_with_ablation(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        main([str(_write_dataset(tmp_path)), "--calibrate", "--ablate"])


def test_rejects_inconsistent_gold_ranking(tmp_path: Path) -> None:
    dataset_path = _write_dataset(tmp_path)
    payload = json.loads(dataset_path.read_text(encoding="utf-8"))
    payload["gold_ranking"] = [1]
    dataset_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="every gold job"):
        load_gold_dataset(dataset_path)


def test_rejects_duplicate_hard_constraint_gold_labels(tmp_path: Path) -> None:
    dataset_path = _write_dataset(tmp_path)
    payload = json.loads(dataset_path.read_text(encoding="utf-8"))
    label = payload["jobs"][0]["hard_constraint_labels"][0]
    payload["jobs"][0]["hard_constraint_labels"].append(label)
    dataset_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="unique names"):
        load_gold_dataset(dataset_path)


@pytest.mark.parametrize(
    ("ranking_ties", "message"),
    (
        ([[1]], "at least two"),
        ([[1, 2], [2, 1]], "at most one"),
        ([[1, 3]], "only contain gold jobs"),
    ),
)
def test_rejects_invalid_ranking_ties(
    tmp_path: Path,
    ranking_ties: list[list[int]],
    message: str,
) -> None:
    dataset_path = _write_dataset(tmp_path)
    payload = json.loads(dataset_path.read_text(encoding="utf-8"))
    payload["ranking_ties"] = ranking_ties
    dataset_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        load_gold_dataset(dataset_path)


def test_rejects_noncontiguous_ranking_ties(tmp_path: Path) -> None:
    dataset_path = _write_dataset(tmp_path)
    payload = json.loads(dataset_path.read_text(encoding="utf-8"))
    payload["jobs"].append(
        {
            **payload["jobs"][1],
            "catalog_number": 3,
        }
    )
    payload["gold_ranking"] = [1, 2, 3]
    payload["ranking_ties"] = [[1, 3]]
    dataset_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="contiguous"):
        load_gold_dataset(dataset_path)


@pytest.mark.parametrize(
    ("duplicate_kind", "message"),
    (
        ("jobs", "unique catalog"),
        ("ranking", "must not contain duplicates"),
    ),
)
def test_rejects_duplicate_gold_identifiers(
    tmp_path: Path,
    duplicate_kind: Literal["jobs", "ranking"],
    message: str,
) -> None:
    dataset_path = _write_dataset(tmp_path)
    payload = json.loads(dataset_path.read_text(encoding="utf-8"))
    if duplicate_kind == "jobs":
        payload["jobs"].append(payload["jobs"][0])
    else:
        payload["gold_ranking"] = [1, 1]
    dataset_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        load_gold_dataset(dataset_path)


def test_rejects_catalog_mismatch(tmp_path: Path) -> None:
    dataset_path = _write_dataset(tmp_path)
    payload = json.loads(dataset_path.read_text(encoding="utf-8"))
    payload["jobs"][1]["catalog_number"] = 3
    payload["gold_ranking"] = [1, 3]
    dataset_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="parsed catalog numbers"):
        evaluate_career_matching(dataset_path, MatchWeights())


def test_rejects_citation_from_unknown_document() -> None:
    loader = LocalDocumentLoader()
    resume = loader.load_bytes("resume.md", b"Python")
    catalog = loader.load_bytes("jobs.md", b"Python")
    evidence = SourceEvidence(document_id=uuid4(), text="Python", start_offset=0, end_offset=6)

    assert not citation_is_valid(("Python", evidence), resume, catalog)
