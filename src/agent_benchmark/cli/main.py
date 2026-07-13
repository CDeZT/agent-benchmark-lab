from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import uuid

from agent_benchmark.adapters import available_adapters
from agent_benchmark.authoritative import preflight_authoritative_corpora
from agent_benchmark.authoritative_pilot import freeze_swebench_pilot, freeze_terminal_bench_pilot, load_authoritative_pilot
from agent_benchmark.audit import AuditOptions, format_audit, run_audit
from agent_benchmark.corpus_audit import audit_corpus
from agent_benchmark.comparability import preflight_matrix
from agent_benchmark.dashboard import write_dashboard
from agent_benchmark.decision_index import build_decision_index
from agent_benchmark.doctor import format_doctor, run_doctor
from agent_benchmark.difficulty import analyze_difficulty
from agent_benchmark.model_registry import adapter_model_for, load_model_registry
from agent_benchmark.next_agent import DEFAULT_PROMPT_PATH, load_next_agent_prompt
from agent_benchmark.reports.matrix import build_matrix_leaderboard, write_matrix_summary
from agent_benchmark.reports.suite import write_suite_summary
from agent_benchmark.runner import ExperimentConfig, ensure_task_environment_supported, run_task
from agent_benchmark.screening import build_screening_report
from agent_benchmark.status import DEFAULT_STATUS_PATH, format_status, load_status
from agent_benchmark.swebench_bridge import SWEbenchBridgeConfig, prepare_swebench_bridge, run_swebench_bridge
from agent_benchmark.terminal_bench_bridge import (
    TerminalBenchBridgeConfig,
    prepare_terminal_bench_bridge,
    run_terminal_bench_bridge,
)
from agent_benchmark.unified_external import (
    external_task_fingerprint,
    is_external_task_id,
    run_external_task_as_summary,
)
from agent_benchmark.task_schema import build_catalog, load_suite, load_task, validate_all
from agent_benchmark.task_fingerprint import task_fingerprint
from agent_benchmark.terminal_ui import SuiteProgress
from agent_benchmark.taxonomy import EVALUATION_AXES, axes_for_task, build_scorecard


DEFAULT_TASKS_DIR = Path("benchmarks/tasks")
DEFAULT_RUNS_DIR = Path("runs")
DEFAULT_SUITES_DIR = Path("benchmarks/suites")
DEFAULT_AUTHORITATIVE_CORPORA_PATH = Path("config/authoritative_corpora.json")
DEFAULT_AUTHORITATIVE_PILOTS_PATH = Path("config/authoritative_pilots.json")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agent-benchmark")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list-tasks", help="List available benchmark tasks.")
    list_parser.add_argument("--tasks-dir", default=str(DEFAULT_TASKS_DIR))

    catalog_parser = subparsers.add_parser("catalog", help="Show task difficulty and provenance coverage.")
    catalog_parser.add_argument("--tasks-dir", default=str(DEFAULT_TASKS_DIR))
    catalog_parser.add_argument("--json", action="store_true", help="Print the machine-readable catalog.")

    difficulty_parser = subparsers.add_parser(
        "calibrate-difficulty",
        help="Assess task discriminability from saved real harness outcomes.",
    )
    difficulty_parser.add_argument("--runs-dir", default=str(DEFAULT_RUNS_DIR))
    difficulty_parser.add_argument("--tasks-dir", default=str(DEFAULT_TASKS_DIR))
    difficulty_parser.add_argument("--include-dummy", action="store_true")
    difficulty_parser.add_argument("--min-combinations", type=int, default=3)
    difficulty_parser.add_argument("--min-runs", type=int, default=9)
    difficulty_parser.add_argument("--min-runs-per-combination", type=int, default=3)
    difficulty_parser.add_argument("--json", action="store_true")

    screening_parser = subparsers.add_parser(
        "screening-report",
        help="Show which tasks are ready for discriminatory screening rather than smoke checks.",
    )
    screening_parser.add_argument("--tasks-dir", default=str(DEFAULT_TASKS_DIR))
    screening_parser.add_argument("--runs-dir", default=str(DEFAULT_RUNS_DIR))
    screening_parser.add_argument("--json", action="store_true")

    taxonomy_parser = subparsers.add_parser("taxonomy", help="Show outcome capability axes and task mappings.")
    taxonomy_parser.add_argument("--tasks-dir", default=str(DEFAULT_TASKS_DIR))
    taxonomy_parser.add_argument("--json", action="store_true")

    corpus_audit_parser = subparsers.add_parser("audit-corpus", help="Audit baseline/reference contrast for benchmark tasks.")
    corpus_audit_parser.add_argument("--tasks-dir", default=str(DEFAULT_TASKS_DIR))
    corpus_audit_parser.add_argument("--json", action="store_true")

    authoritative_parser = subparsers.add_parser(
        "preflight-authoritative",
        help="Check official benchmark evaluator prerequisites without importing any task.",
    )
    authoritative_parser.add_argument("--registry", default=str(DEFAULT_AUTHORITATIVE_CORPORA_PATH))
    authoritative_parser.add_argument("--corpus", help="Optional authoritative corpus id to inspect.")
    authoritative_parser.add_argument("--json", action="store_true")

    freeze_pilot_parser = subparsers.add_parser(
        "freeze-authoritative-pilot",
        help="Freeze selected SWE-bench upstream metadata before any harness evaluation.",
    )
    freeze_pilot_parser.add_argument("--pilot", required=True)
    freeze_pilot_parser.add_argument("--pilots-file", default=str(DEFAULT_AUTHORITATIVE_PILOTS_PATH))
    freeze_pilot_parser.add_argument("--registry", default=str(DEFAULT_AUTHORITATIVE_CORPORA_PATH))
    freeze_pilot_parser.add_argument("--runs-dir", default=str(DEFAULT_RUNS_DIR))
    freeze_pilot_parser.add_argument("--json", action="store_true")

    swebench_bridge_parser = subparsers.add_parser(
        "swebench-bridge",
        help="Prepare or explicitly run one frozen SWE-bench instance through its official evaluator.",
    )
    swebench_bridge_parser.add_argument("--instance-id", required=True, help="One instance selected by the SWE-bench authoritative pilot.")
    swebench_bridge_parser.add_argument("--adapter", required=True, help="Harness adapter that generates the patch.")
    swebench_bridge_parser.add_argument("--model", default="unspecified", help="Canonical model label; unspecified uses the harness default.")
    swebench_bridge_parser.add_argument("--budget-profile", default="open_ended")
    swebench_bridge_parser.add_argument("--evaluator-timeout-seconds", type=int, default=1800)
    swebench_bridge_parser.add_argument(
        "--harness-timeout-seconds",
        type=int,
        default=2400,
        help="Hard timeout for the harness stage (prevents open_ended from hanging forever).",
    )
    swebench_bridge_parser.add_argument("--namespace", default="", help="Official image namespace; empty builds images locally on ARM Macs.")
    swebench_bridge_parser.add_argument("--bridge-dir", help="Resume an existing bridge directory.")
    swebench_bridge_parser.add_argument(
        "--retry-harness",
        action="store_true",
        help="Allow re-running the harness after a previous patch_missing result (default: refuse).",
    )
    swebench_bridge_parser.add_argument("--pilots-file", default=str(DEFAULT_AUTHORITATIVE_PILOTS_PATH))
    swebench_bridge_parser.add_argument("--registry", default=str(DEFAULT_AUTHORITATIVE_CORPORA_PATH))
    swebench_bridge_parser.add_argument("--runs-dir", default=str(DEFAULT_RUNS_DIR))
    swebench_bridge_parser.add_argument("--execute", action="store_true", help="Actually invoke the harness and official Docker evaluator.")
    swebench_bridge_parser.add_argument("--json", action="store_true")

    terminal_bridge_parser = subparsers.add_parser(
        "terminal-bench-bridge",
        help="Prepare or explicitly run one frozen Terminal-Bench task through official tb run.",
    )
    terminal_bridge_parser.add_argument("--instance-id", required=True, help="One task selected by the Terminal-Bench authoritative pilot.")
    terminal_bridge_parser.add_argument("--adapter", required=True, help="Harness adapter mapped to a Terminal-Bench agent (opencode or claude-code).")
    terminal_bridge_parser.add_argument("--model", default="unspecified", help="Optional model override for the Terminal-Bench agent.")
    terminal_bridge_parser.add_argument("--dataset", default="terminal-bench-core==0.1.1")
    terminal_bridge_parser.add_argument("--bridge-dir", help="Resume an existing bridge directory.")
    terminal_bridge_parser.add_argument("--pilots-file", default=str(DEFAULT_AUTHORITATIVE_PILOTS_PATH))
    terminal_bridge_parser.add_argument("--registry", default=str(DEFAULT_AUTHORITATIVE_CORPORA_PATH))
    terminal_bridge_parser.add_argument("--runs-dir", default=str(DEFAULT_RUNS_DIR))
    terminal_bridge_parser.add_argument("--execute", action="store_true", help="Actually invoke official Terminal-Bench Docker evaluation.")
    terminal_bridge_parser.add_argument("--json", action="store_true")

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
    audit_parser.add_argument("--include-real-harness", action="store_true", help="Run real opencode/Claude Code smoke tests.")
    audit_parser.add_argument("--real-harness-adapters", default="opencode,claude-code", help="Comma-separated real harness adapters for audit.")
    audit_parser.add_argument("--real-harness-suite", default="real-smoke", help="Suite id or path for real harness smoke audit.")
    audit_parser.add_argument("--json", action="store_true", help="Print raw JSON audit summary.")

    doctor_parser = subparsers.add_parser("doctor", help="Check local benchmark and harness environment.")
    doctor_parser.add_argument("--json", action="store_true", help="Print raw JSON doctor summary.")

    next_parser = subparsers.add_parser("next-agent-prompt", help="Print the handoff prompt for the next agent.")
    next_parser.add_argument("--prompt-file", default=str(DEFAULT_PROMPT_PATH))

    dashboard_parser = subparsers.add_parser(
        "dashboard",
        help="Build a local historical dashboard from saved runs without inventing scores.",
    )
    dashboard_parser.add_argument("--runs-dir", default=str(DEFAULT_RUNS_DIR))
    dashboard_parser.add_argument("--tasks-dir", default=str(DEFAULT_TASKS_DIR), help="Used to label fingerprint match/mismatch.")
    dashboard_parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_RUNS_DIR / "dashboard"),
        help="Directory for dashboard.json and index.html.",
    )
    dashboard_parser.add_argument("--limit", type=int, default=50, help="Max artifacts per section.")
    dashboard_parser.add_argument("--json", action="store_true", help="Print the dashboard payload JSON.")

    run_parser = subparsers.add_parser("run", help="Run a benchmark task.")
    run_parser.add_argument("--task", required=True, help="Task id or path.")
    run_parser.add_argument("--adapter", default="dummy", help="Harness adapter name.")
    run_parser.add_argument("--model", default="unspecified", help="Canonical model label; omit it to use the CLI default and record any observed identity.")
    run_parser.add_argument("--adapter-model", help="Adapter-specific CLI model identifier; defaults to --model.")
    run_parser.add_argument("--budget-profile", default="open_ended", help="Budget profile label.")
    run_parser.add_argument("--label", default="", help="Optional experiment label.")
    run_parser.add_argument("--repetitions", type=int, default=3)
    run_parser.add_argument("--tasks-dir", default=str(DEFAULT_TASKS_DIR))
    run_parser.add_argument("--runs-dir", default=str(DEFAULT_RUNS_DIR))

    resume_parser = subparsers.add_parser("resume", help="Resume an interrupted task experiment from its checkpoint.")
    resume_parser.add_argument("--experiment-dir", required=True, help="Path to a run directory containing experiment_manifest.json.")

    suite_run_parser = subparsers.add_parser("run-suite", help="Run every task in a benchmark suite.")
    suite_run_parser.add_argument("--suite", required=True, help="Suite id or path.")
    suite_run_parser.add_argument("--adapter", default="dummy", help="Harness adapter name.")
    suite_run_parser.add_argument("--model", default="unspecified", help="Canonical model label; omit it to use the CLI default and record any observed identity.")
    suite_run_parser.add_argument("--adapter-model", help="Adapter-specific CLI model identifier; defaults to --model.")
    suite_run_parser.add_argument("--budget-profile", default="open_ended", help="Budget profile label.")
    suite_run_parser.add_argument("--label", default="", help="Optional experiment label.")
    suite_run_parser.add_argument("--repetitions", type=int, default=3)
    suite_run_parser.add_argument("--tasks-dir", default=str(DEFAULT_TASKS_DIR))
    suite_run_parser.add_argument("--suites-dir", default=str(DEFAULT_SUITES_DIR))
    suite_run_parser.add_argument("--runs-dir", default=str(DEFAULT_RUNS_DIR))
    suite_run_parser.add_argument("--summary", action="store_true", help="Print a compact completion summary instead of the full suite JSON.")
    suite_run_parser.add_argument("--no-progress", action="store_true", help="Disable the live terminal progress display and live_status.json updates.")

    resume_suite_parser = subparsers.add_parser("resume-suite", help="Resume an interrupted suite run from saved task summaries.")
    resume_suite_parser.add_argument("--suite-run-dir", required=True, help="Path containing suite_manifest.json.")
    resume_suite_parser.add_argument("--tasks-dir", default=str(DEFAULT_TASKS_DIR))
    resume_suite_parser.add_argument("--suites-dir", default=str(DEFAULT_SUITES_DIR))
    resume_suite_parser.add_argument("--summary", action="store_true", help="Print a compact completion summary instead of the full suite JSON.")
    resume_suite_parser.add_argument("--no-progress", action="store_true", help="Disable the live terminal progress display and live_status.json updates.")

    matrix_parser = subparsers.add_parser("run-matrix", help="Run a suite across adapter/model/profile combinations.")
    matrix_parser.add_argument("--suite", required=True, help="Suite id or path.")
    matrix_parser.add_argument("--adapters", default="dummy", help="Comma-separated adapter names.")
    matrix_parser.add_argument("--models", default="unspecified", help="Comma-separated canonical model labels; unspecified uses each CLI's current default.")
    matrix_parser.add_argument("--model-registry", help="JSON registry mapping canonical model names to adapter-specific CLI identifiers.")
    matrix_parser.add_argument("--budget-profiles", default="open_ended", help="Comma-separated budget profiles.")
    matrix_parser.add_argument("--label", default="", help="Optional experiment label.")
    matrix_parser.add_argument("--repetitions", type=int, default=3)
    matrix_parser.add_argument("--tasks-dir", default=str(DEFAULT_TASKS_DIR))
    matrix_parser.add_argument("--suites-dir", default=str(DEFAULT_SUITES_DIR))
    matrix_parser.add_argument("--runs-dir", default=str(DEFAULT_RUNS_DIR))
    matrix_parser.add_argument("--no-progress", action="store_true", help="Disable live progress while each suite combination runs.")

    preflight_parser = subparsers.add_parser(
        "preflight-matrix",
        help="Check matrix comparability and environment readiness without invoking a harness.",
    )
    preflight_parser.add_argument("--suite", required=True, help="Suite id or path.")
    preflight_parser.add_argument("--adapters", default="dummy", help="Comma-separated adapter names.")
    preflight_parser.add_argument("--models", default="unspecified", help="Comma-separated canonical model labels; unspecified compares current CLI defaults.")
    preflight_parser.add_argument("--model-registry", help="JSON registry mapping canonical model names to adapter-specific CLI identifiers.")
    preflight_parser.add_argument("--budget-profiles", default="open_ended", help="Comma-separated budget profiles.")
    preflight_parser.add_argument("--repetitions", type=int, default=3)
    preflight_parser.add_argument("--tasks-dir", default=str(DEFAULT_TASKS_DIR))
    preflight_parser.add_argument("--suites-dir", default=str(DEFAULT_SUITES_DIR))
    preflight_parser.add_argument("--json", action="store_true", help="Print the machine-readable preflight report.")

    resume_matrix_parser = subparsers.add_parser("resume-matrix", help="Resume an interrupted matrix run from saved combination checkpoints.")
    resume_matrix_parser.add_argument("--matrix-run-dir", required=True, help="Path containing matrix_manifest.json.")
    resume_matrix_parser.add_argument("--tasks-dir", default=str(DEFAULT_TASKS_DIR))
    resume_matrix_parser.add_argument("--suites-dir", default=str(DEFAULT_SUITES_DIR))
    resume_matrix_parser.add_argument("--no-progress", action="store_true", help="Disable live progress while each suite combination runs.")

    args = parser.parse_args(argv)
    if args.command == "list-tasks":
        return _list_tasks(Path(args.tasks_dir))
    if args.command == "catalog":
        return _catalog(args)
    if args.command == "calibrate-difficulty":
        return _calibrate_difficulty(args)
    if args.command == "screening-report":
        return _screening_report(args)
    if args.command == "taxonomy":
        return _taxonomy(args)
    if args.command == "audit-corpus":
        return _audit_corpus(args)
    if args.command == "preflight-authoritative":
        return _preflight_authoritative(args)
    if args.command == "freeze-authoritative-pilot":
        return _freeze_authoritative_pilot(args)
    if args.command == "swebench-bridge":
        return _swebench_bridge(args)
    if args.command == "terminal-bench-bridge":
        return _terminal_bench_bridge(args)
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
    if args.command == "next-agent-prompt":
        return _next_agent_prompt(args)
    if args.command == "dashboard":
        return _dashboard(args)
    if args.command == "run":
        return _run(args)
    if args.command == "resume":
        return _resume(args)
    if args.command == "run-suite":
        return _run_suite(args)
    if args.command == "resume-suite":
        return _resume_suite(args)
    if args.command == "run-matrix":
        return _run_matrix(args)
    if args.command == "preflight-matrix":
        return _preflight_matrix(args)
    if args.command == "resume-matrix":
        return _resume_matrix(args)
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
        provenance_type = task.provenance.get("type", "unspecified")
        print(
            f"{task.task_id}\t{task.title}\tdifficulty={task.difficulty}\tprovenance={provenance_type}"
            f"\tcapabilities=[{capabilities}]\tdomains=[{domains}]"
        )
    return 0


def _catalog(args: argparse.Namespace) -> int:
    catalog = build_catalog(Path(args.tasks_dir))
    if args.json:
        print(json.dumps(catalog, ensure_ascii=False, indent=2))
        return 0

    distribution = ", ".join(f"{name}={count}" for name, count in catalog["difficulty_distribution"].items())
    provenance = ", ".join(f"{name}={count}" for name, count in catalog["provenance_distribution"].items())
    print(f"Tasks: {catalog['task_count']} ({distribution})")
    print(f"Provenance: {provenance}")
    for task in catalog["tasks"]:
        tests = f"public={'yes' if task['has_public_tests'] else 'no'}, hidden={'yes' if task['has_hidden_tests'] else 'no'}"
        print(
            f"{task['difficulty']}\t{task['id']}\t{task['provenance_type']}\t"
            f"role={task['benchmark_role']}\tenvironment={task['environment']}\t{tests}\t{task['title']}"
        )
    return 0


def _calibrate_difficulty(args: argparse.Namespace) -> int:
    report = analyze_difficulty(
        Path(args.runs_dir),
        include_dummy=args.include_dummy,
        min_combinations=args.min_combinations,
        min_runs=args.min_runs,
        min_runs_per_combination=args.min_runs_per_combination,
        tasks_dir=Path(args.tasks_dir),
    )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    policy = report["policy"]
    print(
        f"Difficulty calibration: {report['task_count']} observed tasks; "
        f"min_combinations={policy['min_combinations']}, min_runs={policy['min_runs']}, "
        f"min_runs_per_combination={policy['min_runs_per_combination']}, include_dummy={policy['dummy_runs_included']}"
    )
    for task in report["tasks"]:
        print(
            f"{task['task_id']}\t{task['classification']}\tcombinations={task['combination_count']}"
            f"\truns={task['run_count']}\trate_range={task['success_rate_range']}"
        )
    return 0


def _screening_report(args: argparse.Namespace) -> int:
    report = build_screening_report(Path(args.tasks_dir), Path(args.runs_dir))
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    summary = report["summary"]
    print(
        "Selection screening report: "
        f"ready={summary['selection_ready_count']}, awaiting={summary['awaiting_real_evidence_count']}, "
        f"warmup={summary['warmup_only_count']}, retune={summary['retune_or_replace_count']}, "
        f"corpus_gate_pending={summary['corpus_gate_pending_count']}, "
        f"official_evaluator_pending={summary['official_evaluator_pending_count']}"
    )
    for task in report["tasks"]:
        calibration = task.get("empirical_calibration")
        empirical = calibration.get("classification") if isinstance(calibration, dict) else "unobserved"
        print(
            f"{task['difficulty']}\t{task['selection_status']}\t{task['id']}\t"
            f"empirical={empirical}\tprovenance={task['provenance_type']}"
        )
    return 0


def _taxonomy(args: argparse.Namespace) -> int:
    tasks = [load_task(path) for path in sorted(Path(args.tasks_dir).iterdir()) if path.is_dir()]
    payload = {
        "axes": {
            axis: {"title": definition["title"], "capabilities": sorted(definition["capabilities"])}
            for axis, definition in EVALUATION_AXES.items()
        },
        "tasks": [{"task_id": task.task_id, "axes": axes_for_task(task.capabilities)} for task in tasks],
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    for task in payload["tasks"]:
        print(f"{task['task_id']}\taxes=[{', '.join(task['axes']) or 'unmapped'}]")
    return 0


def _audit_corpus(args: argparse.Namespace) -> int:
    report = audit_corpus(Path(args.tasks_dir))
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    print(f"Corpus audit: {report['summary']}")
    for task in report["tasks"]:
        print(f"{task['task_id']}\t{task['classification']}")
    return 0


def _preflight_authoritative(args: argparse.Namespace) -> int:
    report = preflight_authoritative_corpora(Path(args.registry), args.corpus)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    docker = report["docker"]
    print(f"Authoritative corpus preflight: Docker ready={docker['ready']} ({docker['detail']})")
    print(f"Execution-ready sources: {report['execution_ready_count']}/{report['source_count']}")
    for source in report["sources"]:
        missing = [requirement["value"] for requirement in source["tool_requirements"] if not requirement["ready"]]
        tools = "ready" if not missing else "missing=" + ",".join(missing)
        print(
            f"{source['id']}\texecution_ready={source['execution_ready']}\t"
            f"imported={source['imported']}\t{tools}"
        )
    return 0


def _freeze_authoritative_pilot(args: argparse.Namespace) -> int:
    pilot_file = Path(args.pilots_file)
    kwargs = (pilot_file, args.pilot, Path(args.registry), Path(args.runs_dir))
    corpus_id = load_authoritative_pilot(pilot_file, args.pilot)["corpus_id"]
    if corpus_id == "swe-bench-verified":
        manifest = freeze_swebench_pilot(*kwargs)
    elif corpus_id == "terminal-bench-core":
        manifest = freeze_terminal_bench_pilot(*kwargs)
    else:
        raise ValueError(f"No freezer is implemented for authoritative corpus '{corpus_id}'.")
    if args.json:
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
    else:
        print(f"Frozen {manifest['instance_count']} upstream instances for {manifest['pilot_id']}")
        print(f"Snapshot SHA-256: {manifest['snapshot_sha256']}")
        print(f"Evidence: {manifest['output_dir']}")
    return 0


def _swebench_bridge(args: argparse.Namespace) -> int:
    config = SWEbenchBridgeConfig(
        pilot_file=Path(args.pilots_file),
        registry_path=Path(args.registry),
        runs_dir=Path(args.runs_dir),
        instance_id=args.instance_id,
        adapter=args.adapter,
        model=args.model,
        budget_profile=args.budget_profile,
        evaluator_timeout_seconds=args.evaluator_timeout_seconds,
        harness_timeout_seconds=args.harness_timeout_seconds,
        namespace=args.namespace,
        bridge_dir=Path(args.bridge_dir) if args.bridge_dir else None,
        retry_harness=bool(getattr(args, "retry_harness", False)),
    )
    result = run_swebench_bridge(config) if args.execute else prepare_swebench_bridge(config)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.execute:
        print(f"SWE-bench bridge status: {result['manifest']['status']}")
        print(f"Evidence: {result['bridge_dir']}")
        print(f"Resolved: {result['official_summary']['resolved']}")
    else:
        print(f"SWE-bench bridge plan: {result['instance_id']} ({result['selection_role']})")
        print("Run again with --execute only when ready to spend harness tokens and build official images.")
    return 0


def _terminal_bench_bridge(args: argparse.Namespace) -> int:
    config = TerminalBenchBridgeConfig(
        pilot_file=Path(args.pilots_file),
        registry_path=Path(args.registry),
        runs_dir=Path(args.runs_dir),
        instance_id=args.instance_id,
        adapter=args.adapter,
        model=args.model,
        dataset=args.dataset,
        bridge_dir=Path(args.bridge_dir) if args.bridge_dir else None,
    )
    result = run_terminal_bench_bridge(config) if args.execute else prepare_terminal_bench_bridge(config)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.execute:
        print(f"Terminal-Bench bridge status: {result['manifest']['status']}")
        print(f"Evidence: {result['bridge_dir']}")
        print(f"Classification: {result['official_summary'].get('classification')}")
        print(f"Resolved: {result['official_summary'].get('resolved')}")
        print("Track: terminal-bench (do not merge with SWE-bench scores).")
    else:
        print(f"Terminal-Bench bridge plan: {result['instance_id']} ({result['selection_role']})")
        print(f"Mapped agent: {result['tb_agent']}")
        print("Run again with --execute only when ready to invoke official Terminal-Bench Docker evaluation.")
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
        include_real_harness=args.include_real_harness,
        real_harness_adapters=_split_csv(args.real_harness_adapters),
        real_harness_suite=args.real_harness_suite,
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


def _next_agent_prompt(args: argparse.Namespace) -> int:
    print(load_next_agent_prompt(Path(args.prompt_file)))
    return 0


def _dashboard(args: argparse.Namespace) -> int:
    tasks_dir = Path(args.tasks_dir)
    payload = write_dashboard(
        Path(args.runs_dir),
        Path(args.output_dir),
        tasks_dir=tasks_dir if tasks_dir.exists() else None,
        limit=max(1, int(args.limit)),
    )
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    counts = payload.get("counts", {})
    output = payload.get("output", {})
    print(
        "Dashboard built: "
        f"matrices={counts.get('matrices', 0)}, suites={counts.get('suites', 0)}, "
        f"tasks={counts.get('tasks', 0)}, swebench_bridges={counts.get('swebench_bridges', 0)}, "
        f"terminal_bench_bridges={counts.get('terminal_bench_bridges', 0)}"
    )
    print(f"HTML: {output.get('html')}")
    print(f"JSON: {output.get('json')}")
    print("Caveat: CLI-default and fingerprint-mismatch rows are provisional historical evidence, not selection-ready rankings.")
    return 0


def _run(args: argparse.Namespace) -> int:
    task_dir = _resolve_task(Path(args.task), Path(args.tasks_dir))
    task = load_task(task_dir)
    config = _config_from_args(args)
    summary = run_task(task, config)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    experiment_dir = summary.get("experiment_dir")
    if experiment_dir:
        report = Path(str(experiment_dir)) / "report.html"
        if report.exists():
            print(f"\nHTML report with radar chart: {report}", file=sys.stderr)
            print("Open with: open " + str(report), file=sys.stderr)
    _emit_dashboard_refresh(config.runs_dir, Path(args.tasks_dir))
    return 0


def _resume(args: argparse.Namespace) -> int:
    experiment_dir = Path(args.experiment_dir)
    manifest_path = experiment_dir / "experiment_manifest.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    task = load_task(Path(data["task_dir"]))
    config = _config_from_saved_data(data["config"], Path(data["runs_dir"]))
    summary = run_task(task, config, resume_experiment_dir=experiment_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    _emit_dashboard_refresh(config.runs_dir, Path(data["task_dir"]).parent)
    return 0


def _run_suite(args: argparse.Namespace) -> int:
    suite_path = _resolve_suite(Path(args.suite), Path(args.suites_dir))
    suite = load_suite(suite_path)
    config = _config_from_args(args)
    suite_summary = _run_suite_with_config(
        suite,
        config,
        Path(args.tasks_dir),
        progress=False if args.no_progress else None,
    )
    _print_suite_result(suite_summary, compact=args.summary)
    _emit_dashboard_refresh(config.runs_dir, Path(args.tasks_dir))
    return 0


def _resume_suite(args: argparse.Namespace) -> int:
    suite_run_dir = Path(args.suite_run_dir)
    manifest_path = suite_run_dir / "suite_manifest.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    suite = load_suite(_resolve_suite(Path(data["suite_id"]), Path(args.suites_dir)))
    config = _config_from_saved_data(data["config"], Path(data["runs_dir"]))
    saved_tasks_dir = Path(data["tasks_dir"])
    tasks_dir = saved_tasks_dir if saved_tasks_dir.is_dir() else Path(args.tasks_dir)
    summary = _run_suite_with_config(
        suite,
        config,
        tasks_dir,
        suite_run_dir=suite_run_dir,
        progress=False if args.no_progress else None,
    )
    _print_suite_result(summary, compact=args.summary)
    _emit_dashboard_refresh(config.runs_dir, tasks_dir)
    return 0


def _run_matrix(args: argparse.Namespace) -> int:
    suite_path = _resolve_suite(Path(args.suite), Path(args.suites_dir))
    suite = load_suite(suite_path)
    combination_specs = _matrix_specs_from_args(args)
    matrix_summary = _run_matrix_with_specs(
        suite,
        combination_specs,
        Path(args.tasks_dir),
        Path(args.runs_dir),
        progress=False if args.no_progress else None,
    )
    print(json.dumps(matrix_summary, ensure_ascii=False, indent=2))
    _emit_dashboard_refresh(Path(args.runs_dir), Path(args.tasks_dir))
    return 0


def _preflight_matrix(args: argparse.Namespace) -> int:
    suite_path = _resolve_suite(Path(args.suite), Path(args.suites_dir))
    suite = load_suite(suite_path)
    try:
        combination_specs = _matrix_specs_from_args(args)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        report = {
            "suite_id": suite.suite_id,
            "combination_count": 0,
            "comparison_mode": "unavailable",
            "execution_ready": False,
            "comparative_ranking_ready": False,
            "identity_configuration_clean": False,
            "same_model_claim_requires_postrun_verification": True,
            "same_model_claim_supported": False,
            "checks": [{"status": "blocked", "code": "model_registry_invalid", "message": str(exc)}],
            "warnings": [],
            "blockers": [{"status": "blocked", "code": "model_registry_invalid", "message": str(exc)}],
            "tasks": [],
            "comparative_task_ids": [],
            "excluded_task_ids": [],
            "model_mappings": [],
        }
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print(f"Matrix preflight: suite={suite.suite_id}")
            print("Execution ready: False")
            print("blocked: " + str(exc))
        return 1
    report = preflight_matrix(
        suite,
        combination_specs,
        Path(args.tasks_dir),
        registry_used=bool(args.model_registry),
    )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Matrix preflight: suite={report['suite_id']} combinations={report['combination_count']}")
        print(f"Execution ready: {report['execution_ready']}")
        print(f"Comparative ranking ready: {report['comparative_ranking_ready']}")
        print(f"Comparison mode: {report['comparison_mode']}")
        print(f"Model mapping configuration clean: {report['identity_configuration_clean']}")
        print("Comparative tasks: " + ", ".join(report["comparative_task_ids"]))
        if report["excluded_task_ids"]:
            print("Excluded tasks: " + ", ".join(report["excluded_task_ids"]))
        for check in report["checks"]:
            if check["status"] != "pass":
                print(f"{check['status']}: {check['message']}")
    return 0 if report["execution_ready"] else 1


def _matrix_specs_from_args(args: argparse.Namespace) -> list[dict[str, object]]:
    adapters = _split_csv(args.adapters)
    models = _split_csv(args.models)
    budget_profiles = _split_csv(args.budget_profiles)
    registry = load_model_registry(Path(args.model_registry)) if args.model_registry else None
    combination_specs = []
    for adapter in adapters:
        for model in models:
            for budget_profile in budget_profiles:
                combination_specs.append(
                    {
                        "adapter": adapter,
                        "model": model,
                        "adapter_model": adapter_model_for(registry, model, adapter) if registry and model != "unspecified" else model,
                        "budget_profile": budget_profile,
                        "label": getattr(args, "label", ""),
                        "repetitions": args.repetitions,
                    }
                )
    return combination_specs


def _resume_matrix(args: argparse.Namespace) -> int:
    matrix_run_dir = Path(args.matrix_run_dir)
    manifest = _load_matrix_manifest(matrix_run_dir)
    suite = load_suite(_resolve_suite(Path(manifest["suite_id"]), Path(args.suites_dir)))
    saved_tasks_dir = Path(manifest["tasks_dir"])
    tasks_dir = saved_tasks_dir if saved_tasks_dir.is_dir() else Path(args.tasks_dir)
    specs = manifest["combination_specs"]
    if not isinstance(specs, list):
        raise ValueError("Matrix manifest combination_specs must be a list.")
    if not all(isinstance(spec, dict) for spec in specs):
        raise ValueError("Matrix manifest contains an invalid combination specification.")
    matrix_summary = _run_matrix_with_specs(
        suite,
        [dict(spec) for spec in specs],
        tasks_dir,
        Path(manifest["runs_dir"]),
        matrix_run_dir=matrix_run_dir,
        progress=False if args.no_progress else None,
    )
    print(json.dumps(matrix_summary, ensure_ascii=False, indent=2))
    _emit_dashboard_refresh(Path(manifest["runs_dir"]), tasks_dir)
    return 0


def _emit_dashboard_refresh(runs_dir: Path, tasks_dir: Path) -> None:
    """Refresh the user-facing historical view after every completed run.

    This is deliberately called only at CLI boundaries, never for each nested
    task inside a suite or matrix, so long experiments do not rebuild the
    dashboard dozens of times.
    """
    output_dir = runs_dir / "dashboard"
    payload = write_dashboard(
        runs_dir,
        output_dir,
        tasks_dir=tasks_dir if tasks_dir.is_dir() else None,
    )
    output = payload.get("output") if isinstance(payload, dict) else {}
    html = output.get("html") if isinstance(output, dict) else None
    if html:
        print(f"\nDashboard refreshed: {html}", file=sys.stderr)


def _run_matrix_with_specs(
    suite: object,
    combination_specs: list[dict[str, object]],
    tasks_dir: Path,
    runs_dir: Path,
    matrix_run_dir: Path | None = None,
    progress: bool | None = False,
) -> dict[str, object]:
    _validate_matrix_specs(combination_specs)
    current_fingerprints = _suite_task_fingerprints(suite, tasks_dir)
    if matrix_run_dir is None:
        matrix_run_id = f"matrix-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
        matrix_run_dir = runs_dir / matrix_run_id
        matrix_run_dir.mkdir(parents=True, exist_ok=True)
        _write_matrix_manifest(matrix_run_dir, matrix_run_id, suite, combination_specs, tasks_dir, runs_dir, "in_progress")
    else:
        manifest = _load_matrix_manifest(matrix_run_dir)
        matrix_run_id = str(manifest["matrix_run_id"])
        if manifest.get("suite_id") != suite.suite_id:
            raise ValueError(f"Resume manifest suite_id does not match '{suite.suite_id}'.")
        if manifest.get("task_ids") != list(suite.tasks):
            raise ValueError("Resume manifest task list does not match the current suite definition.")
        if manifest.get("task_fingerprints") != current_fingerprints:
            raise ValueError("Resume matrix task fingerprints do not match the current task contracts.")
        if manifest.get("combination_specs") != combination_specs:
            raise ValueError("Resume manifest combinations do not match the requested matrix.")

    summaries_dir = matrix_run_dir / "combination_summaries"
    suite_runs_dir = matrix_run_dir / "suite_runs"
    summaries_dir.mkdir(parents=True, exist_ok=True)
    suite_runs_dir.mkdir(parents=True, exist_ok=True)
    combinations: list[dict[str, object]] = []
    for index, spec in enumerate(combination_specs, start=1):
        stem = _matrix_spec_stem(index, spec)
        summary_path = summaries_dir / f"{stem}.json"
        if summary_path.is_file():
            combinations.append(json.loads(summary_path.read_text(encoding="utf-8")))
            continue
        config = ExperimentConfig(
            adapter=str(spec["adapter"]),
            model=str(spec["model"]),
            adapter_model=str(spec.get("adapter_model") or spec["model"]),
            budget_profile=str(spec["budget_profile"]),
            label=str(spec.get("label", "")),
            repetitions=int(spec["repetitions"]),
            runs_dir=runs_dir,
        )
        config.validate()
        suite_summary = _run_suite_with_config(
            suite,
            config,
            tasks_dir,
            suite_run_dir=suite_runs_dir / f"suite-{stem}",
            progress=progress,
        )
        summary_path.write_text(json.dumps(suite_summary, ensure_ascii=False, indent=2), encoding="utf-8")
        combinations.append(suite_summary)
        _write_matrix_checkpoint(matrix_run_dir, combination_specs)

    matrix_summary = {
        "matrix_run_id": matrix_run_id,
        "suite_id": suite.suite_id,
        "combination_count": len(combinations),
        "combinations": combinations,
        "leaderboard": build_matrix_leaderboard(combinations),
        "matrix_run_dir": str(matrix_run_dir),
    }
    write_matrix_summary(matrix_run_dir, matrix_summary)
    _write_matrix_manifest(matrix_run_dir, matrix_run_id, suite, combination_specs, tasks_dir, runs_dir, "complete")
    _write_matrix_checkpoint(matrix_run_dir, combination_specs, complete=True)
    return matrix_summary


def _validate_matrix_specs(specs: list[dict[str, object]]) -> None:
    if not specs:
        raise ValueError("Matrix requires at least one combination.")
    required = {"adapter", "model", "budget_profile", "repetitions"}
    for index, spec in enumerate(specs):
        missing = sorted(required - spec.keys())
        if missing:
            raise ValueError(f"Matrix combination {index} is missing {', '.join(missing)}.")


def _matrix_spec_stem(index: int, spec: dict[str, object]) -> str:
    encoded = json.dumps(spec, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:10]
    return f"{index:03d}-{digest}"


def _write_matrix_manifest(
    matrix_run_dir: Path,
    matrix_run_id: str,
    suite: object,
    combination_specs: list[dict[str, object]],
    tasks_dir: Path,
    runs_dir: Path,
    status: str,
) -> None:
    payload = {
        "matrix_run_id": matrix_run_id,
        "suite_id": suite.suite_id,
        "task_ids": list(suite.tasks),
        "task_fingerprints": _suite_task_fingerprints(suite, tasks_dir),
        "tasks_dir": str(tasks_dir.resolve()),
        "runs_dir": str(runs_dir.resolve()),
        "combination_specs": combination_specs,
        "status": status,
    }
    (matrix_run_dir / "matrix_manifest.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_matrix_manifest(matrix_run_dir: Path) -> dict[str, object]:
    path = matrix_run_dir / "matrix_manifest.json"
    if not path.is_file():
        raise FileNotFoundError(f"Cannot resume matrix: missing matrix manifest at {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid matrix manifest at {path}")
    return payload


def _write_matrix_checkpoint(
    matrix_run_dir: Path,
    combination_specs: list[dict[str, object]],
    complete: bool = False,
) -> None:
    summaries_dir = matrix_run_dir / "combination_summaries"
    completed = [
        _matrix_spec_stem(index, spec)
        for index, spec in enumerate(combination_specs, start=1)
        if (summaries_dir / f"{_matrix_spec_stem(index, spec)}.json").is_file()
    ]
    expected = [_matrix_spec_stem(index, spec) for index, spec in enumerate(combination_specs, start=1)]
    payload = {
        "completed_combinations": completed,
        "remaining_combinations": [stem for stem in expected if stem not in completed],
        "status": "complete" if complete else "in_progress",
    }
    (matrix_run_dir / "checkpoint.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _run_suite_with_config(
    suite: object,
    config: ExperimentConfig,
    tasks_dir: Path,
    suite_run_dir: Path | None = None,
    progress: bool | None = False,
) -> dict[str, object]:
    current_fingerprints = _suite_task_fingerprints(suite, tasks_dir)
    if suite_run_dir is None:
        suite_run_id = f"suite-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
        suite_run_dir = config.runs_dir / suite_run_id
        suite_run_dir.mkdir(parents=True, exist_ok=True)
        _write_suite_manifest(suite_run_dir, suite_run_id, suite, config, tasks_dir, "in_progress")
    elif not (suite_run_dir / "suite_manifest.json").is_file():
        suite_run_id = suite_run_dir.name
        suite_run_dir.mkdir(parents=True, exist_ok=True)
        _write_suite_manifest(suite_run_dir, suite_run_id, suite, config, tasks_dir, "in_progress")
    else:
        manifest = _load_suite_manifest(suite_run_dir)
        suite_run_id = str(manifest["suite_run_id"])
        if manifest.get("suite_id") != suite.suite_id:
            raise ValueError(f"Resume manifest suite_id does not match '{suite.suite_id}'.")
        if manifest.get("task_ids") != list(suite.tasks):
            raise ValueError("Resume manifest task list does not match the current suite definition.")
        if manifest.get("task_fingerprints") != current_fingerprints:
            raise ValueError("Resume suite task fingerprints do not match the current task contracts.")

    summaries = []
    summaries_dir = suite_run_dir / "task_summaries"
    summaries_dir.mkdir(parents=True, exist_ok=True)
    pilots_file = Path(getattr(config, "pilots_file", None) or DEFAULT_AUTHORITATIVE_PILOTS_PATH)
    registry_path = Path(getattr(config, "registry_path", None) or DEFAULT_AUTHORITATIVE_CORPORA_PATH)
    reporter = SuiteProgress(
        suite_run_dir,
        suite_id=suite.suite_id,
        adapter=config.adapter,
        model=config.model,
        budget_profile=config.budget_profile,
        repetitions=config.repetitions,
        task_count=len(suite.tasks),
        enabled=progress,
    ) if progress is not False else None
    if reporter:
        reporter.start()
    try:
        for task_index, task_id in enumerate(suite.tasks, start=1):
            summary_path = summaries_dir / f"{_suite_summary_stem(task_id)}.json"
            external = is_external_task_id(task_id)
            if summary_path.is_file():
                task_summary = json.loads(summary_path.read_text(encoding="utf-8"))
                summaries.append(task_summary)
                if reporter:
                    reporter.recovered_task(_summary_duration(task_summary))
                continue
            if reporter:
                reporter.task_started(task_id, task_index, external=external)
            if external:
                # Authoritative tasks use the same suite loop and summary shape as local tasks.
                task_summary = run_external_task_as_summary(
                    task_id,
                    config,
                    pilots_file=pilots_file,
                    registry_path=registry_path,
                    execute=True,
                )
                if reporter:
                    reporter.complete_external_task(_summary_duration(task_summary))
            else:
                task = load_task(_resolve_task(Path(task_id), tasks_dir))
                ensure_task_environment_supported(task)
                task_summary = run_task(
                    task,
                    config,
                    progress_callback=(
                        lambda event_name, payload, task_id=task_id, task_index=task_index: reporter.event(
                            task_id, task_index, event_name, payload
                        )
                    ) if reporter else None,
                )
            summary_path.write_text(json.dumps(task_summary, ensure_ascii=False, indent=2), encoding="utf-8")
            summaries.append(task_summary)
            _write_suite_checkpoint(suite_run_dir, suite.tasks)
    except KeyboardInterrupt:
        if reporter:
            reporter.finish("interrupted")
        raise
    except BaseException:
        if reporter:
            reporter.finish("failed")
        raise

    official_tasks = [
        item
        for item in summaries
        if isinstance(item.get("task_provenance"), dict)
        and item["task_provenance"].get("type") == "external_official"
    ]
    scored = [item for item in summaries if item not in official_tasks and item.get("include_in_aggregate", True)]
    suite_summary = {
        "suite_run_id": suite_run_id,
        "suite_id": suite.suite_id,
        "adapter": config.adapter,
        "model": config.model,
        "adapter_model": config.invocation_model,
        "budget_profile": config.budget_profile,
        "label": config.label,
        "repetitions_per_task": config.repetitions,
        "task_count": len(summaries),
        "scored_task_count": len(scored),
        "mean_score": round(sum(float(item["mean_score"]) for item in scored) / len(scored), 2) if scored else 0.0,
        "mean_verified_normalized_score": _mean_optional(
            [item.get("mean_verified_normalized_score") for item in scored]
        ),
        "mean_verified_coverage_percent": _mean_optional(
            [item.get("mean_verified_coverage_percent") for item in scored]
        ),
        "mean_duration_seconds": (
            round(sum(float(item["mean_duration_seconds"]) for item in scored) / len(scored), 4) if scored else 0.0
        ),
        "tasks": summaries,
        "scoring_policy": "Local strict scores are aggregated only across local tasks. Official evaluator outcomes are reported as a separate resolution track; unscorable evaluator errors are excluded from that track.",
    }
    suite_summary["official_tracks"] = _official_track_summary(official_tasks)
    suite_summary["decision_index"] = build_decision_index(suite_summary)
    suite_summary["evaluation_axis_scorecard"] = build_scorecard(scored)
    suite_summary["suite_run_dir"] = str(suite_run_dir)
    write_suite_summary(suite_run_dir, suite_summary)
    _write_suite_manifest(suite_run_dir, suite_run_id, suite, config, tasks_dir, "complete")
    _write_suite_checkpoint(suite_run_dir, suite.tasks, complete=True)
    if reporter:
        reporter.finish()
    return suite_summary


def _summary_duration(summary: dict[str, object]) -> float | None:
    value = summary.get("mean_duration_seconds")
    return float(value) * int(summary.get("repetitions") or 1) if isinstance(value, (int, float)) else None


def _print_suite_result(summary: dict[str, object], *, compact: bool) -> None:
    if not compact:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return
    decision = summary.get("decision_index") if isinstance(summary.get("decision_index"), dict) else {}
    official = summary.get("official_tracks") if isinstance(summary.get("official_tracks"), dict) else {}
    print("\nBenchmark complete")
    print(f"  Suite: {summary.get('suite_id')} | Harness: {summary.get('adapter')} | Tasks: {summary.get('task_count')}")
    print(
        "  Local: "
        f"strict={summary.get('mean_score')} | verified={summary.get('mean_verified_normalized_score')} | "
        f"coverage={summary.get('mean_verified_coverage_percent')}%"
    )
    if official.get("task_count"):
        print(
            "  Official SWE: "
            f"resolved={official.get('resolved_attempt_count')}/{official.get('scorable_attempt_count')} | "
            f"rate={official.get('resolution_rate_percent')}%"
        )
    if decision:
        print(f"  Decision index: {decision.get('value')} ({decision.get('status')})")
    print(f"  Reports: {summary.get('suite_run_dir')}")


def _official_track_summary(tasks: list[dict[str, object]]) -> dict[str, object]:
    """Summarize official-resolution evidence without blending it into local scores."""
    if not tasks:
        return {"task_count": 0, "scorable_task_count": 0, "resolved_task_count": 0, "resolution_rate_percent": None}
    ranking = [task for task in tasks if task.get("benchmark_role") == "comparative_candidate"]
    scorable = [task for task in ranking if int(task.get("official_scorable_attempt_count") or 0) > 0]
    resolved = [task for task in scorable if int(task.get("official_resolved_attempt_count") or 0) > 0]
    scorable_attempt_count = sum(int(task.get("official_scorable_attempt_count") or 0) for task in ranking)
    resolved_attempt_count = sum(int(task.get("official_resolved_attempt_count") or 0) for task in ranking)
    diagnostics = [task for task in tasks if task.get("benchmark_role") != "comparative_candidate"]
    outcomes = []
    for task in tasks:
        attempts = int(task.get("official_attempt_count") or task.get("repetitions") or 1)
        scorable_attempts = int(task.get("official_scorable_attempt_count") or (1 if task.get("official_scorable") else 0))
        resolved_attempts = int(task.get("official_resolved_attempt_count") or (1 if task.get("official_resolved") is True else 0))
        outcomes.append(
            {
                "task_id": str(task.get("task_id")),
                "role": str(task.get("benchmark_role")),
                "difficulty": str(task.get("task_difficulty")),
                "attempt_count": attempts,
                "scorable_attempt_count": scorable_attempts,
                "resolved_attempt_count": resolved_attempts,
                "resolution_rate_percent": task.get("official_resolution_rate_percent"),
                "classification": task.get("official_classification"),
                "variance": task.get("variance"),
                "score_confidence_interval_95": task.get("score_confidence_interval_95"),
                "experiment_dir": task.get("experiment_dir"),
            }
        )
    return {
        "task_count": len(tasks),
        "ranking_candidate_task_count": len(ranking),
        "diagnostic_task_count": len(diagnostics),
        "scorable_task_count": len(scorable),
        "resolved_task_count": len(resolved),
        "scorable_attempt_count": scorable_attempt_count,
        "resolved_attempt_count": resolved_attempt_count,
        "resolution_rate_percent": round(100.0 * resolved_attempt_count / scorable_attempt_count, 2)
        if scorable_attempt_count
        else None,
        "unscorable_task_ids": [
            str(task.get("task_id"))
            for task in ranking
            if int(task.get("official_scorable_attempt_count") or 0) == 0
        ],
        "task_outcomes": outcomes,
        "policy": "Official resolution rate is separate from local strict/verified scores. Diagnostic tails do not enter the official ranking rate.",
    }


def _config_from_saved_data(config_data: dict[str, object], runs_dir: Path) -> ExperimentConfig:
    config = ExperimentConfig(
        adapter=str(config_data["adapter"]),
        model=str(config_data["model"]),
        adapter_model=str(config_data.get("adapter_model") or config_data["model"]),
        budget_profile=str(config_data["budget_profile"]),
        label=str(config_data["label"]),
        repetitions=int(config_data["repetitions"]),
        runs_dir=runs_dir,
    )
    config.validate()
    return config


def _write_suite_manifest(
    suite_run_dir: Path,
    suite_run_id: str,
    suite: object,
    config: ExperimentConfig,
    tasks_dir: Path,
    status: str,
) -> None:
    payload = {
        "suite_run_id": suite_run_id,
        "suite_id": suite.suite_id,
        "task_ids": list(suite.tasks),
        "task_fingerprints": _suite_task_fingerprints(suite, tasks_dir),
        "tasks_dir": str(tasks_dir.resolve()),
        "runs_dir": str(config.runs_dir.resolve()),
        "config": {
            "adapter": config.adapter,
            "model": config.model,
            "adapter_model": config.invocation_model,
            "budget_profile": config.budget_profile,
            "label": config.label,
            "repetitions": config.repetitions,
        },
        "status": status,
    }
    (suite_run_dir / "suite_manifest.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_suite_manifest(suite_run_dir: Path) -> dict[str, object]:
    path = suite_run_dir / "suite_manifest.json"
    if not path.is_file():
        raise FileNotFoundError(f"Cannot resume suite: missing suite manifest at {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid suite manifest at {path}")
    return payload


def _suite_task_fingerprints(suite: object, tasks_dir: Path) -> dict[str, str]:
    pilots_file = DEFAULT_AUTHORITATIVE_PILOTS_PATH
    fingerprints: dict[str, str] = {}
    for task_id in list(suite.tasks):
        if is_external_task_id(task_id):
            fingerprints[task_id] = external_task_fingerprint(task_id, pilots_file)
        else:
            fingerprints[task_id] = task_fingerprint(load_task(_resolve_task(Path(task_id), tasks_dir)))
    return fingerprints


def _suite_summary_stem(task_id: str) -> str:
    """Filesystem-safe summary name (external ids contain ':')."""
    return task_id.replace(":", "__").replace("/", "_")


def _write_suite_checkpoint(
    suite_run_dir: Path,
    task_ids: list[str],
    complete: bool = False,
) -> None:
    summaries_dir = suite_run_dir / "task_summaries"
    completed = [
        task_id
        for task_id in task_ids
        if (summaries_dir / f"{_suite_summary_stem(task_id)}.json").is_file()
    ]
    payload = {
        "completed_tasks": completed,
        "remaining_tasks": [task_id for task_id in task_ids if task_id not in completed],
        "status": "complete" if complete else "in_progress",
    }
    (suite_run_dir / "checkpoint.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _mean_optional(values: list[object]) -> float | None:
    numeric = [float(value) for value in values if value is not None]
    return round(sum(numeric) / len(numeric), 2) if numeric else None


def _config_from_args(args: argparse.Namespace) -> ExperimentConfig:
    config = ExperimentConfig(
        adapter=args.adapter,
        model=args.model,
        adapter_model=getattr(args, "adapter_model", None),
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
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("Interrupted. Evidence and checkpoint were preserved for resume.", file=sys.stderr)
        sys.exit(130)
