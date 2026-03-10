from __future__ import annotations

from collections.abc import Iterable

from novelai.glossary.glossary import Glossary, GlossaryEntryLike, GlossaryTerm, normalize_glossary_entries
from novelai.prompts.models import TranslationRequest
from novelai.prompts.templates import (
    DEFAULT_USER_PROMPT_TEMPLATE,
    JSON_CONSISTENCY_BLOCK_TEMPLATE,
    JSON_SYSTEM_PROMPT_TEMPLATE,
    JSON_USER_PROMPT_TEMPLATE,
    MULTILINGUAL_SYSTEM_PROMPT_TEMPLATE,
    STRONG_CONSISTENCY_USER_PROMPT_TEMPLATE,
    STYLE_PRESET_TEMPLATES,
)


def _require_non_empty_text(value: str, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string.")
    if not value.strip():
        raise ValueError(f"{field_name} cannot be empty.")
    return value


def _normalize_language(value: str, field_name: str) -> str:
    return _require_non_empty_text(value, field_name).strip()


def normalize_style_preset(style_preset: str | None) -> str | None:
    if style_preset is None:
        return None
    normalized = _require_non_empty_text(style_preset, "style_preset").strip().lower()
    if normalized not in STYLE_PRESET_TEMPLATES:
        supported = ", ".join(sorted(STYLE_PRESET_TEMPLATES))
        raise ValueError(f"Unsupported style preset '{style_preset}'. Supported presets: {supported}.")
    return normalized


def _coerce_glossary_entries(
    glossary_entries: Iterable[GlossaryEntryLike] | Glossary | None,
) -> list[GlossaryTerm]:
    return normalize_glossary_entries(glossary_entries)


def format_glossary_block(glossary_entries: Iterable[GlossaryEntryLike] | Glossary | None) -> str:
    entries = _coerce_glossary_entries(glossary_entries)
    if not entries:
        return ""

    lines = ["Project glossary:"]
    for entry in entries:
        lines.append(f"- {entry.source} = {entry.target}")
    return "\n".join(lines)


def _format_style_block(style_preset: str | None, target_language: str) -> str:
    normalized = normalize_style_preset(style_preset)
    if normalized is None:
        return ""
    return STYLE_PRESET_TEMPLATES[normalized].format(target_language=target_language)


def _format_additional_instructions(
    *,
    glossary_entries: Iterable[GlossaryEntryLike] | Glossary | None = None,
    style_preset: str | None = None,
    target_language: str,
    json_output: bool = False,
    consistency_mode: bool = False,
) -> str:
    blocks: list[str] = []

    glossary_block = format_glossary_block(glossary_entries)
    if glossary_block:
        blocks.append(glossary_block)

    style_block = _format_style_block(style_preset, target_language)
    if style_block:
        blocks.append(style_block)

    if json_output and consistency_mode:
        blocks.append(JSON_CONSISTENCY_BLOCK_TEMPLATE)

    if not blocks:
        return ""
    return "\n\n" + "\n\n".join(blocks)


def build_system_prompt(source_language: str, target_language: str) -> str:
    return MULTILINGUAL_SYSTEM_PROMPT_TEMPLATE.format(
        source_language=_normalize_language(source_language, "source_language"),
        target_language=_normalize_language(target_language, "target_language"),
    )


def build_user_prompt(
    text: str,
    source_language: str,
    target_language: str,
    glossary_entries: Iterable[GlossaryEntryLike] | Glossary | None = None,
    style_preset: str | None = None,
    consistency_mode: bool = False,
) -> str:
    raw_text = _require_non_empty_text(text, "text")
    normalized_source_language = _normalize_language(source_language, "source_language")
    normalized_target_language = _normalize_language(target_language, "target_language")
    template = (
        STRONG_CONSISTENCY_USER_PROMPT_TEMPLATE
        if consistency_mode
        else DEFAULT_USER_PROMPT_TEMPLATE
    )
    return template.format(
        source_language=normalized_source_language,
        target_language=normalized_target_language,
        text=raw_text,
        additional_instructions=_format_additional_instructions(
            glossary_entries=glossary_entries,
            style_preset=style_preset,
            target_language=normalized_target_language,
        ),
    )


def build_json_system_prompt(source_language: str, target_language: str) -> str:
    return JSON_SYSTEM_PROMPT_TEMPLATE.format(
        source_language=_normalize_language(source_language, "source_language"),
        target_language=_normalize_language(target_language, "target_language"),
    )


def build_json_user_prompt(
    text: str,
    source_language: str,
    target_language: str,
    glossary_entries: Iterable[GlossaryEntryLike] | Glossary | None = None,
    style_preset: str | None = None,
    consistency_mode: bool = False,
) -> str:
    raw_text = _require_non_empty_text(text, "text")
    normalized_source_language = _normalize_language(source_language, "source_language")
    normalized_target_language = _normalize_language(target_language, "target_language")
    return JSON_USER_PROMPT_TEMPLATE.format(
        source_language=normalized_source_language,
        target_language=normalized_target_language,
        text=raw_text,
        additional_instructions=_format_additional_instructions(
            glossary_entries=glossary_entries,
            style_preset=style_preset,
            target_language=normalized_target_language,
            json_output=True,
            consistency_mode=consistency_mode,
        ),
    )


def build_translation_request(
    *,
    text: str,
    source_language: str,
    target_language: str,
    glossary_entries: Iterable[GlossaryEntryLike] | Glossary | None = None,
    style_preset: str | None = None,
    consistency_mode: bool = False,
    json_output: bool = False,
) -> TranslationRequest:
    entries = tuple(_coerce_glossary_entries(glossary_entries))
    normalized_style_preset = normalize_style_preset(style_preset)

    if json_output:
        system_prompt = build_json_system_prompt(source_language, target_language)
        user_prompt = build_json_user_prompt(
            text,
            source_language,
            target_language,
            glossary_entries=entries,
            style_preset=normalized_style_preset,
            consistency_mode=consistency_mode,
        )
    else:
        system_prompt = build_system_prompt(source_language, target_language)
        user_prompt = build_user_prompt(
            text,
            source_language,
            target_language,
            glossary_entries=entries,
            style_preset=normalized_style_preset,
            consistency_mode=consistency_mode,
        )

    return TranslationRequest(
        source_language=_normalize_language(source_language, "source_language"),
        target_language=_normalize_language(target_language, "target_language"),
        text=_require_non_empty_text(text, "text"),
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        glossary_entries=entries,
        style_preset=normalized_style_preset,
        consistency_mode=consistency_mode,
        json_output=json_output,
    )


def build_json_translation_request(
    *,
    text: str,
    source_language: str,
    target_language: str,
    glossary_entries: Iterable[GlossaryEntryLike] | Glossary | None = None,
    style_preset: str | None = None,
    consistency_mode: bool = False,
) -> TranslationRequest:
    return build_translation_request(
        text=text,
        source_language=source_language,
        target_language=target_language,
        glossary_entries=glossary_entries,
        style_preset=style_preset,
        consistency_mode=consistency_mode,
        json_output=True,
    )
