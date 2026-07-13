"""Low-impact, evidence-backed identity probes for default-model benchmark runs."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import tomllib

from agent_benchmark.parsers import parse_harness_output


@dataclass(frozen=True)
class ModelProbe:
    adapter: str
    status: str
    model: str | None
    cost_usd: float | None
    detail: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "ModelProbe":
        return cls(
            adapter=str(payload.get("adapter", "unknown")),
            status=str(payload.get("status", "unknown")),
            model=str(payload["model"]) if isinstance(payload.get("model"), str) else None,
            cost_usd=float(payload["cost_usd"]) if isinstance(payload.get("cost_usd"), (int, float)) else None,
            detail=str(payload.get("detail", "")),
        )


def load_or_probe_default_model(suite_run_dir: Path, *, adapter: str, requested_model: str) -> ModelProbe:
    """Use one saved probe per suite so resume never spends another identity call."""
    path = suite_run_dir / "model_probe.json"
    if path.is_file():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                return ModelProbe.from_dict(payload)
        except (OSError, json.JSONDecodeError, ValueError):
            pass
    probe = probe_default_model(adapter=adapter, requested_model=requested_model)
    path.write_text(json.dumps(probe.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return probe


def probe_default_model(*, adapter: str, requested_model: str) -> ModelProbe:
    """Identify a dynamic default model without giving the probe workspace access.

    Claude Code exposes the model in its structured ``modelUsage`` result only
    after one inference. The probe therefore has a small, explicit hard budget,
    disables all tools, runs in a temporary directory, and is only used for the
    normal ``unspecified`` default-model mode.
    """
    if requested_model != "unspecified":
        return ModelProbe(adapter, "not_needed", None, None, "An explicit model was requested.")
    if adapter == "codex":
        return _configured_codex_model()
    if adapter == "opencode":
        return _probe_opencode_default()
    if adapter != "claude-code":
        return ModelProbe(adapter, "unsupported", None, None, "This adapter has no safe structured default-model probe yet.")
    if os.environ.get("AGENT_BENCH_CLAUDE_CODE_COMMAND"):
        return ModelProbe(adapter, "custom_command", None, None, "A custom Claude command is configured, so the built-in probe is not assumed equivalent.")
    binary = shutil.which("claude")
    if not binary:
        return ModelProbe(adapter, "unavailable", None, None, "Claude Code is not on PATH.")

    command = [
        binary,
        "-p",
        "--output-format",
        "json",
        "--no-session-persistence",
        "--dangerously-skip-permissions",
        "--tools",
        "",
        "--max-budget-usd",
        "0.05",
        "Reply with READY only. Do not read or modify files.",
    ]
    try:
        with tempfile.TemporaryDirectory(prefix="agent-benchmark-model-probe-") as temporary:
            completed = subprocess.run(
                command,
                cwd=temporary,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=90,
            )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return ModelProbe(adapter, "failed", None, None, f"Probe could not complete: {exc}")

    evidence = parse_harness_output(adapter, completed.stdout, completed.stderr)
    if completed.returncode == 0 and evidence.model:
        return ModelProbe(
            adapter,
            "observed",
            evidence.model,
            evidence.cost_usd,
            "Observed from a tool-disabled, temporary-workspace Claude JSON probe.",
        )
    detail = (completed.stderr or completed.stdout).strip().splitlines()
    return ModelProbe(
        adapter,
        "failed",
        None,
        evidence.cost_usd,
        detail[-1][:300] if detail else f"Claude probe exited {completed.returncode} without a model identity.",
    )


def _configured_codex_model() -> ModelProbe:
    """Read Codex's declared default without representing it as observed output."""
    config_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    config_path = config_home / "config.toml"
    try:
        payload = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return ModelProbe("codex", "unsupported", None, None, "Codex default model is not declared in its readable config.")
    model = payload.get("model")
    if isinstance(model, str) and model.strip():
        return ModelProbe("codex", "configured", model.strip(), None, f"Declared in {config_path}; task output must still verify it.")
    return ModelProbe("codex", "unsupported", None, None, "Codex config has no default model declaration.")


def _probe_opencode_default() -> ModelProbe:
    """Probe OpenCode's current default and read its exported session identity."""
    if os.environ.get("AGENT_BENCH_OPENCODE_COMMAND"):
        return ModelProbe("opencode", "custom_command", None, None, "A custom OpenCode command is configured, so the built-in probe is not assumed equivalent.")
    binary = shutil.which("opencode")
    if not binary:
        return ModelProbe("opencode", "unavailable", None, None, "OpenCode is not on PATH.")
    command = [
        binary,
        "run",
        "--auto",
        "--format",
        "json",
        "Reply with READY only. Do not read or modify files.",
    ]
    try:
        with tempfile.TemporaryDirectory(prefix="agent-benchmark-opencode-probe-") as temporary:
            completed = subprocess.run(
                command,
                cwd=temporary,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=90,
            )
            evidence = parse_harness_output("opencode", completed.stdout, completed.stderr)
            session_id = _opencode_session_id(completed.stdout)
            if completed.returncode != 0 or not session_id:
                detail = (completed.stderr or completed.stdout).strip().splitlines()
                return ModelProbe(
                    "opencode",
                    "failed",
                    None,
                    evidence.cost_usd,
                    detail[-1][:300] if detail else f"OpenCode probe exited {completed.returncode} without a session id.",
                )
            exported = subprocess.run(
                [binary, "export", session_id],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=30,
            )
            # The probe is identity metadata, not a user session. Remove it
            # after export so repeated benchmark setup does not clutter the
            # user's OpenCode session history.
            try:
                subprocess.run(
                    [binary, "session", "delete", session_id],
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                    timeout=30,
                )
            except (OSError, subprocess.TimeoutExpired):
                pass
    except (OSError, subprocess.TimeoutExpired) as exc:
        return ModelProbe("opencode", "failed", None, None, f"Probe could not complete: {exc}")
    model = _opencode_exported_model(exported.stdout) if exported.returncode == 0 else None
    if model:
        return ModelProbe(
            "opencode",
            "observed",
            model,
            evidence.cost_usd,
            "Observed from a temporary OpenCode JSON probe and its exported session metadata.",
        )
    detail = (exported.stderr or exported.stdout).strip().splitlines()
    return ModelProbe(
        "opencode",
        "failed",
        None,
        evidence.cost_usd,
        detail[-1][:300] if detail else "OpenCode session export did not expose a model identity.",
    )


def _opencode_session_id(stdout: str) -> str | None:
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        session_id = event.get("sessionID")
        if isinstance(session_id, str) and session_id.strip():
            return session_id.strip()
    return None


def _opencode_exported_model(stdout: str) -> str | None:
    """Read ``info.model.id`` from export output that may have a status prefix."""
    start = stdout.find("{")
    if start < 0:
        return None
    try:
        payload = json.loads(stdout[start:])
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    info = payload.get("info") if isinstance(payload.get("info"), dict) else {}
    model = info.get("model") if isinstance(info.get("model"), dict) else {}
    value = model.get("id")
    return value.strip() if isinstance(value, str) and value.strip() else None
