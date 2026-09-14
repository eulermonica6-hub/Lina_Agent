import json
from pathlib import Path
from typing import Any

import pytest

from scripts import ingest_amazon_ai_jobs


def _job(job_id: str) -> dict[str, Any]:
    return {
        "id_icims": job_id,
        "title": "Amazon AI Agent Engineer",
        "location": "CN, 31, Shanghai",
        "job_category": "Applied Science",
        "description": "利用AWS构建 Agent。详情 https://example.com/job",
        "basic_qualifications": "Python",
        "preferred_qualifications": "Alexa experience",
        "posted_date": "September 14, 2026",
    }


def _no_jobs() -> list[dict[str, Any]]:
    return []


def test_ingest_writes_raw_and_anonymized_payloads(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(ingest_amazon_ai_jobs, "SELECTED_JOB_IDS", ("42",))
    monkeypatch.setattr(ingest_amazon_ai_jobs, "_fetch_jobs", lambda: [_job("42")])

    raw_path, anonymous_path = ingest_amazon_ai_jobs.ingest(tmp_path)

    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    anonymous = json.loads(anonymous_path.read_text(encoding="utf-8"))
    assert raw["jobs"][0]["id_icims"] == "42"
    assert anonymous[0]["case_id"] == "china-ai-role-01"
    assert "Amazon" not in json.dumps(anonymous, ensure_ascii=False)
    assert "AWS" not in json.dumps(anonymous, ensure_ascii=False)
    assert "https://" not in json.dumps(anonymous, ensure_ascii=False)
    assert "[COMPANY_A]" in anonymous[0]["description"]
    assert "[SOURCE_URL_REMOVED]" in anonymous[0]["description"]


def test_ingest_fails_when_a_selected_job_disappears(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(ingest_amazon_ai_jobs, "SELECTED_JOB_IDS", ("missing",))
    monkeypatch.setattr(ingest_amazon_ai_jobs, "_fetch_jobs", _no_jobs)

    with pytest.raises(RuntimeError, match="missing"):
        ingest_amazon_ai_jobs.ingest(tmp_path)
