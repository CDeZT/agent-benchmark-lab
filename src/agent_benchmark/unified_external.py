"""Represent authoritative results in suite artifacts without false score mixing.

Local tasks and official evaluators share resumable suite plumbing, but retain
their own metrics: local ten-dimension scores versus official resolution rate.
"""
from __future__ import annotations

import statistics
from pathlib import Path
from typing import Any

from agent_benchmark.authoritative_pilot import load_authoritative_pilot
from agent_benchmark.metrics import confidence_interval_95
from agent_benchmark.runner import ExperimentConfig
from agent_benchmark.swebench_bridge import SWEbenchBridgeConfig, run_swebench_bridge


SWEBENCH_PREFIX = "swebench:"


def is_external_task_id(task_id: str) -> bool:
    return task_id.startswith(SWEBENCH_PREFIX)


def external_instance_id(task_id: str) -> str:
    if not is_external_task_id(task_id):
        raise ValueError(f"Not an external task id: {task_id}")
    return task_id[len(SWEBENCH_PREFIX) :]


def external_task_fingerprint(task_id: str, pilots_file: Path) -> str:
    """Stable contract id for suite resume: pilot membership + frozen commit."""
    instance_id = external_instance_id(task_id)
    pilot = _swe_pilot(pilots_file)
    item = next((row for row in pilot["instances"] if row["instance_id"] == instance_id), None)
    if item is None:
        raise ValueError(f"External task '{task_id}' is not in the current SWE-bench pilot.")
    return (
        f"swebench|{pilot['id']}|{instance_id}|"
        f"{item.get('expected_base_commit','')}|{item.get('expected_difficulty','')}"
    )


def run_external_task_as_summary(
    task_id: str,
    config: ExperimentConfig,
    *,
    pilots_file: Path,
    registry_path: Path,
    execute: bool = True,
) -> dict[str, Any]:
    """Run (or require) the official bridge and map it to a local-like summary."""
    if not execute:
        raise ValueError("Unified suite requires execute=true for external tasks.")
    instance_id = external_instance_id(task_id)
    bridge_config = SWEbenchBridgeConfig(
        pilot_file=pilots_file,
        registry_path=registry_path,
        runs_dir=config.runs_dir,
        instance_id=instance_id,
        adapter=config.adapter,
        model=config.model,
        budget_profile=config.budget_profile,
    )
    attempts = []
    for repetition in range(1, config.repetitions + 1):
        result = run_swebench_bridge(bridge_config)
        attempt = bridge_result_to_task_summary(
            task_id=task_id,
            config=config,
            bridge_result=result,
            pilots_file=pilots_file,
        )
        attempt["runs"][0]["repetition"] = repetition
        attempts.append(attempt)
    return _aggregate_external_attempts(task_id, config, attempts)


def bridge_result_to_task_summary(
    *,
    task_id: str,
    config: ExperimentConfig,
    bridge_result: dict[str, Any],
    pilots_file: Path,
) -> dict[str, Any]:
    """Map official resolved/not_resolved into the same fields suite scoring uses."""
    instance_id = external_instance_id(task_id)
    pilot = _swe_pilot(pilots_file)
    item = next(row for row in pilot["instances"] if row["instance_id"] == instance_id)
    official = bridge_result.get("official_summary") or {}
    classification = str(official.get("classification") or "evaluator_output_missing")
    scorable = bool(official.get("scorable"))
    resolved = official.get("resolved")

    # The official evaluator establishes only resolution. Do not manufacture
    # planning, intent, execution, or safety evidence from a resolved patch.
    if not scorable:
        # Infrastructure failure: do not pretend the model scored 0 on the task.
        task_completion = 0.0
        mean_score = 0.0
        include_in_aggregate = False
        public_passed = None
        outcome = "evaluator_error_or_incomplete"
    elif resolved is True:
        # A resolution is a 100% external outcome, but only 30% of the local
        # strict score corresponds to task_completion. It is reported on a
        # separate official track and never blended into local strict averages.
        task_completion = 100.0
        mean_score = 30.0
        include_in_aggregate = False
        public_passed = True
        outcome = "resolved"
    else:
        task_completion = 0.0
        mean_score = 0.0
        include_in_aggregate = False
        public_passed = False
        outcome = "not_resolved"

    dimensions = {
        "task_completion": task_completion,
        "intent_understanding": 0.0,
        "planning": 0.0,
        "execution_quality": 0.0,
        "self_repair": 0.0,
        "test_discipline": 0.0,
        "tool_use": 0.0,
        "visual_verification": 0.0,
        "safety_boundary": 0.0,
        "cost_efficiency": 0.0,
    }

    harness = ((bridge_result.get("manifest") or {}).get("stages") or {}).get("harness") or {}
    detected = harness.get("detected_model")
    duration = float(harness.get("duration_seconds") or 0.0)

    return {
        "experiment_id": Path(str(bridge_result.get("bridge_dir", ""))).name or instance_id,
        "task_id": task_id,
        "task_title": f"SWE-bench official: {instance_id}",
        "task_difficulty": str(item.get("expected_difficulty") or "unknown"),
        "task_difficulty_rationale": "Upstream SWE-bench Verified difficulty label; scored by official Docker evaluator.",
        "task_provenance": {
            "type": "external_official",
            "source_benchmark": "SWE-bench_Verified",
            "source_id": instance_id,
            "pilot_id": pilot["id"],
            "selection_role": item.get("selection_role"),
        },
        "task_fingerprint": external_task_fingerprint(task_id, pilots_file),
        "task_capabilities": ["bugfix", "code_understanding", "python_engineering", "cross_module_reasoning"],
        "task_domains": ["python", "software_engineering"],
        "benchmark_role": "comparative_candidate"
        if item.get("selection_role") == "ranking_candidate"
        else "smoke_only",
        "adapter": config.adapter,
        "model": config.model,
        "adapter_model": config.invocation_model,
        "budget_profile": config.budget_profile,
        "label": config.label,
        "experiment_dir": str(bridge_result.get("bridge_dir") or ""),
        "repetitions": 1,
        "mean_score": mean_score,
        "mean_verified_normalized_score": 100.0 if resolved is True else (0.0 if scorable else None),
        "mean_verified_coverage_percent": 30.0 if scorable else 0.0,
        "mean_duration_seconds": duration,
        "mean_cost_usd": harness.get("cost_usd"),
        "variance": 0.0,
        "stdev": 0.0,
        "best_score": mean_score,
        "worst_score": mean_score,
        "score_confidence_interval_95": None,
        "detected_model": detected,
        "detected_models": [detected] if detected else [],
        "model_identity": {
            "status": "default_detected" if detected else "default_unverified",
            "requested_model": config.model,
            "detected_models": [detected] if detected else [],
        },
        "total_tool_calls": int(harness.get("tool_call_count") or 0),
        "include_in_aggregate": include_in_aggregate,
        "official_outcome": outcome,
        "official_classification": classification,
        "official_scorable": scorable,
        "official_resolved": resolved,
        "official_attempt_count": 1,
        "official_scorable_attempt_count": 1 if scorable else 0,
        "official_resolved_attempt_count": 1 if resolved is True else 0,
        "official_resolution_rate_percent": 100.0 if resolved is True else (0.0 if scorable else None),
        "scoring_mode": "official_resolution_separate_track",
        "runs": [
            {
                "run_id": f"{instance_id}-official",
                "repetition": 1,
                "score": mean_score,
                "dimensions": dimensions,
                "measurement": {
                    "dimension_status": {
                        "task_completion": "verified" if scorable else "unavailable",
                        "intent_understanding": "unavailable",
                        "planning": "unavailable",
                        "execution_quality": "unavailable",
                        "self_repair": "unavailable",
                        "test_discipline": "unavailable",
                        "tool_use": "unavailable",
                        "visual_verification": "unavailable",
                        "safety_boundary": "unavailable",
                        "cost_efficiency": "unavailable",
                    },
                    "verified_coverage_percent": 30.0 if scorable else 0.0,
                    "verified_normalized_score": 100.0 if resolved is True else (0.0 if scorable else None),
                    "strict_weighted_score": mean_score,
                },
                "public_test_passed": public_passed,
                "hidden_test_passed": public_passed,
                "duration_seconds": duration,
                "detected_model": detected,
                "tool_call_count": int(harness.get("tool_call_count") or 0),
                "cost_usd": harness.get("cost_usd"),
                "run_dir": str(bridge_result.get("bridge_dir") or ""),
                "official_summary": official,
            }
        ],
    }


def _aggregate_external_attempts(
    task_id: str,
    config: ExperimentConfig,
    attempts: list[dict[str, Any]],
) -> dict[str, Any]:
    """Aggregate repeated official attempts without converting them to local scores."""
    if not attempts:
        raise ValueError(f"No official attempts were recorded for {task_id}.")
    first = dict(attempts[0])
    runs = [attempt["runs"][0] for attempt in attempts]
    scorable = [attempt for attempt in attempts if attempt.get("official_scorable")]
    scores = [float(attempt["mean_score"]) for attempt in scorable]
    resolutions = [bool(attempt.get("official_resolved")) for attempt in scorable]
    durations = [float(attempt.get("mean_duration_seconds") or 0.0) for attempt in attempts]
    detected = [str(attempt["detected_model"]) for attempt in attempts if attempt.get("detected_model")]

    first.update(
        {
            "repetitions": config.repetitions,
            "runs": runs,
            "experiment_dir": ",".join(str(attempt.get("experiment_dir") or "") for attempt in attempts),
            "mean_score": round(statistics.mean(scores), 2) if scores else 0.0,
            "variance": round(statistics.pvariance(scores), 4) if len(scores) > 1 else 0.0,
            "stdev": round(statistics.pstdev(scores), 4) if len(scores) > 1 else 0.0,
            "best_score": max(scores) if scores else 0.0,
            "worst_score": min(scores) if scores else 0.0,
            "score_confidence_interval_95": confidence_interval_95(scores),
            "mean_verified_normalized_score": round(100.0 * sum(resolutions) / len(resolutions), 2)
            if resolutions
            else None,
            "mean_verified_coverage_percent": 30.0 if scorable else 0.0,
            "mean_duration_seconds": round(statistics.mean(durations), 4) if durations else 0.0,
            "detected_models": sorted(set(detected)),
            "include_in_aggregate": False,
            "official_attempt_count": len(attempts),
            "official_scorable_attempt_count": len(scorable),
            "official_resolved_attempt_count": sum(resolutions),
            "official_resolution_rate_percent": round(100.0 * sum(resolutions) / len(resolutions), 2)
            if resolutions
            else None,
            "official_scorable": bool(scorable),
            "official_resolved": bool(sum(resolutions)),
        }
    )
    return first


def _swe_pilot(pilots_file: Path) -> dict[str, Any]:
    data = __import__("json").loads(pilots_file.read_text(encoding="utf-8"))
    pilots = [item for item in data.get("pilots", []) if item.get("corpus_id") == "swe-bench-verified"]
    if not pilots:
        raise ValueError("No SWE-bench pilot found.")
    # Prefer the hard-v2 pilot when multiple are present.
    preferred = next((item for item in pilots if item.get("id") == "swe-bench-verified-hard-v2"), pilots[0])
    return load_authoritative_pilot(pilots_file, preferred["id"])
