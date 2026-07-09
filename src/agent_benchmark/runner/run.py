from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import difflib
import fnmatch
import json
import os
from pathlib import Path
import shutil
import statistics
import time
import uuid

from agent_benchmark.adapters import adapter_by_name
from agent_benchmark.adapters.base import AdapterResult
from agent_benchmark.parsers import parse_harness_output
from agent_benchmark.recorders import JsonlRecorder
from agent_benchmark.reports.html import write_html_report
from agent_benchmark.reports.markdown import write_markdown_report
from agent_benchmark.runner.config import ExperimentConfig
from agent_benchmark.scorers import ScoreResult, score_run
from agent_benchmark.task_schema import TaskSpec


@dataclass
class RunResult:
    run_id: str
    task_id: str
    adapter: str
    model: str
    budget_profile: str
    repetition: int
    score: ScoreResult
    adapter_result: AdapterResult
    changed_files: list[str]
    run_dir: str
    duration_seconds: float
    detected_model: str | None = None
    tool_call_count: int = 0


def run_task(task: TaskSpec, config: ExperimentConfig) -> dict[str, object]:
    config.validate()
    adapter = adapter_by_name(config.adapter)
    experiment_id = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    experiment_dir = config.runs_dir / experiment_id
    experiment_dir.mkdir(parents=True, exist_ok=True)

    results: list[RunResult] = []
    for repetition in range(1, config.repetitions + 1):
        run_start = time.monotonic()
        run_id = f"{experiment_id}-r{repetition}"
        run_dir = experiment_dir / f"repetition_{repetition}"
        workspace = run_dir / "workspace"
        baseline = run_dir / "baseline"
        run_dir.mkdir(parents=True, exist_ok=True)

        recorder = JsonlRecorder(run_dir / "trace.jsonl")
        recorder.event(
            "run.started",
            {
                "run_id": run_id,
                "task_id": task.task_id,
                "adapter": config.adapter,
                "model": config.model,
                "budget_profile": config.budget_profile,
                "label": config.label,
                "repetition": repetition,
            },
        )

        _copy_workspace(task.workspace_path, workspace)
        _copy_workspace(task.workspace_path, baseline)
        (run_dir / "instruction.txt").write_text(task.instruction, encoding="utf-8")

        adapter_result = _run_adapter_with_env(adapter, task, workspace, recorder, config)
        (run_dir / "stdout.log").write_text(adapter_result.stdout, encoding="utf-8")
        (run_dir / "stderr.log").write_text(adapter_result.stderr, encoding="utf-8")
        changed_files = _changed_files(baseline, workspace, task)
        diff_text = _unified_diff(baseline, workspace, changed_files)
        (run_dir / "diff.patch").write_text(diff_text, encoding="utf-8")
        recorder.event("workspace.changed", {"changed_files": changed_files})

        harness_evidence = parse_harness_output(config.adapter, adapter_result.stdout, adapter_result.stderr)
        if harness_evidence.tool_calls:
            recorder.event("harness.tools_parsed", {
                "tool_count": len(harness_evidence.tool_calls),
                "tools": [t["type"] for t in harness_evidence.tool_calls],
            })

        score = score_run(task, baseline, workspace, recorder)
        duration_seconds = time.monotonic() - run_start
        result = RunResult(
            run_id=run_id,
            task_id=task.task_id,
            adapter=config.adapter,
            model=config.model,
            budget_profile=config.budget_profile,
            repetition=repetition,
            score=score,
            adapter_result=adapter_result,
            changed_files=changed_files,
            run_dir=str(run_dir),
            duration_seconds=duration_seconds,
            detected_model=harness_evidence.model,
            tool_call_count=len(harness_evidence.tool_calls),
        )
        results.append(result)
        (run_dir / "result.json").write_text(_result_json(result), encoding="utf-8")
        recorder.event("run.finished", {"run_id": run_id, "score": score.total, "duration_seconds": duration_seconds})

    summary = _summarize(results, experiment_id, experiment_dir, task, config)
    (experiment_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    write_markdown_report(experiment_dir / "report.md", summary, results)
    write_html_report(experiment_dir / "report.html", summary)
    return summary


def _copy_workspace(source: Path, target: Path) -> None:
    if not source.exists():
        raise FileNotFoundError(f"Task workspace does not exist: {source}")
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)


def _run_adapter_with_env(adapter: object, task: TaskSpec, workspace: Path, recorder: JsonlRecorder, config: ExperimentConfig) -> AdapterResult:
    injected = {
        "AGENT_BENCH_MODEL": config.model,
        "AGENT_BENCH_BUDGET_PROFILE": config.budget_profile,
        "AGENT_BENCH_LABEL": config.label,
    }
    previous = {key: os.environ.get(key) for key in injected}
    os.environ.update(injected)
    try:
        return adapter.run(task, workspace, recorder)
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _changed_files(before: Path, after: Path, task: TaskSpec) -> list[str]:
    paths = set()
    for root in [before, after]:
        for path in root.rglob("*"):
            if path.is_file():
                relative = str(path.relative_to(root))
                if not _is_ignored_artifact(relative, task):
                    paths.add(relative)
    changed = []
    for rel in sorted(paths):
        before_path = before / rel
        after_path = after / rel
        if not before_path.exists() or not after_path.exists():
            changed.append(rel)
        elif before_path.read_bytes() != after_path.read_bytes():
            changed.append(rel)
    return changed


def _is_ignored_artifact(relative_path: str, task: TaskSpec) -> bool:
    default_globs = [
        "__pycache__/*",
        "*/__pycache__/*",
        "*.pyc",
        "*.pyo",
        ".pytest_cache/*",
        "*/.pytest_cache/*",
    ]
    return any(fnmatch.fnmatch(relative_path, pattern) for pattern in [*default_globs, *task.artifact_ignore_globs])


def _unified_diff(before: Path, after: Path, changed_files: list[str]) -> str:
    chunks: list[str] = []
    for rel in changed_files:
        before_path = before / rel
        after_path = after / rel
        before_lines = _read_text_lines(before_path)
        after_lines = _read_text_lines(after_path)
        chunks.extend(
            difflib.unified_diff(
                before_lines,
                after_lines,
                fromfile=f"baseline/{rel}",
                tofile=f"workspace/{rel}",
                lineterm="",
            )
        )
        chunks.append("")
    return "\n".join(chunks)


def _read_text_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    try:
        return path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        return [f"<binary file: {path.name}>"]


def _result_json(result: RunResult) -> str:
    return json.dumps(asdict(result), indent=2, ensure_ascii=False)


def _summarize(
    results: list[RunResult],
    experiment_id: str,
    experiment_dir: Path,
    task: TaskSpec,
    config: ExperimentConfig,
) -> dict[str, object]:
    scores = [result.score.total for result in results]
    durations = [result.duration_seconds for result in results]
    adapter_durations = [result.adapter_result.duration_seconds for result in results]
    test_durations = [_test_duration(result.score.evidence.get("test")) for result in results]
    detected_models = [r.detected_model for r in results if r.detected_model]
    total_tool_calls = sum(r.tool_call_count for r in results)
    return {
        "experiment_id": experiment_id,
        "task_id": task.task_id,
        "task_title": task.title,
        "adapter": config.adapter,
        "model": config.model,
        "budget_profile": config.budget_profile,
        "label": config.label,
        "experiment_dir": str(experiment_dir),
        "repetitions": len(results),
        "mean_score": round(statistics.mean(scores), 2) if scores else 0.0,
        "variance": round(statistics.pvariance(scores), 4) if len(scores) > 1 else 0.0,
        "stdev": round(statistics.pstdev(scores), 4) if len(scores) > 1 else 0.0,
        "best_score": max(scores) if scores else 0.0,
        "worst_score": min(scores) if scores else 0.0,
        "mean_duration_seconds": round(statistics.mean(durations), 4) if durations else 0.0,
        "mean_adapter_duration_seconds": round(statistics.mean(adapter_durations), 4) if adapter_durations else 0.0,
        "mean_test_duration_seconds": round(statistics.mean(test_durations), 4) if test_durations else 0.0,
        "mean_cost_usd": None,
        "mean_input_tokens": None,
        "mean_output_tokens": None,
        "detected_model": detected_models[0] if detected_models else None,
        "total_tool_calls": total_tool_calls,
        "runs": [
            {
                "run_id": result.run_id,
                "repetition": result.repetition,
                "score": result.score.total,
                "dimensions": result.score.dimensions,
                "changed_files": result.changed_files,
                "duration_seconds": round(result.duration_seconds, 4),
                "adapter_duration_seconds": round(result.adapter_result.duration_seconds, 4),
                "public_test_passed": _test_passed(result.score.evidence.get("test"), "public"),
                "hidden_test_passed": _test_passed(result.score.evidence.get("test"), "hidden"),
                "cost_usd": None,
                "input_tokens": None,
                "output_tokens": None,
                "detected_model": result.detected_model,
                "tool_call_count": result.tool_call_count,
                "run_dir": result.run_dir,
            }
            for result in results
        ],
    }


def _test_duration(test_evidence: object) -> float:
    if not isinstance(test_evidence, dict):
        return 0.0
    total = 0.0
    for value in test_evidence.values():
        if isinstance(value, dict) and value.get("configured"):
            total += float(value.get("duration_seconds", 0.0))
    return total


def _test_passed(test_evidence: object, kind: str) -> bool | None:
    if not isinstance(test_evidence, dict):
        return None
    result = test_evidence.get(kind)
    if not isinstance(result, dict) or not result.get("configured"):
        return None
    return bool(result.get("passed"))
