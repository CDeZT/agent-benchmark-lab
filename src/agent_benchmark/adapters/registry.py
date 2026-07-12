from __future__ import annotations

from collections.abc import Callable

from agent_benchmark.adapters.aider import AiderAdapter
from agent_benchmark.adapters.base import HarnessAdapter
from agent_benchmark.adapters.claude_code import ClaudeCodeAdapter
from agent_benchmark.adapters.codex import CodexAdapter
from agent_benchmark.adapters.configured import ConfiguredHarnessAdapter
from agent_benchmark.adapters.dummy import DummyAdapter
from agent_benchmark.adapters.generic_command import GenericCommandAdapter
from agent_benchmark.adapters.grok import GrokAdapter
from agent_benchmark.adapters.opencode import OpencodeAdapter
from agent_benchmark.harness_registry import load_harness_registry


AdapterFactory = Callable[[], HarnessAdapter]


_REGISTRY: dict[str, AdapterFactory] = {
    "aider": AiderAdapter,
    "claude-code": ClaudeCodeAdapter,
    "codex": CodexAdapter,
    "dummy": DummyAdapter,
    "generic-command": GenericCommandAdapter,
    "grok": GrokAdapter,
    "opencode": OpencodeAdapter,
}


def adapter_by_name(name: str) -> HarnessAdapter:
    if name in _REGISTRY:
        return _REGISTRY[name]()
    configured = load_harness_registry().get(name)
    if configured is not None:
        return ConfiguredHarnessAdapter(name, configured)
    raise ValueError(f"Unknown adapter '{name}'. Available adapters: {', '.join(available_adapters())}")


def available_adapters() -> list[str]:
    names = set(_REGISTRY)
    names.update(load_harness_registry())
    return sorted(names)
