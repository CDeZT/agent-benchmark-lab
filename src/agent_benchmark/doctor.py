from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
import os
from pathlib import Path
import shutil
import subprocess
from typing import Any


@dataclass
class DoctorCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)


RECOMMENDED_COMMANDS = {
    "opencode": "built-in default uses opencode run --auto (--model intentionally omitted: opencode 1.17.15 crashes with any --model value)",
    "claude-code": "built-in default uses claude -p --dangerously-skip-permissions --no-session-persistence, adding --model only when AGENT_BENCH_MODEL is not unspecified",
}


def run_doctor() -> dict[str, Any]:
    checks = [
        _command_check("python3", ["python3", "--version"]),
        _command_check("node", ["node", "--version"]),
        _command_check("cc", ["cc", "--version"]),
        _command_check("opencode", ["opencode", "--version"]),
        _command_check("claude", ["claude", "--version"]),
        _docker_check(),
        _playwright_check(),
        _env_check("AGENT_BENCH_COMMAND"),
        _env_check("AGENT_BENCH_OPENCODE_COMMAND", recommended=RECOMMENDED_COMMANDS["opencode"]),
        _env_check("AGENT_BENCH_CLAUDE_CODE_COMMAND", recommended=RECOMMENDED_COMMANDS["claude-code"]),
    ]
    return {
        "ok": all(check.status != "error" for check in checks),
        "checks": [asdict(check) for check in checks],
        "recommended_commands": RECOMMENDED_COMMANDS,
    }


def format_doctor(summary: dict[str, Any]) -> str:
    lines = [
        f"Doctor ok: {summary['ok']}",
        "",
        "| Check | Status | Details |",
        "| --- | --- | --- |",
    ]
    for check in summary["checks"]:
        detail = _short_details(check["details"])
        lines.append(f"| {check['name']} | {check['status']} | {detail} |")
    lines.extend(
        [
            "",
            "Recommended command templates:",
            f"- opencode: `{summary['recommended_commands']['opencode']}`",
            f"- claude-code: `{summary['recommended_commands']['claude-code']}`",
        ]
    )
    return "\n".join(lines)


def _command_check(binary: str, version_command: list[str]) -> DoctorCheck:
    path = shutil.which(binary)
    if not path:
        return DoctorCheck(name=f"command:{binary}", status="error", details={"reason": "not found"})
    completed = subprocess.run(
        version_command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=10,
    )
    output = (completed.stdout or completed.stderr).strip().splitlines()
    return DoctorCheck(
        name=f"command:{binary}",
        status="ok" if completed.returncode == 0 else "warning",
        details={
            "path": path,
            "exit_code": completed.returncode,
            "version": output[0] if output else "",
        },
    )


def _env_check(name: str, recommended: str | None = None) -> DoctorCheck:
    value = os.environ.get(name)
    details: dict[str, Any] = {"configured": bool(value)}
    if value:
        details["value"] = value
        return DoctorCheck(name=f"env:{name}", status="ok", details=details)
    if recommended:
        details["recommended"] = recommended
    return DoctorCheck(name=f"env:{name}", status="warning", details=details)


def _docker_check() -> DoctorCheck:
    path = shutil.which("docker")
    if not path:
        return DoctorCheck(name="docker", status="error", details={"reason": "docker command not found"})
    try:
        completed = subprocess.run(
            ["docker", "version", "--format", "{{.Server.Version}}"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return DoctorCheck(name="docker", status="error", details={"path": path, "reason": str(exc)})
    if completed.returncode:
        output = (completed.stderr or completed.stdout).strip().splitlines()
        return DoctorCheck(
            name="docker",
            status="error",
            details={"path": path, "reason": output[-1] if output else "daemon unavailable"},
        )
    return DoctorCheck(name="docker", status="ok", details={"path": path, "server_version": completed.stdout.strip()})


def _playwright_check() -> DoctorCheck:
    node = shutil.which("node")
    if not node:
        return DoctorCheck(name="playwright", status="warning", details={"reason": "Node.js is unavailable"})
    command = [
        node,
        "-e",
        "const fs=require('fs'); const {chromium}=require('playwright'); const path=chromium.executablePath(); if (!fs.existsSync(path)) process.exit(2); console.log(path)",
    ]
    try:
        completed = subprocess.run(
            command,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return DoctorCheck(name="playwright", status="warning", details={"reason": str(exc)})
    if completed.returncode:
        detail = (completed.stderr or completed.stdout).strip().splitlines()
        return DoctorCheck(
            name="playwright",
            status="warning",
            details={"reason": detail[-1] if detail else "package or Chromium browser is unavailable"},
        )
    return DoctorCheck(name="playwright", status="ok", details={"browser_path": completed.stdout.strip()})


def _short_details(details: dict[str, Any]) -> str:
    if "server_version" in details:
        return f"{details.get('path', '')} server={details['server_version']}".strip()
    if "browser_path" in details:
        return details["browser_path"]
    if "version" in details:
        return f"{details.get('path', '')} {details.get('version', '')}".strip()
    if "configured" in details:
        if details["configured"]:
            return "configured"
        recommended = details.get("recommended")
        return f"not configured; recommended: {recommended}" if recommended else "not configured"
    return json.dumps(details, ensure_ascii=False)
