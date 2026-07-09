from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest

from agent_benchmark.adapters import adapter_by_name, available_adapters
from agent_benchmark.audit import AuditOptions, run_audit
from agent_benchmark.doctor import format_doctor, run_doctor
from agent_benchmark.next_agent import load_next_agent_prompt
from agent_benchmark.runner import ExperimentConfig, run_task
from agent_benchmark.scorers import score_run
from agent_benchmark.recorders.jsonl import JsonlRecorder
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
            self.assertEqual(summary["mean_score"], 48.0)
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
                self.assertEqual(summary["mean_score"], 48.0)
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
            self.assertEqual(check_names, ["validate", "real_harness_smoke"])

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


def _restore_env(name: str, value: str | None) -> None:
    if value is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = value


if __name__ == "__main__":
    unittest.main()
