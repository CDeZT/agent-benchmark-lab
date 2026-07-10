from __future__ import annotations

from dataclasses import dataclass


@dataclass
class BudgetProfile:
    name: str
    max_attempts: int | None = None
    max_duration_seconds: float | None = None
    max_tool_calls: int | None = None
    description: str = ""


PROFILES: dict[str, BudgetProfile] = {
    "oneshot": BudgetProfile(name="oneshot", max_attempts=1, description="Single attempt, no retries"),
    "bounded": BudgetProfile(name="bounded", max_attempts=3, max_duration_seconds=300, description="Limited attempts and time"),
    "open_ended": BudgetProfile(name="open_ended", description="No limits"),
    "human_like": BudgetProfile(name="human_like", max_attempts=5, description="Allows normal dev loops"),
    "stress": BudgetProfile(name="stress", max_duration_seconds=3600, description="Long horizon tasks"),
    "audit": BudgetProfile(name="audit", description="Internal audit profile"),
    "real_smoke": BudgetProfile(name="real_smoke", description="Real harness smoke test"),
}


def get_profile(name: str) -> BudgetProfile:
    return PROFILES.get(name, PROFILES["open_ended"])


def profile_instruction_suffix(profile: BudgetProfile) -> str:
    """Generate instruction suffix text for a budget profile."""
    if profile.name == "open_ended":
        return ""
    suffix = f"\n\n[BUDGET PROFILE: {profile.name.upper()} -- {profile.description}.]"
    if profile.max_attempts is not None:
        suffix += f" You have at most {profile.max_attempts} attempt(s)."
    if profile.max_duration_seconds is not None:
        suffix += f" Maximum duration is {profile.max_duration_seconds} seconds."
    suffix += "\n"
    return suffix


KNOWN_PROFILE_NAMES = frozenset(PROFILES.keys())
