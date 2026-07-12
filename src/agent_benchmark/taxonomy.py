from __future__ import annotations

from collections import defaultdict
from typing import Any


EVALUATION_AXES: dict[str, dict[str, object]] = {
    "software_engineering": {
        "title": "Software Engineering",
        "capabilities": {
            "bugfix",
            "feature_implementation",
            "refactoring",
            "code_review",
            "project_generation",
            "api_design",
            "code_understanding",
        },
    },
    "agentic_workflow": {
        "title": "Agentic Workflow",
        "capabilities": {"planning", "test_discipline", "ci_debugging", "debugging", "cross_module_reasoning"},
    },
    "systems_embedded": {
        "title": "Systems and Embedded",
        "capabilities": {
            "c_engineering",
            "systems_programming",
            "memory_management",
            "embedded_engineering",
            "protocol_design",
            "safety_boundary",
        },
    },
    "scientific_computing": {
        "title": "Scientific Computing and Optics",
        "capabilities": {"optics_engineering", "numerical_accuracy", "data_engineering", "performance"},
    },
    "web_ui": {
        "title": "Web and UI",
        "capabilities": {"frontend_visual", "visual_verification", "fullstack", "api_design", "project_generation"},
    },
    "security_reliability": {
        "title": "Security and Reliability",
        "capabilities": {"security", "safety_boundary", "test_discipline", "ci_debugging"},
    },
}

# Domain-axis weights for a composite "direction" total. They are independent of
# the 10 process-dimension weights used inside a single task score.
DEFAULT_AXIS_WEIGHTS: dict[str, float] = {
    "software_engineering": 25.0,
    "agentic_workflow": 15.0,
    "systems_embedded": 20.0,  # C / embedded — user priority
    "scientific_computing": 15.0,  # optics / scientific — user priority
    "web_ui": 15.0,
    "security_reliability": 10.0,
}


def axes_for_task(capabilities: list[str]) -> list[str]:
    capability_set = set(capabilities)
    return [axis for axis, definition in EVALUATION_AXES.items() if capability_set & set(definition["capabilities"])]


def build_scorecard(
    task_summaries: list[dict[str, Any]],
    *,
    axis_weights: dict[str, float] | None = None,
) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    excluded_noncomparative = []
    for task in task_summaries:
        if task.get("benchmark_role", "comparative_candidate") != "comparative_candidate":
            excluded_noncomparative.append(task.get("task_id"))
            continue
        for axis in axes_for_task(list(task.get("task_capabilities", []))):
            grouped[axis].append(task)

    axes = {}
    for axis, tasks in sorted(grouped.items()):
        strict = [float(task["mean_score"]) for task in tasks]
        verified = [
            float(task["mean_verified_normalized_score"])
            for task in tasks
            if task.get("mean_verified_normalized_score") is not None
        ]
        coverage = [float(task.get("mean_verified_coverage_percent", 0.0)) for task in tasks]
        axes[axis] = {
            "title": EVALUATION_AXES[axis]["title"],
            "task_count": len(tasks),
            "mean_strict_score": round(sum(strict) / len(strict), 2),
            "mean_verified_normalized_score": round(sum(verified) / len(verified), 2) if verified else None,
            "mean_verified_coverage_percent": round(sum(coverage) / len(coverage), 2),
            "task_ids": [task["task_id"] for task in tasks],
        }

    domain_total = build_domain_weighted_total(axes, axis_weights=axis_weights)
    return {
        "axes": axes,
        "domain_weighted_total": domain_total,
        "excluded_noncomparative_tasks": excluded_noncomparative,
    }


def build_domain_weighted_total(
    axes: dict[str, dict[str, Any]],
    *,
    axis_weights: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Weighted composite over outcome axes that actually have tasks.

    Missing axes (no comparative tasks in this suite) are excluded and the
    remaining weights are renormalized. This keeps a small probe suite usable
    without pretending untested domains scored zero.
    """
    weights = dict(DEFAULT_AXIS_WEIGHTS if axis_weights is None else axis_weights)
    present = {
        axis: float(values["mean_strict_score"])
        for axis, values in axes.items()
        if isinstance(values, dict) and int(values.get("task_count") or 0) > 0 and axis in weights
    }
    present_verified = {
        axis: float(values["mean_verified_normalized_score"])
        for axis, values in axes.items()
        if isinstance(values, dict)
        and int(values.get("task_count") or 0) > 0
        and axis in weights
        and values.get("mean_verified_normalized_score") is not None
    }
    missing = sorted(axis for axis in weights if axis not in present)
    active_weight = sum(weights[axis] for axis in present)
    active_verified_weight = sum(weights[axis] for axis in present_verified)

    strict_total = None
    if present and active_weight > 0:
        strict_total = round(
            sum(present[axis] * weights[axis] for axis in present) / active_weight,
            2,
        )
    verified_total = None
    if present_verified and active_verified_weight > 0:
        verified_total = round(
            sum(present_verified[axis] * weights[axis] for axis in present_verified) / active_verified_weight,
            2,
        )

    return {
        "policy": "renormalize over outcome axes that have at least one comparative task; smoke_only excluded upstream",
        "configured_weights": weights,
        "active_weights": {axis: weights[axis] for axis in sorted(present)},
        "active_weight_sum": round(active_weight, 2),
        "missing_axes": missing,
        "strict": strict_total,
        "verified_normalized": verified_total,
        "usable": strict_total is not None,
        "note": (
            "Domain-weighted total is a suite-level direction score. "
            "It does not replace the 10 process-dimension task score."
        ),
    }
