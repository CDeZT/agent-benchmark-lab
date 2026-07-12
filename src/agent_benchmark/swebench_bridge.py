"""Bridge a real harness patch to the official SWE-bench evaluator.

The local benchmark runner deliberately does not execute ``external_frozen``
records.  This module owns the separate, auditable lifecycle required for a
real SWE-bench result: freeze exact upstream metadata, create a clean checkout,
let one configured harness produce a patch, then invoke the upstream evaluator.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
from typing import Any
import uuid

from agent_benchmark.adapters import adapter_by_name
from agent_benchmark.authoritative import load_authoritative_corpora, preflight_authoritative_corpora
from agent_benchmark.authoritative_pilot import load_authoritative_pilot
from agent_benchmark.parsers import parse_harness_output
from agent_benchmark.recorders import JsonlRecorder
from agent_benchmark.runner import ExperimentConfig
from agent_benchmark.runner.container import ensure_docker_ready
from agent_benchmark.runner.profiles import profile_instruction_suffix
from agent_benchmark.task_schema import TaskSpec


@dataclass(frozen=True)
class SWEbenchBridgeConfig:
    pilot_file: Path
    registry_path: Path
    runs_dir: Path
    instance_id: str
    adapter: str
    model: str = "unspecified"
    budget_profile: str = "open_ended"
    evaluator_timeout_seconds: int = 1800
    max_workers: int = 1
    namespace: str = ""
    bridge_dir: Path | None = None


def prepare_swebench_bridge(config: SWEbenchBridgeConfig) -> dict[str, Any]:
    """Return a no-cost plan for one selected authoritative SWE-bench instance."""
    selected, corpus, interpreter = _selected_instance_and_evaluator(config)
    return {
        "pilot_id": _pilot_id(config.pilot_file),
        "instance_id": config.instance_id,
        "selection_role": selected["selection_role"],
        "adapter": config.adapter,
        "model": config.model,
        "dataset": corpus.dataset,
        "official_evaluator": corpus.official_evaluator,
        "evaluator_interpreter": str(interpreter),
        "namespace": config.namespace,
        "max_workers": config.max_workers,
        "evaluator_timeout_seconds": config.evaluator_timeout_seconds,
        "execution_requires": [
            "a clean checkout at the frozen base commit",
            "a non-empty harness-generated git patch",
            "the official SWE-bench Docker evaluator",
        ],
        "warning": "This command is a plan only. Execute explicitly to invoke a harness and build official evaluator images.",
    }


def run_swebench_bridge(config: SWEbenchBridgeConfig) -> dict[str, Any]:
    """Run or resume a single-instance SWE-bench bridge.

    The bridge is intentionally one instance at a time.  Each stage persists
    evidence below ``runs/`` so a failed evaluator image build or interrupted
    harness call can resume without generating another patch.
    """
    config = _validated_config(config)
    selected, corpus, interpreter = _selected_instance_and_evaluator(config)
    ensure_docker_ready()
    bridge_dir = config.bridge_dir or _new_bridge_dir(config.runs_dir, config.instance_id)
    bridge_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = bridge_dir / "bridge_manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        _validate_resume_manifest(manifest, config)
    else:
        manifest = {
            "schema_version": 1,
            "bridge_id": bridge_dir.name,
            "status": "in_progress",
            "config": _serializable_config(config),
            "pilot_id": _pilot_id(config.pilot_file),
            "instance_id": config.instance_id,
            "selection_role": selected["selection_role"],
            "official_evaluator": corpus.official_evaluator,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "stages": {},
        }
        _write_json(manifest_path, manifest)

    snapshot_path = bridge_dir / "upstream_instance.json"
    if snapshot_path.exists():
        instance_snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    else:
        instance_snapshot = _fetch_instance(interpreter, corpus.dataset, config.instance_id)
        _validate_snapshot_against_selection(instance_snapshot, selected)
        _write_json(snapshot_path, instance_snapshot)
        _mark_stage(manifest_path, manifest, "upstream_metadata", {"path": str(snapshot_path)})

    workspace = bridge_dir / "workspace"
    instance = instance_snapshot["instance"]
    if not _workspace_at_commit(workspace, str(instance["base_commit"])):
        if workspace.exists():
            shutil.rmtree(workspace)
        checkout_log = bridge_dir / "workspace_setup.log"
        try:
            _clone_checkout(str(instance["repo"]), str(instance["base_commit"]), workspace, checkout_log)
        except Exception as exc:
            manifest["status"] = "workspace_setup_failed"
            manifest["last_error"] = str(exc)
            manifest["updated_at"] = datetime.now(timezone.utc).isoformat()
            _write_json(manifest_path, manifest)
            raise
        _mark_stage(
            manifest_path,
            manifest,
            "workspace",
            {"path": str(workspace), "base_commit": instance["base_commit"], "setup_log": str(checkout_log)},
        )

    patch_path = bridge_dir / "model.patch"
    prediction_path = bridge_dir / "predictions.jsonl"
    if not patch_path.exists():
        adapter_result = _run_harness(config, instance_snapshot, workspace, bridge_dir)
        patch = _workspace_patch(workspace)
        if not patch.strip():
            _mark_stage(
                manifest_path,
                manifest,
                "harness",
                {"exit_code": adapter_result["exit_code"], "patch_generated": False},
            )
            manifest["status"] = "patch_missing"
            _write_json(manifest_path, manifest)
            raise RuntimeError("Harness produced no git patch; official evaluation was not started.")
        patch_path.write_text(patch, encoding="utf-8")
        _mark_stage(manifest_path, manifest, "harness", {**adapter_result, "patch_generated": True, "patch_path": str(patch_path)})
    else:
        patch = patch_path.read_text(encoding="utf-8")
        if not patch.strip():
            raise RuntimeError(f"Saved patch is empty: {patch_path}")

    prediction = _prediction_record(config, patch)
    prediction_path.write_text(json.dumps(prediction, ensure_ascii=False) + "\n", encoding="utf-8")
    _mark_stage(manifest_path, manifest, "prediction", {"path": str(prediction_path), "model_name_or_path": prediction["model_name_or_path"]})

    official_dir = bridge_dir / "official_evaluator"
    summary_path = bridge_dir / "official_summary.json"
    if summary_path.exists() and json.loads(summary_path.read_text(encoding="utf-8")).get("completed"):
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    else:
        official_dir.mkdir(parents=True, exist_ok=True)
        command = _evaluator_command(config, interpreter, corpus.dataset, prediction_path, bridge_dir.name)
        try:
            completed = subprocess.run(
                command,
                cwd=official_dir,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
        except OSError as exc:
            completed = None
            (official_dir / "stdout.log").write_text("", encoding="utf-8")
            (official_dir / "stderr.log").write_text(str(exc), encoding="utf-8")
            summary = {
                "official_evaluator": "swebench.harness.run_evaluation",
                "exit_code": None,
                "classification": "evaluator_invocation_error",
                "scorable": False,
                "completed": False,
                "resolved": None,
                "error": str(exc),
            }
            _write_json(summary_path, summary)
            _mark_stage(
                manifest_path,
                manifest,
                "official_evaluator",
                {"command": command, "exit_code": None, "summary_path": str(summary_path), "error": str(exc)},
            )
        else:
            (official_dir / "stdout.log").write_text(completed.stdout, encoding="utf-8")
            (official_dir / "stderr.log").write_text(completed.stderr, encoding="utf-8")
            summary = _official_summary(official_dir, bridge_dir.name, prediction, completed.returncode)
            _write_json(summary_path, summary)
            _mark_stage(
                manifest_path,
                manifest,
                "official_evaluator",
                {"command": command, "exit_code": completed.returncode, "summary_path": str(summary_path)},
            )

    classification = summary.get("classification", "evaluator_output_missing")
    if classification == "evaluator_error":
        manifest["status"] = "official_evaluator_error"
    elif classification == "evaluator_invocation_error":
        manifest["status"] = "official_evaluator_invocation_error"
    elif summary["completed"]:
        manifest["status"] = "official_evaluation_complete"
    else:
        manifest["status"] = "official_evaluation_incomplete"
    manifest["official_evaluator_evidence"] = str(summary_path)
    manifest["updated_at"] = datetime.now(timezone.utc).isoformat()
    _write_json(manifest_path, manifest)
    return {"bridge_dir": str(bridge_dir), "manifest": manifest, "official_summary": summary}


def _validated_config(config: SWEbenchBridgeConfig) -> SWEbenchBridgeConfig:
    if config.evaluator_timeout_seconds <= 0:
        raise ValueError("evaluator_timeout_seconds must be positive")
    if config.max_workers != 1:
        raise ValueError("SWE-bench bridge intentionally permits exactly one evaluator worker per run.")
    ExperimentConfig(
        adapter=config.adapter,
        model=config.model,
        budget_profile=config.budget_profile,
        repetitions=1,
        runs_dir=config.runs_dir,
    ).validate()
    return config


def _selected_instance_and_evaluator(config: SWEbenchBridgeConfig) -> tuple[dict[str, Any], Any, Path]:
    pilot = load_authoritative_pilot(config.pilot_file, _pilot_id(config.pilot_file))
    if pilot.get("corpus_id") != "swe-bench-verified":
        raise ValueError("SWE-bench bridge requires a swe-bench-verified pilot.")
    selected = next((item for item in pilot["instances"] if item["instance_id"] == config.instance_id), None)
    if selected is None:
        raise ValueError(f"Instance '{config.instance_id}' is not selected by pilot '{pilot['id']}'.")
    corpora = load_authoritative_corpora(config.registry_path)
    corpus = next(item for item in corpora if item.corpus_id == "swe-bench-verified")
    requirement = next(item for item in corpus.tool_requirements if item["kind"] == "python_module" and item["value"] == "swebench")
    interpreter = Path(requirement["interpreter"])
    if not interpreter.is_absolute():
        interpreter = config.registry_path.parent.parent / interpreter
    # ``resolve`` would dereference a virtualenv's python symlink to its base
    # interpreter and lose the installed swebench package. Keep the link, but
    # make it independent of the evaluator report directory's current cwd.
    interpreter = interpreter.absolute()
    if not interpreter.is_file():
        raise FileNotFoundError(f"SWE-bench evaluator interpreter is unavailable: {interpreter}")
    preflight = preflight_authoritative_corpora(config.registry_path, corpus_id="swe-bench-verified")
    if preflight["execution_ready_count"] != 1:
        raise RuntimeError("SWE-bench authoritative preflight is not execution-ready.")
    return selected, corpus, interpreter


def _pilot_id(pilot_file: Path) -> str:
    data = json.loads(pilot_file.read_text(encoding="utf-8"))
    pilots = data.get("pilots", [])
    selected = [item for item in pilots if item.get("corpus_id") == "swe-bench-verified"]
    if len(selected) != 1:
        raise ValueError("Expected exactly one SWE-bench pilot in the configured pilots file.")
    return str(selected[0]["id"])


def _fetch_instance(interpreter: Path, dataset: str, instance_id: str) -> dict[str, Any]:
    script = """
import json, sys
from datasets import load_dataset
from huggingface_hub import HfApi
dataset, instance_id = sys.argv[1:]
rows = load_dataset(dataset, split='test')
for row in rows:
    if row['instance_id'] == instance_id:
        print(json.dumps({'dataset': dataset, 'resolved_revision': HfApi().dataset_info(dataset).sha, 'instance': dict(row)}, ensure_ascii=False, sort_keys=True))
        break
else:
    raise SystemExit('missing instance id: ' + instance_id)
"""
    completed = subprocess.run(
        [str(interpreter), "-c", script, dataset, instance_id],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=180,
    )
    if completed.returncode:
        raise RuntimeError(f"Failed to fetch SWE-bench instance metadata: {completed.stderr[-2000:]}")
    payload = json.loads(completed.stdout)
    if not isinstance(payload, dict) or not isinstance(payload.get("instance"), dict):
        raise RuntimeError("SWE-bench metadata command returned an invalid payload.")
    return payload


def _validate_snapshot_against_selection(snapshot: dict[str, Any], selected: dict[str, Any]) -> None:
    instance = snapshot["instance"]
    for expected_key, upstream_key in (("instance_id", "instance_id"), ("expected_difficulty", "difficulty"), ("expected_base_commit", "base_commit")):
        if instance.get(upstream_key) != selected.get(expected_key):
            raise ValueError(f"Upstream metadata drift for {selected['instance_id']}: {upstream_key}")


def _clone_checkout(repo: str, base_commit: str, workspace: Path, log_path: Path | None = None) -> None:
    """Fetch only the frozen commit instead of cloning a repository's history."""
    url = f"https://github.com/{repo}.git"
    workspace.mkdir(parents=True, exist_ok=False)
    _checked_command(["git", "init", str(workspace)], "initialize SWE-bench repository", log_path)
    _checked_command(["git", "-C", str(workspace), "remote", "add", "origin", url], "configure SWE-bench remote", log_path)
    fetch = ["git", "-C", str(workspace), "-c", "protocol.version=2", "fetch", "--depth=1", "--filter=blob:none", "origin", base_commit]
    try:
        _checked_command(fetch, "fetch frozen SWE-bench base commit", log_path)
    except RuntimeError as exc:
        # Some proxies reject Git protocol filters; the exact shallow fetch is
        # still much smaller and more reproducible than a full-history clone.
        if "filter" not in str(exc).lower():
            raise
        _checked_command(fetch[:7] + ["origin", base_commit], "fetch frozen SWE-bench base commit without filter", log_path)
    _checked_command(["git", "-C", str(workspace), "checkout", "--detach", "FETCH_HEAD"], "checkout SWE-bench base commit", log_path)
    _checked_command(["git", "-C", str(workspace), "clean", "-fdx"], "clean SWE-bench checkout", log_path)


def _workspace_at_commit(workspace: Path, base_commit: str) -> bool:
    """Return true only for a complete checkout of the exact frozen revision."""
    if not (workspace / ".git").exists():
        return False
    completed = subprocess.run(
        ["git", "-C", str(workspace), "rev-parse", "--verify", "HEAD"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return completed.returncode == 0 and completed.stdout.strip() == base_commit


def _run_harness(config: SWEbenchBridgeConfig, snapshot: dict[str, Any], workspace: Path, bridge_dir: Path) -> dict[str, Any]:
    instance = snapshot["instance"]
    instruction = (
        "Resolve this SWE-bench issue in the checked-out repository. Work only in the current workspace. "
        "Do not commit, reset, or modify benchmark/evaluator metadata. Leave the final implementation as a git diff.\n\n"
        f"Repository: {instance['repo']}\nBase commit: {instance['base_commit']}\n"
        f"Upstream difficulty label: {instance.get('difficulty', 'unknown')}\n\n"
        f"Issue:\n{instance['problem_statement']}"
    )
    experiment = ExperimentConfig(
        adapter=config.adapter,
        model=config.model,
        budget_profile=config.budget_profile,
        repetitions=1,
        runs_dir=config.runs_dir,
        label=f"swe-bench:{config.instance_id}",
    )
    task = TaskSpec(
        task_id=config.instance_id,
        title=f"SWE-bench: {config.instance_id}",
        instruction=instruction + profile_instruction_suffix(experiment.profile),
        capabilities=["bugfix", "code_understanding", "debugging"],
        domains=["python", "software_engineering"],
        provenance={"type": "external_frozen", "source_benchmark": "SWE-bench", "source_id": config.instance_id},
        workspace="workspace",
        root=bridge_dir,
    )
    recorder = JsonlRecorder(bridge_dir / "harness_trace.jsonl")
    adapter = adapter_by_name(config.adapter)
    injected = {
        "AGENT_BENCH_MODEL": experiment.invocation_model,
        "AGENT_BENCH_CANONICAL_MODEL": experiment.model,
        "AGENT_BENCH_BUDGET_PROFILE": experiment.budget_profile,
        "AGENT_BENCH_LABEL": experiment.label,
        "AGENT_BENCH_BUDGET_MAX_ATTEMPTS": str(experiment.profile.max_attempts or ""),
        "AGENT_BENCH_BUDGET_MAX_SECONDS": str(experiment.profile.max_duration_seconds or ""),
    }
    previous = {key: os.environ.get(key) for key in injected}
    os.environ.update(injected)
    try:
        result = adapter.run(task, workspace, recorder)
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    (bridge_dir / "harness_stdout.log").write_text(result.stdout, encoding="utf-8")
    (bridge_dir / "harness_stderr.log").write_text(result.stderr, encoding="utf-8")
    evidence = parse_harness_output(config.adapter, result.stdout, result.stderr)
    return {
        "adapter": config.adapter,
        "exit_code": result.exit_code,
        "duration_seconds": result.duration_seconds,
        "detected_model": evidence.model,
        "tool_call_count": len(evidence.tool_calls),
        "cost_usd": evidence.cost_usd,
        "input_tokens": evidence.input_tokens,
        "output_tokens": evidence.output_tokens,
    }


def _workspace_patch(workspace: Path) -> str:
    _checked_command(["git", "-C", str(workspace), "add", "--intent-to-add", "."], "stage untracked files for diff")
    completed = subprocess.run(
        ["git", "-C", str(workspace), "diff", "--binary", "--no-ext-diff"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode:
        raise RuntimeError(f"Unable to produce harness patch: {completed.stderr[-1000:]}")
    return completed.stdout


def _prediction_record(config: SWEbenchBridgeConfig, patch: str) -> dict[str, str]:
    return {
        "instance_id": config.instance_id,
        "model_name_or_path": f"agent-benchmark/{config.adapter}/{config.model}",
        "model_patch": patch,
    }


def _evaluator_command(
    config: SWEbenchBridgeConfig,
    interpreter: Path,
    dataset: str,
    prediction_path: Path,
    run_id: str,
) -> list[str]:
    return [
        str(interpreter.absolute()),
        "-m",
        "swebench.harness.run_evaluation",
        "--dataset_name",
        dataset,
        "--split",
        "test",
        "--instance_ids",
        config.instance_id,
        "--predictions_path",
        str(prediction_path.absolute()),
        "--max_workers",
        str(config.max_workers),
        "--timeout",
        str(config.evaluator_timeout_seconds),
        "--run_id",
        run_id,
        "--namespace",
        config.namespace,
        "--cache_level",
        "env",
        "--clean",
        "false",
    ]


def _official_summary(official_dir: Path, run_id: str, prediction: dict[str, str], exit_code: int) -> dict[str, Any]:
    report_candidates = sorted(official_dir.rglob("report.json"))
    instance_report = next((path for path in report_candidates if prediction["instance_id"] in path.parts), None)
    instance_payload: dict[str, Any] | None = None
    if instance_report is not None:
        try:
            instance_payload = json.loads(instance_report.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            instance_payload = None
    run_reports = sorted(official_dir.glob(f"*.{run_id}.json"))
    run_payload: dict[str, Any] | None = None
    if run_reports:
        try:
            run_payload = json.loads(run_reports[-1].read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            run_payload = None
    result = instance_payload.get(prediction["instance_id"], {}) if instance_payload else {}
    error_ids = run_payload.get("error_ids", []) if isinstance(run_payload, dict) else []
    if exit_code != 0:
        classification = "evaluator_invocation_error"
    elif prediction["instance_id"] in error_ids:
        classification = "evaluator_error"
    elif result.get("resolved") is True:
        classification = "resolved"
    elif instance_payload and prediction["instance_id"] in instance_payload:
        classification = "not_resolved"
    else:
        classification = "evaluator_output_missing"
    completed = classification in {"resolved", "not_resolved"}
    return {
        "official_evaluator": "swebench.harness.run_evaluation",
        "exit_code": exit_code,
        "classification": classification,
        "scorable": completed,
        "completed": completed,
        "resolved": result.get("resolved") if result else None,
        "error_instance_ids": error_ids,
        "instance_report": str(instance_report) if instance_report else None,
        "run_report": str(run_reports[-1]) if run_reports else None,
        "run_report_summary": run_payload,
        "report": result or None,
    }


def _new_bridge_dir(runs_dir: Path, instance_id: str) -> Path:
    safe_instance = instance_id.replace("/", "_").replace("__", "-")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return runs_dir / f"swebench-bridge-{safe_instance}-{stamp}-{uuid.uuid4().hex[:8]}"


def _serializable_config(config: SWEbenchBridgeConfig) -> dict[str, Any]:
    data = asdict(config)
    return {key: str(value) if isinstance(value, Path) else value for key, value in data.items()}


def _validate_resume_manifest(manifest: dict[str, Any], config: SWEbenchBridgeConfig) -> None:
    saved = manifest.get("config", {})
    for field in ("instance_id", "adapter", "model", "budget_profile", "evaluator_timeout_seconds", "namespace"):
        if str(saved.get(field)) != str(getattr(config, field)):
            raise ValueError(f"Bridge resume configuration differs for '{field}'.")


def _mark_stage(manifest_path: Path, manifest: dict[str, Any], name: str, details: dict[str, Any]) -> None:
    manifest.setdefault("stages", {})[name] = {"completed_at": datetime.now(timezone.utc).isoformat(), **details}
    manifest["updated_at"] = datetime.now(timezone.utc).isoformat()
    _write_json(manifest_path, manifest)


def _checked_command(command: list[str], action: str, log_path: Path | None = None) -> None:
    completed = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if log_path is not None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write("$ " + " ".join(command) + "\n")
            handle.write(completed.stdout)
            handle.write(completed.stderr)
            handle.write("\n")
    if completed.returncode:
        suffix = f" See {log_path}." if log_path is not None else ""
        raise RuntimeError(f"Failed to {action}:{suffix} {completed.stderr[-2000:]}")


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
