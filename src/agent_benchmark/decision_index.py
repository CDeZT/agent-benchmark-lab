"""Versioned, explicitly non-authoritative composite for personal tool choice."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


DEFAULT_PROFILE_PATH = Path("config/decision_index_profiles.json")
DEFAULT_PROFILE_ID = "balanced-v1"


def build_decision_index(
    suite_summary: dict[str, Any],
    *,
    profile_path: Path = DEFAULT_PROFILE_PATH,
    profile_id: str = DEFAULT_PROFILE_ID,
) -> dict[str, Any]:
    """Build a declared local/official decision aid without hiding its gates.

    This deliberately does not replace either native measurement. It records a
    frozen profile, both components, and every unmet evidence requirement.
    """
    profile, fingerprint = load_profile(profile_path, profile_id)
    local_score = _number(suite_summary.get("mean_verified_normalized_score"))
    local_coverage = _number(suite_summary.get("mean_verified_coverage_percent"))
    repetitions = int(suite_summary.get("repetitions_per_task") or 0)
    official = suite_summary.get("official_tracks")
    official = official if isinstance(official, dict) else {}
    official_rate = _number(official.get("resolution_rate_percent"))
    official_attempts = int(official.get("scorable_attempt_count") or 0)
    official_candidates = int(official.get("ranking_candidate_task_count") or 0)

    warnings: list[str] = []
    if local_score is None:
        warnings.append("missing_local_verified_normalized_score")
    if local_coverage is None:
        warnings.append("missing_local_verified_coverage")
    elif local_coverage < float(profile["minimum_local_verified_coverage_percent"]):
        warnings.append("local_verified_coverage_below_threshold")
    if repetitions < int(profile["minimum_repetitions_per_task"]):
        warnings.append("repetitions_below_threshold")
    if official_rate is None:
        warnings.append("missing_official_resolution_rate")
    if official_attempts < int(profile["minimum_official_scorable_attempts"]):
        warnings.append("official_scorable_attempts_below_threshold")
    if official_candidates <= 0:
        warnings.append("missing_official_ranking_candidates")

    score = None
    if local_score is not None and official_rate is not None:
        score = round(
            local_score * float(profile["local_verified_normalized_weight"])
            + official_rate * float(profile["official_swe_resolution_weight"]),
            2,
        )
    status = "ready" if score is not None and not warnings else ("provisional" if score is not None else "unavailable")
    return {
        "profile_id": profile_id,
        "profile": profile,
        "profile_fingerprint": fingerprint,
        "status": status,
        "score": score,
        "components": {
            "local_verified_normalized_score": local_score,
            "local_verified_coverage_percent": local_coverage,
            "official_swe_resolution_rate_percent": official_rate,
            "official_scorable_attempt_count": official_attempts,
            "official_ranking_candidate_task_count": official_candidates,
            "repetitions_per_task": repetitions,
        },
        "warnings": warnings,
        "policy": "Decision index is a versioned personal selection aid. It does not replace local scorecards, official evaluator outcomes, confidence intervals, or raw evidence.",
    }


def load_profile(path: Path, profile_id: str) -> tuple[dict[str, Any], str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    profiles = payload.get("profiles") if isinstance(payload, dict) else None
    profile = profiles.get(profile_id) if isinstance(profiles, dict) else None
    if not isinstance(profile, dict):
        raise ValueError(f"Unknown decision index profile '{profile_id}' in {path}.")
    required = {
        "local_verified_normalized_weight",
        "official_swe_resolution_weight",
        "minimum_repetitions_per_task",
        "minimum_local_verified_coverage_percent",
        "minimum_official_scorable_attempts",
        "policy",
    }
    missing = sorted(required - profile.keys())
    if missing:
        raise ValueError(f"Decision index profile '{profile_id}' is missing: {', '.join(missing)}.")
    local_weight = float(profile["local_verified_normalized_weight"])
    official_weight = float(profile["official_swe_resolution_weight"])
    if local_weight < 0 or official_weight < 0 or round(local_weight + official_weight, 9) != 1.0:
        raise ValueError("Decision index component weights must be non-negative and sum to 1.")
    serialized = json.dumps(profile, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return dict(profile), hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _number(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None
