from __future__ import annotations

from typing import Any

from agent_benchmark.adapters.command_base import ShellCommandAdapter


class ConfiguredHarnessAdapter(ShellCommandAdapter):
    """Thin shell adapter created from config/harnesses*.json.

    Used for harnesses that are not hard-coded Python classes. Maintenance is
    intentionally limited to the command template string.
    """

    def __init__(self, name: str, definition: dict[str, Any]) -> None:
        self.name = name
        self.model_selection = str(definition.get("model_selection", "cli"))
        self.command_env = str(definition.get("command_env") or f"AGENT_BENCH_{name.upper().replace('-', '_')}_COMMAND")
        self.timeout_env = str(definition.get("timeout_env") or f"AGENT_BENCH_{name.upper().replace('-', '_')}_TIMEOUT_SECONDS")
        self.default_command_template = str(definition["default_command"])
        self.display_name = str(definition.get("display_name") or name)
