import json
from pathlib import Path
from typing import Literal
from uuid import uuid4

import pytest

from lina_agent.domain.career_matching import MatchWeights
from lina_agent.domain.models import SourceEvidence
from lina_agent.evaluation.career_matching import (
    calibrate_match_weights,
    citation_is_valid,
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
                "review_status": "reviewed",
            },
            {
                "catalog_number": 2,
                "required": ["LangGraph", "Python"],
                "preferred": [],
                "contextual": [],
                "candidate_supported": ["Python"],
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


def test_rejects_inconsistent_gold_ranking(tmp_path: Path) -> None:
    dataset_path = _write_dataset(tmp_path)
    payload = json.loads(dataset_path.read_text(encoding="utf-8"))
    payload["gold_ranking"] = [1]
    dataset_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="every gold job"):
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
