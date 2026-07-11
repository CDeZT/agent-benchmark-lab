from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent_benchmark.scorers.basic import _comparable_score


def write_matrix_summary(run_dir: Path, matrix_summary: dict[str, Any]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "matrix_summary.json").write_text(
        json.dumps(matrix_summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _write_matrix_markdown(run_dir / "matrix_report.md", matrix_summary)


def build_matrix_leaderboard(combinations: list[dict[str, Any]]) -> dict[str, Any]:
    """Rank only comparable tasks while keeping evidence coverage visible.

    When different harnesses instrument different dimensions (e.g. one reports
    cost data but the other doesn't), the ``comparable_dimensions`` intersection
    identifies which dimensions are fair to compare. The ``mean_comparable_score``
    on each row uses only those shared dimensions so harnesses aren't penalised
    for missing telemetry.
    """
    dimensions_by_task, observed_dimensions = _comparable_dimensions_by_task(combinations)
    comparable_dimensions = sorted(set().union(*dimensions_by_task.values())) if dimensions_by_task else []
    noncomparable_dimensions = sorted(observed_dimensions - set(comparable_dimensions))

    rows = [_leaderboard_row(combination, dimensions_by_task) for combination in combinations]
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
    verified_rows = [row for row in ranked if row["model_identity_status"] == "verified_match"]
    for index, row in enumerate(verified_rows, start=1):
        row["verified_rank"] = index if index == 1 or _ranking_key(row) != _ranking_key(verified_rows[index - 2]) else verified_rows[index - 2]["verified_rank"]
    for row in rows:
        row.setdefault("verified_rank", None)
        row["ranking_evidence_state"] = _ranking_evidence_state(row)
    return {
        "ranking_basis": "task-level comparable score (only dimensions evidenced for every repetition of that task in every combination), then verified coverage and verified score; strict score remains diagnostic. Equal comparison evidence scores share rank. Explicit same-model claims require verified model identity. CLI-default rows compare observed current configurations and must not be labelled same-model comparisons.",
        "rows": rows,
        "ranked_combination_count": len(ranked),
        "verified_ranked_combination_count": len(verified_rows),
        "comparable_dimensions": comparable_dimensions,
        "comparable_dimensions_by_task": {task_id: sorted(dims) for task_id, dims in dimensions_by_task.items()},
        "noncomparable_dimensions": noncomparable_dimensions,
    }


def _ranking_key(row: dict[str, Any]) -> tuple[float, float, float]:
    return (
        -float(row["mean_comparable_score"] if row["mean_comparable_score"] is not None else row["mean_strict_score"] or 0.0),
        -float(row["mean_verified_coverage_percent"] or 0.0),
        -float(row["mean_verified_normalized_score"] or 0.0),
    )


def _leaderboard_row(
    combination: dict[str, Any],
    comparable_dimensions_by_task: dict[str, set[str]] | None = None,
) -> dict[str, Any]:
    tasks = combination.get("tasks", [])
    comparable = [task for task in tasks if task.get("benchmark_role", "comparative_candidate") == "comparative_candidate"]
    run_outcomes = [
        _run_success(run)
        for task in comparable
        for run in task.get("runs", [])
        if _run_success(run) is not None
    ]

    # Compute a comparable score using only dimensions that every harness in
    # the comparison has evidence for.  This prevents penalising a harness for
    # missing telemetry that another harness happens to provide.
    mean_comparable_score = None
    if comparable_dimensions_by_task:
        task_scores: list[float] = []
        for task in comparable:
            task_cs = _task_comparable_score(task, comparable_dimensions_by_task.get(str(task.get("task_id")), set()))
            if task_cs is not None:
                task_scores.append(task_cs)
        if task_scores:
            mean_comparable_score = round(sum(task_scores) / len(task_scores), 4)

    return {
        "adapter": combination.get("adapter"),
        "model": combination.get("model"),
        "adapter_model": combination.get("adapter_model", combination.get("model")),
        "budget_profile": combination.get("budget_profile"),
        "suite_run_dir": combination.get("suite_run_dir"),
        "comparative_task_count": len(comparable),
        "model_identity_status": _aggregate_model_identity(comparable),
        "detected_models": _detected_models(comparable),
        "excluded_noncomparative_task_ids": [
            task.get("task_id") for task in tasks if task.get("benchmark_role", "comparative_candidate") != "comparative_candidate"
        ],
        "mean_strict_score": _mean([task.get("mean_score") for task in comparable]),
        "mean_verified_normalized_score": _mean([task.get("mean_verified_normalized_score") for task in comparable]),
        "mean_verified_coverage_percent": _mean([task.get("mean_verified_coverage_percent") for task in comparable]),
        "mean_comparable_score": mean_comparable_score,
        "task_pass_rate_percent": round(100.0 * sum(run_outcomes) / len(run_outcomes), 2) if run_outcomes else None,
        "observed_test_runs": len(run_outcomes),
        "mean_task_stdev": _mean([task.get("stdev") for task in comparable]),
        "mean_duration_seconds": _mean([task.get("mean_duration_seconds") for task in comparable]),
        "mean_cost_usd": _mean([task.get("mean_cost_usd") for task in comparable]),
    }


def _comparable_dimensions_by_task(combinations: list[dict[str, Any]]) -> tuple[dict[str, set[str]], set[str]]:
    """Intersect evidence per task and repetition, avoiding cross-task leakage."""
    task_ids = {
        str(task.get("task_id"))
        for combination in combinations
        for task in combination.get("tasks", [])
        if task.get("benchmark_role", "comparative_candidate") == "comparative_candidate"
    }
    result: dict[str, set[str]] = {}
    observed: set[str] = set()
    for task_id in task_ids:
        combination_sets: list[set[str]] = []
        for combination in combinations:
            matching = next(
                (
                    task
                    for task in combination.get("tasks", [])
                    if task.get("benchmark_role", "comparative_candidate") == "comparative_candidate"
                    and str(task.get("task_id")) == task_id
                ),
                None,
            )
            if not matching:
                combination_sets.append(set())
                continue
            run_sets: list[set[str]] = []
            for run in matching.get("runs", []):
                measurement = run.get("measurement", {})
                if isinstance(measurement, dict):
                    dimensions = set(measurement.get("dimensions_with_evidence", []))
                    observed.update(dimensions)
                    run_sets.append(dimensions)
            combination_sets.append(set.intersection(*run_sets) if run_sets else set())
        result[task_id] = set.intersection(*combination_sets) if combination_sets else set()
    return result, observed


def _task_comparable_score(task: dict[str, Any], comparable_dimensions: set[str]) -> float | None:
    """Compute a comparable score for a single task across its runs.

    Returns the weighted score using only ``comparable_dimensions``, averaged
    across all repetitions. Returns None if no weights or run data is present.
    """
    runs = task.get("runs", [])
    if not runs:
        return None

    # Collect per-dimension mean scores across repetitions and extract weights
    # from the measurement stored with the first run.
    all_dim_keys: set[str] = set()
    weights: dict[str, float] = {}
    for run in runs:
        dims = run.get("dimensions", {})
        if isinstance(dims, dict):
            all_dim_keys.update(dims.keys())
        if not weights:
            measurement = run.get("measurement", {})
            if isinstance(measurement, dict):
                weights = measurement.get("weights", {})
    if not weights:
        return None

    mean_dims: dict[str, float] = {}
    for key in all_dim_keys:
        values = [float(run.get("dimensions", {}).get(key, 0.0)) for run in runs]
        mean_dims[key] = sum(values) / len(values)

    return _comparable_score(mean_dims, weights, comparable_dimensions)


def _aggregate_model_identity(tasks: list[dict[str, Any]]) -> str:
    statuses = {
        str(task.get("model_identity", {}).get("status", "not-recorded"))
        for task in tasks
        if isinstance(task.get("model_identity"), dict)
    }
    if not statuses:
        return "not-recorded"
    if statuses == {"verified_match"}:
        return "verified_match"
    if "mismatch" in statuses:
        return "mismatch"
    if "requested_unverified" in statuses:
        return "requested_unverified"
    if statuses == {"default_detected"}:
        return "default_detected"
    if "default_unverified" in statuses:
        return "default_unverified"
    return "mixed"


def _detected_models(tasks: list[dict[str, Any]]) -> list[str]:
    detected = {
        str(model)
        for task in tasks
        if isinstance(task.get("model_identity"), dict)
        for model in task["model_identity"].get("detected_models", [])
        if model
    }
    return sorted(detected)


def _ranking_evidence_state(row: dict[str, Any]) -> str:
    if row.get("verified_rank"):
        return "verified_model_identity"
    if row.get("model_identity_status") == "default_detected":
        return "cli_default_model_observed"
    if row.get("model_identity_status") == "default_unverified":
        return "cli_default_model_unobserved"
    return "provisional_model_identity"


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
        "| Adapter | Requested Model | Invocation Model | Observed Models | Budget Profile | Strict Score | Verified Score | Coverage | Mean Duration | Suite Run |",
        "| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for item in matrix_summary["combinations"]:
        lines.append(
            f"| `{item['adapter']}` | `{_display_model(item['model'])}` | `{_display_model(item.get('adapter_model', item['model']))}` | `{_observed_models(item)}` | `{item['budget_profile']}` | "
            f"{item['mean_score']} | {item.get('mean_verified_normalized_score')} | "
            f"{item.get('mean_verified_coverage_percent')}% | {item['mean_duration_seconds']} | "
            f"`{item['suite_run_dir']}` |"
        )
    leaderboard = matrix_summary.get("leaderboard")
    if isinstance(leaderboard, dict):
        comparable = leaderboard.get("comparable_dimensions", [])
        noncomparable = leaderboard.get("noncomparable_dimensions", [])
        lines.extend(
            [
                "",
                "## Comparative Ranking",
                "",
                f"- Basis: {leaderboard.get('ranking_basis')}",
                "- `smoke_only` and other non-comparative tasks are excluded from this table.",
            ]
        )
        if comparable:
            lines.append(
                f"- **Comparable dimensions** (instrumented by all harnesses): "
                + ", ".join(f"`{d}`" for d in comparable)
            )
        by_task = leaderboard.get("comparable_dimensions_by_task", {})
        if isinstance(by_task, dict):
            lines.append("- **Task-level common evidence**:")
            for task_id, dimensions in sorted(by_task.items()):
                rendered = ", ".join(f"`{dimension}`" for dimension in dimensions) if dimensions else "none"
                lines.append(f"  - `{task_id}`: {rendered}")
        if noncomparable:
            lines.append(
                f"- **Non-comparable dimensions** (missing telemetry in at least one harness): "
                + ", ".join(f"`{d}`" for d in noncomparable)
                + ". These are excluded from the Comparable Score to avoid penalising harnesses for missing instrumentation."
            )
        lines.extend(
            [
                "",
                "| Rank | Verified Rank | Evidence State | Adapter | Requested Model | Invocation Model | Observed Models | Model Evidence | Profile | Comparative Tasks | Strict | Comparable | Verified | Coverage | Pass Rate | Stdev | Duration | Cost USD |",
                "| ---: | ---: | --- | --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for row in leaderboard.get("rows", []):
            if not row.get("comparative_task_count"):
                continue
            lines.append(
                f"| {row.get('rank') or 'n/a'} | {row.get('verified_rank') or 'n/a'} | `{row.get('ranking_evidence_state')}` | `{row.get('adapter')}` | `{_display_model(row.get('model'))}` | `{_display_model(row.get('adapter_model'))}` | `{', '.join(row.get('detected_models', [])) or 'not reported'}` | "
                f"`{row.get('model_identity_status')}` | `{row.get('budget_profile')}` | {row.get('comparative_task_count')} | "
                f"{row.get('mean_strict_score')} | {row.get('mean_comparable_score')} | "
                f"{row.get('mean_verified_normalized_score')} | "
                f"{row.get('mean_verified_coverage_percent')}% | {row.get('task_pass_rate_percent')}% | "
                f"{row.get('mean_task_stdev')} | {row.get('mean_duration_seconds')} | {row.get('mean_cost_usd')} |"
            )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _display_model(value: object) -> str:
    return "CLI default" if value == "unspecified" else str(value)


def _observed_models(summary: dict[str, Any]) -> str:
    observed = {
        str(model)
        for task in summary.get("tasks", [])
        if isinstance(task.get("model_identity"), dict)
        for model in task["model_identity"].get("detected_models", [])
        if model
    }
    return ", ".join(sorted(observed)) or "not reported"
