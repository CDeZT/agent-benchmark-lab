from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest

from agent_benchmark.adapters import adapter_by_name, available_adapters
from agent_benchmark.adapters.base import AdapterResult
from agent_benchmark.audit import AuditOptions, run_audit
from agent_benchmark.corpus_audit import audit_corpus
from agent_benchmark.doctor import format_doctor, run_doctor
from agent_benchmark.difficulty import analyze_difficulty
from agent_benchmark.next_agent import load_next_agent_prompt
from agent_benchmark.runner import ExperimentConfig, RunResult, run_task
from agent_benchmark.runner.run import _summarize
from agent_benchmark.scorers import ScoreResult, score_run
from agent_benchmark.recorders.jsonl import JsonlRecorder
from agent_benchmark.status import format_status, load_status
from agent_benchmark.task_schema import build_catalog, load_suite, load_task, validate_all
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

        self.assertEqual(catalog["task_count"], 19)
        self.assertEqual(catalog["difficulty_distribution"], {"easy": 3, "medium": 9, "hard": 4, "expert": 3})
        self.assertEqual(catalog["provenance_distribution"]["inspired_by_external"], 1)
        fullstack = next(task for task in catalog["tasks"] if task["id"] == "python-fullstack")
        self.assertEqual(fullstack["environment"], "container_required")
        imaging = next(task for task in catalog["tasks"] if task["id"] == "optics-imaging-pipeline")
        self.assertEqual(imaging["environment"], "container_required")

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
        self.assertEqual(report["summary"], {"passes": 15, "skipped_environment": 4})

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

    def test_container_required_task_cannot_silently_run_locally(self) -> None:
        task = load_task(ROOT / "benchmarks" / "tasks" / "project-generation")

        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(RuntimeError, "requires a containerized environment"):
                run_task(task, ExperimentConfig(adapter="dummy", repetitions=1, runs_dir=Path(tmp)))

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
            )

        self.assertEqual(summary["mean_cost_usd"], 0.02)
        self.assertEqual(summary["mean_input_tokens"], 200)
        self.assertEqual(summary["mean_output_tokens"], 100)
        self.assertEqual(summary["total_tool_calls"], 10)
        self.assertEqual(summary["runs"][0]["cost_usd"], 0.01)
        self.assertEqual(summary["runs"][1]["input_tokens"], 300)

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
                        model="env-model",
                        repetitions=1,
                        runs_dir=Path(tmp),
                    ),
                )
                run_dir = Path(summary["runs"][0]["run_dir"])
                self.assertEqual((run_dir / "workspace" / "model.txt").read_text(encoding="utf-8"), "env-model")
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
            self.assertEqual(summary["mean_score"], 50.0)
            run_dir = Path(summary["runs"][0]["run_dir"])
            result = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
            self.assertEqual(result["score"]["dimensions"]["visual_verification"], 100.0)
            visual_evidence = result["score"]["evidence"]["visual_verification"]
            self.assertEqual(visual_evidence["engine"], "html-static-v1")
            self.assertEqual(len(visual_evidence["checks"]), 3)
            self.assertTrue(all(check["passed"] for check in visual_evidence["checks"]))

    def test_process_planning_scores_when_artifact_exists(self) -> None:
        task = load_task(ROOT / "benchmarks" / "tasks" / "process-planning")

        with tempfile.TemporaryDirectory() as tmp:
            summary = run_task(task, ExperimentConfig(adapter="dummy", repetitions=1, runs_dir=Path(tmp)))
            self.assertEqual(summary["mean_score"], 54.0)
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
        self.assertIn("planned", rendered)
        self.assertIn("public_and_hidden_tests", rendered)

    def test_doctor_outputs_environment_summary(self) -> None:
        summary = run_doctor()
        rendered = format_doctor(summary)

        self.assertIn("command:python3", rendered)
        self.assertIn("opencode", rendered)
        self.assertIn("claude-code", rendered)

    def test_real_harness_adapters_have_default_templates(self) -> None:
        from agent_benchmark.adapters.claude_code import ClaudeCodeAdapter
        from agent_benchmark.adapters.opencode import OpencodeAdapter

        self.assertIn("opencode run", OpencodeAdapter().command_template() or "")
        self.assertIn("claude -p", ClaudeCodeAdapter().command_template() or "")

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
            self.assertEqual(check_names, ["validate", "corpus_quality", "real_harness_smoke"])

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
            self.assertEqual(visual["engine"], "html-static-v1")
            self.assertEqual(len(visual["checks"]), 3)
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
