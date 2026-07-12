"""Load optional harness command templates from JSON.

This keeps "how to start a CLI" out of business logic so a CLI flag change is a
config edit, not a framework rewrite. Built-in Python adapters still win when
the same name is registered in code.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


DEFAULT_HARNESSES_PATH = Path("config/harnesses.json")
DEFAULT_HARNESSES_EXAMPLE_PATH = Path("config/harnesses.example.json")


def harnesses_file_path() -> Path:
    override = os.environ.get("AGENT_BENCH_HARNESSES_FILE")
    if override:
        return Path(override)
    # The example describes possible integrations; it is not an active local
    # registry. Falling back to it made `list-adapters` advertise CLIs that
    # were neither installed nor configured.
    return DEFAULT_HARNESSES_PATH


def load_harness_registry(path: Path | None = None) -> dict[str, dict[str, Any]]:
    """Return harness_id -> definition. Missing file yields an empty registry."""
    target = path or harnesses_file_path()
    if not target.exists():
        return {}
    payload = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Harness registry must be a JSON object.")
    harnesses = payload.get("harnesses", payload)
    if not isinstance(harnesses, dict):
        raise ValueError("Harness registry 'harnesses' must be an object.")
    resolved: dict[str, dict[str, Any]] = {}
    for name, definition in harnesses.items():
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Harness registry keys must be non-empty strings.")
        if not isinstance(definition, dict):
            raise ValueError(f"Harness '{name}' definition must be an object.")
        command = definition.get("default_command") or definition.get("command")
        if not isinstance(command, str) or not command.strip():
            raise ValueError(f"Harness '{name}' needs a non-empty default_command.")
        item = dict(definition)
        item["default_command"] = command
        resolved[name] = item
    return resolved


def list_configured_harnesses(path: Path | None = None) -> list[str]:
    return sorted(load_harness_registry(path))
