from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ExperimentConfig:
    adapter: str
    repetitions: int
    runs_dir: Path
    model: str = "unspecified"
    budget_profile: str = "open_ended"
    label: str = ""

    def validate(self) -> None:
        if self.repetitions < 1:
            raise ValueError("repetitions must be at least 1")
        if not self.adapter:
            raise ValueError("adapter is required")
        if not self.budget_profile:
            raise ValueError("budget_profile is required")
