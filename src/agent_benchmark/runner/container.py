from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import shlex
import shutil
import subprocess
import time
from typing import Any

from agent_benchmark.recorders import JsonlRecorder
from agent_benchmark.task_schema import TaskSpec


class DockerUnavailableError(RuntimeError):
    """Raised before a container-required task can produce misleading output."""


@dataclass(frozen=True)
class ContainerSpec:
    base_image: str
    packages: tuple[str, ...]
    cpus: float
    memory: str
    image_tag: str
    dockerfile: str


def docker_ready() -> tuple[bool, str]:
    """Return daemon readiness without exposing Docker configuration details."""
    if not shutil.which("docker"):
        return False, "docker command was not found"
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
        return False, f"Docker daemon check failed: {exc}"
    if completed.returncode:
        detail = (completed.stderr or completed.stdout).strip().splitlines()
        return False, detail[-1] if detail else "Docker daemon is unavailable"
    return True, completed.stdout.strip() or "Docker daemon is ready"


def ensure_docker_ready() -> None:
    ready, detail = docker_ready()
    if not ready:
        raise DockerUnavailableError(
            "This task requires a Docker-backed environment, but Docker is not ready: " + detail
        )


def container_spec_for_task(task: TaskSpec) -> ContainerSpec:
    """Build a deterministic task environment contract from manifest metadata."""
    metadata = task.metadata
    raw = metadata.get("container", {})
    if not isinstance(raw, dict):
        raise ValueError(f"Task '{task.task_id}' metadata.container must be an object")
    base_image = str(raw.get("base_image", "python:3.12.8-slim-bookworm"))
    packages = tuple(str(item) for item in metadata.get("required_python_packages", []))
    if not packages:
        raise ValueError(f"Task '{task.task_id}' is container_required but has no pinned Python packages")
    unpinned = [package for package in packages if "==" not in package]
    if unpinned:
        raise ValueError(
            f"Task '{task.task_id}' container packages must use exact versions: {', '.join(unpinned)}"
        )
    cpus = float(raw.get("cpus", 2.0))
    memory = str(raw.get("memory", "2g"))
    if cpus <= 0 or not memory:
        raise ValueError(f"Task '{task.task_id}' has invalid container CPU or memory limits")

    dockerfile = "\n".join(
        [
            f"FROM {base_image}",
            "ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1",
            "RUN python3 -m pip install --no-cache-dir " + " ".join(packages),
            "WORKDIR /workspace",
        ]
    ) + "\n"
    fingerprint = hashlib.sha256(dockerfile.encode("utf-8")).hexdigest()[:16]
    return ContainerSpec(
        base_image=base_image,
        packages=packages,
        cpus=cpus,
        memory=memory,
        image_tag=f"agent-benchmark/{task.task_id}:{fingerprint}",
        dockerfile=dockerfile,
    )


@dataclass
class DockerTaskEnvironment:
    task: TaskSpec
    workspace: Path
    run_dir: Path
    spec: ContainerSpec
    image_id: str
    build_reused: bool

    @property
    def evidence(self) -> dict[str, object]:
        return {
            "engine": "docker-v1",
            "image_tag": self.spec.image_tag,
            "image_id": self.image_id,
            "base_image": self.spec.base_image,
            "packages": list(self.spec.packages),
            "cpus": self.spec.cpus,
            "memory": self.spec.memory,
            "workspace_mount": "/workspace:rw",
            "hidden_tests_mount": "/hidden:ro" if self.task.hidden_test_command else None,
            "build_reused": self.build_reused,
        }

    def agent_instruction(self) -> str:
        helper = self.run_dir / "container-test.sh"
        public = " ".join(shlex.quote(part) for part in self.task.test_command)
        return (
            "\n\nContainer test environment:\n"
            "This task's dependencies are intentionally not installed on the host. "
            "Use the prebuilt container verifier while editing this workspace:\n"
            f"  {shlex.quote(str(helper))} public {public}\n"
            "Do not modify the verifier helper. Hidden tests remain evaluator-only.\n"
        )

    def run_test(
        self,
        kind: str,
        command: list[str],
        cwd: Path,
        workspace: Path,
        timeout_seconds: float,
        recorder: JsonlRecorder,
    ) -> dict[str, object]:
        if not command:
            return {"configured": False, "kind": kind, "error": "No test command configured."}
        command_args = self._docker_command(kind, command)
        start = time.monotonic()
        recorder.event(
            f"test.{kind}.started",
            {"command": command, "container_command": command_args, "cwd": str(cwd), "environment": self.evidence},
        )
        try:
            completed = subprocess.run(
                command_args,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout_seconds + 10,
                check=False,
            )
            duration = time.monotonic() - start
            result: dict[str, object] = {
                "configured": True,
                "kind": kind,
                "command": command,
                "container_command": command_args,
                "cwd": str(cwd),
                "exit_code": completed.returncode,
                "passed": completed.returncode == 0,
                "timed_out": False,
                "stdout": completed.stdout[-4000:],
                "stderr": completed.stderr[-4000:],
                "duration_seconds": duration,
                "environment": self.evidence,
            }
        except subprocess.TimeoutExpired as exc:
            duration = time.monotonic() - start
            stdout = exc.stdout if isinstance(exc.stdout, str) else ""
            stderr = exc.stderr if isinstance(exc.stderr, str) else ""
            result = {
                "configured": True,
                "kind": kind,
                "command": command,
                "container_command": command_args,
                "cwd": str(cwd),
                "exit_code": 124,
                "passed": False,
                "timed_out": True,
                "stdout": stdout[-4000:],
                "stderr": (stderr + f"\nTimed out after {timeout_seconds} seconds.")[-4000:],
                "duration_seconds": duration,
                "environment": self.evidence,
            }
        recorder.event(
            f"test.{kind}.finished",
            {
                "exit_code": result["exit_code"],
                "timed_out": result["timed_out"],
                "duration_seconds": result["duration_seconds"],
                "stdout_tail": str(result["stdout"])[-1000:],
                "stderr_tail": str(result["stderr"])[-1000:],
                "environment": self.evidence,
            },
        )
        return result

    def _docker_command(self, kind: str, command: list[str]) -> list[str]:
        hidden_dir = self.task.root / "hidden"
        target_cwd = "/workspace" if kind == "public" else "/hidden"
        docker_command = [
            "docker", "run", "--rm",
            "--cpus", str(self.spec.cpus), "--memory", self.spec.memory,
            "--mount", f"type=bind,src={self.workspace.resolve()},dst=/workspace,rw",
            "--env", "AGENT_BENCH_WORKSPACE=/workspace",
        ]
        if kind == "hidden":
            docker_command.extend(["--mount", f"type=bind,src={hidden_dir.resolve()},dst=/hidden,readonly"])
        docker_command.extend(["--workdir", target_cwd, self.spec.image_tag, *command])
        return docker_command


def prepare_docker_environment(task: TaskSpec, workspace: Path, run_dir: Path) -> DockerTaskEnvironment:
    ensure_docker_ready()
    spec = container_spec_for_task(task)
    dockerfile_path = run_dir / "environment.Dockerfile"
    dockerfile_path.write_text(spec.dockerfile, encoding="utf-8")
    build_log_path = run_dir / "environment-build.log"
    image_id, reused = _ensure_image(spec, dockerfile_path, build_log_path)
    environment = DockerTaskEnvironment(task, workspace, run_dir, spec, image_id, reused)
    (run_dir / "environment.json").write_text(
        json.dumps({**environment.evidence, "spec": asdict(spec)}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    _write_agent_helper(environment)
    return environment


def _ensure_image(spec: ContainerSpec, dockerfile_path: Path, build_log_path: Path) -> tuple[str, bool]:
    inspect = subprocess.run(
        ["docker", "image", "inspect", "--format", "{{.Id}}", spec.image_tag],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=20,
    )
    if inspect.returncode == 0 and inspect.stdout.strip():
        build_log_path.write_text("Reused existing image " + spec.image_tag + "\n", encoding="utf-8")
        return inspect.stdout.strip(), True

    completed = subprocess.run(
        ["docker", "build", "--tag", spec.image_tag, "--file", str(dockerfile_path), str(dockerfile_path.parent)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=600,
    )
    build_log_path.write_text(
        "command: " + shlex.join(["docker", "build", "--tag", spec.image_tag, "--file", str(dockerfile_path), str(dockerfile_path.parent)])
        + "\n\nstdout:\n" + completed.stdout + "\n\nstderr:\n" + completed.stderr,
        encoding="utf-8",
    )
    if completed.returncode:
        raise RuntimeError(
            f"Failed to build Docker image for '{spec.image_tag}'. See {build_log_path}: {completed.stderr[-1000:]}"
        )
    inspect = subprocess.run(
        ["docker", "image", "inspect", "--format", "{{.Id}}", spec.image_tag],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=20,
    )
    if inspect.returncode or not inspect.stdout.strip():
        raise RuntimeError(f"Docker built '{spec.image_tag}' but image ID could not be inspected")
    return inspect.stdout.strip(), False


def _write_agent_helper(environment: DockerTaskEnvironment) -> None:
    helper = environment.run_dir / "container-test.sh"
    workspace_mount = shlex.quote(f"type=bind,src={environment.workspace.resolve()},dst=/workspace,rw")
    script = "\n".join(
        [
            "#!/bin/sh",
            "set -eu",
            "case \"${1:-}\" in",
            "  public) shift ;;",
            "  *) echo 'usage: container-test.sh public <test command...>' >&2; exit 64 ;;",
            "esac",
            "exec docker run --rm "
            f"--cpus {environment.spec.cpus} --memory {shlex.quote(environment.spec.memory)} "
            f"--mount {workspace_mount} --env AGENT_BENCH_WORKSPACE=/workspace "
            f"--workdir /workspace {shlex.quote(environment.spec.image_tag)} \"$@\"",
            "",
        ]
    )
    helper.write_text(script, encoding="utf-8")
    helper.chmod(0o700)
