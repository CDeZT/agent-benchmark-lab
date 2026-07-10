from __future__ import annotations

from collections import defaultdict
from typing import Any


EVALUATION_AXES: dict[str, dict[str, object]] = {
    "software_engineering": {
        "title": "Software Engineering",
        "capabilities": {"bugfix", "feature_implementation", "refactoring", "code_review", "project_generation", "api_design", "code_understanding"},
    },
    "agentic_workflow": {
        "title": "Agentic Workflow",
        "capabilities": {"planning", "test_discipline", "ci_debugging", "debugging", "cross_module_reasoning"},
    },
    "systems_embedded": {
        "title": "Systems and Embedded",
        "capabilities": {"c_engineering", "systems_programming", "memory_management", "embedded_engineering", "protocol_design", "safety_boundary"},
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


def axes_for_task(capabilities: list[str]) -> list[str]:
    capability_set = set(capabilities)
    return [axis for axis, definition in EVALUATION_AXES.items() if capability_set & set(definition["capabilities"])]


def build_scorecard(task_summaries: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    excluded_smoke = []
    for task in task_summaries:
        if task.get("benchmark_role", "comparative_candidate") == "smoke_only":
            excluded_smoke.append(task.get("task_id"))
            continue
        for axis in axes_for_task(list(task.get("task_capabilities", []))):
            grouped[axis].append(task)

    axes = {}
    for axis, tasks in sorted(grouped.items()):
        strict = [float(task["mean_score"]) for task in tasks]
        verified = [float(task["mean_verified_normalized_score"]) for task in tasks if task.get("mean_verified_normalized_score") is not None]
        coverage = [float(task.get("mean_verified_coverage_percent", 0.0)) for task in tasks]
        axes[axis] = {
            "title": EVALUATION_AXES[axis]["title"],
            "task_count": len(tasks),
            "mean_strict_score": round(sum(strict) / len(strict), 2),
            "mean_verified_normalized_score": round(sum(verified) / len(verified), 2) if verified else None,
            "mean_verified_coverage_percent": round(sum(coverage) / len(coverage), 2),
            "task_ids": [task["task_id"] for task in tasks],
        }
    return {"axes": axes, "excluded_smoke_only_tasks": excluded_smoke}
