import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[1]
IMPORTANT_DOCUMENTS = (
    "releaseNote.md",
    "docs/USER_GUIDE.md",
    "docs/CODING_PLAN.md",
    "docs/AGENT_ARCHITECTURE.md",
    "docs/ENGINEERING_HANDBOOK.md",
    "docs/DEVELOPMENT.md",
    "docs/RELEASE_TESTING_0.2.0.md",
    "docs/KNOWLEDGE_BASE.md",
    "docs/MVP_IMPLEMENTATION.md",
    "docs/JOB_MONITORING.md",
    "docs/DOCUMENTATION_GOVERNANCE.md",
    "docs/DATA_ANNOTATION.md",
    "docs/DECISION_SIGNAL_RULES.md",
    "docs/CUDA_RUNNER_SETUP.md",
    "docs/evaluations/JD_PARSER_BASELINE.md",
    "docs/evaluations/CAREER_MATCHING_BASELINE.md",
    "docs/iterations/017-public-jd-ingestion.md",
    "docs/iterations/018-shanghai-ai-internship-scope.md",
    "docs/iterations/019-official-internship-verification.md",
    "docs/iterations/020-career-matching-gold-baseline.md",
    "docs/iterations/021-decision-signal-ablation.md",
    "docs/iterations/022-automatic-decision-signal-baseline.md",
    "docs/iterations/023-hard-constraint-item-gold.md",
    "docs/iterations/024-candidate-availability-confirmation-contract.md",
    "docs/iterations/025-confirmed-availability-gold-rerun.md",
    "docs/iterations/026-ranking-ties-and-inversion-analysis.md",
    "docs/iterations/027-direction-preference-confirmation-contract.md",
    "docs/iterations/028-direction-preference-entry-wiring.md",
    "docs/iterations/029-multi-gold-suite-baseline.md",
    "docs/iterations/030-second-gold-official-jd.md",
    "docs/iterations/031-domestic-global-jd-expansion.md",
    "docs/iterations/032-deterministic-skill-evidence-plan.md",
    "docs/iterations/033-pytorch-inference-baseline.md",
    "docs/iterations/034-pytorch-cpp-rmsnorm-extension.md",
    "docs/iterations/035-cuda-rmsnorm-contract.md",
    "docs/iterations/036-cuda-runner-preflight.md",
    "docs/iterations/037-sqlite-structured-state-persistence.md",
    "docs/iterations/038-versioned-agent-run-snapshots.md",
    "docs/iterations/039-document-and-confirmation-versions.md",
    "docs/iterations/040-agent-run-snapshot-diff.md",
)


def test_readme_links_every_important_document() -> None:
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")

    for relative_path in IMPORTANT_DOCUMENTS:
        assert (PROJECT_ROOT / relative_path).is_file(), relative_path
        assert f"]({relative_path})" in readme, relative_path


def test_anonymized_resume_has_no_obvious_contact_details() -> None:
    resume = (PROJECT_ROOT / "tests/fixtures/resume_anonymized.md").read_text(encoding="utf-8")

    assert re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", resume) is None
    assert re.search(r"(?<!\d)1[3-9]\d{9}(?!\d)", resume) is None
    assert "http://" not in resume
    assert "https://" not in resume


def test_public_agent_fixture_is_anonymous_and_key_file_is_ignored() -> None:
    catalog = (PROJECT_ROOT / "tests/fixtures/job_catalog_anonymized.md").read_text(
        encoding="utf-8"
    )
    gitignore = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")

    assert re.search(r"(?<!\d)1[3-9]\d{9}(?!\d)", catalog) is None
    assert "@" not in catalog
    assert "LLM api key.txt" in gitignore
