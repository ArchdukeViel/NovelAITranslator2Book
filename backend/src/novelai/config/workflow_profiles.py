from __future__ import annotations

from typing import Any

WORKFLOW_PROFILE_STEPS = (
    "glossary_extraction",
    "glossary_translation",
    "glossary_review",
    "body_translation",
    "polish",
    "ocr",
)

LEGACY_WORKFLOW_PROFILE_ALIASES: dict[str, str] = {
    "term_extraction": "glossary_extraction",
    "term_translation": "glossary_translation",
    "term_summary": "glossary_review",
    "reembedding": "polish",
}


def normalize_workflow_profile_step(step: str) -> str:
    key = step.strip()
    return LEGACY_WORKFLOW_PROFILE_ALIASES.get(key, key)


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

    merged_value = dict(value)
    for legacy_step, canonical_step in LEGACY_WORKFLOW_PROFILE_ALIASES.items():
        if canonical_step in merged_value:
            continue
        if legacy_step in merged_value:
            merged_value[canonical_step] = merged_value.get(legacy_step)

    for step in WORKFLOW_PROFILE_STEPS:
        raw_profile = merged_value.get(step)
        if not isinstance(raw_profile, dict):
            continue
        provider = raw_profile.get("provider")
        model = raw_profile.get("model")
        normalized[step] = {
            "provider": provider.strip() if isinstance(provider, str) and provider.strip() else None,
            "model": model.strip() if isinstance(model, str) and model.strip() else None,
        }
    return normalized
