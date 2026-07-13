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
        enabled: bool | None = None,
        stream: TextIO | None = None,
    ) -> None:
        self.suite_run_dir = suite_run_dir
        self.status_path = suite_run_dir / "live_status.json"
        self.suite_id = suite_id
        self.adapter = adapter
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

    def start(self) -> None:
        with self._lock:
            self._persist_locked()
            if self.enabled:
                if self._full_screen:
                    # Keep normal shell scrollback clean, matching the behavior
                    # people expect from a dedicated coding-agent TUI.
                    self.stream.write("\033[?1049h\033[?25l")
                    self._alternate_screen_active = True
                else:
                    self.stream.write(
                        "\n"
                        + _colour("Agent Benchmark Lab", "1;36", self._colour_enabled)
                        + "\n"
                        + f"  Suite      {self.suite_id}\n"
                        + f"  Harness    {self.adapter}\n"
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
        )

    def event(self, task_id: str, task_index: int, event_name: str, payload: dict[str, object]) -> None:
        if event_name == "repetition.started":
            self._update(
                task_id=task_id,
                task_index=task_index,
                repetition=payload.get("repetition"),
                phase="agent working",
            )
            return
        if event_name == "adapter.finished":
            self._update(phase="scoring and verification")
            return
        if event_name == "repetition.finished":
            duration = payload.get("duration_seconds")
            self._complete_attempt(
                float(duration) if isinstance(duration, (int, float)) else None,
                task_id=task_id,
                repetition=payload.get("repetition"),
                score=payload.get("score"),
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

    def _update(self, **changes: object) -> None:
        with self._lock:
            self._current.update({key: value for key, value in changes.items() if value is not None})
            self._persist_locked()
        self._render_live()

    def _complete_attempt(
        self,
        duration_seconds: float | None,
        *,
        task_id: str | None = None,
        repetition: object | None = None,
        score: object | None = None,
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
                    }
                )
                self._recent_attempts = self._recent_attempts[-3:]
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
                f"{repeat} | {phase} | elapsed {_format_duration(self._elapsed_seconds())} | ETA {_format_duration(eta)}"
            )
            if self.interactive:
                self.stream.write("\r\033[2K" + _colour(line, "36", self._colour_enabled))
                self.stream.flush()
                self._last_line_was_live = True
            else:
                self.stream.write(line + "\n")
                self.stream.flush()

    def _render_full_screen_locked(self) -> None:
        """Render a compact coding-agent-style dashboard on the alternate screen."""
        dimensions = shutil.get_terminal_size(fallback=(100, 24))
        width = max(72, dimensions.columns)
        inner = width - 2
        eta = self._eta_seconds_locked()
        elapsed = self._elapsed_seconds()
        percent = 100 * self._completed_attempts / self.total_attempts if self.total_attempts else 100.0
        task = str(self._current.get("task_id", "waiting for first task"))
        task_index = self._current.get("task_index")
        repetition = self._current.get("repetition")
        phase = str(self._current.get("phase", "starting"))
        filled = round(32 * self._completed_attempts / self.total_attempts) if self.total_attempts else 32
        bar = "#" * filled + "-" * (32 - filled)
        spinner = "|/-\\"[int(elapsed * 4) % 4]
        status = f" RUNNING {spinner} " if self._status == "in_progress" else f" {self._status.upper()} "

        def row(text: str, *, colour: str | None = None) -> str:
            plain = _trim(text, inner - 2)
            rendered = _colour(plain, colour, self._colour_enabled) if colour else plain
            return "│ " + rendered + " " * (inner - 2 - len(plain)) + " │"

        def divider(label: str) -> str:
            plain = f" {label} "
            return "├" + plain + "─" * max(0, width - 2 - len(plain)) + "┤"

        title = " Agent Benchmark Lab "
        top_fill = max(0, width - 2 - len(title) - len(status))
        lines = [
            "╭" + _colour(title, "1;36", self._colour_enabled) + "─" * top_fill + _colour(status, "1;33", self._colour_enabled) + "╮",
            row(f"Harness  {self.adapter}    Suite  {self.suite_id}    Repeats  {self.repetitions}"),
            divider("PROGRESS"),
            row(f"[{bar}]  {self._completed_attempts}/{self.total_attempts} attempts  ({percent:5.1f}%)", colour="1;36"),
            divider("CURRENT TASK"),
            row(f"Task      {task_index or 0}/{self.task_count}  {_trim(task, max(12, inner - 24))}", colour="1;37"),
            row(f"Repeat    {repetition or '-'} / {self.repetitions}"),
            row(f"Phase     {phase.upper()}"),
            divider("RUN HEALTH"),
            row(f"Elapsed   {_format_duration(elapsed)}    Estimated remaining   {_format_duration(eta)}"),
            row(f"State     {_trim(str(self.status_path), max(12, inner - 12))}", colour="2"),
            divider("RECENT ATTEMPTS"),
        ]
        if self._recent_attempts:
            for attempt in reversed(self._recent_attempts):
                score = attempt.get("score")
                score_text = f" score={float(score):.1f}" if isinstance(score, (int, float)) else ""
                repeat = attempt.get("repetition") or "-"
                duration = attempt.get("duration_seconds")
                duration_text = _format_duration(float(duration)) if isinstance(duration, (int, float)) else "unknown"
                lines.append(row(f"{attempt['task_id']}  r{repeat}  {duration_text}{score_text}"))
        else:
            lines.append(row("No completed attempts yet. ETA becomes available after the first one.", colour="2"))
        lines.extend(
            [
                "╰" + "─" * (width - 2) + "╯",
                _colour("Ctrl-C preserves checkpoints. The live state and evidence remain in the result directory.", "2", self._colour_enabled),
            ]
        )
        self.stream.write("\033[H\033[2J" + "\n".join(lines) + "\n")
        self.stream.flush()
        self._last_line_was_live = True
