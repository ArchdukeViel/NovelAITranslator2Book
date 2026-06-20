from __future__ import annotations

from collections.abc import Iterable

from novelai.config.settings import settings


def _add_unique(target: list[str], value: str | None) -> None:
    if not isinstance(value, str):
        return
    cleaned = value.strip()
    if cleaned and cleaned not in target:
        target.append(cleaned)


def model_candidates(
    provider_key: str,
    requested_model: str | None,
    supported_models: Iterable[str] | None = None,
) -> list[str]:
    """Return provider model candidates in fallback order."""
    candidates: list[str] = []
    supported = [model for model in supported_models or [] if isinstance(model, str) and model.strip()]

    _add_unique(candidates, requested_model)
    if provider_key == "gemini":
        _add_unique(candidates, settings.PROVIDER_GEMINI_DEFAULT_MODEL)
        for model in settings.PROVIDER_GEMINI_MODEL_FALLBACKS:
            _add_unique(candidates, model)
        for model in supported:
            _add_unique(candidates, model)
    elif supported:
        if requested_model in supported:
            _add_unique(candidates, requested_model)
        else:
            _add_unique(candidates, supported[0])

    if not candidates:
        _add_unique(candidates, requested_model)
    return candidates
