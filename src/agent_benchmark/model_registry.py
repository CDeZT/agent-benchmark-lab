from __future__ import annotations

import json
from pathlib import Path


def load_model_registry(path: Path) -> dict[str, dict[str, str]]:
    """Load canonical model ids mapped to adapter-specific CLI identifiers."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Model registry must be a JSON object.")
    registry: dict[str, dict[str, str]] = {}
    for canonical, mappings in payload.items():
        if not isinstance(canonical, str) or not canonical.strip():
            raise ValueError("Model registry keys must be non-empty canonical model ids.")
        if not isinstance(mappings, dict) or not mappings:
            raise ValueError(f"Model registry entry '{canonical}' must map adapters to identifiers.")
        resolved: dict[str, str] = {}
        for adapter, identifier in mappings.items():
            if not isinstance(adapter, str) or not adapter.strip() or not isinstance(identifier, str) or not identifier.strip():
                raise ValueError(f"Model registry entry '{canonical}' has an invalid adapter mapping.")
            resolved[adapter] = identifier
        registry[canonical] = resolved
    return registry


def adapter_model_for(registry: dict[str, dict[str, str]], canonical_model: str, adapter: str) -> str:
    try:
        return registry[canonical_model][adapter]
    except KeyError as exc:
        raise ValueError(
            f"Model registry has no '{adapter}' mapping for canonical model '{canonical_model}'."
        ) from exc
