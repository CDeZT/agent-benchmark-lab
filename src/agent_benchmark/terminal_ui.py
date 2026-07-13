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
        "task": ("▸", "1;36"),
        "work": ("◌", "1;33"),
        "verify": ("◇", "1;35"),
        "result": ("✓", "1;32"),
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
        self.observed_model: str | None = None
        self._observed_models: list[str] = []
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
        self._colour_enabled = self.interactive and os.environ.get("NO_COLOR") is None
        dimensions = shutil.get_terminal_size(fallback=(100, 24))
        self._full_screen = (
            self.interactive
            and requested_tui != "compact"
            and os.environ.get("TERM", "").lower() != "dumb"
            and dimensions.columns >= 72
            and dimensions.lines >= 18
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

    def start(self) -> None:
        with self._lock:
            self._add_activity_locked("system", "Benchmark session started")
            self._persist_locked()
            if self.enabled:
                if self._full_screen:
                    # Keep normal shell scrollback clean, matching the behavior
                    # people expect from a dedicated coding-agent TUI.
                    self.stream.write("\033[?1049h\033[?25l")
                    self._alternate_screen_active = True
                else:
                    requested_model, selection_detail = self._model_context()
                    self.stream.write(
                        "\n"
                        + _colour("Agent Benchmark Lab", "1;36", self._colour_enabled)
                        + "\n"
                        + f"  Suite      {self.suite_id}\n"
                        + f"  Harness    {self.adapter}\n"
                        + f"  Model      {requested_model}\n"
                        + f"  Selection  {selection_detail}\n"
                        + f"  Work       {self.task_count} tasks x {self.repetitions} repeats = {self.total_attempts} attempts\n"
                        + f"  Live state {self.status_path}\n\n"
                    )
                self.stream.flush()
        if self.interactive:
            self._heartbeat = Thread(target=self._heartbeat_loop, name="agent-benchmark-progress", daemon=True)
            self._heartbeat.start()
            self._render_live()

    def task_started(self, task_id: str, task_index: int, *, external: bool = False) -> None:
        self._update(
            task_id=task_id,
            task_index=task_index,
            repetition=None,
            phase="official evaluator" if external else "preparing workspace",
            activity=("task", f"Task {task_index}/{self.task_count}: {task_id}"),
        )

    def event(self, task_id: str, task_index: int, event_name: str, payload: dict[str, object]) -> None:
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
            self._update(phase="harness working", activity=("work", f"{self.adapter} started"))
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
                self._persist_locked()
            self._render_live()

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
            line = (
                f"[{bar}] {self._completed_attempts}/{self.total_attempts} | {position} {task} | "
                f"{repeat} | {phase} | model {self.observed_model or 'identifying'} | "
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
        """Render a metadata rail plus a runner-derived activity stream."""
        dimensions = shutil.get_terminal_size(fallback=(100, 24))
        width = max(72, dimensions.columns)
        height = max(18, dimensions.lines)
        eta = self._eta_seconds_locked()
        elapsed = self._elapsed_seconds()
        percent = 100 * self._completed_attempts / self.total_attempts if self.total_attempts else 100.0
        task = str(self._current.get("task_id", "waiting for first task"))
        task_index = self._current.get("task_index")
        repetition = self._current.get("repetition")
        phase = str(self._current.get("phase", "starting"))
        filled = round(30 * self._completed_attempts / self.total_attempts) if self.total_attempts else 30
        bar = "█" * filled + "░" * (30 - filled)
        spinner = "◐◓◑◒"[int(elapsed * 4) % 4]
        status = f"RUNNING {spinner}" if self._status == "in_progress" else self._status.upper()
        requested_model, selection_detail = self._model_context()
        if not self._observed_models:
            observed_model = "identifying from harness output"
        elif len(self._observed_models) == 1:
            observed_model = self._observed_models[0]
        else:
            observed_model = f"multiple observed: {', '.join(self._observed_models)}"
        rule = "─" * width

        rail_width = min(31, max(25, width // 3))
        body_width = width - rail_width - 3
        panel_height = max(12, height - 6)
        observed_label = observed_model if self._observed_models else "waiting for harness output"
        progress_label = f"{self._completed_attempts}/{self.total_attempts}  {percent:5.1f}%"
        rail_bar_width = max(1, rail_width - 2)
        rail_filled = round(rail_bar_width * self._completed_attempts / self.total_attempts) if self.total_attempts else rail_bar_width
        rail_bar = "█" * rail_filled + "░" * (rail_bar_width - rail_filled)
        rail: list[tuple[str, str | None]] = [
            ("RUN", "1;36"),
            (self.adapter, "1;37"),
            ("", None),
            ("MODEL", "1;36"),
            (_trim(requested_model, rail_width), "1;37"),
            (_trim("observed: " + observed_label, rail_width), "2"),
            ("", None),
            ("PROGRESS", "1;36"),
            (progress_label, "1;37"),
            ("[" + rail_bar + "]", "1;36"),
            (f"elapsed {_format_duration(elapsed)}", "2"),
            (f"ETA {_format_duration(eta)}", "2"),
            ("", None),
            ("PROFILE", "1;36"),
            (_trim(self.budget_profile, rail_width), "1;37"),
            (_trim(self.suite_id, rail_width), "2"),
        ]
        recent = self._activity[-max(3, panel_height - 7):]
        body: list[tuple[str, str | None]] = [
            (f"{spinner}  {_trim(task, max(12, body_width - 4))}", "1;37"),
            (f"task {task_index or 0}/{self.task_count}  ·  repeat {repetition or '-'}/{self.repetitions}  ·  {phase}", "2"),
            ("", None),
            ("ACTIVITY", "1;36"),
        ]
        for item in reversed(recent):
            marker, colour = _activity_style(item["kind"])
            message = _trim(item["message"], max(12, body_width - 12))
            body.append((f"{marker}  {item['at']}  {message}", colour))
        body.extend(
            [
                ("", None),
                ("MODEL RULE", "1;36"),
                (_trim(selection_detail, body_width), "2"),
            ]
        )

        def pane_line(item: tuple[str, str | None], pane_width: int) -> str:
            text, colour = item
            padded = _trim(text, pane_width).ljust(pane_width)
            return _colour(padded, colour, self._colour_enabled) if colour else padded

        lines = [
            _colour("Agent Benchmark Lab", "1;36", self._colour_enabled)
            + " " * max(1, width - len("Agent Benchmark Lab") - len(status))
            + _colour(status, "1;33", self._colour_enabled),
            _colour(_trim(f"{self.adapter}  ·  {self.suite_id}", width), "2", self._colour_enabled),
            rule,
        ]
        for index in range(panel_height):
            left = rail[index] if index < len(rail) else ("", None)
            right = body[index] if index < len(body) else ("", None)
            lines.append(pane_line(left, rail_width) + " │ " + pane_line(right, body_width))
        lines.extend(
            [
                rule,
                _colour(_trim(f"State: {self.status_path}", width), "2", self._colour_enabled),
                _colour("Ctrl-C preserves checkpoints and evidence.", "2", self._colour_enabled),
            ]
        )
        self.stream.write("\033[H\033[2J" + "\n".join(lines) + "\n")
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
