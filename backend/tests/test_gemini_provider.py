from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import SecretStr

from novelai.config.settings import settings
from novelai.core.errors import ProviderError, ProviderErrorCode
from novelai.prompts import build_json_translation_request, build_translation_request
from novelai.providers.gemini_provider import GeminiProvider


class _FakeModelsAPI:
    def __init__(self, state: dict[str, Any]) -> None:
        self._state = state

    def generate_content(self, **kwargs: Any) -> Any:
        self._state["payload"] = kwargs
        if "raise" in self._state:
            raise self._state["raise"]
        response = self._state.get("response")
        if response is not None:
            return response
        usage = SimpleNamespace(prompt_token_count=80, candidates_token_count=42, total_token_count=122)
        return SimpleNamespace(text=self._state.get("response_text", "gemini translated"), usage_metadata=usage)


class _FakeClient:
    def __init__(self, *, api_key: str, state: dict[str, Any]) -> None:
        self.api_key = api_key
        self.models = _FakeModelsAPI(state)


def test_gemini_provider_uses_request_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    state: dict[str, Any] = {}
    previous_api_key = settings.PROVIDER_GEMINI_API_KEY
    settings.PROVIDER_GEMINI_API_KEY = SecretStr("gemini-key")

    monkeypatch.setattr(
        GeminiProvider,
        "_modern_client",
        staticmethod(lambda: (lambda *, api_key: _FakeClient(api_key=api_key, state=state))),
    )

    request = build_translation_request(
        text="これはテストです。",
        source_language="Japanese",
        target_language="English",
        glossary_entries=[{"source": "魔導具", "target": "magic device"}],
        style_preset="fantasy",
    )

    try:
        provider = GeminiProvider()
        result = asyncio.run(provider.translate(prompt=request.text, model="gemini-3-flash-preview", request=request))
    finally:
        settings.PROVIDER_GEMINI_API_KEY = previous_api_key

    payload = state["payload"]
    assert result["text"] == "gemini translated"
    assert result["metadata"]["usage"]["prompt_tokens"] == 80
    assert result["metadata"]["usage"]["completion_tokens"] == 42
    assert payload["model"] == "gemini-3-flash-preview"
    assert "contents" in payload


def test_gemini_provider_json_mode_sets_response_mime_type(monkeypatch: pytest.MonkeyPatch) -> None:
    state: dict[str, Any] = {"response_text": "{\"paragraphs\": []}"}
    previous_api_key = settings.PROVIDER_GEMINI_API_KEY
    settings.PROVIDER_GEMINI_API_KEY = SecretStr("gemini-key")

    monkeypatch.setattr(
        GeminiProvider,
        "_modern_client",
        staticmethod(lambda: (lambda *, api_key: _FakeClient(api_key=api_key, state=state))),
    )

    request = build_json_translation_request(
        text="第一段落。\n\n第二段落。",
        source_language="Japanese",
        target_language="English",
    )

    try:
        provider = GeminiProvider()
        asyncio.run(provider.translate(prompt=request.text, model="gemini-3-flash-preview", request=request))
    finally:
        settings.PROVIDER_GEMINI_API_KEY = previous_api_key

    payload = state["payload"]
    config = payload.get("config")
    assert isinstance(config, dict)
    assert config.get("response_mime_type") == "application/json"


def test_gemini_provider_accepts_custom_json_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    state: dict[str, Any] = {"response_text": "{\"terms\": []}"}
    previous_api_key = settings.PROVIDER_GEMINI_API_KEY
    settings.PROVIDER_GEMINI_API_KEY = SecretStr("gemini-key")

    monkeypatch.setattr(
        GeminiProvider,
        "_modern_client",
        staticmethod(lambda: (lambda *, api_key: _FakeClient(api_key=api_key, state=state))),
    )

    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {"terms": {"type": "array"}},
        "required": ["terms"],
    }

    try:
        provider = GeminiProvider()
        asyncio.run(provider.translate(prompt="Extract terms", model="gemini-3-flash-preview", json_schema=schema))
    finally:
        settings.PROVIDER_GEMINI_API_KEY = previous_api_key

    payload = state["payload"]
    config = payload.get("config")
    assert isinstance(config, dict)
    assert config.get("response_mime_type") == "application/json"
    assert config.get("response_schema") == schema


def test_gemini_provider_raises_when_api_key_missing() -> None:
    previous = settings.PROVIDER_GEMINI_API_KEY
    settings.PROVIDER_GEMINI_API_KEY = None  # type: ignore[assignment]
    try:
        provider = GeminiProvider()
        with pytest.raises(Exception, match="API key"):
            asyncio.run(provider.translate(prompt="hello", model="gemini-3-flash-preview"))
    finally:
        settings.PROVIDER_GEMINI_API_KEY = previous


def test_gemini_provider_validate_connection_without_sdk(monkeypatch: pytest.MonkeyPatch) -> None:
    previous = settings.PROVIDER_GEMINI_API_KEY
    settings.PROVIDER_GEMINI_API_KEY = SecretStr("gemini-key")
    monkeypatch.setattr(GeminiProvider, "_modern_client", staticmethod(lambda: None))

    try:
        provider = GeminiProvider()
        ok, msg = asyncio.run(provider.validate_connection())
        assert ok is False
        assert "google-genai" in msg
    finally:
        settings.PROVIDER_GEMINI_API_KEY = previous


class _FakeGeminiError(Exception):
    def __init__(self, message: str, *, status_code: int = 429, code: str = "RESOURCE_EXHAUSTED", details: object | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.details = details


def _run_gemini_with_state(monkeypatch: pytest.MonkeyPatch, state: dict[str, Any]) -> None:
    previous_api_key = settings.PROVIDER_GEMINI_API_KEY
    settings.PROVIDER_GEMINI_API_KEY = SecretStr("gemini-key")
    monkeypatch.setattr(
        GeminiProvider,
        "_modern_client",
        staticmethod(lambda: (lambda *, api_key: _FakeClient(api_key=api_key, state=state))),
    )
    try:
        provider = GeminiProvider()
        asyncio.run(provider.translate(prompt="hello", model="gemini-2.5-flash-lite"))
    finally:
        settings.PROVIDER_GEMINI_API_KEY = previous_api_key


def test_gemini_provider_normalizes_resource_exhausted_retry_delay(monkeypatch: pytest.MonkeyPatch) -> None:
    state = {
        "raise": _FakeGeminiError(
            "429 RESOURCE_EXHAUSTED: RPM exceeded",
            details=[{"retryDelay": "21s", "reason": "RATE_LIMIT"}],
        )
    }

    with pytest.raises(ProviderError) as caught:
        _run_gemini_with_state(monkeypatch, state)

    error = caught.value
    assert error.provider_error_code == ProviderErrorCode.RATE_LIMITED
    assert error.provider_key == "gemini"
    assert error.provider_model == "gemini-2.5-flash-lite"
    assert error.retry_after_seconds == 21
    assert error.cooldown_until is not None


def test_gemini_provider_normalizes_daily_quota_exhaustion(monkeypatch: pytest.MonkeyPatch) -> None:
    state = {
        "raise": _FakeGeminiError(
            "429 RESOURCE_EXHAUSTED: Daily quota exceeded for generate_content requests per day",
        )
    }

    with pytest.raises(ProviderError) as caught:
        _run_gemini_with_state(monkeypatch, state)

    assert caught.value.provider_error_code == ProviderErrorCode.QUOTA_EXHAUSTED
    assert caught.value.provider_model == "gemini-2.5-flash-lite"


def test_gemini_provider_normalizes_unknown_provider_error(monkeypatch: pytest.MonkeyPatch) -> None:
    state = {"raise": RuntimeError("provider transport exploded")}

    with pytest.raises(ProviderError) as caught:
        _run_gemini_with_state(monkeypatch, state)

    assert caught.value.provider_error_code == ProviderErrorCode.UNKNOWN
    assert caught.value.provider_key == "gemini"


def test_gemini_provider_normalizes_safety_blocked_response(monkeypatch: pytest.MonkeyPatch) -> None:
    state = {"response": SimpleNamespace(text="", candidates=[SimpleNamespace(finish_reason="SAFETY")])}

    with pytest.raises(ProviderError) as caught:
        _run_gemini_with_state(monkeypatch, state)

    assert caught.value.provider_error_code == ProviderErrorCode.SAFETY_BLOCKED


def test_gemini_provider_normalizes_empty_response(monkeypatch: pytest.MonkeyPatch) -> None:
    state = {"response": SimpleNamespace(text="")}

    with pytest.raises(ProviderError) as caught:
        _run_gemini_with_state(monkeypatch, state)

    assert caught.value.provider_error_code == ProviderErrorCode.EMPTY_OUTPUT


def test_gemini_provider_normalizes_partial_output(monkeypatch: pytest.MonkeyPatch) -> None:
    state = {"response": SimpleNamespace(text="partial text", candidates=[SimpleNamespace(finish_reason="MAX_TOKENS")])}

    with pytest.raises(ProviderError) as caught:
        _run_gemini_with_state(monkeypatch, state)

    assert caught.value.provider_error_code == ProviderErrorCode.PARTIAL_OUTPUT


def test_gemini_provider_normalizes_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    state: dict[str, Any] = {"response_text": "not json"}
    previous_api_key = settings.PROVIDER_GEMINI_API_KEY
    settings.PROVIDER_GEMINI_API_KEY = SecretStr("gemini-key")
    monkeypatch.setattr(
        GeminiProvider,
        "_modern_client",
        staticmethod(lambda: (lambda *, api_key: _FakeClient(api_key=api_key, state=state))),
    )
    try:
        provider = GeminiProvider()
        request = build_json_translation_request(text="hello", source_language="Japanese", target_language="English")
        with pytest.raises(ProviderError) as caught:
            asyncio.run(provider.translate(prompt=request.text, model="gemini-2.5-flash-lite", request=request))
    finally:
        settings.PROVIDER_GEMINI_API_KEY = previous_api_key

    assert caught.value.provider_error_code == ProviderErrorCode.INVALID_JSON
