from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from agent_benchmark.runner.profiles import BudgetProfile, get_profile


@dataclass(frozen=True)
class ExperimentConfig:
    adapter: str
    repetitions: int
    runs_dir: Path
    model: str = "unspecified"
    adapter_model: str | None = None
    budget_profile: str = "open_ended"
    label: str = ""

    def validate(self) -> None:
        if self.repetitions < 1:
            raise ValueError("repetitions must be at least 1")
        if not self.adapter:
            raise ValueError("adapter is required")
        if not self.budget_profile:
            raise ValueError("budget_profile is required")
        if self.adapter_model is not None and not self.adapter_model.strip():
            raise ValueError("adapter_model must be non-empty when supplied")

    @property
    def invocation_model(self) -> str:
        return self.adapter_model or self.model

    @property
    def profile(self) -> BudgetProfile:
        return get_profile(self.budget_profile)
