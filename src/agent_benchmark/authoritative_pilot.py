from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen
import uuid

from agent_benchmark.authoritative import load_authoritative_corpora


def load_authoritative_pilot(path: Path, pilot_id: str) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema_version") != 1 or not isinstance(data.get("pilots"), list):
        raise ValueError("Authoritative pilot registry must be a schema_version 1 object with a pilots list.")
    matches = [pilot for pilot in data["pilots"] if isinstance(pilot, dict) and pilot.get("id") == pilot_id]
    if len(matches) != 1:
        raise ValueError(f"Unknown or duplicate authoritative pilot '{pilot_id}'.")
    pilot = matches[0]
    if pilot.get("status") != "selected_not_imported":
        raise ValueError(f"Pilot '{pilot_id}' must be selected_not_imported before freezing metadata.")
    instances = pilot.get("instances")
    if not isinstance(instances, list) or not instances:
        raise ValueError(f"Pilot '{pilot_id}' needs at least one selected instance.")
    if any(not isinstance(item, dict) or not str(item.get("instance_id", "")).strip() for item in instances):
        raise ValueError(f"Pilot '{pilot_id}' has an invalid selected instance.")
    return pilot


def freeze_swebench_pilot(pilot_file: Path, pilot_id: str, registry_path: Path, runs_dir: Path) -> dict[str, Any]:
    """Freeze selected upstream metadata before any harness is allowed to solve it."""
    pilot = load_authoritative_pilot(pilot_file, pilot_id)
    if pilot.get("corpus_id") != "swe-bench-verified":
        raise ValueError("Only swe-bench-verified pilots are supported by this freezer.")
    corpus = next((item for item in load_authoritative_corpora(registry_path) if item.corpus_id == pilot["corpus_id"]), None)
    if corpus is None:
        raise ValueError(f"Pilot '{pilot_id}' references an unknown corpus.")
    requirement = next((item for item in corpus.tool_requirements if item["kind"] == "python_module" and item["value"] == "swebench"), None)
    if requirement is None or "interpreter" not in requirement:
        raise ValueError("SWE-bench pilot needs a dedicated swebench interpreter in the authoritative registry.")
    interpreter = Path(requirement["interpreter"])
    if not interpreter.is_absolute():
        interpreter = registry_path.parent.parent / interpreter
    if not interpreter.is_file():
        raise FileNotFoundError(f"SWE-bench evaluator interpreter is unavailable: {interpreter}")

    selected = pilot["instances"]
    snapshot = _fetch_swebench_metadata(interpreter, corpus.dataset, selected)
    _validate_snapshot(snapshot, selected)
    canonical = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    snapshot_hash = hashlib.sha256(canonical).hexdigest()
    output_dir = runs_dir / f"authoritative-pilot-{pilot_id}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "upstream_snapshot.json").write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest = {
        "pilot_id": pilot_id,
        "corpus_id": corpus.corpus_id,
        "status": "metadata_frozen_not_imported",
        "selection_policy": pilot["selection_policy"],
        "instance_count": len(selected),
        "snapshot_sha256": snapshot_hash,
        "upstream_snapshot": str(output_dir / "upstream_snapshot.json"),
        "official_evaluator": corpus.official_evaluator,
        "next_step": "Generate per-instance harness patches, then evaluate them with the upstream SWE-bench evaluator.",
    }
    (output_dir / "pilot_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return {**manifest, "output_dir": str(output_dir)}


def freeze_terminal_bench_pilot(pilot_file: Path, pilot_id: str, registry_path: Path, runs_dir: Path) -> dict[str, Any]:
    """Freeze task YAML from an immutable Terminal-Bench registry commit."""
    pilot = load_authoritative_pilot(pilot_file, pilot_id)
    if pilot.get("corpus_id") != "terminal-bench-core":
        raise ValueError("Only terminal-bench-core pilots are supported by this freezer.")
    corpus = next((item for item in load_authoritative_corpora(registry_path) if item.corpus_id == pilot["corpus_id"]), None)
    if corpus is None:
        raise ValueError(f"Pilot '{pilot_id}' references an unknown corpus.")
    source_commit = str(pilot.get("source_commit", ""))
    if not source_commit:
        raise ValueError(f"Terminal-Bench pilot '{pilot_id}' needs source_commit.")
    instances: list[dict[str, Any]] = []
    for selected in pilot["instances"]:
        task_id = selected["instance_id"]
        url = f"https://raw.githubusercontent.com/laude-institute/terminal-bench/{source_commit}/tasks/{task_id}/task.yaml"
        raw = _fetch_url(url)
        metadata = _task_yaml_metadata(raw)
        for expected_key, metadata_key in (
            ("expected_difficulty", "difficulty"),
            ("expected_category", "category"),
            ("expected_max_agent_timeout_sec", "max_agent_timeout_sec"),
        ):
            if selected.get(expected_key) != metadata.get(metadata_key):
                raise ValueError(f"Terminal-Bench metadata mismatch for {task_id}: {metadata_key}")
        instances.append({"instance_id": task_id, "source_url": url, "sha256": hashlib.sha256(raw.encode()).hexdigest(), "metadata": metadata, "task_yaml": raw})
    snapshot = {"dataset": corpus.dataset, "dataset_version": corpus.dataset_version, "source_commit": source_commit, "instances": instances}
    canonical = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    output_dir = runs_dir / f"authoritative-pilot-{pilot_id}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "upstream_snapshot.json").write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest = {
        "pilot_id": pilot_id,
        "corpus_id": corpus.corpus_id,
        "status": "metadata_frozen_not_imported",
        "selection_policy": pilot["selection_policy"],
        "instance_count": len(instances),
        "snapshot_sha256": hashlib.sha256(canonical).hexdigest(),
        "upstream_snapshot": str(output_dir / "upstream_snapshot.json"),
        "official_evaluator": corpus.official_evaluator,
        "next_step": "Run the selected tasks through the official Terminal-Bench harness without mixing this track with SWE-bench scores.",
        "output_dir": str(output_dir),
    }
    (output_dir / "pilot_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def _fetch_swebench_metadata(interpreter: Path, dataset: str, selected: list[dict[str, Any]]) -> dict[str, Any]:
    script = """
import json, sys
from datasets import load_dataset
from huggingface_hub import HfApi
dataset, selected = sys.argv[1], json.loads(sys.argv[2])
rows = load_dataset(dataset, split='test')
by_id = {row['instance_id']: dict(row) for row in rows}
ids = [item['instance_id'] for item in selected]
missing = [item for item in ids if item not in by_id]
if missing:
    raise SystemExit('missing instance ids: ' + ', '.join(missing))
print(json.dumps({'dataset': dataset, 'resolved_revision': HfApi().dataset_info(dataset).sha, 'instances': [by_id[item] for item in ids]}, ensure_ascii=False, sort_keys=True))
"""
    completed = subprocess.run(
        [str(interpreter), "-c", script, dataset, json.dumps(selected)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=180,
    )
    if completed.returncode:
        raise RuntimeError(f"Failed to fetch SWE-bench pilot metadata: {completed.stderr[-2000:]}")
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"SWE-bench metadata command returned invalid JSON: {completed.stdout[-1000:]}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("instances"), list):
        raise RuntimeError("SWE-bench metadata command returned an invalid payload.")
    return payload


def _validate_snapshot(snapshot: dict[str, Any], selected: list[dict[str, Any]]) -> None:
    instances = snapshot["instances"]
    if len(instances) != len(selected):
        raise ValueError("SWE-bench snapshot instance count does not match pilot selection.")
    for expected, observed in zip(selected, instances, strict=True):
        for key, upstream_key in (("instance_id", "instance_id"), ("expected_difficulty", "difficulty"), ("expected_base_commit", "base_commit")):
            if expected[key] != observed.get(upstream_key):
                raise ValueError(f"SWE-bench metadata mismatch for {expected['instance_id']}: {upstream_key}")


def _fetch_url(url: str) -> str:
    for attempt in range(3):
        try:
            with urlopen(url, timeout=45) as response:  # noqa: S310 - fixed official HTTPS source.
                return response.read().decode("utf-8")
        except URLError:
            if attempt == 2:
                raise
    raise RuntimeError("unreachable")


def _task_yaml_metadata(raw: str) -> dict[str, str]:
    fields = {}
    for line in raw.splitlines():
        for key in ("difficulty", "category", "max_agent_timeout_sec"):
            prefix = key + ":"
            if line.startswith(prefix):
                fields[key] = line[len(prefix):].strip()
    if len(fields) != 3:
        raise ValueError("Terminal-Bench task YAML is missing expected top-level metadata.")
    return fields
