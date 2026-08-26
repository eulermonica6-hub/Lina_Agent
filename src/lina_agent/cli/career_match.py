import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from lina_agent.application.career_agent import CareerAgentRun, CareerMatchAgent
from lina_agent.infrastructure.llm_career_planner import LLMCareerPlanner
from lina_agent.infrastructure.llm_provider import build_economic_router


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="读取本地简历与 JD 目录，生成带证据的确定性技能匹配报告。"
    )
    parser.add_argument("--resume", required=True, type=Path, help="TXT、Markdown 或 DOCX 简历")
    parser.add_argument("--jobs", required=True, type=Path, help="Markdown JD 目录")
    parser.add_argument("--top", type=int, default=5, help="返回岗位数量，默认 5")
    parser.add_argument(
        "--include-inactive",
        action="store_true",
        help="包含已下线或不可投递岗位",
    )
    parser.add_argument(
        "--use-llm",
        action="store_true",
        help="使用经济型 Provider 生成匿名化智能行动计划",
    )
    parser.add_argument(
        "--format",
        choices=("markdown", "json"),
        default="markdown",
        help="输出格式，默认 markdown",
    )
    arguments = parser.parse_args(argv)
    planner = LLMCareerPlanner(build_economic_router()) if arguments.use_llm else None
    run = CareerMatchAgent(planner=planner).execute_paths(
        arguments.resume,
        arguments.jobs,
        top_k=arguments.top,
        include_inactive=arguments.include_inactive,
    )
    if arguments.format == "json":
        print(json.dumps(run.model_dump(mode="json"), ensure_ascii=False, indent=2))
    else:
        print(format_markdown(run))


def format_markdown(run: CareerAgentRun) -> str:
    skill_names = "、".join(mention.skill for mention in run.candidate.skills) or "未识别"
    lines = [
        "# Lina 初步职业匹配报告",
        "",
        f"- 运行状态：{run.state}",
        f"- 简历：{run.candidate.source_name}",
        f"- 候选人技能：{skill_names}",
        f"- 岗位：共 {run.total_jobs} 个，参与排序 {run.considered_jobs} 个",
        "",
        "## Top 匹配",
        "",
    ]
    if not run.matches:
        lines.append("没有可展示的岗位。")
    for rank, match in enumerate(run.matches, start=1):
        matched = "、".join(item.skill for item in match.matched_required) or "无"
        missing = "、".join(item.skill for item in match.missing_required) or "无"
        lines.extend(
            (
                f"### {rank}. {match.title} | {match.company}",
                "",
                f"- 证据覆盖分：{match.score:.1f}",
                f"- 已覆盖明确技能：{matched}",
                f"- 未覆盖明确技能：{missing}",
                "",
            )
        )
    if run.action_plan is not None:
        lines.extend(("## 智能行动计划", "", run.action_plan.summary, ""))
        lines.extend(
            f"{action.priority}. {action.action}：{action.reason}"
            for action in run.action_plan.priority_actions
        )
        lines.append("")
    lines.extend(("## 使用边界", "", *(f"- {warning}" for warning in run.warnings)))
    return "\n".join(lines)
