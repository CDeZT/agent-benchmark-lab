from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_suite_summary(run_dir: Path, suite_summary: dict[str, Any]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "suite_summary.json").write_text(
        json.dumps(suite_summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _write_suite_markdown(run_dir / "suite_report.md", suite_summary)


def _write_suite_markdown(path: Path, suite_summary: dict[str, Any]) -> None:
    lines = [
        f"# Suite Report: {suite_summary['suite_id']}",
        "",
        f"- Adapter: `{suite_summary['adapter']}`",
        f"- Model: `{suite_summary['model']}`",
        f"- Adapter model: `{suite_summary.get('adapter_model', suite_summary['model'])}`",
        f"- Budget profile: `{suite_summary['budget_profile']}`",
        f"- Repetitions per task: {suite_summary['repetitions_per_task']}",
        f"- Task count: {suite_summary['task_count']}",
        f"- Mean score: {suite_summary['mean_score']}",
        f"- Mean verified normalized score: {suite_summary.get('mean_verified_normalized_score')}",
        f"- Mean verified evidence coverage: {suite_summary.get('mean_verified_coverage_percent')}%",
        f"- Mean duration seconds: {suite_summary['mean_duration_seconds']}",
        "",
        "| Task | Strict Score | Score 95% CI | Verified Score | Coverage | Mean Duration | Variance | Experiment |",
        "| --- | ---: | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for task in suite_summary["tasks"]:
        lines.append(
            f"| `{task['task_id']}` | {task['mean_score']} | {_format_interval(task.get('score_confidence_interval_95'))} | {task.get('mean_verified_normalized_score')} | "
            f"{task.get('mean_verified_coverage_percent')}% | {task['mean_duration_seconds']} | "
            f"{task['variance']} | `{task['experiment_dir']}` |"
        )
    scorecard = suite_summary.get("evaluation_axis_scorecard", {})
    axes = scorecard.get("axes", {}) if isinstance(scorecard, dict) else {}
    if axes:
        lines.extend(["", "## Outcome Capability Scorecard", "", "| Axis | Tasks | Strict | Verified | Coverage |", "| --- | ---: | ---: | ---: | ---: |"])
        for axis, values in axes.items():
            lines.append(
                f"| {values['title']} (`{axis}`) | {values['task_count']} | {values['mean_strict_score']} | "
                f"{values['mean_verified_normalized_score']} | {values['mean_verified_coverage_percent']}% |"
            )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _format_interval(interval: object) -> str:
    if not isinstance(interval, dict):
        return "n/a"
    return f"[{interval.get('lower')}, {interval.get('upper')}] (n={interval.get('n')})"
