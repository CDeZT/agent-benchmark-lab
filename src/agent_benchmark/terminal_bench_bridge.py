"""Bridge one Terminal-Bench pilot task through the official ``tb run`` harness.

Terminal-Bench scores must stay on a separate track from SWE-bench repository
issues. This module never invents a local score: it only plans or invokes the
upstream CLI and preserves raw official output under ``runs/``.
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

from agent_benchmark.authoritative import load_authoritative_corpora, preflight_authoritative_corpora
from agent_benchmark.authoritative_pilot import load_authoritative_pilot
from agent_benchmark.runner.container import ensure_docker_ready


# Map project adapter names to Terminal-Bench built-in agent identifiers.
ADAPTER_TO_TB_AGENT = {
    "opencode": "opencode",
    "claude-code": "claude-code",
}


@dataclass(frozen=True)
class TerminalBenchBridgeConfig:
    pilot_file: Path
    registry_path: Path
    runs_dir: Path
    instance_id: str
    adapter: str
    model: str = "unspecified"
    dataset: str = "terminal-bench-core==0.1.1"
    bridge_dir: Path | None = None
    agent_timeout_multiplier: float = 1.0


def prepare_terminal_bench_bridge(config: TerminalBenchBridgeConfig) -> dict[str, Any]:
    """Return a no-cost plan for one selected Terminal-Bench pilot task."""
    selected, corpus, tb_agent = _selected_task_and_agent(config)
    return {
        "pilot_id": _pilot_id(config.pilot_file),
        "instance_id": config.instance_id,
        "selection_role": selected["selection_role"],
        "adapter": config.adapter,
        "tb_agent": tb_agent,
        "model": config.model,
        "dataset": config.dataset,
        "official_evaluator": corpus.official_evaluator,
        "expected_difficulty": selected.get("expected_difficulty"),
        "expected_category": selected.get("expected_category"),
        "expected_max_agent_timeout_sec": selected.get("expected_max_agent_timeout_sec"),
        "command_preview": _tb_command(config, tb_agent, Path("runs/terminal-bench-bridge-preview"), "preview"),
        "warning": (
            "This command is a plan only. Execute explicitly to invoke the official "
            "Terminal-Bench harness and Docker sandbox. Results must not be merged "
            "with SWE-bench repository-issue scores."
        ),
    }


def run_terminal_bench_bridge(config: TerminalBenchBridgeConfig) -> dict[str, Any]:
    """Run or resume one Terminal-Bench pilot task through ``tb run``."""
    selected, corpus, tb_agent = _selected_task_and_agent(config)
    ensure_docker_ready()
    tb_path = shutil.which("tb")
    if not tb_path:
        raise FileNotFoundError("Terminal-Bench CLI 'tb' is not on PATH.")

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
            "track": "terminal-bench",
            "config": _serializable_config(config),
            "pilot_id": _pilot_id(config.pilot_file),
            "instance_id": config.instance_id,
            "selection_role": selected["selection_role"],
            "tb_agent": tb_agent,
            "official_evaluator": corpus.official_evaluator,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "stages": {},
        }
        _write_json(manifest_path, manifest)

    meta_path = bridge_dir / "task_selection.json"
    if not meta_path.exists():
        _write_json(
            meta_path,
            {
                "instance_id": config.instance_id,
                "selection_role": selected["selection_role"],
                "expected_difficulty": selected.get("expected_difficulty"),
                "expected_category": selected.get("expected_category"),
                "expected_max_agent_timeout_sec": selected.get("expected_max_agent_timeout_sec"),
                "dataset": config.dataset,
                "source_commit": _pilot_source_commit(config.pilot_file),
            },
        )
        _mark_stage(manifest_path, manifest, "selection", {"path": str(meta_path)})

    summary_path = bridge_dir / "official_summary.json"
    if summary_path.exists() and json.loads(summary_path.read_text(encoding="utf-8")).get("completed"):
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    else:
        official_dir = bridge_dir / "official_tb_run"
        official_dir.mkdir(parents=True, exist_ok=True)
        run_id = bridge_dir.name
        command = _tb_command(config, tb_agent, official_dir, run_id)
        command[0] = tb_path
        env = os.environ.copy()
        # Keep host credentials available to built-in agents that need them.
        try:
            completed = subprocess.run(
                command,
                cwd=bridge_dir,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                env=env,
            )
        except OSError as exc:
            summary = {
                "official_evaluator": "tb run",
                "exit_code": None,
                "classification": "evaluator_invocation_error",
                "scorable": False,
                "completed": False,
                "resolved": None,
                "error": str(exc),
                "command": command,
            }
            _write_json(summary_path, summary)
            (official_dir / "stdout.log").write_text("", encoding="utf-8")
            (official_dir / "stderr.log").write_text(str(exc), encoding="utf-8")
            _mark_stage(
                manifest_path,
                manifest,
                "official_evaluator",
                {"command": command, "exit_code": None, "error": str(exc), "summary_path": str(summary_path)},
            )
        else:
            (official_dir / "stdout.log").write_text(completed.stdout, encoding="utf-8")
            (official_dir / "stderr.log").write_text(completed.stderr, encoding="utf-8")
            summary = _official_summary(official_dir, run_id, config.instance_id, completed.returncode, command)
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
    elif summary.get("completed"):
        manifest["status"] = "official_evaluation_complete"
    else:
        manifest["status"] = "official_evaluation_incomplete"
    manifest["official_evaluator_evidence"] = str(summary_path)
    manifest["selection_role"] = selected["selection_role"]
    manifest["updated_at"] = datetime.now(timezone.utc).isoformat()
    _write_json(manifest_path, manifest)
    return {"bridge_dir": str(bridge_dir), "manifest": manifest, "official_summary": summary}


def _selected_task_and_agent(config: TerminalBenchBridgeConfig) -> tuple[dict[str, Any], Any, str]:
    pilot = load_authoritative_pilot(config.pilot_file, _pilot_id(config.pilot_file))
    if pilot.get("corpus_id") != "terminal-bench-core":
        raise ValueError("Terminal-Bench bridge requires a terminal-bench-core pilot.")
    selected = next((item for item in pilot["instances"] if item["instance_id"] == config.instance_id), None)
    if selected is None:
        raise ValueError(f"Instance '{config.instance_id}' is not selected by pilot '{pilot['id']}'.")
    if config.adapter not in ADAPTER_TO_TB_AGENT:
        raise ValueError(
            f"Adapter '{config.adapter}' is not mapped to a Terminal-Bench agent. "
            f"Supported: {', '.join(sorted(ADAPTER_TO_TB_AGENT))}."
        )
    tb_agent = ADAPTER_TO_TB_AGENT[config.adapter]
    corpora = load_authoritative_corpora(config.registry_path)
    corpus = next(item for item in corpora if item.corpus_id == "terminal-bench-core")
    preflight = preflight_authoritative_corpora(config.registry_path, corpus_id="terminal-bench-core")
    if preflight["execution_ready_count"] != 1:
        raise RuntimeError("Terminal-Bench authoritative preflight is not execution-ready.")
    return selected, corpus, tb_agent


def _pilot_id(pilot_file: Path) -> str:
    data = json.loads(pilot_file.read_text(encoding="utf-8"))
    selected = [item for item in data.get("pilots", []) if item.get("corpus_id") == "terminal-bench-core"]
    if len(selected) != 1:
        raise ValueError("Expected exactly one Terminal-Bench pilot in the configured pilots file.")
    return str(selected[0]["id"])


def _pilot_source_commit(pilot_file: Path) -> str | None:
    data = json.loads(pilot_file.read_text(encoding="utf-8"))
    selected = next(item for item in data.get("pilots", []) if item.get("corpus_id") == "terminal-bench-core")
    return selected.get("source_commit")


def _tb_command(config: TerminalBenchBridgeConfig, tb_agent: str, output_path: Path, run_id: str) -> list[str]:
    command = [
        "tb",
        "run",
        "--dataset",
        config.dataset,
        "--task-id",
        config.instance_id,
        "--agent",
        tb_agent,
        "--output-path",
        str(output_path.absolute()),
        "--run-id",
        run_id,
        "--no-upload-results",
    ]
    if config.model and config.model != "unspecified":
        command.extend(["--model", config.model])
    if config.agent_timeout_multiplier and config.agent_timeout_multiplier != 1.0:
        command.extend(["--global-timeout-multiplier", str(config.agent_timeout_multiplier)])
    return command


def _official_summary(
    official_dir: Path,
    run_id: str,
    instance_id: str,
    exit_code: int,
    command: list[str],
) -> dict[str, Any]:
    """Classify Terminal-Bench output without inventing scores.

    Terminal-Bench writes run directories with results JSON. Layout can vary by
    version, so we search conservatively for known result files and only mark
    completed when an explicit is_resolved/accuracy field is present.
    """
    result_files = sorted(official_dir.rglob("results.json")) + sorted(official_dir.rglob("result.json"))
    result_payload: dict[str, Any] | None = None
    result_path: Path | None = None
    for path in result_files:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict):
            result_payload = payload
            result_path = path
            break

    resolved: bool | None = None
    if isinstance(result_payload, dict):
        if "is_resolved" in result_payload:
            resolved = bool(result_payload["is_resolved"])
        elif "resolved" in result_payload:
            resolved = bool(result_payload["resolved"])
        elif isinstance(result_payload.get("results"), list):
            for item in result_payload["results"]:
                if isinstance(item, dict) and item.get("task_id") == instance_id:
                    if "is_resolved" in item:
                        resolved = bool(item["is_resolved"])
                    elif "resolved" in item:
                        resolved = bool(item["resolved"])
                    break
        elif isinstance(result_payload.get("tasks"), dict):
            task_item = result_payload["tasks"].get(instance_id)
            if isinstance(task_item, dict):
                if "is_resolved" in task_item:
                    resolved = bool(task_item["is_resolved"])
                elif "resolved" in task_item:
                    resolved = bool(task_item["resolved"])

    if exit_code != 0 and resolved is None:
        classification = "evaluator_invocation_error"
    elif resolved is True:
        classification = "resolved"
    elif resolved is False:
        classification = "not_resolved"
    else:
        classification = "evaluator_output_missing"

    completed = classification in {"resolved", "not_resolved"}
    return {
        "official_evaluator": "tb run",
        "track": "terminal-bench",
        "exit_code": exit_code,
        "classification": classification,
        "scorable": completed,
        "completed": completed,
        "resolved": resolved,
        "instance_id": instance_id,
        "run_id": run_id,
        "result_path": str(result_path) if result_path else None,
        "result": result_payload,
        "command": command,
        "note": "Terminal-Bench results must not be merged into SWE-bench repository-issue rankings.",
    }


def _new_bridge_dir(runs_dir: Path, instance_id: str) -> Path:
    safe = instance_id.replace("/", "_").replace(".", "-")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return runs_dir / f"terminal-bench-bridge-{safe}-{stamp}-{uuid.uuid4().hex[:8]}"


def _serializable_config(config: TerminalBenchBridgeConfig) -> dict[str, Any]:
    data = asdict(config)
    return {key: str(value) if isinstance(value, Path) else value for key, value in data.items()}


def _validate_resume_manifest(manifest: dict[str, Any], config: TerminalBenchBridgeConfig) -> None:
    saved = manifest.get("config", {})
    for field in ("instance_id", "adapter", "model", "dataset"):
        if str(saved.get(field)) != str(getattr(config, field)):
            raise ValueError(f"Terminal-Bench bridge resume configuration differs for '{field}'.")


def _mark_stage(manifest_path: Path, manifest: dict[str, Any], name: str, details: dict[str, Any]) -> None:
    stages = manifest.setdefault("stages", {})
    stages[name] = {"completed_at": datetime.now(timezone.utc).isoformat(), **details}
    manifest["updated_at"] = datetime.now(timezone.utc).isoformat()
    _write_json(manifest_path, manifest)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
