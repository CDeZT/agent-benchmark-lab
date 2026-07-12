"""SWE-bench Verified metadata freezer.

This module deliberately freezes upstream task metadata without pretending that
the records are locally runnable SWE-bench tasks.  An official evaluation needs
the pinned upstream repository/image, a harness-produced patch, and preserved
official evaluator output.  Until that bridge exists, records use the
``external_frozen`` provenance type and cannot enter a local leaderboard.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def list_swebench_instances(max_count: int = 20) -> list[dict[str, Any]]:
    """Load SWE-bench Verified instances from the HuggingFace dataset."""
    try:
        from datasets import load_dataset
    except ImportError:
        raise RuntimeError("Install datasets: pip install datasets")

    ds = load_dataset("SWE-bench/SWE-bench_Verified", split="test")

    # Group by difficulty for stratified sampling
    by_difficulty: dict[str, list[dict[str, Any]]] = {}
    for item in ds:
        diff = item.get("difficulty", "unknown")
        if diff not in by_difficulty:
            by_difficulty[diff] = []
        by_difficulty[diff].append(item)

    # Stratified sample: take proportional from each difficulty
    selected: list[dict[str, Any]] = []
    for diff, items in sorted(by_difficulty.items()):
        count = max(1, len(items) * max_count // len(ds))
        selected.extend(items[:count])

    return selected[:max_count]


def create_swebench_task_manifest(
    instance: dict[str, Any],
    tasks_dir: Path,
) -> dict[str, Any]:
    """Freeze a SWE-bench instance as metadata-only evidence.

    The historical function name is retained for callers, but it does not
    import an executable benchmark environment or mark the task as scored.
    """
    instance_id = instance["instance_id"]
    repo = instance["repo"]
    task_id = f"swebench-{instance_id.replace('/', '_').replace('__', '-')}"

    task_dir = tasks_dir / task_id
    task_dir.mkdir(parents=True, exist_ok=True)

    # Create workspace directory (will be populated by the evaluator)
    workspace_dir = task_dir / "workspace"
    workspace_dir.mkdir(exist_ok=True)

    # Create instruction from problem statement
    instruction = (
        f"Fix the issue in {repo} described below.\n\n"
        f"Repository: {repo}\n"
        f"Base commit: {instance['base_commit']}\n\n"
        f"Problem:\n{instance['problem_statement']}\n\n"
        f"After fixing, run the test patch to verify your fix."
    )

    # Create task manifest
    manifest = {
        "id": task_id,
        "title": f"SWE-bench: {instance_id}",
        "instruction": instruction,
        "capabilities": ["bugfix", "code_understanding", "debugging"],
        "domains": ["python", "software_engineering"],
        "difficulty": _map_difficulty(instance.get("difficulty", "")),
        "difficulty_rationale": (
            "Metadata-only SWE-bench record; local tier is a coarse ordering "
            f"derived from upstream label {instance.get('difficulty', 'unknown')!r}, "
            "not an empirical difficulty claim."
        ),
        "provenance": {
            "type": "external_frozen",
            "source_benchmark": "SWE-bench",
            "source_id": instance_id,
            "source_url": f"https://github.com/SWE-bench/SWE-bench",
            "source_version": "Verified",
            "license_note": "MIT license",
            "importer_version": "1.0.0",
            "freeze_status": "metadata_only_official_evaluator_pending",
        },
        "metadata": {
            "environment": "external_evaluator_only",
            "benchmark_role": "external_evaluator_pending",
            "swebench": {
                "instance_id": instance_id,
                "repo": repo,
                "base_commit": instance["base_commit"],
                "difficulty": instance.get("difficulty"),
                "fail_to_pass": instance.get("FAIL_TO_PASS"),
                "pass_to_pass": instance.get("PASS_TO_PASS"),
            },
        },
        "workspace": "workspace",
        "test_command": [],
        "protected_paths": [],
    }

    # Write manifest
    (task_dir / "task.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # Write problem statement as instruction file
    (workspace_dir / "INSTRUCTION.md").write_text(
        instruction,
        encoding="utf-8",
    )

    return manifest


def _map_difficulty(swebench_diff: str) -> str:
    """Map SWE-bench difficulty to our difficulty levels."""
    if "15 min" in swebench_diff or "30 min" in swebench_diff:
        return "easy"
    if "1 hour" in swebench_diff:
        return "medium"
    if "2 hour" in swebench_diff or "4 hour" in swebench_diff:
        return "hard"
    return "medium"


def import_swebench_subset(
    tasks_dir: Path,
    max_count: int = 10,
) -> list[dict[str, Any]]:
    """Freeze a subset of SWE-bench Verified metadata for later bridging."""
    instances = list_swebench_instances(max_count)
    manifests = []
    for instance in instances:
        manifest = create_swebench_task_manifest(instance, tasks_dir)
        manifests.append(manifest)
    return manifests
