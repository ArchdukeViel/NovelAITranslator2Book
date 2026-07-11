"""Mock Gemini provider for e2e integration tests.

Implements the TranslationProvider interface with deterministic
translations and configurable failure injection. No real API calls.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from novelai.providers.base import TranslationProvider


class MockGeminiProvider(TranslationProvider):
    """Deterministic mock provider for e2e tests.

    Returns ``[EN] {source_text}`` for any input. Supports per-chapter
    failure injection and call-count tracking for assertions.
    """

    provider_key = "mock-gemini"

    def __init__(self) -> None:
        self._call_count: int = 0
        self._fail_at: int | None = None  # fail starting at this call number (1-based)

    @property
    def key(self) -> str:
        return self.provider_key

    def available_models(self) -> list[str]:
        return ["mock-gemini-default"]

    def get_call_count(self) -> int:
        """Return total translate calls across all chunks."""
        return self._call_count

    def reset(self) -> None:
        """Reset call count and failure injection."""
        self._call_count = 0
        self._fail_at = None

    async def translate(
        self,
        prompt: str,
        model: str | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> Mapping[str, Any]:
        self._call_count += 1

        if self._fail_at is not None and self._call_count >= self._fail_at:
            raise RuntimeError("Simulated provider failure")

        # Return clean English text (no CJK) so Translation QA passes.
        return {"text": "This is the translated content."}
