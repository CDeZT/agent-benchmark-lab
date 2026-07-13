"""Small, dependency-free terminal progress UI for long benchmark suites.

The benchmark must remain scriptable, so live rendering is sent to stderr and
the final machine-readable result remains on stdout.  The same state is saved
to ``live_status.json`` so a user can inspect a long-running or interrupted
experiment without relying on terminal scrollback.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import sys
from threading import Event, Lock, Thread
import time
from typing import TextIO


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _format_duration(seconds: float | None) -> str:
    if seconds is None:
        return "calculating"
    total = max(0, round(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours:d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def _colour(text: str, code: str, enabled: bool) -> str:
    return f"\033[{code}m{text}\033[0m" if enabled else text


def _trim(text: str, width: int) -> str:
    """Keep fixed TUI rows stable even for long task ids and paths."""
    if len(text) <= width:
        return text
    return text[: max(0, width - 3)] + "..."


def _activity_style(kind: str) -> tuple[str, str]:
    """Map real lifecycle events to a small, stable visual vocabulary."""
    return {
        "system": ("·", "2"),
        "task": ("◆", "1;38;5;45"),
        "work": ("◌", "1;38;5;220"),
        "workspace": ("↳", "38;5;111"),
        "edit": ("✦", "1;38;5;81"),
        "verify": ("◇", "1;38;5;213"),
        "result": ("✓", "1;38;5;114"),
    }.get(kind, ("·", "2"))


class SuiteProgress:
    """Render and persist suite-level progress without changing score evidence."""

    def __init__(
        self,
        suite_run_dir: Path,
        *,
        suite_id: str,
        adapter: str,
        repetitions: int,
        task_count: int,
        model: str = "unspecified",
        adapter_model: str | None = None,
        model_selection: str = "environment_only",
        observed_model: str | None = None,
        observed_source: str | None = None,
        model_hint: str | None = None,
        model_hint_source: str | None = None,
        budget_profile: str = "open_ended",
        enabled: bool | None = None,
        stream: TextIO | None = None,
    ) -> None:
        self.suite_run_dir = suite_run_dir
        self.status_path = suite_run_dir / "live_status.json"
        self.suite_id = suite_id
        self.adapter = adapter
        self.requested_model = model
        self.adapter_model = adapter_model or model
        self.model_selection = model_selection
        self.budget_profile = budget_profile
        self.observed_model = observed_model.strip() if observed_model else None
        self._observed_models = [self.observed_model] if self.observed_model else []
        self._observed_source = observed_source
        self._model_hint = model_hint.strip() if model_hint else None
        self._model_hint_source = model_hint_source
        self.repetitions = repetitions
        self.task_count = task_count
        self.total_attempts = task_count * repetitions
        self.stream = stream or sys.stderr
        requested_mode = os.environ.get("AGENT_BENCH_PROGRESS", "auto").lower()
        requested_tui = os.environ.get("AGENT_BENCH_TUI", "auto").lower()
        terminal_is_interactive = bool(getattr(self.stream, "isatty", lambda: False)())
        self.enabled = enabled if enabled is not None else requested_mode != "off" and (
            terminal_is_interactive or requested_mode == "plain"
        )
        self.interactive = self.enabled and terminal_is_interactive and requested_mode != "plain"
        colour_mode = os.environ.get("AGENT_BENCH_COLOR", "auto").lower()
        self._colour_enabled = self.interactive and (
            colour_mode == "always" or (colour_mode != "never" and os.environ.get("NO_COLOR") is None)
        )
        dimensions = shutil.get_terminal_size(fallback=(100, 24))
        self._full_screen = (
            self.interactive
            and requested_tui != "compact"
            and os.environ.get("TERM", "").lower() != "dumb"
            and dimensions.columns >= 72
            and dimensions.lines >= 22
        )
        if requested_tui == "full" and self.interactive:
            self._full_screen = True
        self._alternate_screen_active = False
        self._started_monotonic = time.monotonic()
        self._started_at = _utc_now()
        self._completed_attempts = 0
        self._completed_durations: list[float] = []
        self._current: dict[str, object] = {"phase": "starting"}
        self._status = "in_progress"
        self._lock = Lock()
        self._stop_event = Event()
        self._heartbeat: Thread | None = None
        self._last_line_was_live = False
        self._recent_attempts: list[dict[str, object]] = []
        self._activity: list[dict[str, str]] = []
        self._workspace_path: Path | None = None
        self._workspace_snapshot: dict[str, int] = {}
        self._workspace_change_count = 0
        self._last_workspace_scan = 0.0
        self._last_frame: list[str] = []

    def start(self) -> None:
        with self._lock:
            self._add_activity_locked("system", "Benchmark session started")
            if self.observed_model:
                self._add_activity_locked("system", f"Model observed by startup probe: {self.observed_model}")
            self._persist_locked()
            if self.enabled:
                if self._full_screen:
                    # Keep normal shell scrollback clean, matching the behavior
                    # people expect from a dedicated coding-agent TUI.
                    self.stream.write("\033[?1049h\033[?25l")
                    self._alternate_screen_active = True
                else:
                    requested_model, selection_detail = self._model_context()
                    observed_line = (
                        f"  Observed   {self.observed_model} ({self._observed_source or 'harness evidence'})\n"
                        if self.observed_model
                        else ""
                    )
                    hint_line = (
                        f"  Configured {self._model_hint} (unverified configured default)\n"
                        if self._model_hint and not self.observed_model
                        else ""
                    )
                    self.stream.write(
                        "\n"
                        + _colour("Agent Benchmark Lab", "1;36", self._colour_enabled)
                        + "\n"
                        + f"  Suite      {self.suite_id}\n"
                        + f"  Harness    {self.adapter}\n"
                        + f"  Model      {requested_model}\n"
                        + observed_line
                        + hint_line
                        + f"  Selection  {selection_detail}\n"
                        + f"  Work       {self.task_count} tasks x {self.repetitions} repeats = {self.total_attempts} attempts\n"
                        + f"  Live state {self.status_path}\n\n"
                    )
                self.stream.flush()
        if self.interactive:
            self._heartbeat = Thread(target=self._heartbeat_loop, name="agent-benchmark-progress", daemon=True)
            self._heartbeat.start()
            self._render_live()

    def task_started(
        self,
        task_id: str,
        task_index: int,
        *,
        task_title: str | None = None,
        external: bool = False,
    ) -> None:
        self._update(
            task_id=task_id,
            task_title=task_title,
            task_index=task_index,
            repetition=None,
            phase="official evaluator" if external else "preparing workspace",
            activity=("task", f"Task {task_index}/{self.task_count}: {task_title or task_id}"),
        )

    def event(self, task_id: str, task_index: int, event_name: str, payload: dict[str, object]) -> None:
        if event_name == "workspace.ready":
            raw_workspace = payload.get("workspace")
            workspace = Path(raw_workspace) if isinstance(raw_workspace, str) else None
            with self._lock:
                self._workspace_path = workspace
                self._workspace_snapshot = self._workspace_state_locked()
                self._workspace_change_count = 0
            self._update(
                phase="workspace ready",
                activity=("workspace", "Isolated task workspace is ready"),
            )
            return
        if event_name == "environment.preparing":
            self._update(phase="preparing evaluator", activity=("workspace", "Preparing task environment"))
            return
        if event_name == "repetition.started":
            self._update(
                task_id=task_id,
                task_index=task_index,
                repetition=payload.get("repetition"),
                phase="agent working",
                activity=("work", f"Repeat {payload.get('repetition', '?')}/{self.repetitions} started"),
            )
            return
        if event_name == "adapter.started":
            self._update(phase="agent session active", activity=("work", f"{self.adapter} agent session started"))
            return
        if event_name == "adapter.finished":
            self._update(phase="scoring and verification", activity=("verify", "Harness finished; scoring evidence"))
            return
        if event_name == "repetition.finished":
            duration = payload.get("duration_seconds")
            detected_model = payload.get("detected_model")
            if isinstance(detected_model, str) and detected_model.strip():
                with self._lock:
                    self.observed_model = detected_model.strip()
                    self._observed_source = "harness_output"
                    if self.observed_model not in self._observed_models:
                        self._observed_models.append(self.observed_model)
            self._complete_attempt(
                float(duration) if isinstance(duration, (int, float)) else None,
                task_id=task_id,
                repetition=payload.get("repetition"),
                score=payload.get("score"),
                detected_model=detected_model if isinstance(detected_model, str) else None,
            )

    def complete_external_task(self, duration_seconds: float | None) -> None:
        per_attempt = (duration_seconds / self.repetitions) if duration_seconds is not None and self.repetitions else None
        for _ in range(self.repetitions):
            self._complete_attempt(per_attempt, task_id=str(self._current.get("task_id", "external task")))

    def recovered_task(self, duration_seconds: float | None) -> None:
        self.complete_external_task(duration_seconds)

    def finish(self, status: str = "complete") -> None:
        self._status = status
        self._stop_event.set()
        if self._heartbeat:
            self._heartbeat.join(timeout=1.5)
        with self._lock:
            self._current["phase"] = "complete" if status == "complete" else status
            self._add_activity_locked("result" if status == "complete" else "system", f"Benchmark {status}")
            self._persist_locked()
            if self._alternate_screen_active:
                self.stream.write("\033[?25h\033[?1049l")
                self._alternate_screen_active = False
            elif self.interactive and self._last_line_was_live:
                self.stream.write("\r\033[2K")
            if self.enabled:
                label = "DONE" if status == "complete" else status.upper()
                self.stream.write(
                    f"{_colour(label, '1;32' if status == 'complete' else '1;31', self._colour_enabled)} "
                    f"{self._completed_attempts}/{self.total_attempts} attempts | "
                    f"elapsed {_format_duration(self._elapsed_seconds())}\n"
                )
                self.stream.flush()
            self._last_line_was_live = False

    def _update(self, *, activity: tuple[str, str] | None = None, **changes: object) -> None:
        with self._lock:
            self._current.update({key: value for key, value in changes.items() if value is not None})
            if activity:
                self._add_activity_locked(*activity)
            self._persist_locked()
        self._render_live()

    def _complete_attempt(
        self,
        duration_seconds: float | None,
        *,
        task_id: str | None = None,
        repetition: object | None = None,
        score: object | None = None,
        detected_model: str | None = None,
    ) -> None:
        with self._lock:
            self._completed_attempts = min(self.total_attempts, self._completed_attempts + 1)
            if duration_seconds is not None and duration_seconds >= 0:
                self._completed_durations.append(duration_seconds)
            if task_id:
                self._recent_attempts.append(
                    {
                        "task_id": task_id,
                        "repetition": repetition,
                        "duration_seconds": duration_seconds,
                        "score": score,
                        "detected_model": detected_model.strip() if detected_model and detected_model.strip() else None,
                    }
                )
                self._recent_attempts = self._recent_attempts[-3:]
                score_text = f"score {float(score):.1f}" if isinstance(score, (int, float)) else "scored"
                self._add_activity_locked("result", f"Repeat {repetition or '?'} complete: {score_text}")
            self._current["phase"] = "completed attempt"
            self._persist_locked()
        self._render_live()

    def _heartbeat_loop(self) -> None:
        while not self._stop_event.wait(0.5):
            with self._lock:
                self._refresh_workspace_activity_locked()
                self._persist_locked()
            self._render_live()

    def _workspace_state_locked(self) -> dict[str, int]:
        if self._workspace_path is None or not self._workspace_path.is_dir():
            return {}
        state: dict[str, int] = {}
        ignored_directories = {".git", "node_modules", ".venv", "venv", "__pycache__"}
        try:
            for path in self._workspace_path.rglob("*"):
                if not path.is_file() or any(part in ignored_directories for part in path.parts):
                    continue
                try:
                    relative = str(path.relative_to(self._workspace_path))
                    state[relative] = path.stat().st_mtime_ns
                except OSError:
                    continue
        except OSError:
            return state
        return state

    def _refresh_workspace_activity_locked(self) -> None:
        """Surface actual workspace mutations while the harness is running."""
        now = time.monotonic()
        if now - self._last_workspace_scan < 1.0:
            return
        self._last_workspace_scan = now
        current = self._workspace_state_locked()
        if not current and not self._workspace_snapshot:
            return
        changed = [path for path, mtime in current.items() if self._workspace_snapshot.get(path) != mtime]
        removed = [path for path in self._workspace_snapshot if path not in current]
        self._workspace_snapshot = current
        mutations = changed + removed
        if not mutations:
            return
        self._workspace_change_count += len(mutations)
        preview = ", ".join(_trim(path, 34) for path in mutations[:2])
        suffix = "" if len(mutations) <= 2 else f" +{len(mutations) - 2} more"
        self._current["phase"] = "agent editing workspace"
        self._add_activity_locked("edit", f"Workspace changed: {preview}{suffix}")

    def _elapsed_seconds(self) -> float:
        return time.monotonic() - self._started_monotonic

    def _eta_seconds_locked(self) -> float | None:
        if not self._completed_durations:
            return None
        remaining = max(0, self.total_attempts - self._completed_attempts)
        return (sum(self._completed_durations) / len(self._completed_durations)) * remaining

    def _persist_locked(self) -> None:
        eta = self._eta_seconds_locked()
        percent = round(100 * self._completed_attempts / self.total_attempts, 1) if self.total_attempts else 100.0
        payload = {
            "schema_version": 1,
            "status": self._status,
            "suite_id": self.suite_id,
            "adapter": self.adapter,
            "model": {
                "requested": self.requested_model,
                "adapter_model": self.adapter_model,
                "selection": self.model_selection,
                "observed": self.observed_model,
                "observed_models": list(self._observed_models),
                "observed_source": self._observed_source,
                "configured_hint": self._model_hint,
                "configured_hint_source": self._model_hint_source,
                "identity_status": (
                    "observed_multiple" if len(self._observed_models) > 1
                    else "observed" if self.observed_model
                    else "awaiting_harness_evidence"
                ),
            },
            "repetitions": self.repetitions,
            "started_at": self._started_at,
            "updated_at": _utc_now(),
            "elapsed_seconds": round(self._elapsed_seconds(), 1),
            "estimated_remaining_seconds": round(eta, 1) if eta is not None else None,
            "progress": {
                "completed_attempts": self._completed_attempts,
                "total_attempts": self.total_attempts,
                "percent": percent,
            },
            "current": dict(self._current),
            "recent_attempts": list(self._recent_attempts),
            "activity": list(self._activity),
            "display": {"mode": "full" if self._full_screen else "compact" if self.interactive else "plain"},
        }
        temporary = self.status_path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.status_path)

    def _render_live(self) -> None:
        if not self.enabled:
            return
        with self._lock:
            if self._full_screen:
                self._render_full_screen_locked()
                return
            eta = self._eta_seconds_locked()
            task = str(self._current.get("task_id", "waiting"))
            task_index = self._current.get("task_index")
            repetition = self._current.get("repetition")
            phase = str(self._current.get("phase", "starting"))
            filled = round(24 * self._completed_attempts / self.total_attempts) if self.total_attempts else 24
            bar = "#" * filled + "-" * (24 - filled)
            position = f"task {task_index}/{self.task_count}" if task_index is not None else "task 0/" + str(self.task_count)
            repeat = f"repeat {repetition}/{self.repetitions}" if repetition is not None else "repeat -/" + str(self.repetitions)
            display_model = self.observed_model or self._model_hint or "identity pending"
            line = (
                f"[{bar}] {self._completed_attempts}/{self.total_attempts} | {position} {task} | "
                f"{repeat} | {phase} | model {display_model} | "
                f"elapsed {_format_duration(self._elapsed_seconds())} | ETA {_format_duration(eta)}"
            )
            if self.interactive:
                self.stream.write("\r\033[2K" + _colour(line, "36", self._colour_enabled))
                self.stream.flush()
                self._last_line_was_live = True
            else:
                self.stream.write(line + "\n")
                self.stream.flush()

    def _render_full_screen_locked(self) -> None:
        """Render a stable, centered agent session without full-screen flicker."""
        dimensions = shutil.get_terminal_size(fallback=(100, 24))
        width = max(72, dimensions.columns)
        height = max(18, dimensions.lines)
        eta = self._eta_seconds_locked()
        elapsed = self._elapsed_seconds()
        percent = 100 * self._completed_attempts / self.total_attempts if self.total_attempts else 100.0
        task = str(self._current.get("task_id", "waiting for first task"))
        task_title = str(self._current.get("task_title") or task)
        task_index = self._current.get("task_index")
        repetition = self._current.get("repetition")
        phase = str(self._current.get("phase", "starting"))
        filled = round(30 * self._completed_attempts / self.total_attempts) if self.total_attempts else 30
        bar = "█" * filled + "░" * (30 - filled)
        spinner = "◐◓◑◒"[int(elapsed * 4) % 4]
        status = f"RUNNING {spinner}" if self._status == "in_progress" else self._status.upper()
        requested_model, selection_detail = self._model_context()
        if not self._observed_models and self._model_hint:
            observed_model = self._model_hint
        elif not self._observed_models:
            observed_model = "Model identity pending"
        elif len(self._observed_models) == 1:
            observed_model = self._observed_models[0]
        else:
            observed_model = f"multiple observed: {', '.join(self._observed_models)}"
        canvas_width = min(78, width - 6)
        left_padding = " " * max(0, (width - canvas_width) // 2)
        rule = "─" * canvas_width
        # The footer needs one spare row for the cursor.  Keeping the entire
        # frame inside the actual terminal prevents alternate-screen scrolls
        # that can hide the model header on a standard 80x24 terminal.
        activity_limit = max(1, height - 21)
        recent = self._activity[-activity_limit:]

        def line(text: str = "", *, colour: str | None = None, centered: bool = False) -> str:
            content = _trim(text, canvas_width)
            if centered:
                content = content.center(canvas_width)
            rendered = _colour(content, colour, self._colour_enabled) if colour else content
            return left_padding + rendered

        source = (
            "VERIFIED AT STARTUP"
            if self._observed_source == "startup_probe"
            else "VERIFIED FROM HARNESS OUTPUT"
            if self._observed_source == "harness_output"
            else "CONFIGURED DEFAULT (UNVERIFIED)"
            if self._model_hint
            else "IDENTITY PENDING"
        )
        source_detail = (
            "This suite's configured default was observed before task 1."
            if self._observed_source == "startup_probe"
            else "This identity came from a completed harness attempt."
            if self._observed_source == "harness_output"
            else self._model_hint_source or "This configured default will be checked against harness output."
            if self._model_hint
            else selection_detail
        )
        progress_text = f"{self._completed_attempts:>2}/{self.total_attempts:<2} attempts   {percent:5.1f}%"
        elapsed_text = f"elapsed {_format_duration(elapsed)}   ETA {_format_duration(eta)}"
        workspace_text = (
            f"{self._workspace_change_count} workspace mutation(s) observed"
            if self._workspace_path is not None
            else "workspace details pending"
        )
        lines = [
            line("◈  AGENT BENCHMARK", colour="1;38;5;45"),
            line(f"{self.adapter}  /  {observed_model}", colour="1;38;5;231"),
            line(f"{source}   ·   {status}", colour="1;38;5;114" if self._observed_models else "1;38;5;220"),
            line(source_detail, colour="38;5;246"),
            line(rule),
            line("WORKING ON", colour="1;38;5;45"),
            line(_trim(task_title, max(12, canvas_width - 2)), colour="1;38;5;231"),
            line(f"{task}   ·   task {task_index or 0}/{self.task_count}   ·   repeat {repetition or '-'}/{self.repetitions}", colour="38;5;246"),
            line(f"{spinner}  {phase}", colour="1;38;5;220"),
            line(f"{_colour('█' * filled + '░' * (30 - filled), '1;38;5;45', self._colour_enabled)}  {progress_text}", colour="1;38;5;231"),
            line(f"{elapsed_text}   ·   {workspace_text}", colour="38;5;246"),
            line(rule),
            line("LIVE ACTIVITY", colour="1;38;5;45"),
        ]
        for item in reversed(recent):
            marker, colour = _activity_style(item["kind"])
            lines.append(line(f"{marker}  {item['at']}  {_trim(item['message'], max(12, canvas_width - 12))}", colour=colour))
        lines.extend(
            [
                line(rule),
                line(f"Ctrl-C preserves checkpoints and evidence   ·   {requested_model}", colour="2"),
            ]
        )
        self._render_frame_locked(lines)

    def _render_frame_locked(self, lines: list[str]) -> None:
        """Update only changed terminal rows after the initial alternate-screen draw."""
        if not self._last_frame:
            self.stream.write("\033[H\033[2J")
        previous = self._last_frame
        for index, content in enumerate(lines, start=1):
            if index > len(previous) or previous[index - 1] != content:
                self.stream.write(f"\033[{index};1H\033[2K{content}")
        for index in range(len(lines) + 1, len(previous) + 1):
            self.stream.write(f"\033[{index};1H\033[2K")
        self.stream.write(f"\033[{len(lines) + 1};1H")
        self._last_frame = list(lines)
        self.stream.flush()
        self._last_line_was_live = True

    def _add_activity_locked(self, kind: str, message: str) -> None:
        self._activity.append({"at": _utc_now()[11:19], "kind": kind, "message": message})
        self._activity = self._activity[-12:]

    def _model_context(self) -> tuple[str, str]:
        """Describe model selection without turning a requested label into evidence."""
        if self.model_selection == "configured_default_only":
            if self.requested_model != "unspecified":
                return (
                    "harness configured default",
                    f"Requested label: {self.requested_model} (this harness does not accept a model override)",
                )
            return "harness configured default", "The harness chooses its configured default; identity is checked after it runs."
        if self.requested_model == "unspecified":
            return "current CLI default", "No model override was sent; identity is checked from real harness output."
        if self.model_selection == "environment_only":
            return self.requested_model, "Adapter receives this value through its configured environment; identity is checked from real harness output."
        if self.adapter_model != self.requested_model:
            return self.requested_model, f"Adapter invocation: {self.adapter_model} (will be verified from harness output)."
        return self.requested_model, "Requested through the harness CLI; identity is checked from real harness output."
