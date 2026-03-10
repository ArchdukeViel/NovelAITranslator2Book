from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import SecretStr

from novelai.config.settings import settings
from novelai.core.errors import ProviderError
from novelai.prompts import build_json_translation_request, build_translation_request
from novelai.providers.openai_provider import OpenAIProvider


class _FakeResponsesAPI:
    def __init__(self, state: dict[str, object]) -> None:
        self._state = state

    async def create(self, **kwargs):
        self._state["payload"] = kwargs
        return SimpleNamespace(
            output_text="translated text",
            usage=SimpleNamespace(input_tokens=120, output_tokens=80, total_tokens=200),
        )


class _FakeAsyncOpenAI:
    def __init__(self, *, api_key: str, state: dict[str, object]) -> None:
        self.api_key = api_key
        self.responses = _FakeResponsesAPI(state)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


async def _run_provider_call(request):
    provider = OpenAIProvider()
    return await provider.translate(prompt=request.text, model="gpt-5.4", request=request)


def test_openai_provider_uses_responses_payload(monkeypatch):
    state: dict[str, Any] = {}
    previous_api_key = settings.PROVIDER_OPENAI_API_KEY
    settings.PROVIDER_OPENAI_API_KEY = SecretStr("test-key")
    monkeypatch.setattr(
        OpenAIProvider,
        "_modern_async_client",
        staticmethod(lambda: (lambda *, api_key: _FakeAsyncOpenAI(api_key=api_key, state=state))),
    )

    request = build_translation_request(
        text="これはテストです。",
        source_language="Japanese",
        target_language="English",
        glossary_entries=[{"source": "魔導具", "target": "magic device"}],
        style_preset="fantasy",
    )

    try:
        import asyncio

        result = asyncio.run(_run_provider_call(request))
    finally:
        settings.PROVIDER_OPENAI_API_KEY = previous_api_key

    payload = state["payload"]

    assert result["text"] == "translated text"
    assert result["metadata"]["usage"]["prompt_tokens"] == 120
    assert result["metadata"]["usage"]["completion_tokens"] == 80
    assert payload["model"] == "gpt-5.4"
    assert payload["input"][0]["role"] == "system"
    assert payload["input"][1]["role"] == "user"
    assert payload["input"][1]["content"][0]["type"] == "input_text"


def test_openai_provider_adds_json_schema_for_json_mode(monkeypatch):
    state: dict[str, Any] = {}
    previous_api_key = settings.PROVIDER_OPENAI_API_KEY
    settings.PROVIDER_OPENAI_API_KEY = SecretStr("test-key")
    monkeypatch.setattr(
        OpenAIProvider,
        "_modern_async_client",
        staticmethod(lambda: (lambda *, api_key: _FakeAsyncOpenAI(api_key=api_key, state=state))),
    )

    request = build_json_translation_request(
        text="第一段落。\n\n第二段落。",
        source_language="Japanese",
        target_language="English",
    )

    try:
        import asyncio

        asyncio.run(_run_provider_call(request))
    finally:
        settings.PROVIDER_OPENAI_API_KEY = previous_api_key

    payload = state["payload"]

    assert payload["text"]["format"]["type"] == "json_schema"
    assert payload["text"]["format"]["name"] == "translation_output"


# ---------------------------------------------------------------------------
# Error handling tests
# ---------------------------------------------------------------------------


def test_openai_provider_raises_when_api_key_missing():
    """Provider should raise ProviderError when no API key is configured."""
    previous = settings.PROVIDER_OPENAI_API_KEY
    settings.PROVIDER_OPENAI_API_KEY = None  # type: ignore[assignment]
    try:
        provider = OpenAIProvider()
        with pytest.raises(ProviderError, match="API key not configured"):
            asyncio.run(provider.translate(prompt="hello", model="gpt-5.4"))
    finally:
        settings.PROVIDER_OPENAI_API_KEY = previous


class _RaisingResponsesAPI:
    """Fake responses API that raises an exception on create."""

    def __init__(self, exc: Exception) -> None:
        self._exc = exc

    async def create(self, **kwargs):  # noqa: ANN003
        raise self._exc


class _FakeAsyncOpenAIWithError:
    """Fake AsyncOpenAI client that wraps a raising responses endpoint."""

    def __init__(self, *, api_key: str, exc: Exception) -> None:
        self.api_key = api_key
        self.responses = _RaisingResponsesAPI(exc)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


def test_openai_provider_propagates_api_error(monkeypatch):
    """Provider should let API errors bubble up so callers can handle them."""
    previous = settings.PROVIDER_OPENAI_API_KEY
    settings.PROVIDER_OPENAI_API_KEY = SecretStr("test-key")

    api_error = RuntimeError("quota exceeded")
    monkeypatch.setattr(
        OpenAIProvider,
        "_modern_async_client",
        staticmethod(lambda: (lambda *, api_key: _FakeAsyncOpenAIWithError(api_key=api_key, exc=api_error))),
    )

    try:
        provider = OpenAIProvider()
        with pytest.raises(RuntimeError, match="quota exceeded"):
            asyncio.run(provider.translate(prompt="hello", model="gpt-5.4"))
    finally:
        settings.PROVIDER_OPENAI_API_KEY = previous


def test_openai_provider_raises_when_openai_package_missing(monkeypatch):
    """Provider should raise ProviderError when the openai package is not installed."""
    previous = settings.PROVIDER_OPENAI_API_KEY
    settings.PROVIDER_OPENAI_API_KEY = SecretStr("test-key")
    monkeypatch.setattr(OpenAIProvider, "_modern_async_client", staticmethod(lambda: None))

    try:
        provider = OpenAIProvider()
        with pytest.raises(ProviderError, match="openai package required"):
            asyncio.run(provider.translate(prompt="hello", model="gpt-5.4"))
    finally:
        settings.PROVIDER_OPENAI_API_KEY = previous


def test_openai_provider_rejects_non_translation_request():
    """Provider should raise TypeError when request is not a TranslationRequest."""
    previous = settings.PROVIDER_OPENAI_API_KEY
    settings.PROVIDER_OPENAI_API_KEY = SecretStr("test-key")
    try:
        provider = OpenAIProvider()
        with pytest.raises(TypeError, match="TranslationRequest"):
            asyncio.run(provider.translate(prompt="hello", model="gpt-5.4", request="not a request"))
    finally:
        settings.PROVIDER_OPENAI_API_KEY = previous


class _FakeModelsAPI:
    """Fake models API for validate_connection tests."""

    def __init__(self, exc: Exception | None = None) -> None:
        self._exc = exc

    async def list(self):  # noqa: ANN001
        if self._exc:
            raise self._exc
        return []


class _FakeAsyncOpenAIForValidation:
    def __init__(self, *, api_key: str, models_exc: Exception | None = None) -> None:
        self.api_key = api_key
        self.models = _FakeModelsAPI(models_exc)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


def test_validate_connection_returns_failure_on_api_error(monkeypatch):
    """validate_connection should return (False, message) when the API call fails."""
    previous = settings.PROVIDER_OPENAI_API_KEY
    settings.PROVIDER_OPENAI_API_KEY = SecretStr("test-key")

    monkeypatch.setattr(
        OpenAIProvider,
        "_modern_async_client",
        staticmethod(lambda: (lambda *, api_key: _FakeAsyncOpenAIForValidation(api_key=api_key, models_exc=ConnectionError("timeout")))),
    )

    try:
        provider = OpenAIProvider()
        ok, msg = asyncio.run(provider.validate_connection())
        assert ok is False
        assert "timeout" in msg
    finally:
        settings.PROVIDER_OPENAI_API_KEY = previous


def test_validate_connection_success(monkeypatch):
    """validate_connection should return (True, message) on success."""
    previous = settings.PROVIDER_OPENAI_API_KEY
    settings.PROVIDER_OPENAI_API_KEY = SecretStr("test-key")

    monkeypatch.setattr(
        OpenAIProvider,
        "_modern_async_client",
        staticmethod(lambda: (lambda *, api_key: _FakeAsyncOpenAIForValidation(api_key=api_key))),
    )

    try:
        provider = OpenAIProvider()
        ok, msg = asyncio.run(provider.validate_connection())
        assert ok is True
        assert "valid" in msg.lower()
    finally:
        settings.PROVIDER_OPENAI_API_KEY = previous


def test_validate_connection_fails_without_api_key():
    """validate_connection should return failure when no API key is set."""
    previous = settings.PROVIDER_OPENAI_API_KEY
    settings.PROVIDER_OPENAI_API_KEY = None  # type: ignore[assignment]
    try:
        provider = OpenAIProvider()
        ok, msg = asyncio.run(provider.validate_connection())
        assert ok is False
        assert "API key" in msg
    finally:
        settings.PROVIDER_OPENAI_API_KEY = previous
