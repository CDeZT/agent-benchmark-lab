from __future__ import annotations

from collections.abc import Callable

from agent_benchmark.adapters.base import HarnessAdapter
from agent_benchmark.adapters.claude_code import ClaudeCodeAdapter
from agent_benchmark.adapters.dummy import DummyAdapter
from agent_benchmark.adapters.generic_command import GenericCommandAdapter
from agent_benchmark.adapters.opencode import OpencodeAdapter


AdapterFactory = Callable[[], HarnessAdapter]


_REGISTRY: dict[str, AdapterFactory] = {
    "claude-code": ClaudeCodeAdapter,
    "dummy": DummyAdapter,
    "generic-command": GenericCommandAdapter,
    "opencode": OpencodeAdapter,
}


def adapter_by_name(name: str) -> HarnessAdapter:
    try:
        return _REGISTRY[name]()
    except KeyError as exc:
        raise ValueError(f"Unknown adapter '{name}'. Available adapters: {', '.join(available_adapters())}") from exc


def available_adapters() -> list[str]:
    return sorted(_REGISTRY)
