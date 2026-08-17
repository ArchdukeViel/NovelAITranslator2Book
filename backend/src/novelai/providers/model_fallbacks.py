from __future__ import annotations

from collections.abc import Iterable

from novelai.config.settings import GEMINI_DEFAULT_MODEL


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
    """Return one model for Gemini and a requested/supported model for others.

    Gemini deliberately has no alternate-model path. A stale explicit Gemini
    model is retained here so the provider can reject it as configuration
    instead of silently rewriting the caller's identity.
    """
    candidates: list[str] = []
    supported = [model for model in supported_models or [] if isinstance(model, str) and model.strip()]

    if provider_key.strip().lower() == "gemini":
        _add_unique(candidates, requested_model or GEMINI_DEFAULT_MODEL)
        return candidates

    _add_unique(candidates, requested_model)
    if not candidates and supported:
        _add_unique(candidates, supported[0])
    return candidates
