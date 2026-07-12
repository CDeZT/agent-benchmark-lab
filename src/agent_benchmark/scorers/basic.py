from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
import re
import subprocess
import time
from typing import Any, Callable

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


def _score_tool_use_from_workspace_edits(baseline: Path, workspace: Path) -> tuple[float, dict[str, Any]]:
    """Score tool_use from real file edits when harness telemetry is missing.

    A workspace diff proves that an agent produced an edit, not which tools it
    used or how it used them. Keep this as a useful fallback signal, but mark
    it heuristic rather than letting it inflate verified tool-use coverage.
    """
    ignore = {".pyc", ".pyo", ".o", ".so", ".dylib", ".DS_Store"}
    changed: list[str] = []
    if not baseline.exists() or not workspace.exists():
        return 0.0, {"source": "workspace_edits", "strength": "heuristic", "tool_count": 0, "changed_files": []}
    for path in sorted(workspace.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix in ignore or path.name in ignore:
            continue
        rel = path.relative_to(workspace)
        base = baseline / rel
        try:
            current = path.read_bytes()
        except OSError:
            continue
        if not base.is_file():
            changed.append(str(rel))
            continue
        try:
            if base.read_bytes() != current:
                changed.append(str(rel))
        except OSError:
            changed.append(str(rel))
    # Prefer source-like edits over pure metadata noise.
    source_changed = [
        name
        for name in changed
        if Path(name).suffix in {".py", ".c", ".h", ".js", ".ts", ".tsx", ".jsx", ".html", ".css", ".json", ".md", ".txt"}
        or name.endswith("Makefile")
    ]
    useful = source_changed or changed
    if not useful:
        return 0.0, {
            "source": "workspace_edits",
            "strength": "heuristic",
            "tool_count": 0,
            "changed_files": [],
            "method": "no_workspace_edits",
        }
    # One real edit => agent used tools; more files => slightly higher score.
    count_score = min(len(useful) / 3.0, 1.0) * 50.0
    presence_score = 50.0
    score = round(presence_score + count_score, 2)
    return score, {
        "source": "workspace_edits",
        "strength": "heuristic",
        "tool_types": ["workspace_edit"],
        "tool_count": len(useful),
        "changed_files": useful[:20],
        "variety_score": 12.5,
        "count_score": round(count_score, 2),
        "method": "workspace_diff_fallback",
    }


def _score_cost_efficiency(harness_evidence: HarnessEvidence) -> tuple[float, dict[str, Any]]:
    """Score the cost_efficiency dimension from harness evidence.

    If token/cost data is available, score based on actual cost (lower = better).
    Otherwise, keep the dimension at zero. Tool-call count is useful evidence
    for tool_use, but it is not a cost measurement and should not stand in for
    token/provider billing data.

    Returns (score, evidence) where score is 0-100.
    """
    # Priority 1: Real token/cost data.
    # Guard: zero cost/tokens when nothing happened is not "perfect efficiency".
    if harness_evidence.cost_usd is not None:
        cost = harness_evidence.cost_usd
        if cost <= 0:
            return 0.0, {
                "method": "cost_usd",
                "cost_usd": cost,
                "score": 0.0,
                "reason": "zero cost is not evidence of efficiency",
            }
        # Score based on cost: lower cost = higher score
        score = max(0.0, min(100.0, 100.0 - (cost * 500.0)))
        return round(score, 2), {
            "method": "cost_usd",
            "cost_usd": cost,
            "score": round(score, 2),
        }

    if harness_evidence.input_tokens is not None or harness_evidence.output_tokens is not None:
        total_tokens = (harness_evidence.input_tokens or 0) + (harness_evidence.output_tokens or 0)
        if total_tokens <= 0:
            return 0.0, {
                "method": "token_count",
                "input_tokens": harness_evidence.input_tokens,
                "output_tokens": harness_evidence.output_tokens,
                "total_tokens": total_tokens,
                "score": 0.0,
                "reason": "zero tokens is not evidence of efficiency",
            }
        # Score based on token count: fewer tokens = more efficient
        score = max(0.0, min(100.0, 100.0 - (total_tokens / 200.0)))
        return round(score, 2), {
            "method": "token_count",
            "input_tokens": harness_evidence.input_tokens,
            "output_tokens": harness_evidence.output_tokens,
            "total_tokens": total_tokens,
            "score": round(score, 2),
        }

    # No evidence available
    return 0.0, {
        "method": "no_token_or_cost_evidence",
        "score": 0.0,
        "tool_count": len(harness_evidence.tool_calls),
    }


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
    measurement: dict[str, object] = field(default_factory=dict)


def score_run(
    task: TaskSpec,
    baseline: Path,
    workspace: Path,
    recorder: JsonlRecorder,
    harness_evidence: HarnessEvidence | None = None,
    test_runner: Callable[[str, list[str], Path, Path, float, JsonlRecorder], dict[str, object]] | None = None,
    environment_evidence: dict[str, object] | None = None,
) -> ScoreResult:
    dimensions: dict[str, float] = {}
    evidence: dict[str, object] = {}

    execute_test = test_runner or _run_test_command
    public_test = execute_test("public", task.test_command, workspace, workspace, task.test_timeout_seconds, recorder)
    hidden_test = execute_test(
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
    if environment_evidence:
        evidence["environment"] = environment_evidence

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

    visual = score_visual_checks(workspace, task.visual_checks, artifacts_dir=workspace.parent / "visual")
    dimensions["visual_verification"] = visual.score
    evidence["visual_verification"] = {"engine": visual.engine, "verified": visual.verified, "checks": visual.checks}
    recorder.event(
        "visual.checked",
        {
            "engine": visual.engine,
            "verified": visual.verified,
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

    # tool_use: scored from parsed harness output (tool call count and variety).
    # Structured harness telemetry (JSON turns / parsed tool events) is strong
    # evidence and is marked verified; keyword-only traces remain heuristic.
    if harness_evidence and harness_evidence.tool_calls:
        tool_types = {t["type"] for t in harness_evidence.tool_calls}
        call_count = len(harness_evidence.tool_calls)
        # Score: 50% for having any tools, 50% for variety (up to 4+ types)
        variety_score = min(len(tool_types) / 4.0, 1.0) * 50.0
        count_score = min(call_count / 5.0, 1.0) * 50.0
        dimensions["tool_use"] = round(variety_score + count_score, 2)
        structured_types = {
            "read",
            "edit",
            "search",
            "bash",
            "interaction",
            "agent_turn",
            "tool",
            "tool_call",
            "toolCall",
            "function_call",
        }
        has_structured = any(
            str(item.get("type", "")) in structured_types or str(item.get("type", "")).startswith("server_")
            for item in harness_evidence.tool_calls
            if isinstance(item, dict)
        )
        evidence["tool_use"] = {
            "tool_types": sorted(tool_types),
            "tool_count": call_count,
            "variety_score": round(variety_score, 2),
            "count_score": round(count_score, 2),
            "source": "structured_harness" if has_structured else "keyword_trace",
            "strength": "verified" if has_structured else "heuristic",
        }
        recorder.event("tool_use.scored", evidence["tool_use"])
    else:
        # Some CLIs (e.g. Grok plain JSON) fix files without exposing tool logs.
        # Real workspace edits are still evidence that the agent used tools.
        edit_score, edit_evidence = _score_tool_use_from_workspace_edits(baseline, workspace)
        if edit_score > 0:
            dimensions["tool_use"] = edit_score
            evidence["tool_use"] = edit_evidence
            recorder.event("tool_use.scored", edit_evidence)

    # self_repair: scored from stdout.log / stderr.log content analysis.
    # Looks for evidence of self-correction (retry language, fix actions,
    # multiple attempts, etc.) in the agent's execution logs.
    self_repair_score, self_repair_evidence = _score_self_repair(workspace)
    dimensions["self_repair"] = self_repair_score
    evidence["self_repair"] = self_repair_evidence
    recorder.event("self_repair.scored", self_repair_evidence)

    # cost_efficiency: scored only from real token/cost data. Tool-call counts
    # are preserved under tool_use evidence and must not masquerade as cost.
    if harness_evidence:
        cost_score, cost_evidence = _score_cost_efficiency(harness_evidence)
        dimensions["cost_efficiency"] = cost_score
        evidence["cost_efficiency"] = cost_evidence
        recorder.event("cost_efficiency.scored", cost_evidence)

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
    measurement = _measurement_summary(task, weights, dimensions, evidence)
    measurement["strict_weighted_score"] = round(total, 2)
    recorder.event(
        "score.computed",
        {"total": total, "dimensions": dimensions, "measurement": measurement},
    )
    return ScoreResult(
        total=round(total, 2),
        dimensions=dimensions,
        evidence=evidence,
        measurement=measurement,
    )


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


def _measurement_summary(
    task: TaskSpec,
    weights: dict[str, float],
    dimensions: dict[str, float],
    evidence: dict[str, object],
) -> dict[str, object]:
    """Separate verified measurement coverage from the strict all-dimension score.

    `total` deliberately keeps unavailable dimensions at zero, so a harness
    cannot obtain a high total through missing telemetry. This companion view
    shows how much of that total is backed by task-specific, executable
    evidence. Heuristic trace interpretation remains visible but is not folded
    into the verified normalized score.
    """
    statuses = {name: "unavailable" for name in weights}

    test_evidence = evidence.get("test")
    if isinstance(test_evidence, dict) and any(
        isinstance(value, dict) and value.get("configured") for value in test_evidence.values()
    ):
        statuses["task_completion"] = "verified"

    if task.protected_paths:
        statuses["safety_boundary"] = "verified"
    visual_evidence = evidence.get("visual_verification")
    if isinstance(visual_evidence, dict) and visual_evidence.get("verified"):
        statuses["visual_verification"] = "verified"

    process_evidence = evidence.get("process")
    if isinstance(process_evidence, dict):
        process_dimensions = process_evidence.get("dimensions")
        if isinstance(process_dimensions, dict):
            for name in process_dimensions:
                if name in statuses:
                    statuses[name] = "verified"

    self_repair_evidence = evidence.get("self_repair")
    if isinstance(self_repair_evidence, dict) and "error" not in self_repair_evidence:
        if statuses.get("self_repair") != "verified":
            statuses["self_repair"] = "heuristic"

    tool_evidence = evidence.get("tool_use")
    if isinstance(tool_evidence, dict) and tool_evidence.get("tool_count") is not None:
        if tool_evidence.get("strength") == "verified" or tool_evidence.get("source") in {
            "structured_harness",
        }:
            statuses["tool_use"] = "verified"
        elif statuses.get("tool_use") != "verified":
            statuses["tool_use"] = "heuristic"

    cost_evidence = evidence.get("cost_efficiency")
    if isinstance(cost_evidence, dict) and cost_evidence.get("method") not in {None, "no_token_or_cost_evidence"}:
        statuses["cost_efficiency"] = "verified"

    verified_dimensions = [name for name, status in statuses.items() if status == "verified"]
    heuristic_dimensions = [name for name, status in statuses.items() if status == "heuristic"]
    # Dimensions with at least some evidence (verified or heuristic). Used at the
    # matrix comparison level to determine which dimensions are fair to compare
    # across different harnesses -- if one harness has telemetry for cost_efficiency
    # but another doesn't, it is excluded from cross-harness comparison.
    dimensions_with_evidence = sorted(
        name for name, status in statuses.items() if status != "unavailable"
    )
    verified_weight = sum(weights[name] for name in verified_dimensions)
    weighted_verified_score = sum(dimensions.get(name, 0.0) * weights[name] for name in verified_dimensions)
    normalized = weighted_verified_score / verified_weight if verified_weight else None
    return {
        "dimension_status": statuses,
        "verified_dimensions": verified_dimensions,
        "heuristic_dimensions": heuristic_dimensions,
        "dimensions_with_evidence": dimensions_with_evidence,
        "weights": weights,
        "verified_weight": round(verified_weight, 2),
        "total_weight": round(sum(weights.values()), 2),
        "verified_coverage_percent": round(100.0 * verified_weight / sum(weights.values()), 2) if weights else 0.0,
        "verified_normalized_score": round(normalized, 2) if normalized is not None else None,
    }


def _comparable_score(
    dimensions: dict[str, float],
    weights: dict[str, float],
    comparable_dimensions: set[str],
) -> float | None:
    """Compute a score using only dimensions shared across all harnesses.

    When comparing harnesses that instrument different dimensions (e.g. one
    reports cost data but not tool calls, another the reverse), the strict
    all-dimension score penalises the harness with fewer evidence sources. This
    helper produces a fairer comparison by limiting the score to dimensions that
    every harness in the comparison has evidence for.

    Returns None if there are no comparable dimensions.
    """
    comp_weights = {k: v for k, v in weights.items() if k in comparable_dimensions}
    if not comp_weights:
        return None
    total_weight = sum(comp_weights.values())
    total = sum(dimensions.get(k, 0.0) * v for k, v in comp_weights.items()) / total_weight
    return round(total, 2)


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
