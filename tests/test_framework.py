from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest

from agent_benchmark.adapters import available_adapters
from agent_benchmark.audit import AuditOptions, run_audit
from agent_benchmark.doctor import format_doctor, run_doctor
from agent_benchmark.runner import ExperimentConfig, run_task
from agent_benchmark.status import format_status, load_status
from agent_benchmark.task_schema import load_suite, load_task, validate_all


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

    def test_dummy_run_writes_evidence(self) -> None:
        task = load_task(ROOT / "benchmarks" / "tasks" / "python-bugfix")

        with tempfile.TemporaryDirectory() as tmp:
            summary = run_task(task, ExperimentConfig(adapter="dummy", repetitions=2, runs_dir=Path(tmp)))

            self.assertEqual(summary["repetitions"], 2)
            self.assertEqual(summary["model"], "unspecified")
            self.assertEqual(summary["budget_profile"], "open_ended")
            self.assertEqual(summary["mean_score"], 36.0)
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
                self.assertTrue(result["score"]["evidence"]["test"]["public"]["passed"])
                self.assertTrue(result["score"]["evidence"]["test"]["hidden"]["passed"])

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
                self.assertEqual(summary["mean_score"], 36.0)
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
            self.assertEqual(summary["mean_score"], 40.0)
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
            self.assertEqual(summary["mean_score"], 44.0)
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


def _restore_env(name: str, value: str | None) -> None:
    if value is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = value


if __name__ == "__main__":
    unittest.main()
