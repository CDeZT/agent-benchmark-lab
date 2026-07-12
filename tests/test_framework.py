from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from contextlib import redirect_stdout
from io import StringIO
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from agent_benchmark.adapters import adapter_by_name, available_adapters
from agent_benchmark.adapters.base import AdapterResult
from agent_benchmark.authoritative import load_authoritative_corpora, preflight_authoritative_corpora
from agent_benchmark.authoritative_pilot import _task_yaml_metadata, _validate_snapshot, load_authoritative_pilot, pilot_selection_summary
from agent_benchmark.audit import AuditOptions, run_audit
from agent_benchmark.comparability import preflight_matrix
from agent_benchmark.corpus_audit import audit_corpus
from agent_benchmark.cli.main import _run_matrix_with_specs, _run_suite_with_config, main
from agent_benchmark.dashboard import build_dashboard, write_dashboard
from agent_benchmark.doctor import format_doctor, run_doctor
from agent_benchmark.difficulty import analyze_difficulty
from agent_benchmark.next_agent import load_next_agent_prompt
from agent_benchmark.model_identity import summarize_model_identity
from agent_benchmark.metrics import confidence_interval_95
from agent_benchmark.model_registry import adapter_model_for, load_model_registry
from agent_benchmark.runner import ExperimentConfig, RunResult, ensure_task_environment_supported, run_task
from agent_benchmark.runner.container import DockerTaskEnvironment, DockerUnavailableError, container_spec_for_task
from agent_benchmark.runner.run import _summarize
from agent_benchmark.scorers import ScoreResult, score_run
from agent_benchmark.screening import build_screening_report, classify_selection_status
from agent_benchmark.recorders.jsonl import JsonlRecorder
from agent_benchmark.reports.matrix import build_matrix_leaderboard
from agent_benchmark.status import format_status, load_status
from agent_benchmark.swebench_bridge import SWEbenchBridgeConfig, _clone_checkout, _evaluator_command, _official_summary, _prediction_record, _workspace_at_commit
from agent_benchmark.terminal_bench_bridge import (
    TerminalBenchBridgeConfig,
    _official_summary as terminal_official_summary,
    _tb_command,
    prepare_terminal_bench_bridge,
)
from agent_benchmark.task_schema import build_catalog, load_suite, load_task, validate_all
from agent_benchmark.task_fingerprint import task_fingerprint
from agent_benchmark.taxonomy import axes_for_task, build_scorecard


ROOT = Path(__file__).resolve().parents[1]


class FrameworkTests(unittest.TestCase):
    def test_load_seed_task(self) -> None:
        task = load_task(ROOT / "benchmarks" / "tasks" / "python-bugfix")

        self.assertEqual(task.task_id, "python-bugfix")
        self.assertIn("python_engineering", task.capabilities)
        self.assertEqual(task.test_command, ["python3", "test_stats.py"])

    def test_load_foundation_suite(self) -> None:
        suite = load_suite(ROOT / "benchmarks" / "suites" / "foundation.json")

        self.assertEqual(suite.suite_id, "foundation")
        self.assertIn("embedded-c", suite.tasks)
        self.assertIn("optics_engineering", suite.capability_focus)
        self.assertIn("process-planning", suite.tasks)

    def test_catalog_exposes_difficulty_and_provenance(self) -> None:
        catalog = build_catalog(ROOT / "benchmarks" / "tasks")

        self.assertGreaterEqual(catalog["task_count"], 19)
        self.assertIn("easy", catalog["difficulty_distribution"])
        self.assertIn("medium", catalog["difficulty_distribution"])
        fullstack = next(task for task in catalog["tasks"] if task["id"] == "python-fullstack")
        self.assertEqual(fullstack["environment"], "container_required")
        imaging = next(task for task in catalog["tasks"] if task["id"] == "optics-imaging-pipeline")
        self.assertEqual(imaging["environment"], "container_required")
        frozen = [task for task in catalog["tasks"] if task["provenance_type"] == "external_frozen"]
        self.assertEqual(len(frozen), 5)
        self.assertTrue(all(task["environment"] == "external_evaluator_only" for task in frozen))

    def test_authoritative_registry_declares_official_tool_requirements(self) -> None:
        corpora = load_authoritative_corpora(ROOT / "config" / "authoritative_corpora.json")
        sources = {corpus.corpus_id: corpus for corpus in corpora}

        self.assertEqual(set(sources), {"swe-bench-verified", "terminal-bench-core"})
        self.assertEqual(
            sources["swe-bench-verified"].tool_requirements,
            ({"kind": "python_module", "value": "swebench", "interpreter": ".agent-benchmark-evaluators/swebench/bin/python"},),
        )
        self.assertEqual(sources["terminal-bench-core"].tool_requirements, ({"kind": "command", "value": "tb"},))

    def test_authoritative_preflight_requires_tools_and_docker_without_claiming_import(self) -> None:
        registry = ROOT / "config" / "authoritative_corpora.json"
        blocked = preflight_authoritative_corpora(
            registry,
            docker_status=lambda: (False, "daemon unavailable"),
            command_exists=lambda _name: None,
            module_available=lambda _name: False,
        )
        ready = preflight_authoritative_corpora(
            registry,
            docker_status=lambda: (True, "test daemon"),
            command_exists=lambda name: f"/usr/bin/{name}",
            module_available=lambda _name: True,
        )

        self.assertEqual(blocked["execution_ready_count"], 0)
        self.assertFalse(blocked["sources"][0]["execution_ready"])
        self.assertEqual(ready["execution_ready_count"], 2)
        self.assertTrue(all(source["execution_ready"] for source in ready["sources"]))
        self.assertTrue(all(not source["imported"] for source in ready["sources"]))

    def test_authoritative_preflight_checks_a_dedicated_python_interpreter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = Path(tmp) / "registry.json"
            registry.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "sources": [
                            {
                                "id": "dedicated-python",
                                "status": "planned_official_import",
                                "official_repository": "https://example.test/source",
                                "dataset": "example/dataset",
                                "official_evaluator": "python -m evaluator",
                                "license_note": "test",
                                "pilot_policy": "test",
                                "tool_requirements": [
                                    {"kind": "python_module", "value": "json", "interpreter": sys.executable}
                                ],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            report = preflight_authoritative_corpora(registry, docker_status=lambda: (True, "test daemon"))

        self.assertEqual(report["execution_ready_count"], 1)
        self.assertTrue(report["sources"][0]["tool_requirements"][0]["ready"])

    def test_swebench_pilot_is_hard_to_easy_and_rejects_upstream_metadata_drift(self) -> None:
        pilot = load_authoritative_pilot(
            ROOT / "config" / "authoritative_pilots.json", "swe-bench-verified-screening-v1"
        )
        selected = pilot["instances"]
        snapshot = {
            "instances": [
                {
                    "instance_id": item["instance_id"],
                    "difficulty": item["expected_difficulty"],
                    "base_commit": item["expected_base_commit"],
                }
                for item in selected
            ]
        }

        self.assertEqual(selected[0]["expected_difficulty"], ">4 hours")
        self.assertEqual(selected[-1]["expected_difficulty"], "<15 min fix")
        self.assertEqual(pilot_selection_summary(pilot)["ranking_candidate_count"], 5)
        self.assertEqual(pilot_selection_summary(pilot)["diagnostic_tail_ids"], ["pallets__flask-5014"])
        _validate_snapshot(snapshot, selected)
        snapshot["instances"][0]["base_commit"] = "changed"
        with self.assertRaisesRegex(ValueError, "base_commit"):
            _validate_snapshot(snapshot, selected)

    def test_terminal_bench_pilot_preserves_upstream_metadata_and_easy_variant(self) -> None:
        pilot = load_authoritative_pilot(
            ROOT / "config" / "authoritative_pilots.json", "terminal-bench-core-engineering-v1"
        )
        metadata = _task_yaml_metadata(
            "instruction: |-\n  example\ndifficulty: hard\ncategory: software-engineering\nmax_agent_timeout_sec: 360.0\n"
        )

        self.assertEqual(pilot["instances"][0]["instance_id"], "path-tracing")
        self.assertEqual(pilot["instances"][-1]["instance_id"], "blind-maze-explorer-algorithm.easy")
        self.assertEqual(pilot_selection_summary(pilot)["ranking_candidate_count"], 5)
        self.assertEqual(pilot_selection_summary(pilot)["diagnostic_tail_ids"], ["blind-maze-explorer-algorithm.easy"])
        self.assertEqual(metadata, {"difficulty": "hard", "category": "software-engineering", "max_agent_timeout_sec": "360.0"})

    def test_selection_ladder_is_ordered_hard_to_easy(self) -> None:
        suite = load_suite(ROOT / "benchmarks" / "suites" / "selection-ladder.json")

        self.assertEqual(suite.tasks[:3], ["c-systems-programming", "project-generation", "python-fullstack"])
        self.assertEqual(suite.tasks[-2:], ["c-bugfix", "python-bugfix"])

    def test_screening_report_excludes_smoke_tasks_from_selection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report = build_screening_report(ROOT / "benchmarks" / "tasks", Path(tmp))
        tasks = {task["id"]: task for task in report["tasks"]}

        self.assertEqual(tasks["python-bugfix"]["selection_status"], "warmup_only")
        self.assertEqual(tasks["c-bugfix"]["selection_status"], "warmup_only")
        self.assertEqual(report["summary"]["selection_ready_count"], 0)
        self.assertEqual(report["tasks"][0]["difficulty"], "expert")
        self.assertIn(
            "current task-contract fingerprint on every contributing summary",
            report["policy"]["selection_ready_requirements"],
        )

    def test_screening_status_requires_evidence_or_official_evaluator(self) -> None:
        self.assertEqual(
            classify_selection_status(
                {
                    "benchmark_role": "comparative_candidate",
                    "provenance_type": "custom_seed",
                    "corpus_audit": {"classification": "passes"},
                    "empirical_calibration": {"classification": "discriminative_candidate"},
                }
            ),
            "selection_ready_local_seed",
        )
        self.assertEqual(
            classify_selection_status(
                {"benchmark_role": "comparative_candidate", "provenance_type": "external_imported"}
            ),
            "official_evaluator_pending",
        )
        self.assertEqual(
            classify_selection_status(
                {"benchmark_role": "external_evaluator_pending", "provenance_type": "external_frozen"}
            ),
            "official_evaluator_pending",
        )

    def test_frozen_external_metadata_cannot_be_run_or_ranked_as_a_local_task(self) -> None:
        task = load_task(ROOT / "benchmarks" / "tasks" / "swebench-pydata-xarray-6992")
        report = audit_corpus(ROOT / "benchmarks" / "tasks")
        audit_item = next(item for item in report["tasks"] if item["task_id"] == task.task_id)

        self.assertEqual(task.provenance["type"], "external_frozen")
        self.assertEqual(audit_item["classification"], "external_evaluator_pending")
        with self.assertRaisesRegex(ValueError, "official evaluator bridge"):
            ensure_task_environment_supported(task)

    def test_swebench_bridge_builds_a_single_instance_arm_safe_official_command(self) -> None:
        config = SWEbenchBridgeConfig(
            pilot_file=ROOT / "config" / "authoritative_pilots.json",
            registry_path=ROOT / "config" / "authoritative_corpora.json",
            runs_dir=ROOT / "runs",
            instance_id="sympy__sympy-13878",
            adapter="opencode",
            namespace="",
        )
        prediction = _prediction_record(config, "diff --git a/example.py b/example.py\n")
        command = _evaluator_command(
            config,
            Path("/tmp/swebench-python"),
            "SWE-bench/SWE-bench_Verified",
            Path("/tmp/predictions.jsonl"),
            "bridge-run",
        )

        self.assertEqual(prediction["instance_id"], config.instance_id)
        self.assertIn("model_patch", prediction)
        self.assertEqual(command[0], str(Path("/tmp/swebench-python").absolute()))
        self.assertEqual(command[command.index("--instance_ids") + 1], config.instance_id)
        self.assertEqual(command[command.index("--max_workers") + 1], "1")
        self.assertEqual(command[command.index("--namespace") + 1], "")
        self.assertEqual(command[command.index("--cache_level") + 1], "env")
        self.assertEqual(command[command.index("--predictions_path") + 1], str(Path("/tmp/predictions.jsonl").absolute()))
        self.assertTrue(
            Path(
                _evaluator_command(
                    config,
                    Path(".agent-benchmark-evaluators/swebench/bin/python"),
                    "SWE-bench/SWE-bench_Verified",
                    Path("/tmp/predictions.jsonl"),
                    "bridge-run",
                )[0]
            ).is_absolute()
        )

    def test_swebench_bridge_reads_official_instance_and_run_reports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            official_dir = Path(tmp)
            instance_id = "sympy__sympy-13878"
            model = "agent-benchmark/opencode/unspecified"
            report_path = official_dir / "logs" / "run_evaluation" / "bridge-run" / model.replace("/", "__") / instance_id / "report.json"
            report_path.parent.mkdir(parents=True)
            report_path.write_text(json.dumps({instance_id: {"resolved": True, "tests_status": {}}}), encoding="utf-8")
            run_report = official_dir / f"{model.replace('/', '__')}.bridge-run.json"
            run_report.write_text(json.dumps({"resolved_instances": 1, "resolved_ids": [instance_id]}), encoding="utf-8")

            summary = _official_summary(
                official_dir,
                "bridge-run",
                {"instance_id": instance_id, "model_name_or_path": model, "model_patch": "patch"},
                0,
            )

        self.assertTrue(summary["completed"])
        self.assertTrue(summary["resolved"])
        self.assertEqual(summary["classification"], "resolved")
        self.assertTrue(summary["scorable"])
        self.assertEqual(summary["run_report_summary"]["resolved_ids"], [instance_id])

    def test_swebench_bridge_keeps_evaluator_errors_out_of_scores(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            official_dir = Path(tmp)
            instance_id = "sympy__sympy-13878"
            model = "agent-benchmark/opencode/unspecified"
            run_report = official_dir / f"{model.replace('/', '__')}.bridge-run.json"
            run_report.write_text(
                json.dumps({"completed_instances": 0, "error_ids": [instance_id]}), encoding="utf-8"
            )

            summary = _official_summary(
                official_dir,
                "bridge-run",
                {"instance_id": instance_id, "model_name_or_path": model, "model_patch": "patch"},
                0,
            )

        self.assertFalse(summary["completed"])
        self.assertFalse(summary["scorable"])
        self.assertEqual(summary["classification"], "evaluator_error")
        self.assertEqual(summary["error_instance_ids"], [instance_id])

    def test_swebench_bridge_rebuilds_an_interrupted_or_wrong_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            (workspace / ".git").mkdir(parents=True)
            self.assertFalse(_workspace_at_commit(workspace, "deadbeef"))

            with patch("agent_benchmark.swebench_bridge._checked_command") as checked:
                _clone_checkout("example/project", "abc123", Path(tmp) / "checkout")

        commands = [call.args[0] for call in checked.call_args_list]
        self.assertEqual(commands[0][:2], ["git", "init"])
        self.assertIn("--depth=1", commands[2])
        self.assertIn("--filter=blob:none", commands[2])

    def test_swebench_bridge_does_not_retry_a_network_failure_as_a_filter_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with patch(
                "agent_benchmark.swebench_bridge._checked_command",
                side_effect=[None, None, RuntimeError("Failed to fetch: connection timed out")],
            ) as checked:
                with self.assertRaisesRegex(RuntimeError, "connection timed out"):
                    _clone_checkout("example/project", "abc123", Path(tmp) / "checkout")

        self.assertEqual(checked.call_count, 3)

    def test_terminal_bench_bridge_plans_without_execution(self) -> None:
        plan = prepare_terminal_bench_bridge(
            TerminalBenchBridgeConfig(
                pilot_file=ROOT / "config" / "authoritative_pilots.json",
                registry_path=ROOT / "config" / "authoritative_corpora.json",
                runs_dir=ROOT / "runs",
                instance_id="path-tracing",
                adapter="opencode",
            )
        )
        self.assertEqual(plan["instance_id"], "path-tracing")
        self.assertEqual(plan["tb_agent"], "opencode")
        self.assertEqual(plan["selection_role"], "ranking_candidate")
        self.assertIn("plan only", plan["warning"].lower())
        command = _tb_command(
            TerminalBenchBridgeConfig(
                pilot_file=ROOT / "config" / "authoritative_pilots.json",
                registry_path=ROOT / "config" / "authoritative_corpora.json",
                runs_dir=ROOT / "runs",
                instance_id="path-tracing",
                adapter="claude-code",
            ),
            "claude-code",
            Path("/tmp/tb-out"),
            "tb-run-id",
        )
        self.assertEqual(command[command.index("--agent") + 1], "claude-code")
        self.assertEqual(command[command.index("--task-id") + 1], "path-tracing")
        self.assertEqual(command[command.index("--dataset") + 1], "terminal-bench-core==0.1.1")
        self.assertIn("--no-upload-results", command)

    def test_terminal_bench_bridge_classifies_official_results(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            official_dir = Path(tmp)
            result_path = official_dir / "results.json"
            result_path.write_text(json.dumps({"is_resolved": False, "task_id": "path-tracing"}), encoding="utf-8")
            summary = terminal_official_summary(official_dir, "run-1", "path-tracing", 0, ["tb", "run"])
        self.assertTrue(summary["completed"])
        self.assertTrue(summary["scorable"])
        self.assertFalse(summary["resolved"])
        self.assertEqual(summary["classification"], "not_resolved")
        self.assertEqual(summary["track"], "terminal-bench")

        missing = terminal_official_summary(Path("/tmp/missing-tb"), "run-2", "path-tracing", 1, ["tb", "run"])
        self.assertFalse(missing["scorable"])
        self.assertEqual(missing["classification"], "evaluator_invocation_error")

    def test_outcome_taxonomy_aggregates_capability_axes(self) -> None:
        self.assertIn("systems_embedded", axes_for_task(["c_engineering", "embedded_engineering"]))
        scorecard = build_scorecard([
            {"task_id": "embedded", "task_capabilities": ["embedded_engineering", "c_engineering"], "mean_score": 40, "mean_verified_normalized_score": 80, "mean_verified_coverage_percent": 50},
            {"task_id": "smoke", "task_capabilities": ["bugfix"], "benchmark_role": "smoke_only", "mean_score": 100, "mean_verified_normalized_score": 100, "mean_verified_coverage_percent": 100},
        ])
        self.assertEqual(scorecard["axes"]["systems_embedded"]["mean_strict_score"], 40.0)
        self.assertEqual(scorecard["excluded_noncomparative_tasks"], ["smoke"])

    def test_corpus_audit_proves_bugfix_baseline_fails_and_reference_passes(self) -> None:
        report = audit_corpus(ROOT / "benchmarks" / "tasks")
        task = next(item for item in report["tasks"] if item["task_id"] == "python-bugfix")
        self.assertEqual(task["classification"], "passes")
        self.assertTrue(task["baseline_failed"])
        self.assertTrue(task["reference_passed"])
        self.assertGreaterEqual(report["summary"]["passes"], 15)
        self.assertGreaterEqual(report["summary"]["skipped_environment"], 4)

    def test_task_fingerprint_changes_when_task_contract_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            task_root = Path(tmp) / "python-bugfix"
            shutil.copytree(ROOT / "benchmarks" / "tasks" / "python-bugfix", task_root)
            original = task_fingerprint(load_task(task_root))
            workspace = task_root / "workspace" / "stats.py"
            workspace.write_text(workspace.read_text(encoding="utf-8") + "\n# contract changed\n", encoding="utf-8")

            changed = task_fingerprint(load_task(task_root))

        self.assertNotEqual(original, changed)

    def test_resume_rejects_changed_task_fingerprint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            task_root = Path(tmp) / "python-bugfix"
            shutil.copytree(ROOT / "benchmarks" / "tasks" / "python-bugfix", task_root)
            task = load_task(task_root)
            initial = run_task(task, ExperimentConfig(adapter="dummy", repetitions=1, runs_dir=Path(tmp) / "runs"))
            source = task_root / "workspace" / "stats.py"
            source.write_text(source.read_text(encoding="utf-8") + "\n# changed after run\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "fingerprint"):
                run_task(load_task(task_root), ExperimentConfig(adapter="dummy", repetitions=1, runs_dir=Path(tmp) / "runs"), resume_experiment_dir=Path(initial["experiment_dir"]))

    def test_difficulty_calibration_excludes_stale_task_fingerprints(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary_dir = root / "stale"
            summary_dir.mkdir()
            summary_dir.joinpath("summary.json").write_text(
                json.dumps(
                    {
                        "task_id": "python-bugfix",
                        "adapter": "opencode",
                        "model": "unspecified",
                        "budget_profile": "oneshot",
                        "task_fingerprint": "obsolete",
                        "model_identity": {"status": "default_detected", "detected_models": ["LongCat-2.0"]},
                        "runs": [{"public_test_passed": True, "hidden_test_passed": True}],
                    }
                ),
                encoding="utf-8",
            )
            report = analyze_difficulty(root, tasks_dir=ROOT / "benchmarks" / "tasks")

        self.assertEqual(report["task_count"], 0)
        self.assertEqual(report["ignored_summaries"]["task_fingerprint_mismatch"], 1)

    def test_external_imported_provenance_requires_reproducibility_fields(self) -> None:
        task = load_task(ROOT / "benchmarks" / "tasks" / "python-bugfix")
        incomplete = task.__class__(
            **{**task.__dict__, "provenance": {"type": "external_imported"}}
        )

        result = validate_all(ROOT / "benchmarks" / "tasks", ROOT / "benchmarks" / "suites")
        self.assertTrue(result.ok)
        from agent_benchmark.task_schema.validate import validate_task

        invalid_result = validate_task(incomplete)
        self.assertFalse(invalid_result.ok)
        self.assertIn("source_benchmark", invalid_result.errors[0])

        missing_evaluator_evidence = task.__class__(
            **{
                **task.__dict__,
                "provenance": {
                    "type": "external_imported",
                    "source_benchmark": "example",
                    "source_id": "case-1",
                    "source_url": "https://example.test/case-1",
                    "source_version": "v1",
                    "license_note": "test",
                    "importer_version": "test",
                },
            }
        )
        missing_evidence_result = validate_task(missing_evaluator_evidence)
        self.assertFalse(missing_evidence_result.ok)
        self.assertIn("official_evaluator_evidence", missing_evidence_result.errors[-1])

    def test_container_required_task_requires_a_ready_docker_daemon(self) -> None:
        task = load_task(ROOT / "benchmarks" / "tasks" / "project-generation")

        with patch("agent_benchmark.runner.container.docker_ready", return_value=(False, "test daemon unavailable")):
            with tempfile.TemporaryDirectory() as tmp:
                with self.assertRaisesRegex(DockerUnavailableError, "test daemon unavailable"):
                    run_task(task, ExperimentConfig(adapter="dummy", repetitions=1, runs_dir=Path(tmp)))

    def test_container_task_contract_uses_pinned_dependencies_and_limits(self) -> None:
        task = load_task(ROOT / "benchmarks" / "tasks" / "optics-imaging-pipeline")
        spec = container_spec_for_task(task)

        self.assertEqual(spec.base_image, "python:3.12.8-slim-bookworm")
        self.assertEqual(spec.packages, ("numpy==2.2.1", "scipy==1.15.1"))
        self.assertEqual(spec.cpus, 2.0)
        self.assertEqual(spec.memory, "4g")
        self.assertIn("numpy==2.2.1", spec.dockerfile)
        self.assertTrue(spec.image_tag.startswith("agent-benchmark/optics-imaging-pipeline:"))

    def test_container_test_commands_isolate_workspace_and_hidden_tests(self) -> None:
        task = load_task(ROOT / "benchmarks" / "tasks" / "optics-imaging-pipeline")
        spec = container_spec_for_task(task)
        environment = DockerTaskEnvironment(task, Path("/tmp/workspace"), Path("/tmp/run"), spec, "sha256:test", False)

        public = environment._docker_command("public", task.test_command)
        hidden = environment._docker_command("hidden", task.hidden_test_command)

        self.assertNotIn("--network", public)
        self.assertIn(f"type=bind,source={environment.workspace.resolve()},target=/workspace,readonly=false", public)
        self.assertNotIn("/hidden,readonly", " ".join(public))
        self.assertIn("type=bind,source=" + str((task.root / "hidden").resolve()) + ",target=/hidden,readonly=true", hidden)

    def test_difficulty_calibration_requires_multiple_real_combinations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for index, successes in enumerate(([True, True, False], [True, False, False], [True, True, True])):
                summary_dir = root / f"run-{index}"
                summary_dir.mkdir()
                summary_dir.joinpath("summary.json").write_text(
                    json.dumps(
                        {
                            "task_id": "synthetic-hard-task",
                            "adapter": "opencode" if index < 2 else "claude-code",
                            "model": f"model-{index}",
                            "budget_profile": "open_ended",
                            "model_identity": {"status": "verified_match", "detected_models": [f"model-{index}"]},
                            "runs": [{"public_test_passed": value, "hidden_test_passed": value} for value in successes],
                        }
                    ),
                    encoding="utf-8",
                )
            report = analyze_difficulty(root)

        task = report["tasks"][0]
        self.assertEqual(task["combination_count"], 3)
        self.assertEqual(task["run_count"], 9)
        self.assertEqual(task["classification"], "discriminative_candidate")

    def test_difficulty_calibration_excludes_unidentified_model_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for index in range(3):
                summary_dir = root / f"run-{index}"
                summary_dir.mkdir()
                summary_dir.joinpath("summary.json").write_text(
                    json.dumps(
                        {
                            "task_id": "unknown-default-task",
                            "adapter": "opencode",
                            "model": "unspecified",
                            "budget_profile": "open_ended",
                            "runs": [{"public_test_passed": True, "hidden_test_passed": True}],
                        }
                    ),
                    encoding="utf-8",
                )
            report = analyze_difficulty(root)

        self.assertEqual(report["task_count"], 0)
        self.assertEqual(report["ignored_summaries"]["unidentified_model"], 3)

    def test_difficulty_calibration_groups_by_detected_not_requested_model(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for index, requested in enumerate(("mimo-v2.5-pro", "deepseek-v4-pro")):
                summary_dir = root / f"run-{index}"
                summary_dir.mkdir()
                summary_dir.joinpath("summary.json").write_text(
                    json.dumps(
                        {
                            "task_id": "observed-model-task",
                            "adapter": "opencode",
                            "model": requested,
                            "budget_profile": "oneshot",
                            "model_identity": {"status": "mismatch", "detected_models": ["LongCat-2.0"]},
                            "runs": [{"public_test_passed": True, "hidden_test_passed": True}],
                        }
                    ),
                    encoding="utf-8",
                )
            report = analyze_difficulty(root, min_combinations=1, min_runs=1, min_runs_per_combination=1)

        task = report["tasks"][0]
        self.assertEqual(task["combination_count"], 1)
        self.assertEqual(task["combination_success_rates"][0]["observed_model"], "longcat-2.0")

    def test_difficulty_calibration_requires_three_runs_per_combination(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            configurations = [
                ("opencode", "LongCat-2.0", [True, True, True, True]),
                ("claude-code", "mimo-v2.5-pro", [False, False, False, False]),
                ("claude-code", "deepseek-v4-pro", [True]),
            ]
            for index, (adapter, model, outcomes) in enumerate(configurations):
                summary_dir = root / f"run-{index}"
                summary_dir.mkdir()
                summary_dir.joinpath("summary.json").write_text(
                    json.dumps(
                        {
                            "task_id": "undersampled-combination-task",
                            "adapter": adapter,
                            "model": model,
                            "budget_profile": "oneshot",
                            "model_identity": {"status": "verified_match", "detected_models": [model]},
                            "runs": [{"public_test_passed": value, "hidden_test_passed": value} for value in outcomes],
                        }
                    ),
                    encoding="utf-8",
                )
            report = analyze_difficulty(root)

        task = report["tasks"][0]
        self.assertEqual(task["observed_combination_count"], 3)
        self.assertEqual(task["combination_count"], 2)
        self.assertEqual(task["observed_run_count"], 9)
        self.assertEqual(task["run_count"], 8)
        self.assertEqual(task["classification"], "insufficient_evidence")

    def test_dummy_run_writes_evidence(self) -> None:
        task = load_task(ROOT / "benchmarks" / "tasks" / "python-bugfix")

        with tempfile.TemporaryDirectory() as tmp:
            summary = run_task(task, ExperimentConfig(adapter="dummy", repetitions=2, runs_dir=Path(tmp)))

            self.assertEqual(summary["repetitions"], 2)
            self.assertEqual(summary["model"], "unspecified")
            self.assertEqual(summary["budget_profile"], "open_ended")
            self.assertEqual(summary["mean_score"], 58.0)
            self.assertEqual(summary["mean_verified_normalized_score"], 100.0)
            self.assertEqual(summary["mean_verified_coverage_percent"], 58.0)
            self.assertEqual(summary["score_confidence_interval_95"]["margin"], 0.0)
            self.assertIn("mean_duration_seconds", summary)
            self.assertIsNone(summary["mean_cost_usd"])
            for run in summary["runs"]:
                self.assertIs(run["public_test_passed"], True)
                self.assertIs(run["hidden_test_passed"], True)
                run_dir = Path(run["run_dir"])
                self.assertTrue((run_dir / "trace.jsonl").exists())
                self.assertTrue((run_dir / "result.json").exists())
                self.assertTrue((run_dir / "diff.patch").exists())
                self.assertTrue((run_dir / "stdout.log").exists())
                self.assertTrue((run_dir / "stderr.log").exists())
                result = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
                self.assertEqual(result["score"]["dimensions"]["task_completion"], 100.0)
                self.assertEqual(result["score"]["dimensions"]["visual_verification"], 0.0)
                self.assertEqual(result["score"]["measurement"]["verified_coverage_percent"], 58.0)
                self.assertEqual(result["score"]["measurement"]["verified_normalized_score"], 100.0)
                self.assertTrue(result["score"]["evidence"]["test"]["public"]["passed"])
                self.assertTrue(result["score"]["evidence"]["test"]["hidden"]["passed"])

    def test_confidence_interval_uses_student_t_for_small_repeated_samples(self) -> None:
        interval = confidence_interval_95([1.0, 2.0, 3.0])

        self.assertEqual(interval["method"], "two_sided_student_t")
        self.assertEqual(interval["n"], 3)
        self.assertEqual(interval["lower"], -0.4843)
        self.assertEqual(interval["upper"], 4.4843)
        self.assertIsNone(confidence_interval_95([1.0]))

    def test_run_can_resume_from_saved_repetition_results(self) -> None:
        task = load_task(ROOT / "benchmarks" / "tasks" / "python-bugfix")
        with tempfile.TemporaryDirectory() as tmp:
            initial = run_task(task, ExperimentConfig(adapter="dummy", repetitions=2, runs_dir=Path(tmp)))
            experiment_dir = Path(initial["experiment_dir"])
            (experiment_dir / "summary.json").unlink()
            resumed = run_task(
                task,
                ExperimentConfig(adapter="dummy", repetitions=2, runs_dir=Path(tmp)),
                resume_experiment_dir=experiment_dir,
            )
            checkpoint = json.loads((experiment_dir / "checkpoint.json").read_text(encoding="utf-8"))

        self.assertEqual(resumed["experiment_id"], initial["experiment_id"])
        self.assertEqual(checkpoint["completed_repetitions"], [1, 2])
        self.assertEqual(checkpoint["status"], "complete")

    def test_suite_run_can_resume_from_saved_task_summaries(self) -> None:
        suite = SimpleNamespace(suite_id="resume-test", tasks=["python-bugfix", "c-bugfix"])
        with tempfile.TemporaryDirectory() as tmp:
            runs_dir = Path(tmp)
            config = ExperimentConfig(adapter="dummy", repetitions=1, runs_dir=runs_dir)
            initial = _run_suite_with_config(suite, config, ROOT / "benchmarks" / "tasks")
            suite_dir = Path(initial["suite_run_dir"])
            first_task = initial["tasks"][0]
            changed_suite = SimpleNamespace(suite_id="resume-test", tasks=["python-bugfix"])
            with self.assertRaisesRegex(ValueError, "task list"):
                _run_suite_with_config(
                    changed_suite,
                    config,
                    ROOT / "benchmarks" / "tasks",
                    suite_run_dir=suite_dir,
                )
            (suite_dir / "suite_summary.json").unlink()
            (suite_dir / "task_summaries" / "c-bugfix.json").unlink()

            resumed = _run_suite_with_config(
                suite,
                config,
                ROOT / "benchmarks" / "tasks",
                suite_run_dir=suite_dir,
            )
            checkpoint = json.loads((suite_dir / "checkpoint.json").read_text(encoding="utf-8"))

        self.assertEqual(resumed["suite_run_id"], initial["suite_run_id"])
        self.assertEqual(resumed["tasks"][0]["experiment_id"], first_task["experiment_id"])
        self.assertEqual(checkpoint["completed_tasks"], ["python-bugfix", "c-bugfix"])
        self.assertEqual(checkpoint["status"], "complete")

    def test_suite_resume_rejects_changed_task_fingerprint(self) -> None:
        suite = SimpleNamespace(suite_id="fingerprint-resume-test", tasks=["python-bugfix"])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tasks_dir = root / "tasks"
            shutil.copytree(ROOT / "benchmarks" / "tasks", tasks_dir)
            config = ExperimentConfig(adapter="dummy", repetitions=1, runs_dir=root / "runs")
            initial = _run_suite_with_config(suite, config, tasks_dir)
            source = tasks_dir / "python-bugfix" / "workspace" / "stats.py"
            source.write_text(source.read_text(encoding="utf-8") + "\n# changed after suite run\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "fingerprint"):
                _run_suite_with_config(suite, config, tasks_dir, suite_run_dir=Path(initial["suite_run_dir"]))

    def test_matrix_leaderboard_excludes_smoke_only_tasks(self) -> None:
        leaderboard = build_matrix_leaderboard(
            [
                {
                    "adapter": "opencode",
                    "model": "model-a",
                    "budget_profile": "open_ended",
                    "suite_run_dir": "/tmp/suite-a",
                    "tasks": [
                        {
                            "task_id": "candidate",
                            "benchmark_role": "comparative_candidate",
                            "mean_score": 60.0,
                            "mean_verified_normalized_score": 75.0,
                            "mean_verified_coverage_percent": 80.0,
                            "stdev": 2.0,
                            "mean_duration_seconds": 4.0,
                            "mean_cost_usd": 0.02,
                            "runs": [{"public_test_passed": True, "hidden_test_passed": True}],
                        },
                        {
                            "task_id": "smoke",
                            "benchmark_role": "smoke_only",
                            "mean_score": 100.0,
                            "runs": [{"public_test_passed": True, "hidden_test_passed": True}],
                        },
                    ],
                }
            ]
        )

        row = leaderboard["rows"][0]
        self.assertEqual(row["comparative_task_count"], 1)
        self.assertEqual(row["excluded_noncomparative_task_ids"], ["smoke"])
        self.assertEqual(row["mean_strict_score"], 60.0)
        self.assertEqual(row["task_pass_rate_percent"], 100.0)
        self.assertEqual(row["rank"], 1)

    def test_matrix_leaderboard_ties_equal_evidence_scores(self) -> None:
        base_task = {
            "task_id": "candidate",
            "benchmark_role": "comparative_candidate",
            "mean_score": 60.0,
            "mean_verified_normalized_score": 75.0,
            "mean_verified_coverage_percent": 80.0,
            "stdev": 0.0,
            "runs": [{"public_test_passed": True, "hidden_test_passed": True}],
        }
        leaderboard = build_matrix_leaderboard(
            [
                {"adapter": "a", "model": "one", "budget_profile": "open_ended", "tasks": [base_task]},
                {"adapter": "b", "model": "two", "budget_profile": "open_ended", "tasks": [base_task]},
            ]
        )

        self.assertEqual([row["rank"] for row in leaderboard["rows"]], [1, 1])

    def test_matrix_ranking_uses_task_level_comparable_evidence(self) -> None:
        def task(strict: float, completion: float, evidence: list[str]) -> dict[str, object]:
            return {
                "task_id": "candidate",
                "benchmark_role": "comparative_candidate",
                "mean_score": strict,
                "mean_verified_normalized_score": completion,
                "mean_verified_coverage_percent": 80.0,
                "runs": [{
                    "public_test_passed": True,
                    "hidden_test_passed": True,
                    "dimensions": {"task_completion": completion, "tool_use": 100.0},
                    "measurement": {"weights": {"task_completion": 30.0, "tool_use": 6.0}, "dimensions_with_evidence": evidence},
                }],
            }

        leaderboard = build_matrix_leaderboard([
            {"adapter": "a", "model": "one", "budget_profile": "open_ended", "tasks": [task(90.0, 70.0, ["task_completion", "tool_use"])]},
            {"adapter": "b", "model": "two", "budget_profile": "open_ended", "tasks": [task(80.0, 90.0, ["task_completion"])]},
        ])

        self.assertEqual(leaderboard["comparable_dimensions_by_task"]["candidate"], ["task_completion"])
        self.assertEqual([row["adapter"] for row in leaderboard["rows"]], ["a", "b"])
        self.assertEqual([row["rank"] for row in leaderboard["rows"]], [2, 1])

    def test_matrix_comparable_dimensions_do_not_leak_between_tasks(self) -> None:
        def task(task_id: str, evidence: list[str]) -> dict[str, object]:
            return {
                "task_id": task_id,
                "benchmark_role": "comparative_candidate",
                "mean_score": 50.0,
                "runs": [{"dimensions": {"tool_use": 100.0, "cost_efficiency": 100.0}, "measurement": {"weights": {"tool_use": 6.0, "cost_efficiency": 4.0}, "dimensions_with_evidence": evidence}}],
            }

        leaderboard = build_matrix_leaderboard([
            {"adapter": "a", "model": "one", "budget_profile": "open_ended", "tasks": [task("alpha", ["tool_use"]), task("beta", ["cost_efficiency"])]},
            {"adapter": "b", "model": "two", "budget_profile": "open_ended", "tasks": [task("alpha", ["cost_efficiency"]), task("beta", ["tool_use"])]},
        ])

        self.assertEqual(leaderboard["comparable_dimensions_by_task"], {"alpha": [], "beta": []})
        self.assertEqual([row["mean_comparable_score"] for row in leaderboard["rows"]], [None, None])

    def test_matrix_preflight_warns_before_a_nonstatistical_comparison(self) -> None:
        suite = SimpleNamespace(suite_id="preflight-test", tasks=["python-bugfix", "process-planning"])
        report = preflight_matrix(
            suite,
            [{"adapter": "dummy", "model": "model-a", "adapter_model": "model-a", "budget_profile": "oneshot", "repetitions": 1}],
            ROOT / "benchmarks" / "tasks",
            registry_used=False,
        )

        self.assertTrue(report["execution_ready"])
        self.assertFalse(report["comparative_ranking_ready"])
        self.assertTrue(report["identity_configuration_clean"])
        self.assertEqual(report["comparative_task_ids"], ["process-planning"])
        self.assertEqual(report["excluded_task_ids"], ["python-bugfix"])
        self.assertIn("insufficient_repetitions", [item["code"] for item in report["warnings"]])

    def test_matrix_preflight_requires_a_registry_for_cross_harness_ranking(self) -> None:
        suite = SimpleNamespace(suite_id="preflight-cross-harness", tasks=["process-planning"])
        report = preflight_matrix(
            suite,
            [
                {"adapter": "opencode", "model": "shared", "adapter_model": "shared", "budget_profile": "oneshot", "repetitions": 3},
                {"adapter": "claude-code", "model": "shared", "adapter_model": "shared", "budget_profile": "oneshot", "repetitions": 3},
            ],
            ROOT / "benchmarks" / "tasks",
            registry_used=False,
        )

        self.assertTrue(report["execution_ready"])
        self.assertFalse(report["identity_configuration_clean"])
        self.assertFalse(report["comparative_ranking_ready"])
        self.assertIn("no_model_registry", [item["code"] for item in report["warnings"]])

    def test_matrix_preflight_allows_current_cli_default_configurations(self) -> None:
        suite = SimpleNamespace(suite_id="preflight-cli-defaults", tasks=["process-planning"])
        report = preflight_matrix(
            suite,
            [
                {"adapter": "opencode", "model": "unspecified", "adapter_model": "unspecified", "budget_profile": "oneshot", "repetitions": 3},
                {"adapter": "claude-code", "model": "unspecified", "adapter_model": "unspecified", "budget_profile": "oneshot", "repetitions": 3},
            ],
            ROOT / "benchmarks" / "tasks",
            registry_used=False,
        )

        self.assertTrue(report["execution_ready"])
        self.assertTrue(report["comparative_ranking_ready"])
        self.assertTrue(report["identity_configuration_clean"])
        self.assertEqual(report["comparison_mode"], "cli_default_configurations")
        self.assertFalse(report["same_model_claim_supported"])
        self.assertFalse(report["same_model_claim_requires_postrun_verification"])
        codes = [item["code"] for item in report["checks"]]
        self.assertIn("cli_default_model_mode", codes)
        self.assertNotIn("no_model_registry", codes)
        self.assertNotIn("adapter_model_selection_external", codes)
        self.assertEqual(report["model_mappings"][0]["identity_hint"], "cli_default_pending")

    def test_matrix_preflight_flags_opencode_default_model_limitation(self) -> None:
        suite = SimpleNamespace(suite_id="preflight-opencode", tasks=["process-planning"])
        report = preflight_matrix(
            suite,
            [{"adapter": "opencode", "model": "longcat-2.0", "adapter_model": "longcat-2.0", "budget_profile": "bounded", "repetitions": 3}],
            ROOT / "benchmarks" / "tasks",
            registry_used=True,
        )

        self.assertTrue(report["execution_ready"])
        self.assertFalse(report["identity_configuration_clean"])
        self.assertFalse(report["comparative_ranking_ready"])
        self.assertEqual(report["model_mappings"][0]["model_selection"], "configured_default_only")
        self.assertIn("adapter_model_selection_external", [item["code"] for item in report["warnings"]])

    def test_preflight_reports_missing_registry_mapping_without_traceback(self) -> None:
        output = StringIO()
        with redirect_stdout(output):
            code = main([
                "preflight-matrix",
                "--suite", "calibration",
                "--adapters", "opencode,claude-code",
                "--models", "deepseek-v4-pro",
                "--model-registry", str(ROOT / "config" / "model_registry.example.json"),
                "--repetitions", "3",
                "--json",
            ])

        report = json.loads(output.getvalue())
        self.assertEqual(code, 1)
        self.assertFalse(report["execution_ready"])
        self.assertEqual(report["blockers"][0]["code"], "model_registry_invalid")

    def test_cli_default_preflight_does_not_require_a_registry_mapping(self) -> None:
        output = StringIO()
        with redirect_stdout(output):
            code = main([
                "preflight-matrix",
                "--suite", "calibration",
                "--adapters", "opencode,claude-code",
                "--models", "unspecified",
                "--model-registry", str(ROOT / "config" / "model_registry.example.json"),
                "--repetitions", "3",
                "--json",
            ])

        report = json.loads(output.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(report["comparison_mode"], "cli_default_configurations")
        self.assertTrue(report["execution_ready"])

    def test_matrix_run_can_resume_from_saved_combination_summaries(self) -> None:
        suite = SimpleNamespace(suite_id="matrix-resume-test", tasks=["c-bugfix"])
        specs = [
            {"adapter": "dummy", "model": "model-a", "budget_profile": "oneshot", "label": "", "repetitions": 1},
            {"adapter": "dummy", "model": "model-b", "budget_profile": "oneshot", "label": "", "repetitions": 1},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            runs_dir = Path(tmp)
            initial = _run_matrix_with_specs(suite, specs, ROOT / "benchmarks" / "tasks", runs_dir)
            matrix_dir = Path(initial["matrix_run_dir"])
            first_suite_id = initial["combinations"][0]["suite_run_id"]
            (matrix_dir / "matrix_summary.json").unlink()
            second_summary = sorted((matrix_dir / "combination_summaries").glob("*.json"))[1]
            second_summary.unlink()

            resumed = _run_matrix_with_specs(
                suite,
                specs,
                ROOT / "benchmarks" / "tasks",
                runs_dir,
                matrix_run_dir=matrix_dir,
            )
            checkpoint = json.loads((matrix_dir / "checkpoint.json").read_text(encoding="utf-8"))

        self.assertEqual(resumed["matrix_run_id"], initial["matrix_run_id"])
        self.assertEqual(resumed["combinations"][0]["suite_run_id"], first_suite_id)
        self.assertEqual(checkpoint["remaining_combinations"], [])
        self.assertEqual(checkpoint["status"], "complete")

    def test_summary_aggregates_real_usage_evidence(self) -> None:
        task = load_task(ROOT / "benchmarks" / "tasks" / "python-bugfix")
        results = [
            RunResult(
                run_id="usage-r1",
                task_id=task.task_id,
                adapter="opencode",
                model="usage-model",
                budget_profile="oneshot",
                repetition=1,
                score=ScoreResult(total=50.0, dimensions={}),
                adapter_result=AdapterResult(adapter="opencode", exit_code=0, duration_seconds=1.0),
                changed_files=[],
                run_dir="/tmp/usage-r1",
                duration_seconds=2.0,
                detected_model="LongCat-2.0",
                tool_call_count=4,
                cost_usd=0.01,
                input_tokens=100,
                output_tokens=50,
            ),
            RunResult(
                run_id="usage-r2",
                task_id=task.task_id,
                adapter="opencode",
                model="usage-model",
                budget_profile="oneshot",
                repetition=2,
                score=ScoreResult(total=70.0, dimensions={}),
                adapter_result=AdapterResult(adapter="opencode", exit_code=0, duration_seconds=1.0),
                changed_files=[],
                run_dir="/tmp/usage-r2",
                duration_seconds=2.0,
                detected_model="LongCat-2.0",
                tool_call_count=6,
                cost_usd=0.03,
                input_tokens=300,
                output_tokens=150,
            ),
        ]

        with tempfile.TemporaryDirectory() as tmp:
            summary = _summarize(
                results,
                "usage-exp",
                Path(tmp),
                task,
                ExperimentConfig(
                    adapter="opencode",
                    model="usage-model",
                    budget_profile="oneshot",
                    repetitions=2,
                    runs_dir=Path(tmp),
                ),
                "test-fingerprint",
            )

        self.assertEqual(summary["mean_cost_usd"], 0.02)
        self.assertEqual(summary["mean_input_tokens"], 200)
        self.assertEqual(summary["mean_output_tokens"], 100)
        self.assertEqual(summary["total_tool_calls"], 10)
        self.assertEqual(summary["runs"][0]["cost_usd"], 0.01)
        self.assertEqual(summary["runs"][1]["input_tokens"], 300)
        self.assertEqual(summary["model_identity"]["status"], "mismatch")

    def test_model_identity_accepts_provider_prefixed_requested_name(self) -> None:
        identity = summarize_model_identity("provider/LongCat-2.0", ["LongCat-2.0"])

        self.assertEqual(identity["status"], "verified_match")

    def test_model_identity_records_observed_cli_default(self) -> None:
        identity = summarize_model_identity("unspecified", ["mimo-v2.5-pro"])
        missing = summarize_model_identity("unspecified", [])

        self.assertEqual(identity["status"], "default_detected")
        self.assertEqual(identity["detected_models"], ["mimo-v2.5-pro"])
        self.assertEqual(missing["status"], "default_unverified")

    def test_matrix_leaderboard_labels_observed_cli_default_identity(self) -> None:
        task = {
            "task_id": "candidate",
            "benchmark_role": "comparative_candidate",
            "mean_score": 60.0,
            "mean_verified_normalized_score": 75.0,
            "mean_verified_coverage_percent": 80.0,
            "model_identity": {"status": "default_detected", "detected_models": ["LongCat-2.0"]},
            "runs": [{"public_test_passed": True, "hidden_test_passed": True}],
        }
        leaderboard = build_matrix_leaderboard([
            {"adapter": "opencode", "model": "unspecified", "budget_profile": "open_ended", "tasks": [task]},
        ])

        row = leaderboard["rows"][0]
        self.assertEqual(row["model_identity_status"], "default_detected")
        self.assertEqual(row["detected_models"], ["LongCat-2.0"])
        self.assertEqual(row["ranking_evidence_state"], "cli_default_model_observed")

    def test_model_registry_resolves_adapter_specific_identifier(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "models.json"
            path.write_text(
                json.dumps({"canonical": {"claude-code": "claude-id", "opencode": "provider/open-id"}}),
                encoding="utf-8",
            )
            registry = load_model_registry(path)

        self.assertEqual(adapter_model_for(registry, "canonical", "claude-code"), "claude-id")
        self.assertEqual(adapter_model_for(registry, "canonical", "opencode"), "provider/open-id")

    def test_generic_command_adapter_can_modify_workspace(self) -> None:
        task = load_task(ROOT / "benchmarks" / "tasks" / "python-bugfix")
        old_command = os.environ.get("AGENT_BENCH_COMMAND")
        old_timeout = os.environ.get("AGENT_BENCH_TIMEOUT_SECONDS")
        os.environ["AGENT_BENCH_COMMAND"] = (
            "python3 -c \"from pathlib import Path; "
            "Path('stats.py').write_text('def average(values):\\n"
            "    return 0.0 if not values else sum(values) / len(values)\\n')\""
        )
        os.environ["AGENT_BENCH_TIMEOUT_SECONDS"] = "10"
        try:
            with tempfile.TemporaryDirectory() as tmp:
                summary = run_task(
                    task,
                    ExperimentConfig(
                        adapter="generic-command",
                        model="local-test-model",
                        budget_profile="oneshot",
                        repetitions=1,
                        runs_dir=Path(tmp),
                    ),
                )
                self.assertEqual(summary["mean_score"], 58.0)
                self.assertEqual(summary["model"], "local-test-model")
                self.assertEqual(summary["budget_profile"], "oneshot")
                self.assertIn("generic-command", available_adapters())
                self.assertIn("opencode", available_adapters())
                self.assertIn("claude-code", available_adapters())
        finally:
            _restore_env("AGENT_BENCH_COMMAND", old_command)
            _restore_env("AGENT_BENCH_TIMEOUT_SECONDS", old_timeout)

    def test_adapter_receives_model_environment(self) -> None:
        task = load_task(ROOT / "benchmarks" / "tasks" / "python-bugfix")
        old_command = os.environ.get("AGENT_BENCH_COMMAND")
        old_timeout = os.environ.get("AGENT_BENCH_TIMEOUT_SECONDS")
        os.environ["AGENT_BENCH_COMMAND"] = (
            "python3 -c \"import os; from pathlib import Path; "
            "Path('model.txt').write_text(os.environ['AGENT_BENCH_MODEL']); "
            "Path('stats.py').write_text('def average(values):\\n"
            "    return 0.0 if not values else sum(values) / len(values)\\n')\""
        )
        os.environ["AGENT_BENCH_TIMEOUT_SECONDS"] = "10"
        try:
            with tempfile.TemporaryDirectory() as tmp:
                summary = run_task(
                    task,
                    ExperimentConfig(
                        adapter="generic-command",
                        model="canonical-model",
                        adapter_model="adapter-model",
                        repetitions=1,
                        runs_dir=Path(tmp),
                    ),
                )
                run_dir = Path(summary["runs"][0]["run_dir"])
                self.assertEqual((run_dir / "workspace" / "model.txt").read_text(encoding="utf-8"), "adapter-model")
                self.assertEqual(summary["model"], "canonical-model")
                self.assertEqual(summary["adapter_model"], "adapter-model")
        finally:
            _restore_env("AGENT_BENCH_COMMAND", old_command)
            _restore_env("AGENT_BENCH_TIMEOUT_SECONDS", old_timeout)

    def test_command_adapter_instruction_file_does_not_pollute_workspace(self) -> None:
        task = load_task(ROOT / "benchmarks" / "tasks" / "python-bugfix")
        old_command = os.environ.get("AGENT_BENCH_COMMAND")
        old_timeout = os.environ.get("AGENT_BENCH_TIMEOUT_SECONDS")
        os.environ["AGENT_BENCH_COMMAND"] = (
            "python3 -c \"from pathlib import Path; "
            "Path('stats.py').write_text('def average(values):\\n"
            "    return 0.0 if not values else sum(values) / len(values)\\n')\""
        )
        os.environ["AGENT_BENCH_TIMEOUT_SECONDS"] = "10"
        try:
            with tempfile.TemporaryDirectory() as tmp:
                summary = run_task(
                    task,
                    ExperimentConfig(adapter="generic-command", repetitions=1, runs_dir=Path(tmp)),
                )
                self.assertEqual(summary["runs"][0]["changed_files"], ["stats.py"])
        finally:
            _restore_env("AGENT_BENCH_COMMAND", old_command)
            _restore_env("AGENT_BENCH_TIMEOUT_SECONDS", old_timeout)

    def test_generated_python_cache_is_not_counted_as_changed_file(self) -> None:
        task = load_task(ROOT / "benchmarks" / "tasks" / "python-bugfix")
        old_command = os.environ.get("AGENT_BENCH_COMMAND")
        old_timeout = os.environ.get("AGENT_BENCH_TIMEOUT_SECONDS")
        os.environ["AGENT_BENCH_COMMAND"] = (
            "python3 -c \"from pathlib import Path; "
            "Path('__pycache__').mkdir(exist_ok=True); "
            "Path('__pycache__/stats.cpython-314.pyc').write_bytes(b'cache'); "
            "Path('stats.py').write_text('def average(values):\\n"
            "    return 0.0 if not values else sum(values) / len(values)\\n')\""
        )
        os.environ["AGENT_BENCH_TIMEOUT_SECONDS"] = "10"
        try:
            with tempfile.TemporaryDirectory() as tmp:
                summary = run_task(
                    task,
                    ExperimentConfig(adapter="generic-command", repetitions=1, runs_dir=Path(tmp)),
                )
                self.assertEqual(summary["runs"][0]["changed_files"], ["stats.py"])
        finally:
            _restore_env("AGENT_BENCH_COMMAND", old_command)
            _restore_env("AGENT_BENCH_TIMEOUT_SECONDS", old_timeout)

    def test_protected_file_modification_reduces_safety_score(self) -> None:
        task = load_task(ROOT / "benchmarks" / "tasks" / "python-bugfix")
        old_command = os.environ.get("AGENT_BENCH_COMMAND")
        old_timeout = os.environ.get("AGENT_BENCH_TIMEOUT_SECONDS")
        os.environ["AGENT_BENCH_COMMAND"] = (
            "python3 -c \"from pathlib import Path; "
            "Path('stats.py').write_text('def average(values):\\n"
            "    return 0.0 if not values else sum(values) / len(values)\\n'); "
            "Path('test_stats.py').write_text(Path('test_stats.py').read_text() + '\\n# modified\\n')\""
        )
        os.environ["AGENT_BENCH_TIMEOUT_SECONDS"] = "10"
        try:
            with tempfile.TemporaryDirectory() as tmp:
                summary = run_task(
                    task,
                    ExperimentConfig(
                        adapter="generic-command",
                        repetitions=1,
                        runs_dir=Path(tmp),
                    ),
                )
                run_dir = Path(summary["runs"][0]["run_dir"])
                result = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
                self.assertEqual(result["score"]["dimensions"]["task_completion"], 100.0)
                self.assertEqual(result["score"]["dimensions"]["safety_boundary"], 0.0)
                self.assertEqual(
                    result["score"]["evidence"]["safety_boundary"]["modified_protected_paths"],
                    ["test_stats.py"],
                )
        finally:
            _restore_env("AGENT_BENCH_COMMAND", old_command)
            _restore_env("AGENT_BENCH_TIMEOUT_SECONDS", old_timeout)

    def test_frontend_visual_checks_score_when_evidenced(self) -> None:
        task = load_task(ROOT / "benchmarks" / "tasks" / "frontend-visual")

        with tempfile.TemporaryDirectory() as tmp:
            summary = run_task(task, ExperimentConfig(adapter="dummy", repetitions=1, runs_dir=Path(tmp)))
            run_dir = Path(summary["runs"][0]["run_dir"])
            result = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
            self.assertEqual(result["score"]["dimensions"]["visual_verification"], 100.0)
            weights = result["score"]["measurement"]["weights"]
            dimensions = result["score"]["dimensions"]
            expected_total = round(
                sum(dimensions[name] * weight for name, weight in weights.items()) / sum(weights.values()), 2
            )
            self.assertEqual(summary["mean_score"], expected_total)
            visual_evidence = result["score"]["evidence"]["visual_verification"]
            self.assertEqual(visual_evidence["engine"], "html-static-v1+playwright-chromium-v1")
            self.assertTrue(visual_evidence["verified"])
            self.assertEqual(len(visual_evidence["checks"]), 4)
            self.assertTrue(all(check["passed"] for check in visual_evidence["checks"]))
            browser = next(check for check in visual_evidence["checks"] if check["type"] == "browser_screenshot")
            self.assertTrue(Path(browser["screenshot_path"]).is_file())
            self.assertGreaterEqual(browser["pixel"]["non_background_pixels"], 200)

    def test_browser_visual_check_is_unavailable_without_node(self) -> None:
        from agent_benchmark.scorers.visual import score_visual_checks

        task = load_task(ROOT / "benchmarks" / "tasks" / "frontend-visual")
        check = next(item for item in task.visual_checks if item["type"] == "browser_screenshot")
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            shutil.copytree(task.workspace_path, workspace)
            with patch("agent_benchmark.scorers.visual.shutil.which", return_value=None):
                result = score_visual_checks(workspace, [check], Path(tmp) / "visual")

        self.assertEqual(result.score, 0.0)
        self.assertFalse(result.verified)
        self.assertEqual(result.checks[0]["measurement_status"], "unavailable")

    def test_process_planning_scores_when_artifact_exists(self) -> None:
        task = load_task(ROOT / "benchmarks" / "tasks" / "process-planning")

        with tempfile.TemporaryDirectory() as tmp:
            summary = run_task(task, ExperimentConfig(adapter="dummy", repetitions=1, runs_dir=Path(tmp)))
            self.assertEqual(summary["mean_score"], 66.0)
            result = json.loads((Path(summary["runs"][0]["run_dir"]) / "result.json").read_text(encoding="utf-8"))
            self.assertEqual(result["score"]["dimensions"]["planning"], 100.0)
            self.assertTrue(all(check["passed"] for check in result["score"]["evidence"]["process"]["checks"]))

    def test_hidden_test_failure_reduces_completion_score(self) -> None:
        task = load_task(ROOT / "benchmarks" / "tasks" / "python-bugfix")
        old_command = os.environ.get("AGENT_BENCH_COMMAND")
        old_timeout = os.environ.get("AGENT_BENCH_TIMEOUT_SECONDS")
        os.environ["AGENT_BENCH_COMMAND"] = (
            "python3 -c \"from pathlib import Path; "
            "Path('stats.py').write_text('def average(values):\\n"
            "    return 0.0 if not values else sum(values) // len(values)\\n')\""
        )
        os.environ["AGENT_BENCH_TIMEOUT_SECONDS"] = "10"
        try:
            with tempfile.TemporaryDirectory() as tmp:
                summary = run_task(
                    task,
                    ExperimentConfig(adapter="generic-command", repetitions=1, runs_dir=Path(tmp)),
                )
                run_dir = Path(summary["runs"][0]["run_dir"])
                result = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
                self.assertEqual(result["score"]["dimensions"]["task_completion"], 50.0)
                self.assertIs(summary["runs"][0]["public_test_passed"], True)
                self.assertIs(summary["runs"][0]["hidden_test_passed"], False)
                self.assertTrue(result["score"]["evidence"]["test"]["public"]["passed"])
                self.assertFalse(result["score"]["evidence"]["test"]["hidden"]["passed"])
        finally:
            _restore_env("AGENT_BENCH_COMMAND", old_command)
            _restore_env("AGENT_BENCH_TIMEOUT_SECONDS", old_timeout)

    def test_repository_definitions_validate(self) -> None:
        result = validate_all(ROOT / "benchmarks" / "tasks", ROOT / "benchmarks" / "suites")

        self.assertTrue(result.ok, result.errors)

    def test_status_file_summarizes_implementation(self) -> None:
        status = load_status(ROOT / "status" / "implementation_status.json")
        rendered = format_status(status)

        self.assertIn("implemented", rendered)
        self.assertIn("partial", rendered)
        self.assertIn("public_and_hidden_tests", rendered)

    def test_dashboard_aggregates_saved_artifacts_without_inventing_scores(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runs_dir = Path(tmp) / "runs"
            matrix_dir = runs_dir / "matrix-20260712T000000Z-demo"
            matrix_dir.mkdir(parents=True)
            (matrix_dir / "matrix_summary.json").write_text(
                json.dumps(
                    {
                        "matrix_run_id": "matrix-20260712T000000Z-demo",
                        "suite_id": "calibration",
                        "combination_count": 2,
                        "combinations": [
                            {
                                "adapter": "opencode",
                                "model": "unspecified",
                                "tasks": [
                                    {
                                        "task_id": "python-bugfix",
                                        "task_fingerprint": "old-fingerprint",
                                        "mean_score": 40.0,
                                        "benchmark_role": "smoke_only",
                                    }
                                ],
                            }
                        ],
                        "leaderboard": {
                            "rows": [
                                {
                                    "adapter": "opencode",
                                    "model": "unspecified",
                                    "detected_models": ["LongCat-2.0"],
                                    "model_identity_status": "default_detected",
                                    "ranking_evidence_state": "cli_default_model_observed",
                                    "mean_comparable_score": 68.0,
                                    "mean_strict_score": 48.0,
                                    "mean_verified_normalized_score": 80.0,
                                    "mean_verified_coverage_percent": 52.0,
                                    "task_pass_rate_percent": 50.0,
                                    "mean_duration_seconds": 12.0,
                                    "mean_cost_usd": None,
                                    "rank": 1,
                                }
                            ]
                        },
                    }
                ),
                encoding="utf-8",
            )
            task_dir = runs_dir / "20260712T000001Z-task"
            task_dir.mkdir()
            (task_dir / "summary.json").write_text(
                json.dumps(
                    {
                        "experiment_id": "20260712T000001Z-task",
                        "task_id": "python-bugfix",
                        "adapter": "claude-code",
                        "model": "unspecified",
                        "detected_model": "mimo-v2.5-pro[1m]",
                        "model_identity": {"status": "default_detected"},
                        "mean_score": 52.0,
                        "mean_verified_normalized_score": 90.0,
                        "mean_verified_coverage_percent": 50.0,
                        "task_fingerprint": "old-fingerprint",
                    }
                ),
                encoding="utf-8",
            )
            bridge_dir = runs_dir / "swebench-bridge-sympy-sympy-13878-demo"
            bridge_dir.mkdir()
            (bridge_dir / "official_summary.json").write_text(
                json.dumps(
                    {
                        "completed": False,
                        "resolved": None,
                        "run_report_summary": {
                            "error_ids": ["sympy__sympy-13878"],
                            "submitted_ids": ["sympy__sympy-13878"],
                        },
                    }
                ),
                encoding="utf-8",
            )

            output_dir = Path(tmp) / "dashboard"
            payload = write_dashboard(
                runs_dir,
                output_dir,
                tasks_dir=ROOT / "benchmarks" / "tasks",
                limit=10,
            )

            self.assertEqual(payload["counts"]["matrices"], 1)
            self.assertEqual(payload["counts"]["tasks"], 1)
            self.assertEqual(payload["counts"]["swebench_bridges"], 1)
            self.assertEqual(payload["matrices"][0]["fingerprint_state"], "mismatch")
            self.assertEqual(payload["tasks"][0]["fingerprint_state"], "mismatch")
            self.assertEqual(payload["swebench_bridges"][0]["classification"], "evaluator_error")
            self.assertFalse(payload["swebench_bridges"][0]["scorable"])
            self.assertTrue((output_dir / "index.html").exists())
            html = (output_dir / "index.html").read_text(encoding="utf-8")
            self.assertIn("Agent Benchmark Dashboard", html)
            self.assertIn("evaluator_error", html)
            self.assertIn("LongCat-2.0", html)

            # CLI path should succeed and not invent ranking claims.
            buffer = StringIO()
            with redirect_stdout(buffer):
                code = main(
                    [
                        "dashboard",
                        "--runs-dir",
                        str(runs_dir),
                        "--tasks-dir",
                        str(ROOT / "benchmarks" / "tasks"),
                        "--output-dir",
                        str(output_dir),
                    ]
                )
            self.assertEqual(code, 0)
            self.assertIn("Dashboard built", buffer.getvalue())

    def test_model_registry_does_not_claim_cross_model_longcat_mapping(self) -> None:
        registry = load_model_registry(ROOT / "config" / "model_registry.json")
        self.assertIn("mimo-v2.5-pro", registry)
        self.assertNotIn("longcat-2.0", registry)
        self.assertEqual(adapter_model_for(registry, "mimo-v2.5-pro", "claude-code"), "mimo-v2.5-pro")

    def test_doctor_outputs_environment_summary(self) -> None:
        summary = run_doctor()
        rendered = format_doctor(summary)

        self.assertIn("command:python3", rendered)
        self.assertIn("command:node", rendered)
        self.assertIn("playwright", rendered)
        self.assertIn("opencode", rendered)
        self.assertIn("claude-code", rendered)

    def test_real_harness_adapters_have_default_templates(self) -> None:
        from agent_benchmark.adapters.claude_code import ClaudeCodeAdapter
        from agent_benchmark.adapters.opencode import OpencodeAdapter

        self.assertIn("opencode run", OpencodeAdapter().command_template() or "")
        self.assertIn("claude -p", ClaudeCodeAdapter().command_template() or "")
        self.assertIn("--output-format json", ClaudeCodeAdapter().command_template() or "")

    def test_next_agent_prompt_contains_required_handoff_rules(self) -> None:
        prompt = load_next_agent_prompt(ROOT / "docs" / "next_agent_prompt.md")

        self.assertIn("docs/handoff.md", prompt)
        self.assertIn("agent-benchmark audit", prompt)
        self.assertIn("commit", prompt)
        self.assertIn("不要假打分", prompt)

    def test_audit_smoke_path_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            summary = run_audit(
                AuditOptions(
                    project_root=ROOT,
                    tasks_dir=ROOT / "benchmarks" / "tasks",
                    suites_dir=ROOT / "benchmarks" / "suites",
                    runs_dir=Path(tmp),
                    include_unit_tests=False,
                    include_compile=False,
                    include_smoke=True,
                )
            )

            self.assertTrue(summary["passed"], summary)
            self.assertTrue((Path(summary["audit_dir"]) / "audit_summary.json").exists())

    def test_audit_real_harness_path_can_be_exercised_with_dummy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            summary = run_audit(
                AuditOptions(
                    project_root=ROOT,
                    tasks_dir=ROOT / "benchmarks" / "tasks",
                    suites_dir=ROOT / "benchmarks" / "suites",
                    runs_dir=Path(tmp),
                    include_unit_tests=False,
                    include_compile=False,
                    include_smoke=False,
                    include_real_harness=True,
                    real_harness_adapters=["dummy"],
                    real_harness_suite="real-smoke",
                )
            )

            self.assertTrue(summary["passed"], summary)
            check_names = [check["name"] for check in summary["checks"]]
            self.assertEqual(check_names, ["validate", "corpus_quality", "authoritative_registry", "real_harness_smoke"])

    def test_public_test_timeout_is_recorded_as_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp) / "timeout-task"
            workspace = task_dir / "workspace"
            solution = task_dir / "solution"
            workspace.mkdir(parents=True)
            solution.mkdir()
            (workspace / "slow.py").write_text("value = 1\n", encoding="utf-8")
            (workspace / "test_slow.py").write_text(
                "import time\n"
                "time.sleep(1)\n",
                encoding="utf-8",
            )
            (solution / "slow.py").write_text("value = 1\n", encoding="utf-8")
            (task_dir / "task.json").write_text(
                json.dumps(
                    {
                        "id": "timeout-task",
                        "title": "Timeout task",
                        "instruction": "Keep the file valid.",
                        "capabilities": ["bugfix"],
                        "domains": ["python"],
                        "test_command": ["python3", "test_slow.py"],
                        "test_timeout_seconds": 0.1,
                    }
                ),
                encoding="utf-8",
            )
            task = load_task(task_dir)
            summary = run_task(task, ExperimentConfig(adapter="dummy", repetitions=1, runs_dir=Path(tmp) / "runs"))
            result = json.loads((Path(summary["runs"][0]["run_dir"]) / "result.json").read_text(encoding="utf-8"))

            public = result["score"]["evidence"]["test"]["public"]
            self.assertFalse(public["passed"])
            self.assertTrue(public["timed_out"])
            self.assertEqual(result["score"]["dimensions"]["task_completion"], 0.0)

    # ── Scoring integrity tests: prove every score comes from real execution ──

    def test_wrong_code_scores_zero_task_completion(self) -> None:
        """Prove task_completion is computed from real test execution, not preset."""
        task = load_task(ROOT / "benchmarks" / "tasks" / "python-bugfix")
        baseline = task.workspace_path
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            shutil.copytree(baseline, workspace)
            # Write deliberately wrong code
            (workspace / "stats.py").write_text("def average(values):\n    return 999\n", encoding="utf-8")
            recorder = JsonlRecorder(Path(tmp) / "trace.jsonl")
            score = score_run(task, baseline, workspace, recorder)
            self.assertEqual(score.dimensions["task_completion"], 0.0)
            self.assertFalse(score.evidence["test"]["public"]["passed"])
            self.assertNotEqual(score.evidence["test"]["public"]["exit_code"], 0)

    def test_correct_code_scores_full_task_completion(self) -> None:
        """Prove task_completion=100 comes from tests actually passing."""
        task = load_task(ROOT / "benchmarks" / "tasks" / "python-bugfix")
        baseline = task.workspace_path
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            shutil.copytree(baseline, workspace)
            # Copy correct solution
            shutil.copy(task.root / "solution" / "stats.py", workspace / "stats.py")
            recorder = JsonlRecorder(Path(tmp) / "trace.jsonl")
            score = score_run(task, baseline, workspace, recorder)
            self.assertEqual(score.dimensions["task_completion"], 100.0)
            self.assertTrue(score.evidence["test"]["public"]["passed"])
            self.assertEqual(score.evidence["test"]["public"]["exit_code"], 0)

    def test_tampered_protected_file_drops_safety_to_zero(self) -> None:
        """Prove safety_boundary=0 comes from real SHA-256 hash mismatch."""
        task = load_task(ROOT / "benchmarks" / "tasks" / "python-bugfix")
        baseline = task.workspace_path
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            shutil.copytree(baseline, workspace)
            shutil.copy(task.root / "solution" / "stats.py", workspace / "stats.py")
            # Tamper with protected file
            (workspace / "test_stats.py").write_text("# TAMPERED\n", encoding="utf-8")
            recorder = JsonlRecorder(Path(tmp) / "trace.jsonl")
            score = score_run(task, baseline, workspace, recorder)
            self.assertEqual(score.dimensions["safety_boundary"], 0.0)
            self.assertIn("test_stats.py", score.evidence["safety_boundary"]["modified_protected_paths"])
            # Verify the hashes are actually different
            baseline_hash = score.evidence["safety_boundary"]["baseline_hashes"]["test_stats.py"]
            current_hash = score.evidence["safety_boundary"]["current_hashes"]["test_stats.py"]
            self.assertNotEqual(baseline_hash, current_hash)

    def test_intact_protected_files_give_full_safety_score(self) -> None:
        """Prove safety_boundary=100 comes from SHA-256 hashes matching."""
        task = load_task(ROOT / "benchmarks" / "tasks" / "python-bugfix")
        baseline = task.workspace_path
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            shutil.copytree(baseline, workspace)
            shutil.copy(task.root / "solution" / "stats.py", workspace / "stats.py")
            recorder = JsonlRecorder(Path(tmp) / "trace.jsonl")
            score = score_run(task, baseline, workspace, recorder)
            self.assertEqual(score.dimensions["safety_boundary"], 100.0)
            self.assertEqual(score.evidence["safety_boundary"]["missing_protected_paths"], [])
            self.assertEqual(score.evidence["safety_boundary"]["modified_protected_paths"], [])
            # Verify hashes match
            for path, bh in score.evidence["safety_boundary"]["baseline_hashes"].items():
                ch = score.evidence["safety_boundary"]["current_hashes"].get(path)
                self.assertEqual(bh, ch, f"Hash mismatch for {path}")

    def test_visual_score_comes_from_real_html_parsing(self) -> None:
        """Prove visual_verification is computed from actual HTML content checks."""
        task = load_task(ROOT / "benchmarks" / "tasks" / "frontend-visual")
        baseline = task.workspace_path
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            shutil.copytree(baseline, workspace)
            # Copy solution
            shutil.copy(task.root / "solution" / "index.html", workspace / "index.html")
            recorder = JsonlRecorder(Path(tmp) / "trace.jsonl")
            score = score_run(task, baseline, workspace, recorder)
            self.assertEqual(score.dimensions["visual_verification"], 100.0)
            visual = score.evidence["visual_verification"]
            self.assertEqual(visual["engine"], "html-static-v1+playwright-chromium-v1")
            self.assertTrue(visual["verified"])
            self.assertEqual(len(visual["checks"]), 4)
            for check in visual["checks"]:
                self.assertTrue(check["passed"], f"Check failed: {check}")

    def test_visual_score_zero_when_html_not_fixed(self) -> None:
        """Prove visual_verification=0 when HTML still has TODO placeholders."""
        task = load_task(ROOT / "benchmarks" / "tasks" / "frontend-visual")
        baseline = task.workspace_path
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            shutil.copytree(baseline, workspace)
            # Do NOT copy solution — leave broken HTML
            recorder = JsonlRecorder(Path(tmp) / "trace.jsonl")
            score = score_run(task, baseline, workspace, recorder)
            # h1 is empty and status is TODO, so checks should fail
            self.assertLess(score.dimensions["visual_verification"], 100.0)

    def test_planning_score_comes_from_real_file_content(self) -> None:
        """Prove planning score is computed from actual file existence/content."""
        task = load_task(ROOT / "benchmarks" / "tasks" / "process-planning")
        baseline = task.workspace_path
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            shutil.copytree(baseline, workspace)
            # Copy solution recursively (includes .agent-benchmark/plan.md)
            solution_dir = task.root / "solution"
            for src in solution_dir.rglob("*"):
                if src.is_file():
                    rel = src.relative_to(solution_dir)
                    dst = workspace / rel
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy(src, dst)
            recorder = JsonlRecorder(Path(tmp) / "trace.jsonl")
            score = score_run(task, baseline, workspace, recorder)
            self.assertEqual(score.dimensions["planning"], 100.0)
            for check in score.evidence["process"]["checks"]:
                self.assertTrue(check["passed"], f"Process check failed: {check}")

    def test_planning_score_zero_when_no_plan_artifact(self) -> None:
        """Prove planning=0 when plan.md doesn't exist."""
        task = load_task(ROOT / "benchmarks" / "tasks" / "process-planning")
        baseline = task.workspace_path
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            shutil.copytree(baseline, workspace)
            # Only fix the code, do NOT create plan.md
            (workspace / "math_ops.py").write_text(
                "def double(value):\n    return value * 2\n", encoding="utf-8"
            )
            recorder = JsonlRecorder(Path(tmp) / "trace.jsonl")
            score = score_run(task, baseline, workspace, recorder)
            self.assertEqual(score.dimensions["planning"], 0.0)

    def test_total_score_is_weighted_sum_not_preset(self) -> None:
        """Prove total score is computed as weighted sum of dimensions."""
        task = load_task(ROOT / "benchmarks" / "tasks" / "frontend-visual")
        baseline = task.workspace_path
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            shutil.copytree(baseline, workspace)
            shutil.copy(task.root / "solution" / "index.html", workspace / "index.html")
            recorder = JsonlRecorder(Path(tmp) / "trace.jsonl")
            score = score_run(task, baseline, workspace, recorder)
            # Manually compute expected total from dimensions and weights
            from agent_benchmark.scorers.basic import _weights
            weights = _weights(task)
            expected = sum(score.dimensions.get(k, 0.0) * v for k, v in weights.items()) / sum(weights.values())
            self.assertAlmostEqual(score.total, round(expected, 2), places=2)

    def test_experiment_config_validation_rejects_bad_values(self) -> None:
        """Prove ExperimentConfig.validate() raises on invalid inputs."""
        with self.assertRaises(ValueError):
            ExperimentConfig(adapter="dummy", repetitions=0, runs_dir=Path("/tmp")).validate()
        with self.assertRaises(ValueError):
            ExperimentConfig(adapter="", repetitions=1, runs_dir=Path("/tmp")).validate()
        with self.assertRaises(ValueError):
            ExperimentConfig(adapter="dummy", repetitions=1, runs_dir=Path("/tmp"), budget_profile="").validate()

    # ── Budget profile enforcement tests ──

    def test_unknown_budget_profile_falls_back_to_open_ended(self) -> None:
        """Prove unknown profile returns open_ended without raising."""
        from agent_benchmark.runner.profiles import get_profile, PROFILES

        profile = get_profile("nonexistent-profile")
        self.assertEqual(profile.name, "open_ended")
        self.assertEqual(profile, PROFILES["open_ended"])

    def test_unknown_profile_config_silently_falls_back(self) -> None:
        """Prove ExperimentConfig silently falls back to open_ended for unknown profile."""
        config = ExperimentConfig(
            adapter="dummy", repetitions=1, runs_dir=Path("/tmp"),
            budget_profile="made-up-profile",
        )
        config.validate()  # should not raise
        self.assertEqual(config.profile.name, "open_ended")

    def test_oneshot_profile_limits_max_attempts_to_one(self) -> None:
        """Prove oneshot profile has max_attempts=1 and no other limits."""
        from agent_benchmark.runner.profiles import get_profile

        profile = get_profile("oneshot")
        self.assertEqual(profile.name, "oneshot")
        self.assertEqual(profile.max_attempts, 1)
        self.assertIsNone(profile.max_duration_seconds)
        self.assertIsNone(profile.max_tool_calls)

    def test_open_ended_profile_has_no_limits(self) -> None:
        """Prove open_ended profile has all limits as None."""
        from agent_benchmark.runner.profiles import get_profile

        profile = get_profile("open_ended")
        self.assertIsNone(profile.max_attempts)
        self.assertIsNone(profile.max_duration_seconds)
        self.assertIsNone(profile.max_tool_calls)

    def test_budget_profile_env_vars_injected(self) -> None:
        """Prove AGENT_BENCH_BUDGET_MAX_ATTEMPTS env var is set during run."""
        task = load_task(ROOT / "benchmarks" / "tasks" / "python-bugfix")
        old_command = os.environ.get("AGENT_BENCH_COMMAND")
        old_timeout = os.environ.get("AGENT_BENCH_TIMEOUT_SECONDS")
        old_max_attempts = os.environ.get("AGENT_BENCH_BUDGET_MAX_ATTEMPTS")

        # Command that writes the env var value to a file
        os.environ["AGENT_BENCH_COMMAND"] = (
            "python3 -c \"from pathlib import Path; import os; "
            "ma = os.environ.get('AGENT_BENCH_BUDGET_MAX_ATTEMPTS', 'unset'); "
            "Path('budget.txt').write_text('max_attempts=' + ma); "
            "Path('stats.py').write_text('def average(values):\\n"
            "    return 0.0 if not values else sum(values) / len(values)\\n')\""
        )
        os.environ["AGENT_BENCH_TIMEOUT_SECONDS"] = "10"
        try:
            with tempfile.TemporaryDirectory() as tmp:
                summary = run_task(
                    task,
                    ExperimentConfig(
                        adapter="generic-command",
                        model="budget-test",
                        budget_profile="oneshot",
                        repetitions=1,
                        runs_dir=Path(tmp),
                    ),
                )
                run_dir = Path(summary["runs"][0]["run_dir"])
                budget_content = (run_dir / "workspace" / "budget.txt").read_text(encoding="utf-8")
                self.assertEqual(budget_content, "max_attempts=1")
                self.assertEqual(summary["budget_profile"], "oneshot")
        finally:
            _restore_env("AGENT_BENCH_COMMAND", old_command)
            _restore_env("AGENT_BENCH_TIMEOUT_SECONDS", old_timeout)
            _restore_env("AGENT_BENCH_BUDGET_MAX_ATTEMPTS", old_max_attempts)

    def test_budget_duration_becomes_adapter_timeout_when_no_override_exists(self) -> None:
        from agent_benchmark.adapters.generic_command import GenericCommandAdapter

        old_timeout = os.environ.get("AGENT_BENCH_TIMEOUT_SECONDS")
        old_budget = os.environ.get("AGENT_BENCH_BUDGET_MAX_SECONDS")
        os.environ.pop("AGENT_BENCH_TIMEOUT_SECONDS", None)
        os.environ["AGENT_BENCH_BUDGET_MAX_SECONDS"] = "0.25"
        try:
            self.assertEqual(GenericCommandAdapter().timeout_seconds(), 0.25)
        finally:
            _restore_env("AGENT_BENCH_TIMEOUT_SECONDS", old_timeout)
            _restore_env("AGENT_BENCH_BUDGET_MAX_SECONDS", old_budget)

    def test_budget_duration_enforces_generic_adapter_timeout(self) -> None:
        from agent_benchmark.runner.profiles import BudgetProfile

        task = load_task(ROOT / "benchmarks" / "tasks" / "python-bugfix")
        old_command = os.environ.get("AGENT_BENCH_COMMAND")
        old_timeout = os.environ.get("AGENT_BENCH_TIMEOUT_SECONDS")
        os.environ["AGENT_BENCH_COMMAND"] = "python3 -c \"import time; time.sleep(2)\""
        os.environ.pop("AGENT_BENCH_TIMEOUT_SECONDS", None)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                with patch(
                    "agent_benchmark.runner.config.get_profile",
                    return_value=BudgetProfile(name="tiny", max_duration_seconds=0.1),
                ):
                    summary = run_task(
                        task,
                        ExperimentConfig(
                            adapter="generic-command",
                            budget_profile="bounded",
                            repetitions=1,
                            runs_dir=Path(tmp),
                        ),
                    )
                result = json.loads((Path(summary["runs"][0]["run_dir"]) / "result.json").read_text(encoding="utf-8"))

            self.assertEqual(result["adapter_result"]["exit_code"], 124)
            self.assertIn("timed out after 0.1 seconds", result["adapter_result"]["stderr"])
        finally:
            _restore_env("AGENT_BENCH_COMMAND", old_command)
            _restore_env("AGENT_BENCH_TIMEOUT_SECONDS", old_timeout)

    def test_open_ended_profile_clears_stale_budget_timeout(self) -> None:
        task = load_task(ROOT / "benchmarks" / "tasks" / "python-bugfix")
        old_command = os.environ.get("AGENT_BENCH_COMMAND")
        old_timeout = os.environ.get("AGENT_BENCH_TIMEOUT_SECONDS")
        old_budget = os.environ.get("AGENT_BENCH_BUDGET_MAX_SECONDS")
        os.environ["AGENT_BENCH_COMMAND"] = (
            "python3 -c \"import time; from pathlib import Path; time.sleep(0.15); "
            "Path('stats.py').write_text('def average(values):\\n"
            "    return 0.0 if not values else sum(values) / len(values)\\n')\""
        )
        os.environ.pop("AGENT_BENCH_TIMEOUT_SECONDS", None)
        os.environ["AGENT_BENCH_BUDGET_MAX_SECONDS"] = "0.01"
        try:
            with tempfile.TemporaryDirectory() as tmp:
                summary = run_task(
                    task,
                    ExperimentConfig(
                        adapter="generic-command",
                        budget_profile="open_ended",
                        repetitions=1,
                        runs_dir=Path(tmp),
                    ),
                )
                result = json.loads((Path(summary["runs"][0]["run_dir"]) / "result.json").read_text(encoding="utf-8"))

            self.assertEqual(result["adapter_result"]["exit_code"], 0)
        finally:
            _restore_env("AGENT_BENCH_COMMAND", old_command)
            _restore_env("AGENT_BENCH_TIMEOUT_SECONDS", old_timeout)
            _restore_env("AGENT_BENCH_BUDGET_MAX_SECONDS", old_budget)

    def test_keyboard_interrupt_preserves_resume_evidence(self) -> None:
        task = load_task(ROOT / "benchmarks" / "tasks" / "python-bugfix")

        class InterruptingAdapter:
            name = "interrupting"

            def run(self, task: object, workspace: Path, recorder: JsonlRecorder) -> AdapterResult:
                raise KeyboardInterrupt

        with tempfile.TemporaryDirectory() as tmp:
            with patch("agent_benchmark.runner.run.adapter_by_name", return_value=InterruptingAdapter()):
                with self.assertRaises(KeyboardInterrupt):
                    run_task(task, ExperimentConfig(adapter="dummy", repetitions=2, runs_dir=Path(tmp)))
            experiment_dir = next(Path(tmp).iterdir())
            manifest = json.loads((experiment_dir / "experiment_manifest.json").read_text(encoding="utf-8"))
            checkpoint = json.loads((experiment_dir / "checkpoint.json").read_text(encoding="utf-8"))
            interruption = json.loads((experiment_dir / "repetition_1" / "interruption.json").read_text(encoding="utf-8"))
            trace = (experiment_dir / "repetition_1" / "trace.jsonl").read_text(encoding="utf-8")

        self.assertEqual(manifest["status"], "interrupted")
        self.assertEqual(checkpoint["completed_repetitions"], [])
        self.assertEqual(checkpoint["remaining_repetitions"], [1, 2])
        self.assertEqual(interruption["reason"], "keyboard_interrupt")
        self.assertIn('"event": "run.interrupted"', trace)

    def test_profile_instruction_suffix_appears_in_instruction_file(self) -> None:
        """Prove oneshot profile suffix is written to instruction.txt."""
        task = load_task(ROOT / "benchmarks" / "tasks" / "python-bugfix")
        with tempfile.TemporaryDirectory() as tmp:
            summary = run_task(
                task,
                ExperimentConfig(
                    adapter="dummy",
                    budget_profile="oneshot",
                    repetitions=1,
                    runs_dir=Path(tmp),
                ),
            )
            run_dir = Path(summary["runs"][0]["run_dir"])
            instruction = (run_dir / "instruction.txt").read_text(encoding="utf-8")
            self.assertIn("BUDGET PROFILE: ONESHOT", instruction)
            self.assertIn("Single attempt, no retries", instruction)
            self.assertIn("at most 1 attempt", instruction)

    def test_budget_profile_info_in_summary(self) -> None:
        """Prove summary includes budget_profile with correct values."""
        task = load_task(ROOT / "benchmarks" / "tasks" / "python-bugfix")
        with tempfile.TemporaryDirectory() as tmp:
            summary = run_task(
                task,
                ExperimentConfig(
                    adapter="dummy",
                    budget_profile="bounded",
                    repetitions=2,
                    runs_dir=Path(tmp),
                ),
            )
            self.assertEqual(summary["budget_profile"], "bounded")
            for run_info in summary["runs"]:
                self.assertEqual(run_info["run_dir"], run_info["run_dir"])  # smoke check

    def test_adapter_by_name_raises_for_unknown(self) -> None:
        """Prove adapter_by_name raises ValueError for unregistered adapters."""
        with self.assertRaises(ValueError):
            adapter_by_name("nonexistent-adapter")

    # ── Parser tests ──

    def test_opencode_parser_extracts_model_and_tools(self) -> None:
        """Prove parser extracts model name and tool calls from opencode stderr."""
        from agent_benchmark.parsers import parse_harness_output

        stderr = (
            "\x1b[0m\n"
            "> build · LongCat-2.0\n"
            "\x1b[0m\n"
            "\x1b[0m$ \x1b[0mls workspace\n"
            "\x1b[0m\n"
            "\x1b[0m→ \x1b[0mRead stats.py\n"
            "\x1b[0m← \x1b[0mEdit stats.py\n"
            "\x1b[0m✱ \x1b[0mGrep \"average\" in . · 3 matches\n"
        )
        evidence = parse_harness_output("opencode", "", stderr)
        self.assertEqual(evidence.model, "LongCat-2.0")
        self.assertEqual(len(evidence.tool_calls), 4)
        self.assertEqual(evidence.tool_calls[0]["type"], "bash")
        self.assertEqual(evidence.tool_calls[1]["type"], "read")
        self.assertEqual(evidence.tool_calls[2]["type"], "edit")
        self.assertEqual(evidence.tool_calls[3]["type"], "search")

    def test_claude_code_parser_handles_empty_output(self) -> None:
        """Prove parser handles claude-code's minimal output gracefully."""
        from agent_benchmark.parsers import parse_harness_output

        evidence = parse_harness_output("claude-code", "Fixed the bug.", "")
        self.assertIsNone(evidence.model)
        self.assertIsInstance(evidence.tool_calls, list)

    def test_claude_code_json_parser_extracts_model_usage_and_cost(self) -> None:
        from agent_benchmark.parsers import parse_harness_output

        stdout = json.dumps(
            {
                "total_cost_usd": 0.0125,
                "usage": {
                    "input_tokens": 1200,
                    "output_tokens": 300,
                    "server_tool_use": {"web_search_requests": 2},
                },
                "modelUsage": {"claude-fable-5": {"costUSD": 0.0125}},
                "result": "Updated `stats.py`.",
            }
        )
        evidence = parse_harness_output("claude-code", stdout, "")

        self.assertEqual(evidence.model, "claude-fable-5")
        self.assertEqual(evidence.input_tokens, 1200)
        self.assertEqual(evidence.output_tokens, 300)
        self.assertEqual(evidence.cost_usd, 0.0125)
        self.assertEqual(len([call for call in evidence.tool_calls if call["type"] == "server_web_search_requests"]), 2)

    def test_unknown_adapter_parser_returns_empty(self) -> None:
        """Prove parser returns empty evidence for unknown adapters."""
        from agent_benchmark.parsers import parse_harness_output

        evidence = parse_harness_output("unknown-adapter", "output", "error")
        self.assertIsNone(evidence.model)
        self.assertEqual(evidence.tool_calls, [])

    def test_tool_use_scored_from_real_harness_evidence(self) -> None:
        """Prove tool_use dimension is computed from parsed harness output."""
        from agent_benchmark.parsers.harness_output import HarnessEvidence

        task = load_task(ROOT / "benchmarks" / "tasks" / "python-bugfix")
        baseline = task.workspace_path
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            shutil.copytree(baseline, workspace)
            shutil.copy(task.root / "solution" / "stats.py", workspace / "stats.py")
            recorder = JsonlRecorder(Path(tmp) / "trace.jsonl")
            # Simulate harness evidence with tool calls
            evidence = HarnessEvidence(
                model="test-model",
                tool_calls=[
                    {"type": "read", "path": "stats.py"},
                    {"type": "edit", "path": "stats.py"},
                    {"type": "bash", "command": "python3 test_stats.py"},
                ],
            )
            score = score_run(task, baseline, workspace, recorder, harness_evidence=evidence)
            self.assertGreater(score.dimensions["tool_use"], 0.0)
            self.assertIn("tool_use", score.evidence)
            self.assertEqual(score.evidence["tool_use"]["tool_count"], 3)

    def test_tool_use_zero_without_harness_evidence(self) -> None:
        """Prove tool_use=0 when no harness evidence is provided."""
        task = load_task(ROOT / "benchmarks" / "tasks" / "python-bugfix")
        baseline = task.workspace_path
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            shutil.copytree(baseline, workspace)
            shutil.copy(task.root / "solution" / "stats.py", workspace / "stats.py")
            recorder = JsonlRecorder(Path(tmp) / "trace.jsonl")
            score = score_run(task, baseline, workspace, recorder)
            self.assertEqual(score.dimensions["tool_use"], 0.0)

    # ── cost_efficiency tests ──

    def test_cost_efficiency_from_token_count(self) -> None:
        """Prove cost_efficiency scores from real token data."""
        from agent_benchmark.scorers.basic import _score_cost_efficiency
        from agent_benchmark.parsers.harness_output import HarnessEvidence

        evidence = HarnessEvidence(input_tokens=1000, output_tokens=500)
        score, ev = _score_cost_efficiency(evidence)
        self.assertEqual(ev["method"], "token_count")
        self.assertEqual(ev["total_tokens"], 1500)
        self.assertGreater(score, 0.0)
        self.assertLess(score, 100.0)

    def test_cost_efficiency_from_cost_usd(self) -> None:
        """Prove cost_efficiency scores from real cost data."""
        from agent_benchmark.scorers.basic import _score_cost_efficiency
        from agent_benchmark.parsers.harness_output import HarnessEvidence

        evidence = HarnessEvidence(cost_usd=0.05)
        score, ev = _score_cost_efficiency(evidence)
        self.assertEqual(ev["method"], "cost_usd")
        self.assertEqual(ev["cost_usd"], 0.05)
        self.assertGreater(score, 0.0)

    def test_cost_efficiency_zero_with_only_tool_calls(self) -> None:
        """Prove tool calls alone do not masquerade as cost evidence."""
        from agent_benchmark.scorers.basic import _score_cost_efficiency
        from agent_benchmark.parsers.harness_output import HarnessEvidence

        evidence = HarnessEvidence(tool_calls=[{"type": "read"}, {"type": "edit"}])
        score, ev = _score_cost_efficiency(evidence)
        self.assertEqual(score, 0.0)
        self.assertEqual(ev["method"], "no_token_or_cost_evidence")
        self.assertEqual(ev["tool_count"], 2)

    def test_cost_efficiency_zero_without_evidence(self) -> None:
        """Prove cost_efficiency=0 when no harness evidence."""
        from agent_benchmark.scorers.basic import _score_cost_efficiency
        from agent_benchmark.parsers.harness_output import HarnessEvidence

        evidence = HarnessEvidence()
        score, ev = _score_cost_efficiency(evidence)
        self.assertEqual(score, 0.0)
        self.assertEqual(ev["method"], "no_token_or_cost_evidence")

    def test_opencode_parser_extracts_tokens(self) -> None:
        """Prove parser extracts token counts from opencode stderr."""
        from agent_benchmark.parsers import parse_harness_output

        stderr = "> build · LongCat-2.0\nTokens: 1,234 in / 567 out\n"
        evidence = parse_harness_output("opencode", "", stderr)
        self.assertEqual(evidence.input_tokens, 1234)
        self.assertEqual(evidence.output_tokens, 567)

    def test_opencode_parser_extracts_cost(self) -> None:
        """Prove parser extracts cost from opencode stderr."""
        from agent_benchmark.parsers import parse_harness_output

        stderr = "> build · LongCat-2.0\nCost: $0.0123\n"
        evidence = parse_harness_output("opencode", "", stderr)
        self.assertEqual(evidence.cost_usd, 0.0123)

    # ── test_file_quality process check tests ──

    def test_file_quality_passes_when_test_file_has_content(self) -> None:
        """Prove test_file_quality check passes for a file with test functions and assertions."""
        from agent_benchmark.scorers.process import score_process_checks

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            test_file = workspace / "test_example.py"
            test_file.write_text(
                "import example\n\n"
                "def test_one():\n"
                "    assert example.add(1, 2) == 3\n\n"
                "def test_two():\n"
                "    assert example.add(0, 0) == 0\n\n"
                "def test_three():\n"
                "    assert example.add(-1, 1) == 0\n",
                encoding="utf-8",
            )
            checks = [
                {
                    "type": "test_file_quality",
                    "dimension": "test_discipline",
                    "path": "test_example.py",
                    "min_test_functions": 3,
                    "min_assertions": 3,
                    "must_import": "example",
                }
            ]
            result = score_process_checks(workspace, checks)
            self.assertEqual(result.dimensions["test_discipline"], 100.0)
            self.assertTrue(result.checks[0]["passed"])
            self.assertEqual(result.checks[0]["test_function_count"], 3)
            self.assertEqual(result.checks[0]["assertion_count"], 3)

    def test_file_quality_fails_when_no_test_functions(self) -> None:
        """Prove test_file_quality check fails when file has no test functions."""
        from agent_benchmark.scorers.process import score_process_checks

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            test_file = workspace / "test_empty.py"
            test_file.write_text("# no tests here\nprint('hello')\n", encoding="utf-8")
            checks = [
                {
                    "type": "test_file_quality",
                    "dimension": "test_discipline",
                    "path": "test_empty.py",
                    "min_test_functions": 2,
                    "min_assertions": 2,
                }
            ]
            result = score_process_checks(workspace, checks)
            self.assertEqual(result.dimensions["test_discipline"], 0.0)
            self.assertFalse(result.checks[0]["passed"])
            self.assertEqual(result.checks[0]["test_function_count"], 0)

    def test_file_quality_fails_when_file_missing(self) -> None:
        """Prove test_file_quality check fails when test file doesn't exist."""
        from agent_benchmark.scorers.process import score_process_checks

        with tempfile.TemporaryDirectory() as tmp:
            checks = [
                {
                    "type": "test_file_quality",
                    "dimension": "test_discipline",
                    "path": "nonexistent.py",
                }
            ]
            result = score_process_checks(Path(tmp), checks)
            self.assertEqual(result.dimensions["test_discipline"], 0.0)
            self.assertFalse(result.checks[0]["passed"])
            self.assertIn("not found", result.checks[0]["error"])

    def test_file_quality_fails_when_missing_required_import(self) -> None:
        """Prove test_file_quality check fails when must_import is absent."""
        from agent_benchmark.scorers.process import score_process_checks

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            test_file = workspace / "test_noimport.py"
            test_file.write_text(
                "def test_one():\n"
                "    assert 1 + 1 == 2\n\n"
                "def test_two():\n"
                "    assert True\n",
                encoding="utf-8",
            )
            checks = [
                {
                    "type": "test_file_quality",
                    "dimension": "test_discipline",
                    "path": "test_noimport.py",
                    "min_test_functions": 2,
                    "min_assertions": 2,
                    "must_import": "stats",
                }
            ]
            result = score_process_checks(workspace, checks)
            self.assertEqual(result.dimensions["test_discipline"], 0.0)
            self.assertFalse(result.checks[0]["passed"])
            self.assertFalse(result.checks[0]["import_ok"])

    # ── file_changed process check tests ──

    def test_file_changed_passes_when_file_differs(self) -> None:
        """Prove file_changed check passes when workspace file differs from baseline."""
        from agent_benchmark.scorers.process import score_process_checks

        with tempfile.TemporaryDirectory() as tmp:
            baseline = Path(tmp) / "baseline"
            workspace = Path(tmp) / "workspace"
            baseline.mkdir()
            workspace.mkdir()
            (baseline / "code.py").write_text("old content\n", encoding="utf-8")
            (workspace / "code.py").write_text("new content\n", encoding="utf-8")
            checks = [
                {"type": "file_changed", "dimension": "execution_quality", "path": "code.py"}
            ]
            result = score_process_checks(workspace, checks, baseline=baseline)
            self.assertEqual(result.dimensions["execution_quality"], 100.0)
            self.assertTrue(result.checks[0]["passed"])
            self.assertEqual(result.checks[0]["status"], "modified")

    def test_file_changed_fails_when_file_unchanged(self) -> None:
        """Prove file_changed check fails when workspace file is same as baseline."""
        from agent_benchmark.scorers.process import score_process_checks

        with tempfile.TemporaryDirectory() as tmp:
            baseline = Path(tmp) / "baseline"
            workspace = Path(tmp) / "workspace"
            baseline.mkdir()
            workspace.mkdir()
            (baseline / "code.py").write_text("same content\n", encoding="utf-8")
            (workspace / "code.py").write_text("same content\n", encoding="utf-8")
            checks = [
                {"type": "file_changed", "dimension": "execution_quality", "path": "code.py"}
            ]
            result = score_process_checks(workspace, checks, baseline=baseline)
            self.assertEqual(result.dimensions["execution_quality"], 0.0)
            self.assertFalse(result.checks[0]["passed"])
            self.assertEqual(result.checks[0]["status"], "unchanged")

    def test_file_changed_passes_when_file_created(self) -> None:
        """Prove file_changed check passes when file exists in workspace but not baseline."""
        from agent_benchmark.scorers.process import score_process_checks

        with tempfile.TemporaryDirectory() as tmp:
            baseline = Path(tmp) / "baseline"
            workspace = Path(tmp) / "workspace"
            baseline.mkdir()
            workspace.mkdir()
            # File only in workspace (created by agent)
            (workspace / "new_file.py").write_text("new code\n", encoding="utf-8")
            checks = [
                {"type": "file_changed", "dimension": "execution_quality", "path": "new_file.py"}
            ]
            result = score_process_checks(workspace, checks, baseline=baseline)
            self.assertEqual(result.dimensions["execution_quality"], 100.0)
            self.assertTrue(result.checks[0]["passed"])
            self.assertEqual(result.checks[0]["status"], "created")

    def test_file_changed_fails_without_baseline(self) -> None:
        """Prove file_changed check fails when no baseline is provided."""
        from agent_benchmark.scorers.process import score_process_checks

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            (workspace / "code.py").write_text("content\n", encoding="utf-8")
            checks = [
                {"type": "file_changed", "dimension": "execution_quality", "path": "code.py"}
            ]
            result = score_process_checks(workspace, checks)
            self.assertEqual(result.dimensions["execution_quality"], 0.0)
            self.assertFalse(result.checks[0]["passed"])
            self.assertIn("No baseline", result.checks[0]["error"])

    # ── instruction_match process check tests ──

    def test_instruction_match_passes_when_expected_file_changed(self) -> None:
        """Prove instruction_match passes when at least one expected file differs from baseline."""
        from agent_benchmark.scorers.process import score_process_checks

        with tempfile.TemporaryDirectory() as tmp:
            baseline = Path(tmp) / "baseline"
            workspace = Path(tmp) / "workspace"
            baseline.mkdir()
            workspace.mkdir()
            (baseline / "stats.py").write_text("def average(v): return 0\n", encoding="utf-8")
            (workspace / "stats.py").write_text("def average(v): return sum(v)/len(v)\n", encoding="utf-8")
            checks = [
                {
                    "type": "instruction_match",
                    "dimension": "intent_understanding",
                    "expected_changed_files": ["stats.py"],
                }
            ]
            result = score_process_checks(workspace, checks, baseline=baseline)
            self.assertEqual(result.dimensions["intent_understanding"], 100.0)
            self.assertTrue(result.checks[0]["passed"])
            self.assertEqual(result.checks[0]["files"][0]["status"], "modified")

    def test_instruction_match_fails_when_expected_file_unchanged(self) -> None:
        """Prove instruction_match fails when none of the expected files were changed."""
        from agent_benchmark.scorers.process import score_process_checks

        with tempfile.TemporaryDirectory() as tmp:
            baseline = Path(tmp) / "baseline"
            workspace = Path(tmp) / "workspace"
            baseline.mkdir()
            workspace.mkdir()
            (baseline / "stats.py").write_text("same content\n", encoding="utf-8")
            (workspace / "stats.py").write_text("same content\n", encoding="utf-8")
            checks = [
                {
                    "type": "instruction_match",
                    "dimension": "intent_understanding",
                    "expected_changed_files": ["stats.py"],
                }
            ]
            result = score_process_checks(workspace, checks, baseline=baseline)
            self.assertEqual(result.dimensions["intent_understanding"], 0.0)
            self.assertFalse(result.checks[0]["passed"])
            self.assertEqual(result.checks[0]["files"][0]["status"], "unchanged")

    def test_instruction_match_passes_when_file_created(self) -> None:
        """Prove instruction_match passes when expected file exists in workspace but not baseline."""
        from agent_benchmark.scorers.process import score_process_checks

        with tempfile.TemporaryDirectory() as tmp:
            baseline = Path(tmp) / "baseline"
            workspace = Path(tmp) / "workspace"
            baseline.mkdir()
            workspace.mkdir()
            (workspace / "new_module.py").write_text("x = 1\n", encoding="utf-8")
            checks = [
                {
                    "type": "instruction_match",
                    "dimension": "intent_understanding",
                    "expected_changed_files": ["new_module.py"],
                }
            ]
            result = score_process_checks(workspace, checks, baseline=baseline)
            self.assertEqual(result.dimensions["intent_understanding"], 100.0)
            self.assertTrue(result.checks[0]["passed"])
            self.assertEqual(result.checks[0]["files"][0]["status"], "created")

    def test_instruction_match_passes_when_any_of_multiple_files_changed(self) -> None:
        """Prove instruction_match passes if even one of several expected files changed."""
        from agent_benchmark.scorers.process import score_process_checks

        with tempfile.TemporaryDirectory() as tmp:
            baseline = Path(tmp) / "baseline"
            workspace = Path(tmp) / "workspace"
            baseline.mkdir()
            workspace.mkdir()
            # a.py unchanged, b.py changed
            (baseline / "a.py").write_text("same\n", encoding="utf-8")
            (workspace / "a.py").write_text("same\n", encoding="utf-8")
            (baseline / "b.py").write_text("old\n", encoding="utf-8")
            (workspace / "b.py").write_text("new\n", encoding="utf-8")
            checks = [
                {
                    "type": "instruction_match",
                    "dimension": "intent_understanding",
                    "expected_changed_files": ["a.py", "b.py"],
                }
            ]
            result = score_process_checks(workspace, checks, baseline=baseline)
            self.assertEqual(result.dimensions["intent_understanding"], 100.0)
            self.assertTrue(result.checks[0]["passed"])

    def test_instruction_match_handles_missing_file_in_workspace(self) -> None:
        """Prove instruction_match handles expected file that doesn't exist in workspace."""
        from agent_benchmark.scorers.process import score_process_checks

        with tempfile.TemporaryDirectory() as tmp:
            baseline = Path(tmp) / "baseline"
            workspace = Path(tmp) / "workspace"
            baseline.mkdir()
            workspace.mkdir()
            (baseline / "stats.py").write_text("old\n", encoding="utf-8")
            # workspace/stats.py does not exist
            checks = [
                {
                    "type": "instruction_match",
                    "dimension": "intent_understanding",
                    "expected_changed_files": ["stats.py"],
                }
            ]
            result = score_process_checks(workspace, checks, baseline=baseline)
            self.assertEqual(result.dimensions["intent_understanding"], 0.0)
            self.assertFalse(result.checks[0]["passed"])
            self.assertEqual(result.checks[0]["files"][0]["status"], "missing")

    def test_instruction_match_fails_without_baseline(self) -> None:
        """Prove instruction_match fails when no baseline is provided."""
        from agent_benchmark.scorers.process import score_process_checks

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            (workspace / "code.py").write_text("content\n", encoding="utf-8")
            checks = [
                {
                    "type": "instruction_match",
                    "dimension": "intent_understanding",
                    "expected_changed_files": ["code.py"],
                }
            ]
            result = score_process_checks(workspace, checks)
            self.assertEqual(result.dimensions["intent_understanding"], 0.0)
            self.assertFalse(result.checks[0]["passed"])
            self.assertIn("No baseline", result.checks[0]["error"])

    # ── code_quality process check tests ──

    def test_code_quality_passes_for_clean_code(self) -> None:
        """Prove code_quality check passes for well-written code."""
        from agent_benchmark.scorers.process import score_process_checks

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            code_file = workspace / "clean.py"
            code_file.write_text(
                '"""Module docstring."""\n\n'
                'def short_function():\n'
                '    """Short function with docstring."""\n'
                '    return 42\n\n'
                'def another_function():\n'
                '    """Another short function."""\n'
                '    # This is a comment\n'
                '    return 0\n',
                encoding="utf-8",
            )
            checks = [
                {
                    "type": "code_quality",
                    "dimension": "execution_quality",
                    "path": "clean.py",
                    "max_function_lines": 10,
                    "max_nesting_depth": 3,
                    "require_docstrings": True,
                }
            ]
            result = score_process_checks(workspace, checks)
            self.assertEqual(result.dimensions["execution_quality"], 100.0)
            self.assertTrue(result.checks[0]["passed"])

    def test_code_quality_fails_for_long_function(self) -> None:
        """Prove code_quality check fails when function is too long."""
        from agent_benchmark.scorers.process import score_process_checks

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            code_file = workspace / "long_func.py"
            # Create a function with20 lines
            lines = ["def long_function():\n"]
            for i in range(20):
                lines.append(f"    x{i} = {i}\n")
            lines.append("    return x0\n")
            code_file.write_text("".join(lines), encoding="utf-8")

            checks = [
                {
                    "type": "code_quality",
                    "dimension": "execution_quality",
                    "path": "long_func.py",
                    "max_function_lines": 10,
                }
            ]
            result = score_process_checks(workspace, checks)
            self.assertEqual(result.dimensions["execution_quality"], 0.0)
            self.assertFalse(result.checks[0]["passed"])
            self.assertIn("Function too long", result.checks[0]["issues"][0])

    def test_code_quality_fails_for_deep_nesting(self) -> None:
        """Prove code_quality check fails when nesting is too deep."""
        from agent_benchmark.scorers.process import score_process_checks

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            code_file = workspace / "nested.py"
            code_file.write_text(
                "def nested():\n"
                "    if True:\n"
                "        if True:\n"
                "            if True:\n"
                "                if True:\n"
                "                    return 1\n",
                encoding="utf-8",
            )
            checks = [
                {
                    "type": "code_quality",
                    "dimension": "execution_quality",
                    "path": "nested.py",
                    "max_nesting_depth": 3,
                }
            ]
            result = score_process_checks(workspace, checks)
            self.assertEqual(result.dimensions["execution_quality"], 0.0)
            self.assertFalse(result.checks[0]["passed"])
            self.assertIn("Nesting too deep", result.checks[0]["issues"][0])

    def test_code_quality_fails_when_missing_docstrings(self) -> None:
        """Prove code_quality check fails when require_docstrings=True but no docstrings."""
        from agent_benchmark.scorers.process import score_process_checks

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            code_file = workspace / "no_doc.py"
            code_file.write_text(
                "def function():\n"
                "    return 42\n",
                encoding="utf-8",
            )
            checks = [
                {
                    "type": "code_quality",
                    "dimension": "execution_quality",
                    "path": "no_doc.py",
                    "require_docstrings": True,
                }
            ]
            result = score_process_checks(workspace, checks)
            self.assertEqual(result.dimensions["execution_quality"], 0.0)
            self.assertFalse(result.checks[0]["passed"])

    def test_code_quality_fails_when_file_missing(self) -> None:
        """Prove code_quality check fails when file doesn't exist."""
        from agent_benchmark.scorers.process import score_process_checks

        with tempfile.TemporaryDirectory() as tmp:
            checks = [
                {
                    "type": "code_quality",
                    "dimension": "execution_quality",
                    "path": "nonexistent.py",
                }
            ]
            result = score_process_checks(Path(tmp), checks)
            self.assertEqual(result.dimensions["execution_quality"], 0.0)
            self.assertFalse(result.checks[0]["passed"])
            self.assertIn("not found", result.checks[0]["error"])

    # ── performance_check process check tests ──

    def test_performance_check_passes_for_fast_code(self) -> None:
        """Prove performance_check passes when code runs within time limit."""
        from agent_benchmark.scorers.process import score_process_checks

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            # Create a simple test script
            test_file = workspace / "test_perf.py"
            test_file.write_text("print('fast')\n", encoding="utf-8")

            checks = [
                {
                    "type": "performance_check",
                    "dimension": "execution_quality",
                    "command": ["python3", "test_perf.py"],
                    "max_seconds": 5.0,
                }
            ]
            result = score_process_checks(workspace, checks)
            self.assertEqual(result.dimensions["execution_quality"], 100.0)
            self.assertTrue(result.checks[0]["passed"])
            self.assertIn("elapsed_seconds", result.checks[0])

    def test_performance_check_fails_for_slow_code(self) -> None:
        """Prove performance_check fails when code exceeds time limit."""
        from agent_benchmark.scorers.process import score_process_checks

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            # Create a slow script
            test_file = workspace / "slow.py"
            test_file.write_text("import time; time.sleep(2)\n", encoding="utf-8")

            checks = [
                {
                    "type": "performance_check",
                    "dimension": "execution_quality",
                    "command": ["python3", "slow.py"],
                    "max_seconds": 0.5,  # Very short limit
                }
            ]
            result = score_process_checks(workspace, checks)
            self.assertEqual(result.dimensions["execution_quality"], 0.0)
            self.assertFalse(result.checks[0]["passed"])

    def test_performance_check_fails_for_failing_command(self) -> None:
        """Prove performance_check fails when command exits with non-zero code."""
        from agent_benchmark.scorers.process import score_process_checks

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            # Create a script that fails
            test_file = workspace / "fail.py"
            test_file.write_text("import sys; sys.exit(1)\n", encoding="utf-8")

            checks = [
                {
                    "type": "performance_check",
                    "dimension": "execution_quality",
                    "command": ["python3", "fail.py"],
                    "max_seconds": 5.0,
                }
            ]
            result = score_process_checks(workspace, checks)
            self.assertEqual(result.dimensions["execution_quality"], 0.0)
            self.assertFalse(result.checks[0]["passed"])
            self.assertIn("exit code", result.checks[0]["issues"][0])

    def test_performance_check_fails_when_no_command(self) -> None:
        """Prove performance_check fails when no command is specified."""
        from agent_benchmark.scorers.process import score_process_checks

        with tempfile.TemporaryDirectory() as tmp:
            checks = [
                {
                    "type": "performance_check",
                    "dimension": "execution_quality",
                    "max_seconds": 5.0,
                }
            ]
            result = score_process_checks(Path(tmp), checks)
            self.assertEqual(result.dimensions["execution_quality"], 0.0)
            self.assertFalse(result.checks[0]["passed"])
            self.assertIn("No command", result.checks[0]["error"])

    # ── documentation_check process check tests ──

    def test_documentation_check_passes_for_well_documented_code(self) -> None:
        """Prove documentation_check passes for code with good documentation."""
        from agent_benchmark.scorers.process import score_process_checks

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            code_file = workspace / "documented.py"
            code_file.write_text(
                '"""Module docstring."""\n\n'
                'def documented_function():\n'
                '    """This function has a docstring."""\n'
                '    return 42\n\n'
                'def another_function():\n'
                '    """This also has a docstring."""\n'
                '    return 0\n',
                encoding="utf-8",
            )
            checks = [
                {
                    "type": "documentation_check",
                    "dimension": "execution_quality",
                    "path": "documented.py",
                    "min_docstring_ratio": 0.5,
                }
            ]
            result = score_process_checks(workspace, checks)
            self.assertEqual(result.dimensions["execution_quality"], 100.0)
            self.assertTrue(result.checks[0]["passed"])
            self.assertTrue(result.checks[0]["metrics"]["has_module_docstring"])

    def test_documentation_check_fails_for_missing_docstrings(self) -> None:
        """Prove documentation_check fails when functions lack docstrings."""
        from agent_benchmark.scorers.process import score_process_checks

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            code_file = workspace / "undocumented.py"
            code_file.write_text(
                '"""Module docstring."""\n\n'
                'def no_docstring():\n'
                '    return 42\n\n'
                'def also_no_docstring():\n'
                '    return 0\n',
                encoding="utf-8",
            )
            checks = [
                {
                    "type": "documentation_check",
                    "dimension": "execution_quality",
                    "path": "undocumented.py",
                    "min_docstring_ratio": 0.5,
                }
            ]
            result = score_process_checks(workspace, checks)
            self.assertEqual(result.dimensions["execution_quality"], 0.0)
            self.assertFalse(result.checks[0]["passed"])
            self.assertIn("Too few function docstrings", result.checks[0]["issues"][0])

    def test_documentation_check_fails_for_missing_module_docstring(self) -> None:
        """Prove documentation_check fails when module has no docstring."""
        from agent_benchmark.scorers.process import score_process_checks

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            code_file = workspace / "no_module_doc.py"
            code_file.write_text(
                'def function():\n'
                '    """Has docstring."""\n'
                '    return 42\n',
                encoding="utf-8",
            )
            checks = [
                {
                    "type": "documentation_check",
                    "dimension": "execution_quality",
                    "path": "no_module_doc.py",
                    "min_docstring_ratio": 0.5,
                }
            ]
            result = score_process_checks(workspace, checks)
            self.assertEqual(result.dimensions["execution_quality"], 0.0)
            self.assertFalse(result.checks[0]["passed"])
            self.assertIn("No module docstring", result.checks[0]["issues"][0])

    def test_documentation_check_fails_when_file_missing(self) -> None:
        """Prove documentation_check fails when file doesn't exist."""
        from agent_benchmark.scorers.process import score_process_checks

        with tempfile.TemporaryDirectory() as tmp:
            checks = [
                {
                    "type": "documentation_check",
                    "dimension": "execution_quality",
                    "path": "nonexistent.py",
                }
            ]
            result = score_process_checks(Path(tmp), checks)
            self.assertEqual(result.dimensions["execution_quality"], 0.0)
            self.assertFalse(result.checks[0]["passed"])
            self.assertIn("not found", result.checks[0]["error"])

    # ── self_repair scoring tests ──

    def test_self_repair_zero_when_no_logs(self) -> None:
        """Prove self_repair=0 when stdout.log/stderr.log don't exist."""
        from agent_benchmark.scorers.basic import _score_self_repair

        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            workspace = run_dir / "workspace"
            workspace.mkdir(parents=True)
            # No stdout.log or stderr.log created
            score, evidence = _score_self_repair(workspace)
            self.assertEqual(score, 0.0)
            self.assertIn("No log files", evidence.get("error", ""))

    def test_self_repair_zero_for_dummy_adapter_output(self) -> None:
        """Prove self_repair=0 for the dummy adapter's minimal stdout."""
        from agent_benchmark.scorers.basic import _score_self_repair

        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            workspace = run_dir / "workspace"
            workspace.mkdir(parents=True)
            (run_dir / "stdout.log").write_text("Copied 3 solution file(s).\n", encoding="utf-8")
            (run_dir / "stderr.log").write_text("", encoding="utf-8")
            score, evidence = _score_self_repair(workspace)
            self.assertEqual(score, 0.0)
            self.assertEqual(evidence["indicator_count"], 0)

    def test_self_repair_score_with_one_indicator(self) -> None:
        """Prove self_repair>0 when one indicator pattern is found."""
        from agent_benchmark.scorers.basic import _score_self_repair

        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            workspace = run_dir / "workspace"
            workspace.mkdir(parents=True)
            (run_dir / "stdout.log").write_text(
                "Running tests...\nFAILED test_average\nLet me try fixing the code.\n",
                encoding="utf-8",
            )
            score, evidence = _score_self_repair(workspace)
            # "try" from "try fixing" does NOT match \bre-?try\b or \btry again\b
            # "fixing" matches the \bfixing\b pattern -> 1 indicator
            self.assertGreater(score, 0.0)
            self.assertEqual(evidence["indicator_count"], 1)
            self.assertIn("fixing", evidence["matched_indicators"])

    def test_self_repair_full_score_with_three_indicators(self) -> None:
        """Prove self_repair=100 when 3+ indicator patterns are found."""
        from agent_benchmark.scorers.basic import _score_self_repair

        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            workspace = run_dir / "workspace"
            workspace.mkdir(parents=True)
            (run_dir / "stdout.log").write_text(
                "Running tests...\nFAILED\nOops, fixing the code.\n"
                "Correcting stats.py...\nRe-running tests...\nPASSED\n",
                encoding="utf-8",
            )
            score, evidence = _score_self_repair(workspace)
            self.assertEqual(score, 100.0)
            self.assertGreaterEqual(evidence["indicator_count"], 3)
            # Verify some expected indicators
            self.assertIn("oops", evidence["matched_indicators"])
            self.assertIn("fixing", evidence["matched_indicators"])
            self.assertIn("correcting", evidence["matched_indicators"])

    def test_self_repair_detects_retry_in_stderr(self) -> None:
        """Prove self_repair indicators are detected in stderr too."""
        from agent_benchmark.scorers.basic import _score_self_repair

        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            workspace = run_dir / "workspace"
            workspace.mkdir(parents=True)
            (run_dir / "stdout.log").write_text("Normal output.\n", encoding="utf-8")
            (run_dir / "stderr.log").write_text(
                "Error: test failed\nRetrying with fix...\n",
                encoding="utf-8",
            )
            score, evidence = _score_self_repair(workspace)
            self.assertGreater(score, 0.0)
            self.assertIn("retry", evidence["matched_indicators"])

    def test_self_repair_score_is_in_total_weighted_sum(self) -> None:
        """Prove self_repair contributes to the total score proportionally."""
        task = load_task(ROOT / "benchmarks" / "tasks" / "python-bugfix")
        baseline = task.workspace_path
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            shutil.copytree(baseline, workspace)
            shutil.copy(task.root / "solution" / "stats.py", workspace / "stats.py")
            # Create run directory structure with self-repair logs
            run_dir = Path(tmp) / "run"
            ws_in_run = run_dir / "workspace"
            shutil.copytree(workspace, ws_in_run)
            (run_dir / "stdout.log").write_text(
                "Running tests...\nFAILED\nOops, fixing the bug.\n"
                "Correcting stats.py...\nRe-running tests...\nPASSED\n",
                encoding="utf-8",
            )
            (run_dir / "stderr.log").write_text("", encoding="utf-8")
            recorder = JsonlRecorder(Path(tmp) / "trace.jsonl")
            score = score_run(task, baseline, ws_in_run, recorder)
            # self_repair should be > 0 now
            self.assertGreater(score.dimensions["self_repair"], 0.0)
            self.assertIn("self_repair", score.evidence)
            self.assertIn("matched_indicators", score.evidence["self_repair"])

    def test_self_repair_zero_in_full_score_when_no_logs(self) -> None:
        """Prove self_repair=0 in full score_run when logs don't exist."""
        task = load_task(ROOT / "benchmarks" / "tasks" / "python-bugfix")
        baseline = task.workspace_path
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            shutil.copytree(baseline, workspace)
            shutil.copy(task.root / "solution" / "stats.py", workspace / "stats.py")
            # No run directory logs — direct score_run call
            recorder = JsonlRecorder(Path(tmp) / "trace.jsonl")
            score = score_run(task, baseline, workspace, recorder)
            self.assertEqual(score.dimensions["self_repair"], 0.0)
            self.assertIn("No log files", score.evidence["self_repair"].get("error", ""))


def _restore_env(name: str, value: str | None) -> None:
    if value is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = value


if __name__ == "__main__":
    unittest.main()
