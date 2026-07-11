from __future__ import annotations

from collections import defaultdict
import json
from pathlib import Path
import statistics
from typing import Any

from agent_benchmark.task_fingerprint import task_fingerprint
from agent_benchmark.task_schema import load_task

def analyze_difficulty(
    runs_dir: Path,
    *,
    include_dummy: bool = False,
    min_combinations: int = 3,
    min_runs: int = 9,
    min_runs_per_combination: int = 3,
    tasks_dir: Path | None = None,
) -> dict[str, Any]:
    """Classify empirical task discriminability from saved experiment summaries.

    A declared tier is only a hypothesis. This analysis evaluates real outcome
    data across harness/model/profile combinations. It intentionally refuses to
    classify a task as discriminative until enough non-dummy evidence exists.
    """
    grouped: dict[str, dict[tuple[str, str, str], list[float]]] = defaultdict(lambda: defaultdict(list))
    ignored_summaries = {
        "dummy_adapter": 0,
        "unidentified_model": 0,
        "no_completion_outcome": 0,
        "task_fingerprint_mismatch": 0,
    }
    current_fingerprints = _current_fingerprints(tasks_dir) if tasks_dir else {}
    for path in sorted(runs_dir.rglob("summary.json")) if runs_dir.exists() else []:
        summary = _load_summary(path)
        if summary is None:
            continue
        adapter = str(summary.get("adapter", ""))
        if not include_dummy and adapter == "dummy":
            ignored_summaries["dummy_adapter"] += 1
            continue
        task_id = str(summary["task_id"])
        if tasks_dir is not None and summary.get("task_fingerprint") != current_fingerprints.get(task_id):
            ignored_summaries["task_fingerprint_mismatch"] += 1
            continue
        observed_model = _observed_model(summary)
        if observed_model is None:
            ignored_summaries["unidentified_model"] += 1
            continue
        combination = (adapter, observed_model, str(summary.get("budget_profile", "")))
        recorded_outcome = False
        for run in summary.get("runs", []):
            if isinstance(run, dict):
                outcome = _completion_outcome(run)
                if outcome is not None:
                    grouped[task_id][combination].append(outcome)
                    recorded_outcome = True
        if not recorded_outcome:
            ignored_summaries["no_completion_outcome"] += 1

    tasks = []
    for task_id, combinations in sorted(grouped.items()):
        observed_combination_rates = [
            {
                "adapter": key[0],
                "observed_model": key[1],
                "budget_profile": key[2],
                "run_count": len(outcomes),
                "success_rate": round(statistics.mean(outcomes), 4),
                "eligible_for_classification": len(outcomes) >= min_runs_per_combination,
            }
            for key, outcomes in sorted(combinations.items())
        ]
        combination_rates = [item for item in observed_combination_rates if item["eligible_for_classification"]]
        rates = [item["success_rate"] for item in combination_rates]
        run_count = sum(item["run_count"] for item in combination_rates)
        tasks.append(
            {
                "task_id": task_id,
                "combination_count": len(combination_rates),
                "run_count": run_count,
                "observed_combination_count": len(observed_combination_rates),
                "observed_run_count": sum(item["run_count"] for item in observed_combination_rates),
                "combination_success_rates": observed_combination_rates,
                "success_rate_range": round(max(rates) - min(rates), 4) if rates else None,
                "classification": _classify(rates, len(combination_rates), run_count, min_combinations, min_runs),
            }
        )
    return {
        "policy": {
            "dummy_runs_included": include_dummy,
            "min_combinations": min_combinations,
            "min_runs": min_runs,
            "min_runs_per_combination": min_runs_per_combination,
            "candidate_success_rate_band": [0.2, 0.8],
            "minimum_between_combination_gap": 0.2,
            "combination_key": "adapter x observed_model x budget_profile",
            "unidentified_model_summaries_excluded": True,
            "task_fingerprint_match_required": tasks_dir is not None,
        },
        "task_count": len(tasks),
        "ignored_summaries": ignored_summaries,
        "tasks": tasks,
    }


def _current_fingerprints(tasks_dir: Path) -> dict[str, str]:
    if not tasks_dir.exists():
        return {}
    return {
        task.task_id: task_fingerprint(task)
        for path in tasks_dir.iterdir()
        if path.is_dir()
        for task in [load_task(path)]
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


def _observed_model(summary: dict[str, Any]) -> str | None:
    """Return one actual model identity or refuse to pool uncertain history.

    A requested CLI label can be stale, mapped to another provider identifier,
    or ignored by a harness. Difficulty statistics must therefore use the model
    exposed by saved harness output. A summary that observed multiple models is
    also excluded: it cannot represent one repeatable configuration.
    """
    identity = summary.get("model_identity")
    candidates: set[str] = set()
    if isinstance(identity, dict):
        candidates.update(
            str(model).strip()
            for model in identity.get("detected_models", [])
            if isinstance(model, str) and model.strip()
        )
    if not candidates:
        candidates.update(
            str(run.get("detected_model")).strip()
            for run in summary.get("runs", [])
            if isinstance(run, dict) and isinstance(run.get("detected_model"), str) and run["detected_model"].strip()
        )
    if len(candidates) != 1:
        return None
    return next(iter(candidates)).casefold().split("/")[-1]


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
