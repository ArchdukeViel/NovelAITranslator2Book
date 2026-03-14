from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import SecretStr

from novelai.config.settings import settings
from novelai.prompts import build_json_translation_request, build_translation_request
from novelai.providers.gemini_provider import GeminiProvider


class _FakeModelsAPI:
    def __init__(self, state: dict[str, Any]) -> None:
        self._state = state

    def generate_content(self, **kwargs: Any) -> Any:
        self._state["payload"] = kwargs
        usage = SimpleNamespace(prompt_token_count=80, candidates_token_count=42, total_token_count=122)
        return SimpleNamespace(text="gemini translated", usage_metadata=usage)


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
    state: dict[str, Any] = {}
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
    state: dict[str, Any] = {}
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
