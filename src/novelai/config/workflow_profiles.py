from __future__ import annotations

from typing import Any

WORKFLOW_PROFILE_STEPS = (
    "term_extraction",
    "term_summary",
    "term_translation",
    "body_translation",
    "ocr",
    "reembedding",
)


def default_workflow_profiles() -> dict[str, dict[str, str | None]]:
    return {
        step: {
            "provider": None,
            "model": None,
        }
        for step in WORKFLOW_PROFILE_STEPS
    }


def normalize_workflow_profiles(value: Any) -> dict[str, dict[str, str | None]]:
    normalized = default_workflow_profiles()
    if not isinstance(value, dict):
        return normalized

    for step in WORKFLOW_PROFILE_STEPS:
        raw_profile = value.get(step)
        if not isinstance(raw_profile, dict):
            continue
        provider = raw_profile.get("provider")
        model = raw_profile.get("model")
        normalized[step] = {
            "provider": provider.strip() if isinstance(provider, str) and provider.strip() else None,
            "model": model.strip() if isinstance(model, str) and model.strip() else None,
        }
    return normalized
