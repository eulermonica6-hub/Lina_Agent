import json
import runpy
import sys
from pathlib import Path

import pytest

import lina_agent.cli.career_match as career_match_cli
from lina_agent.application.career_agent import CareerMatchAgent
from lina_agent.cli.career_match import format_markdown, main
from lina_agent.infrastructure.document_loader import LocalDocumentLoader
from lina_agent.infrastructure.llm_career_planner import LLMCareerPlanner
from lina_agent.infrastructure.llm_provider import (
    LLMProviderName,
    LLMRequest,
    LLMResult,
    LLMUsage,
)

JOBS = """### 1. Agent 工程师 | 甲公司
**任职要求**
- Python
**状态与来源**
- 招聘中
"""


class _PlanProvider:
    def complete(self, request: LLMRequest) -> LLMResult:
        assert request.messages[1].role == "user"
        return LLMResult(
            provider=LLMProviderName.GROQ,
            model="test-model",
            content=(
                '{"summary":"优先补齐岗位缺口","priority_actions":'
                '[{"priority":1,"target_skills":["Python"],'
                '"action":"完成项目","reason":"形成证据",'
                '"deliverable":"可运行仓库","acceptance_criteria":"测试通过",'
                '"time_budget_hours":8}]}'
            ),
            usage=LLMUsage(total_tokens=20),
        )


def test_cli_outputs_markdown_report(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    resume = tmp_path / "resume.txt"
    jobs = tmp_path / "jobs.md"
    resume.write_text("RAG", encoding="utf-8")
    jobs.write_text(JOBS, encoding="utf-8")

    main(("--resume", str(resume), "--jobs", str(jobs), "--top", "1"))

    output = capsys.readouterr().out
    assert "# Lina 初步职业匹配报告" in output
    assert "Agent 工程师" in output
    assert "未覆盖明确技能：Python" in output
    assert "Python：优先级 high" in output


def test_cli_outputs_json_and_forwards_inactive_option(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    resume = tmp_path / "resume.txt"
    jobs = tmp_path / "jobs.md"
    resume.write_text("Python", encoding="utf-8")
    jobs.write_text(JOBS.replace("招聘中", "已下线"), encoding="utf-8")

    main(
        (
            "--resume",
            str(resume),
            "--jobs",
            str(jobs),
            "--include-inactive",
            "--format",
            "json",
        )
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["considered_jobs"] == 1
    assert payload["matches"][0]["catalog_number"] == 1


def test_markdown_formatter_explains_empty_result() -> None:
    loader = LocalDocumentLoader()
    resume = loader.load_bytes("resume.txt", "沟通能力".encode())
    jobs = loader.load_bytes("jobs.md", "### 1. 综合岗位 | 公司\n**状态与来源**\n- 已下线".encode())
    run = CareerMatchAgent.execute_documents(resume, jobs)

    output = format_markdown(run)

    assert "候选人技能：未识别" in output
    assert "没有可展示的岗位" in output


def test_python_module_entrypoint(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resume = tmp_path / "resume.txt"
    jobs = tmp_path / "jobs.md"
    resume.write_text("Python", encoding="utf-8")
    jobs.write_text(JOBS, encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        ["lina_agent.cli", "--resume", str(resume), "--jobs", str(jobs)],
    )

    runpy.run_module("lina_agent.cli", run_name="__main__")

    assert "Lina 初步职业匹配报告" in capsys.readouterr().out


def test_cli_can_opt_in_to_anonymized_llm_plan(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resume = tmp_path / "resume.txt"
    jobs = tmp_path / "jobs.md"
    resume.write_text("Python", encoding="utf-8")
    jobs.write_text(JOBS, encoding="utf-8")
    monkeypatch.setattr(
        career_match_cli,
        "LLMCareerPlanner",
        lambda: LLMCareerPlanner(_PlanProvider()),
    )

    main(("--resume", str(resume), "--jobs", str(jobs), "--use-llm"))

    output = capsys.readouterr().out
    assert "## 智能行动计划" in output
    assert "优先补齐岗位缺口" in output
    assert "1. 完成项目：形成证据" in output
    assert "产出物：可运行仓库" in output
    assert "验收：测试通过" in output
