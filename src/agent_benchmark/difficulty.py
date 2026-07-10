from __future__ import annotations

from collections import defaultdict
import json
from pathlib import Path
import statistics
from typing import Any


def analyze_difficulty(
    runs_dir: Path,
    *,
    include_dummy: bool = False,
    min_combinations: int = 3,
    min_runs: int = 9,
) -> dict[str, Any]:
    """Classify empirical task discriminability from saved experiment summaries.

    A declared tier is only a hypothesis. This analysis evaluates real outcome
    data across harness/model/profile combinations. It intentionally refuses to
    classify a task as discriminative until enough non-dummy evidence exists.
    """
    grouped: dict[str, dict[tuple[str, str, str], list[float]]] = defaultdict(lambda: defaultdict(list))
    for path in sorted(runs_dir.rglob("summary.json")) if runs_dir.exists() else []:
        summary = _load_summary(path)
        if summary is None:
            continue
        adapter = str(summary.get("adapter", ""))
        if not include_dummy and adapter == "dummy":
            continue
        task_id = str(summary["task_id"])
        combination = (adapter, str(summary.get("model", "unspecified")), str(summary.get("budget_profile", "")))
        for run in summary.get("runs", []):
            if isinstance(run, dict):
                outcome = _completion_outcome(run)
                if outcome is not None:
                    grouped[task_id][combination].append(outcome)

    tasks = []
    for task_id, combinations in sorted(grouped.items()):
        combination_rates = [
            {
                "adapter": key[0],
                "model": key[1],
                "budget_profile": key[2],
                "run_count": len(outcomes),
                "success_rate": round(statistics.mean(outcomes), 4),
            }
            for key, outcomes in sorted(combinations.items())
        ]
        rates = [item["success_rate"] for item in combination_rates]
        run_count = sum(item["run_count"] for item in combination_rates)
        tasks.append(
            {
                "task_id": task_id,
                "combination_count": len(combination_rates),
                "run_count": run_count,
                "combination_success_rates": combination_rates,
                "success_rate_range": round(max(rates) - min(rates), 4) if rates else None,
                "classification": _classify(rates, len(combination_rates), run_count, min_combinations, min_runs),
            }
        )
    return {
        "policy": {
            "dummy_runs_included": include_dummy,
            "min_combinations": min_combinations,
            "min_runs": min_runs,
            "candidate_success_rate_band": [0.2, 0.8],
            "minimum_between_combination_gap": 0.2,
        },
        "task_count": len(tasks),
        "tasks": tasks,
    }


def _load_summary(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or not data.get("task_id") or not isinstance(data.get("runs"), list):
        return None
    return data


def _completion_outcome(run: dict[str, Any]) -> float | None:
    outcomes = [run.get("public_test_passed"), run.get("hidden_test_passed")]
    observed = [value for value in outcomes if isinstance(value, bool)]
    if not observed:
        return None
    return 1.0 if all(observed) else 0.0


def _classify(
    rates: list[float],
    combination_count: int,
    run_count: int,
    min_combinations: int,
    min_runs: int,
) -> str:
    if combination_count < min_combinations or run_count < min_runs:
        return "insufficient_evidence"
    if min(rates) >= 0.9:
        return "too_easy"
    if max(rates) <= 0.1:
        return "too_hard"
    if min(rates) <= 0.8 and max(rates) >= 0.2 and max(rates) - min(rates) >= 0.2:
        return "discriminative_candidate"
    return "needs_more_diversity"
