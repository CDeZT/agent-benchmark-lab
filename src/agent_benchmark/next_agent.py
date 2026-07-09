from __future__ import annotations

from pathlib import Path


DEFAULT_PROMPT_PATH = Path("docs/next_agent_prompt.md")


def load_next_agent_prompt(path: Path = DEFAULT_PROMPT_PATH) -> str:
    return path.read_text(encoding="utf-8")
