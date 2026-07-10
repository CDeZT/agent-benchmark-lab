from __future__ import annotations


def summarize_model_identity(requested_model: str, detected_models: list[str]) -> dict[str, object]:
    """State whether a requested model is supported by saved harness evidence."""
    unique = sorted({model.strip() for model in detected_models if model and model.strip()})
    if requested_model == "unspecified":
        return {
            "status": "not_requested",
            "requested_model": requested_model,
            "detected_models": unique,
            "reason": "No explicit model was requested for this experiment.",
        }
    if not unique:
        return {
            "status": "requested_unverified",
            "requested_model": requested_model,
            "detected_models": [],
            "reason": "Harness output did not expose an actual model identity.",
        }
    requested = _canonical_model_name(requested_model)
    detected = {_canonical_model_name(model) for model in unique}
    if detected == {requested}:
        return {
            "status": "verified_match",
            "requested_model": requested_model,
            "detected_models": unique,
            "reason": "All detected model identities match the requested model.",
        }
    return {
        "status": "mismatch",
        "requested_model": requested_model,
        "detected_models": unique,
        "reason": "Detected model identity does not exactly match the requested model.",
    }


def _canonical_model_name(value: str) -> str:
    return value.strip().casefold().split("/")[-1]
