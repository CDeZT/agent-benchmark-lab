from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import uuid

from agent_benchmark.adapters import available_adapters
from agent_benchmark.audit import AuditOptions, format_audit, run_audit
from agent_benchmark.doctor import format_doctor, run_doctor
from agent_benchmark.reports.matrix import write_matrix_summary
from agent_benchmark.reports.suite import write_suite_summary
from agent_benchmark.runner import ExperimentConfig, run_task
from agent_benchmark.status import DEFAULT_STATUS_PATH, format_status, load_status
from agent_benchmark.task_schema import load_suite, load_task, validate_all


DEFAULT_TASKS_DIR = Path("benchmarks/tasks")
DEFAULT_RUNS_DIR = Path("runs")
DEFAULT_SUITES_DIR = Path("benchmarks/suites")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agent-benchmark")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list-tasks", help="List available benchmark tasks.")
    list_parser.add_argument("--tasks-dir", default=str(DEFAULT_TASKS_DIR))

    suites_parser = subparsers.add_parser("list-suites", help="List available benchmark suites.")
    suites_parser.add_argument("--suites-dir", default=str(DEFAULT_SUITES_DIR))

    subparsers.add_parser("list-adapters", help="List available harness adapters.")

    validate_parser = subparsers.add_parser("validate", help="Validate task and suite definitions.")
    validate_parser.add_argument("--tasks-dir", default=str(DEFAULT_TASKS_DIR))
    validate_parser.add_argument("--suites-dir", default=str(DEFAULT_SUITES_DIR))

    status_parser = subparsers.add_parser("status", help="Show requirement implementation status.")
    status_parser.add_argument("--status-file", default=str(DEFAULT_STATUS_PATH))
    status_parser.add_argument("--json", action="store_true", help="Print raw JSON status.")

    audit_parser = subparsers.add_parser("audit", help="Run project self-checks.")
    audit_parser.add_argument("--tasks-dir", default=str(DEFAULT_TASKS_DIR))
    audit_parser.add_argument("--suites-dir", default=str(DEFAULT_SUITES_DIR))
    audit_parser.add_argument("--runs-dir", default=str(DEFAULT_RUNS_DIR))
    audit_parser.add_argument("--suite", default="foundation")
    audit_parser.add_argument("--skip-unit-tests", action="store_true")
    audit_parser.add_argument("--skip-compile", action="store_true")
    audit_parser.add_argument("--skip-smoke", action="store_true")
    audit_parser.add_argument("--json", action="store_true", help="Print raw JSON audit summary.")

    doctor_parser = subparsers.add_parser("doctor", help="Check local benchmark and harness environment.")
    doctor_parser.add_argument("--json", action="store_true", help="Print raw JSON doctor summary.")

    run_parser = subparsers.add_parser("run", help="Run a benchmark task.")
    run_parser.add_argument("--task", required=True, help="Task id or path.")
    run_parser.add_argument("--adapter", default="dummy", help="Harness adapter name.")
    run_parser.add_argument("--model", default="unspecified", help="Model name to record for this experiment.")
    run_parser.add_argument("--budget-profile", default="open_ended", help="Budget profile label.")
    run_parser.add_argument("--label", default="", help="Optional experiment label.")
    run_parser.add_argument("--repetitions", type=int, default=3)
    run_parser.add_argument("--tasks-dir", default=str(DEFAULT_TASKS_DIR))
    run_parser.add_argument("--runs-dir", default=str(DEFAULT_RUNS_DIR))

    suite_run_parser = subparsers.add_parser("run-suite", help="Run every task in a benchmark suite.")
    suite_run_parser.add_argument("--suite", required=True, help="Suite id or path.")
    suite_run_parser.add_argument("--adapter", default="dummy", help="Harness adapter name.")
    suite_run_parser.add_argument("--model", default="unspecified", help="Model name to record for this suite run.")
    suite_run_parser.add_argument("--budget-profile", default="open_ended", help="Budget profile label.")
    suite_run_parser.add_argument("--label", default="", help="Optional experiment label.")
    suite_run_parser.add_argument("--repetitions", type=int, default=3)
    suite_run_parser.add_argument("--tasks-dir", default=str(DEFAULT_TASKS_DIR))
    suite_run_parser.add_argument("--suites-dir", default=str(DEFAULT_SUITES_DIR))
    suite_run_parser.add_argument("--runs-dir", default=str(DEFAULT_RUNS_DIR))

    matrix_parser = subparsers.add_parser("run-matrix", help="Run a suite across adapter/model/profile combinations.")
    matrix_parser.add_argument("--suite", required=True, help="Suite id or path.")
    matrix_parser.add_argument("--adapters", default="dummy", help="Comma-separated adapter names.")
    matrix_parser.add_argument("--models", default="unspecified", help="Comma-separated model names to record.")
    matrix_parser.add_argument("--budget-profiles", default="open_ended", help="Comma-separated budget profiles.")
    matrix_parser.add_argument("--label", default="", help="Optional experiment label.")
    matrix_parser.add_argument("--repetitions", type=int, default=3)
    matrix_parser.add_argument("--tasks-dir", default=str(DEFAULT_TASKS_DIR))
    matrix_parser.add_argument("--suites-dir", default=str(DEFAULT_SUITES_DIR))
    matrix_parser.add_argument("--runs-dir", default=str(DEFAULT_RUNS_DIR))

    args = parser.parse_args(argv)
    if args.command == "list-tasks":
        return _list_tasks(Path(args.tasks_dir))
    if args.command == "list-suites":
        return _list_suites(Path(args.suites_dir))
    if args.command == "list-adapters":
        return _list_adapters()
    if args.command == "validate":
        return _validate(args)
    if args.command == "status":
        return _status(args)
    if args.command == "audit":
        return _audit(args)
    if args.command == "doctor":
        return _doctor(args)
    if args.command == "run":
        return _run(args)
    if args.command == "run-suite":
        return _run_suite(args)
    if args.command == "run-matrix":
        return _run_matrix(args)
    parser.error("Unknown command")
    return 2


def _list_tasks(tasks_dir: Path) -> int:
    for task_dir in sorted(path for path in tasks_dir.iterdir() if path.is_dir()):
        try:
            task = load_task(task_dir)
        except Exception as exc:  # noqa: BLE001 - CLI should show malformed tasks.
            print(f"{task_dir.name}: invalid ({exc})")
            continue
        capabilities = ", ".join(task.capabilities) or "none"
        domains = ", ".join(task.domains) or "none"
        print(f"{task.task_id}\t{task.title}\tcapabilities=[{capabilities}]\tdomains=[{domains}]")
    return 0


def _list_adapters() -> int:
    for adapter in available_adapters():
        print(adapter)
    return 0


def _list_suites(suites_dir: Path) -> int:
    for suite_path in sorted(suites_dir.glob("*.json")):
        suite = load_suite(suite_path)
        focus = ", ".join(suite.capability_focus) or "none"
        tasks = ", ".join(suite.tasks) or "none"
        print(f"{suite.suite_id}\t{suite.title}\tfocus=[{focus}]\ttasks=[{tasks}]")
    return 0


def _validate(args: argparse.Namespace) -> int:
    result = validate_all(Path(args.tasks_dir), Path(args.suites_dir))
    for warning in result.warnings:
        print(f"warning: {warning}", file=sys.stderr)
    for error in result.errors:
        print(f"error: {error}", file=sys.stderr)
    if result.ok:
        print("validation ok")
        return 0
    return 1


def _status(args: argparse.Namespace) -> int:
    status = load_status(Path(args.status_file))
    if args.json:
        print(json.dumps(status, ensure_ascii=False, indent=2))
    else:
        print(format_status(status))
    return 0


def _audit(args: argparse.Namespace) -> int:
    options = AuditOptions(
        project_root=Path.cwd(),
        tasks_dir=Path(args.tasks_dir),
        suites_dir=Path(args.suites_dir),
        runs_dir=Path(args.runs_dir),
        suite=args.suite,
        include_unit_tests=not args.skip_unit_tests,
        include_compile=not args.skip_compile,
        include_smoke=not args.skip_smoke,
    )
    summary = run_audit(options)
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(format_audit(summary))
    return 0 if summary["passed"] else 1


def _doctor(args: argparse.Namespace) -> int:
    summary = run_doctor()
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(format_doctor(summary))
    return 0 if summary["ok"] else 1


def _run(args: argparse.Namespace) -> int:
    task_dir = _resolve_task(Path(args.task), Path(args.tasks_dir))
    task = load_task(task_dir)
    config = _config_from_args(args)
    summary = run_task(task, config)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def _run_suite(args: argparse.Namespace) -> int:
    suite_path = _resolve_suite(Path(args.suite), Path(args.suites_dir))
    suite = load_suite(suite_path)
    config = _config_from_args(args)
    suite_summary = _run_suite_with_config(suite, config, Path(args.tasks_dir))
    print(json.dumps(suite_summary, ensure_ascii=False, indent=2))
    return 0


def _run_matrix(args: argparse.Namespace) -> int:
    suite_path = _resolve_suite(Path(args.suite), Path(args.suites_dir))
    suite = load_suite(suite_path)
    adapters = _split_csv(args.adapters)
    models = _split_csv(args.models)
    budget_profiles = _split_csv(args.budget_profiles)
    combinations = []
    for adapter in adapters:
        for model in models:
            for budget_profile in budget_profiles:
                config = ExperimentConfig(
                    adapter=adapter,
                    model=model,
                    budget_profile=budget_profile,
                    label=args.label,
                    repetitions=args.repetitions,
                    runs_dir=Path(args.runs_dir),
                )
                config.validate()
                combinations.append(_run_suite_with_config(suite, config, Path(args.tasks_dir)))

    matrix_summary = {
        "matrix_run_id": f"matrix-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}",
        "suite_id": suite.suite_id,
        "combination_count": len(combinations),
        "combinations": combinations,
    }
    matrix_run_dir = Path(args.runs_dir) / matrix_summary["matrix_run_id"]
    matrix_summary["matrix_run_dir"] = str(matrix_run_dir)
    write_matrix_summary(matrix_run_dir, matrix_summary)
    print(json.dumps(matrix_summary, ensure_ascii=False, indent=2))
    return 0


def _run_suite_with_config(suite: object, config: ExperimentConfig, tasks_dir: Path) -> dict[str, object]:
    summaries = []
    for task_id in suite.tasks:
        task_dir = _resolve_task(Path(task_id), tasks_dir)
        task = load_task(task_dir)
        summaries.append(run_task(task, config))
    suite_summary = {
        "suite_run_id": f"suite-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}",
        "suite_id": suite.suite_id,
        "adapter": config.adapter,
        "model": config.model,
        "budget_profile": config.budget_profile,
        "label": config.label,
        "repetitions_per_task": config.repetitions,
        "task_count": len(summaries),
        "mean_score": round(sum(item["mean_score"] for item in summaries) / len(summaries), 2) if summaries else 0.0,
        "mean_duration_seconds": (
            round(sum(item["mean_duration_seconds"] for item in summaries) / len(summaries), 4) if summaries else 0.0
        ),
        "tasks": summaries,
    }
    suite_run_dir = config.runs_dir / suite_summary["suite_run_id"]
    suite_summary["suite_run_dir"] = str(suite_run_dir)
    write_suite_summary(suite_run_dir, suite_summary)
    return suite_summary


def _config_from_args(args: argparse.Namespace) -> ExperimentConfig:
    config = ExperimentConfig(
        adapter=args.adapter,
        model=args.model,
        budget_profile=args.budget_profile,
        label=args.label,
        repetitions=args.repetitions,
        runs_dir=Path(args.runs_dir),
    )
    config.validate()
    return config


def _split_csv(raw: str) -> list[str]:
    values = [item.strip() for item in raw.split(",") if item.strip()]
    if not values:
        raise ValueError("CSV argument must contain at least one value")
    return values


def _resolve_task(task_arg: Path, tasks_dir: Path) -> Path:
    if task_arg.exists():
        return task_arg
    candidate = tasks_dir / str(task_arg)
    if candidate.exists():
        return candidate
    raise FileNotFoundError(f"Could not find task '{task_arg}' in {tasks_dir}")


def _resolve_suite(suite_arg: Path, suites_dir: Path) -> Path:
    if suite_arg.exists():
        return suite_arg
    candidate = suites_dir / str(suite_arg)
    if candidate.exists():
        return candidate
    candidate_json = suites_dir / f"{suite_arg}.json"
    if candidate_json.exists():
        return candidate_json
    raise FileNotFoundError(f"Could not find suite '{suite_arg}' in {suites_dir}")


if __name__ == "__main__":
    sys.exit(main())
