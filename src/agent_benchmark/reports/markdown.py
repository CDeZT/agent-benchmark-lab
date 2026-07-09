from __future__ import annotations

from pathlib import Path
from typing import Any


def write_markdown_report(path: Path, summary: dict[str, Any], results: list[object]) -> None:
    detected = summary.get("detected_model")
    model_display = f"{summary['model']}" + (f" (detected: {detected})" if detected and detected != summary["model"] else "")
    lines = [
        f"# Benchmark Report: {summary['task_id']}",
        "",
        f"- Adapter: `{summary['adapter']}`",
        f"- Model: `{model_display}`",
        f"- Budget profile: `{summary['budget_profile']}`",
        f"- Repetitions: {summary['repetitions']}",
        f"- Mean score: {summary['mean_score']}",
        f"- Variance: {summary['variance']}",
        f"- Standard deviation: {summary['stdev']}",
        f"- Best score: {summary['best_score']}",
        f"- Worst score: {summary['worst_score']}",
        f"- Mean duration seconds: {summary['mean_duration_seconds']}",
        f"- Mean adapter duration seconds: {summary['mean_adapter_duration_seconds']}",
        f"- Mean test duration seconds: {summary['mean_test_duration_seconds']}",
        f"- Mean cost USD: {summary['mean_cost_usd']}",
        f"- Total tool calls: {summary.get('total_tool_calls', 0)}",
        "",
        "## Runs",
        "",
        "| Rep | Score | Public | Hidden | Tools | Duration | Changed Files |",
        "| ---: | ---: | --- | --- | ---: | ---: | --- |",
    ]
    for run in summary["runs"]:
        changed = ", ".join(run["changed_files"]) if run["changed_files"] else "none"
        tools = run.get("tool_call_count", 0)
        lines.append(
            f"| {run['repetition']} | {run['score']} | {_status(run['public_test_passed'])} | "
            f"{_status(run['hidden_test_passed'])} | {tools} | {run['duration_seconds']} | {changed} |"
        )
    lines.extend(["", "## Notes", "", "Scores are evidence-backed by per-run `result.json`, `trace.jsonl`, and `diff.patch`."])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _status(value: object) -> str:
    if value is True:
        return "pass"
    if value is False:
        return "fail"
    return "n/a"
