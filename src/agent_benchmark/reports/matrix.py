from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_matrix_summary(run_dir: Path, matrix_summary: dict[str, Any]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "matrix_summary.json").write_text(
        json.dumps(matrix_summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _write_matrix_markdown(run_dir / "matrix_report.md", matrix_summary)


def build_matrix_leaderboard(combinations: list[dict[str, Any]]) -> dict[str, Any]:
    """Rank only comparable tasks while keeping evidence coverage visible.

    Strict score is the primary ordering because unavailable dimensions stay at
    zero. The report must still show verified score and coverage next to it so
    an instrumentation gap is never mistaken for a capability gap.
    """
    rows = [_leaderboard_row(combination) for combination in combinations]
    ranked = [row for row in rows if row["comparative_task_count"]]
    ranked.sort(
        key=_ranking_key
    )
    previous_key: tuple[float, float, float] | None = None
    current_rank = 0
    for index, row in enumerate(ranked, start=1):
        key = _ranking_key(row)
        if key != previous_key:
            current_rank = index
            previous_key = key
        row["rank"] = current_rank
    for row in rows:
        row.setdefault("rank", None)
    return {
        "ranking_basis": "comparative-task strict score, then evidence coverage and verified score; equal evidence scores share rank while variance, duration, and cost remain separate evidence",
        "rows": rows,
        "ranked_combination_count": len(ranked),
    }


def _ranking_key(row: dict[str, Any]) -> tuple[float, float, float]:
    return (
        -float(row["mean_strict_score"] or 0.0),
        -float(row["mean_verified_coverage_percent"] or 0.0),
        -float(row["mean_verified_normalized_score"] or 0.0),
    )


def _leaderboard_row(combination: dict[str, Any]) -> dict[str, Any]:
    tasks = combination.get("tasks", [])
    comparable = [task for task in tasks if task.get("benchmark_role", "comparative_candidate") == "comparative_candidate"]
    run_outcomes = [
        _run_success(run)
        for task in comparable
        for run in task.get("runs", [])
        if _run_success(run) is not None
    ]
    return {
        "adapter": combination.get("adapter"),
        "model": combination.get("model"),
        "budget_profile": combination.get("budget_profile"),
        "suite_run_dir": combination.get("suite_run_dir"),
        "comparative_task_count": len(comparable),
        "excluded_noncomparative_task_ids": [
            task.get("task_id") for task in tasks if task.get("benchmark_role", "comparative_candidate") != "comparative_candidate"
        ],
        "mean_strict_score": _mean([task.get("mean_score") for task in comparable]),
        "mean_verified_normalized_score": _mean([task.get("mean_verified_normalized_score") for task in comparable]),
        "mean_verified_coverage_percent": _mean([task.get("mean_verified_coverage_percent") for task in comparable]),
        "task_pass_rate_percent": round(100.0 * sum(run_outcomes) / len(run_outcomes), 2) if run_outcomes else None,
        "observed_test_runs": len(run_outcomes),
        "mean_task_stdev": _mean([task.get("stdev") for task in comparable]),
        "mean_duration_seconds": _mean([task.get("mean_duration_seconds") for task in comparable]),
        "mean_cost_usd": _mean([task.get("mean_cost_usd") for task in comparable]),
    }


def _run_success(run: dict[str, Any]) -> bool | None:
    outcomes = [run.get("public_test_passed"), run.get("hidden_test_passed")]
    observed = [bool(value) for value in outcomes if value is not None]
    return all(observed) if observed else None


def _mean(values: list[object]) -> float | None:
    numeric = [float(value) for value in values if value is not None]
    return round(sum(numeric) / len(numeric), 4) if numeric else None


def _write_matrix_markdown(path: Path, matrix_summary: dict[str, Any]) -> None:
    lines = [
        f"# Matrix Report: {matrix_summary['suite_id']}",
        "",
        f"- Matrix run id: `{matrix_summary['matrix_run_id']}`",
        f"- Combination count: {matrix_summary['combination_count']}",
        "",
        "## Raw Suite Aggregations",
        "",
        "| Adapter | Model | Budget Profile | Strict Score | Verified Score | Coverage | Mean Duration | Suite Run |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for item in matrix_summary["combinations"]:
        lines.append(
            f"| `{item['adapter']}` | `{item['model']}` | `{item['budget_profile']}` | "
            f"{item['mean_score']} | {item.get('mean_verified_normalized_score')} | "
            f"{item.get('mean_verified_coverage_percent')}% | {item['mean_duration_seconds']} | "
            f"`{item['suite_run_dir']}` |"
        )
    leaderboard = matrix_summary.get("leaderboard")
    if isinstance(leaderboard, dict):
        lines.extend(
            [
                "",
                "## Comparative Ranking",
                "",
                f"- Basis: {leaderboard.get('ranking_basis')}",
                "- `smoke_only` and other non-comparative tasks are excluded from this table.",
                "",
                "| Rank | Adapter | Model | Profile | Comparative Tasks | Strict | Verified | Coverage | Pass Rate | Stdev | Duration | Cost USD |",
                "| ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for row in leaderboard.get("rows", []):
            if not row.get("comparative_task_count"):
                continue
            lines.append(
                f"| {row.get('rank') or 'n/a'} | `{row.get('adapter')}` | `{row.get('model')}` | "
                f"`{row.get('budget_profile')}` | {row.get('comparative_task_count')} | "
                f"{row.get('mean_strict_score')} | {row.get('mean_verified_normalized_score')} | "
                f"{row.get('mean_verified_coverage_percent')}% | {row.get('task_pass_rate_percent')}% | "
                f"{row.get('mean_task_stdev')} | {row.get('mean_duration_seconds')} | {row.get('mean_cost_usd')} |"
            )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
