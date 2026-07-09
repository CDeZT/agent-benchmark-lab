from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
import re
import subprocess
import time
from typing import Any

from agent_benchmark.parsers.harness_output import HarnessEvidence
from agent_benchmark.recorders import JsonlRecorder
from agent_benchmark.scorers.integrity import score_protected_paths
from agent_benchmark.scorers.process import score_process_checks
from agent_benchmark.scorers.visual import score_visual_checks
from agent_benchmark.task_schema import TaskSpec


# Self-repair indicator patterns.  Each compiled regex that matches anywhere in
# stdout.log or stderr.log counts as one distinct evidence point.  The score is
# proportional to the number of matched indicators (3+ = 100).
_SELF_REPAIR_INDICATORS: list[tuple[re.Pattern[str], str]] = [
    # No trailing \b on retry/rerun so "retrying", "re-running" also match.
    (re.compile(r"\bre-?try", re.I), "retry"),
    (re.compile(r"\btry again\b", re.I), "try_again"),
    (re.compile(r"\bre-?run", re.I), "rerun"),
    (re.compile(r"\bfixing\b", re.I), "fixing"),
    (re.compile(r"\bcorrecting\b", re.I), "correcting"),
    (re.compile(r"\bpatching\b", re.I), "patching"),
    (re.compile(r"\bdebugging\b", re.I), "debugging"),
    (re.compile(r"\boops\b", re.I), "oops"),
    (re.compile(r"\bmy mistake\b", re.I), "my_mistake"),
    (re.compile(r"\battempt\s*[2-9]\b", re.I), "multiple_attempts"),
]


def _score_self_repair(workspace: Path) -> tuple[float, dict[str, Any]]:
    """Score the self_repair dimension by scanning stdout/stderr logs.

    The run directory is ``workspace.parent`` (workspace lives at
    ``<run_dir>/workspace``, logs at ``<run_dir>/stdout.log``).
    Returns ``(score, evidence)`` where score is 0-100.
    """
    run_dir = workspace.parent
    stdout_path = run_dir / "stdout.log"
    stderr_path = run_dir / "stderr.log"

    log_content = ""
    logs_found = False
    for log_path in (stdout_path, stderr_path):
        if log_path.is_file():
            logs_found = True
            log_content += log_path.read_text(encoding="utf-8", errors="replace") + "\n"

    if not logs_found:
        return 0.0, {"error": "No log files found in run directory."}

    matched: list[str] = []
    for pattern, label in _SELF_REPAIR_INDICATORS:
        if pattern.search(log_content):
            matched.append(label)

    # Score: proportional to indicator count, 3+ indicators = full score.
    score = round(min(len(matched) / 3.0, 1.0) * 100.0, 2)
    evidence: dict[str, Any] = {
        "matched_indicators": matched,
        "indicator_count": len(matched),
        "target_count": 3,
    }
    return score, evidence


@dataclass
class ScoreResult:
    total: float
    dimensions: dict[str, float]
    evidence: dict[str, object] = field(default_factory=dict)


def score_run(
    task: TaskSpec,
    baseline: Path,
    workspace: Path,
    recorder: JsonlRecorder,
    harness_evidence: HarnessEvidence | None = None,
) -> ScoreResult:
    dimensions: dict[str, float] = {}
    evidence: dict[str, object] = {}

    public_test = _run_test_command("public", task.test_command, workspace, workspace, task.test_timeout_seconds, recorder)
    hidden_test = _run_test_command(
        "hidden",
        task.hidden_test_command,
        task.root / "hidden",
        workspace,
        task.test_timeout_seconds,
        recorder,
    )
    test_results = [result for result in [public_test, hidden_test] if result["configured"]]
    if test_results:
        dimensions["task_completion"] = sum(100.0 if result["passed"] else 0.0 for result in test_results) / len(test_results)
    else:
        dimensions["task_completion"] = 0.0
    evidence["test"] = {"public": public_test, "hidden": hidden_test}

    integrity = score_protected_paths(task, baseline, workspace)
    dimensions["safety_boundary"] = integrity.score
    evidence["safety_boundary"] = {
        "missing_protected_paths": integrity.missing,
        "modified_protected_paths": integrity.modified,
        "baseline_hashes": integrity.baseline_hashes,
        "current_hashes": integrity.current_hashes,
    }
    recorder.event(
        "integrity.checked",
        {
            "score": integrity.score,
            "missing_protected_paths": integrity.missing,
            "modified_protected_paths": integrity.modified,
        },
    )

    visual = score_visual_checks(workspace, task.visual_checks)
    dimensions["visual_verification"] = visual.score
    evidence["visual_verification"] = {"engine": visual.engine, "checks": visual.checks}
    recorder.event(
        "visual.checked",
        {
            "engine": visual.engine,
            "score": visual.score,
            "check_count": len(visual.checks),
            "passed_count": sum(1 for check in visual.checks if check.get("passed")),
        },
    )

    process = score_process_checks(workspace, task.process_checks, baseline=baseline)
    dimensions.update(process.dimensions)
    evidence["process"] = {"checks": process.checks, "dimensions": process.dimensions}
    recorder.event(
        "process.checked",
        {
            "dimensions": process.dimensions,
            "check_count": len(process.checks),
            "passed_count": sum(1 for check in process.checks if check.get("passed")),
        },
    )

    # tool_use: scored from parsed harness output (tool call count and variety)
    if harness_evidence and harness_evidence.tool_calls:
        tool_types = {t["type"] for t in harness_evidence.tool_calls}
        call_count = len(harness_evidence.tool_calls)
        # Score: 50% for having any tools, 50% for variety (up to 4+ types)
        variety_score = min(len(tool_types) / 4.0, 1.0) * 50.0
        count_score = min(call_count / 5.0, 1.0) * 50.0
        dimensions["tool_use"] = round(variety_score + count_score, 2)
        evidence["tool_use"] = {
            "tool_types": sorted(tool_types),
            "tool_count": call_count,
            "variety_score": round(variety_score, 2),
            "count_score": round(count_score, 2),
        }
        recorder.event("tool_use.scored", evidence["tool_use"])

    # self_repair: scored from stdout.log / stderr.log content analysis.
    # Looks for evidence of self-correction (retry language, fix actions,
    # multiple attempts, etc.) in the agent's execution logs.
    self_repair_score, self_repair_evidence = _score_self_repair(workspace)
    dimensions["self_repair"] = self_repair_score
    evidence["self_repair"] = self_repair_evidence
    recorder.event("self_repair.scored", self_repair_evidence)

    # Framework placeholders are deliberately explicit. They are not fake high
    # scores; they mark dimensions that need richer evidence in later phases.
    # setdefault will NOT overwrite values already populated above (e.g.
    # process_checks dimensions), so existing evidence is preserved.
    for dimension in [
        "intent_understanding",
        "planning",
        "execution_quality",
        "self_repair",
        "test_discipline",
        "tool_use",
        "cost_efficiency",
    ]:
        dimensions.setdefault(dimension, 0.0)

    weights = _weights(task)
    total_weight = sum(weights.values())
    total = sum(dimensions.get(name, 0.0) * weight for name, weight in weights.items()) / total_weight
    recorder.event("score.computed", {"total": total, "dimensions": dimensions})
    return ScoreResult(total=round(total, 2), dimensions=dimensions, evidence=evidence)


def _weights(task: TaskSpec) -> dict[str, float]:
    defaults = {
        "task_completion": 30.0,
        "intent_understanding": 10.0,
        "planning": 8.0,
        "execution_quality": 12.0,
        "self_repair": 10.0,
        "test_discipline": 10.0,
        "tool_use": 6.0,
        "visual_verification": 4.0,
        "safety_boundary": 6.0,
        "cost_efficiency": 4.0,
    }
    defaults.update(task.scoring_weights)
    return defaults


def _run_test_command(
    kind: str,
    command: list[str],
    cwd: Path,
    workspace: Path,
    timeout_seconds: float,
    recorder: JsonlRecorder,
) -> dict[str, object]:
    if not command:
        return {"configured": False, "kind": kind, "error": "No test command configured."}

    env = os.environ.copy()
    env["AGENT_BENCH_WORKSPACE"] = str(workspace.resolve())
    start = time.monotonic()
    recorder.event(f"test.{kind}.started", {"command": command, "cwd": str(cwd)})
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
            check=False,
        )
        duration = time.monotonic() - start
        result = {
            "configured": True,
            "kind": kind,
            "command": command,
            "cwd": str(cwd),
            "exit_code": completed.returncode,
            "passed": completed.returncode == 0,
            "timed_out": False,
            "stdout": completed.stdout[-4000:],
            "stderr": completed.stderr[-4000:],
            "duration_seconds": duration,
        }
        recorder.event(
            f"test.{kind}.finished",
            {
                "exit_code": completed.returncode,
                "duration_seconds": duration,
                "stdout_tail": completed.stdout[-1000:],
                "stderr_tail": completed.stderr[-1000:],
            },
        )
    except subprocess.TimeoutExpired as exc:
        duration = time.monotonic() - start
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        result = {
            "configured": True,
            "kind": kind,
            "command": command,
            "cwd": str(cwd),
            "exit_code": 124,
            "passed": False,
            "timed_out": True,
            "stdout": stdout[-4000:],
            "stderr": (stderr + f"\nTimed out after {timeout_seconds} seconds.")[-4000:],
            "duration_seconds": duration,
        }
        recorder.event(
            f"test.{kind}.finished",
            {
                "exit_code": 124,
                "timed_out": True,
                "duration_seconds": duration,
                "stdout_tail": stdout[-1000:],
                "stderr_tail": stderr[-1000:],
            },
        )
    return result
