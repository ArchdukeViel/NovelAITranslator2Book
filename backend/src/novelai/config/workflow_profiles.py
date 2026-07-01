from __future__ import annotations

from typing import Any

from novelai.prompts.templates import HONORIFIC_POLICY_BLOCKS, STYLE_PRESET_TEMPLATES

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

WORKFLOW_DEFAULTS_KEYS = ("style_preset", "consistency_mode", "honorific_policy")


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


def default_workflow_defaults() -> dict[str, Any]:
    return {
        "style_preset": None,
        "consistency_mode": False,
        "honorific_policy": None,
    }


def normalize_workflow_defaults(value: Any) -> dict[str, Any]:
    defaults = default_workflow_defaults()
    if not isinstance(value, dict):
        return defaults

    style_preset = value.get("style_preset")
    if isinstance(style_preset, str) and style_preset.strip():
        normalized = style_preset.strip().lower()
        if normalized in STYLE_PRESET_TEMPLATES:
            defaults["style_preset"] = normalized

    consistency_mode = value.get("consistency_mode")
    if isinstance(consistency_mode, bool):
        defaults["consistency_mode"] = consistency_mode

    honorific_policy = value.get("honorific_policy")
    if isinstance(honorific_policy, str) and honorific_policy.strip():
        normalized = honorific_policy.strip().lower()
        if normalized in HONORIFIC_POLICY_BLOCKS:
            defaults["honorific_policy"] = normalized

    return defaults


def normalize_workflow_profiles(value: Any) -> dict[str, Any]:
    profiles = default_workflow_profiles()
    raw_defaults: dict[str, Any] = {}

    if isinstance(value, dict):
        merged_value = dict(value)
        for legacy_step, canonical_step in LEGACY_WORKFLOW_PROFILE_ALIASES.items():
            if canonical_step in merged_value:
                continue
            if legacy_step in merged_value:
                merged_value[canonical_step] = merged_value.get(legacy_step)

        if "defaults" in merged_value:
            raw_defaults = merged_value.pop("defaults")
            if not isinstance(raw_defaults, dict):
                raw_defaults = {}

        for step in WORKFLOW_PROFILE_STEPS:
            raw_profile = merged_value.get(step)
            if not isinstance(raw_profile, dict):
                continue
            provider = raw_profile.get("provider")
            model = raw_profile.get("model")
            profiles[step] = {
                "provider": provider.strip() if isinstance(provider, str) and provider.strip() else None,
                "model": model.strip() if isinstance(model, str) and model.strip() else None,
            }

    return {
        "steps": profiles,
        "defaults": normalize_workflow_defaults(raw_defaults),
    }
