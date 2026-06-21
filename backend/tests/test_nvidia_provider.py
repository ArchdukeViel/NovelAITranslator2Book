from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx
import pytest
from pydantic import SecretStr

from novelai.config.settings import settings
from novelai.core.errors import ProviderError, ProviderErrorCode
from novelai.prompts import build_translation_request
from novelai.providers.nvidia_provider import NVIDIAProvider


class _FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


class _FakeAsyncClient:
    state: dict[str, Any] = {}

    def __init__(self, *, timeout: float) -> None:
        self.timeout = timeout
        self.state = self.__class__.state
        self.state["timeout"] = timeout

    async def __aenter__(self) -> _FakeAsyncClient:
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    async def post(self, url: str, *, headers: dict[str, str], json: dict[str, Any]) -> _FakeResponse:
        self.state["url"] = url
        self.state["headers"] = dict(headers)
        self.state["json"] = dict(json)
        if "raise" in self.state:
            raise self.state["raise"]
        return _FakeResponse(
            self.state.get(
                "response",
                {
                    "choices": [{"message": {"content": "nvidia translated"}, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
                },
            )
        )


@pytest.fixture
def nvidia_settings(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    previous_key = settings.NVIDIA_API_KEY
    previous_base_url = settings.NVIDIA_BASE_URL
    previous_model = settings.NVIDIA_DEFAULT_MODEL
    previous_timeout = settings.NVIDIA_TIMEOUT_SECONDS
    state: dict[str, Any] = {}
    _FakeAsyncClient.state = state
    monkeypatch.setattr("novelai.providers.nvidia_provider.httpx.AsyncClient", _FakeAsyncClient)
    settings.NVIDIA_API_KEY = SecretStr("nvidia-test-key")
    settings.NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
    settings.NVIDIA_DEFAULT_MODEL = "google/gemma-4-31b-it"
    settings.NVIDIA_TIMEOUT_SECONDS = 12.0
    try:
        yield state
    finally:
        settings.NVIDIA_API_KEY = previous_key
        settings.NVIDIA_BASE_URL = previous_base_url
        settings.NVIDIA_DEFAULT_MODEL = previous_model
        settings.NVIDIA_TIMEOUT_SECONDS = previous_timeout


def test_nvidia_provider_uses_default_base_url_and_model(nvidia_settings: dict[str, Any]) -> None:
    provider = NVIDIAProvider()

    result = asyncio.run(provider.translate("Translate this.", max_tokens=64, temperature=0.2, top_p=0.95))

    assert result["text"] == "nvidia translated"
    assert nvidia_settings["url"] == "https://integrate.api.nvidia.com/v1/chat/completions"
    assert nvidia_settings["json"]["model"] == "google/gemma-4-31b-it"
    assert [message["role"] for message in nvidia_settings["json"]["messages"]] == ["system", "user"]
    assert nvidia_settings["json"]["messages"][1]["content"] == "Translate this."
    assert nvidia_settings["json"]["stream"] is False
    assert nvidia_settings["json"]["max_tokens"] == 64
    assert nvidia_settings["json"]["temperature"] == 0.2
    assert nvidia_settings["json"]["top_p"] == 0.95
    assert nvidia_settings["json"]["chat_template_kwargs"] == {"enable_thinking": False}
    assert nvidia_settings["headers"]["Accept"] == "application/json"
    assert nvidia_settings["headers"]["Authorization"] == "Bearer nvidia-test-key"


def test_nvidia_provider_accepts_chat_template_kwargs(nvidia_settings: dict[str, Any]) -> None:
    provider = NVIDIAProvider()

    asyncio.run(
        provider.translate(
            "Translate this.",
            chat_template_kwargs={"enable_thinking": True},
        )
    )

    assert nvidia_settings["json"]["chat_template_kwargs"] == {"enable_thinking": True}


def test_nvidia_provider_translation_request_preserves_prompt_shape(nvidia_settings: dict[str, Any]) -> None:
    provider = NVIDIAProvider()
    source_text = "\u3053\u3093\u306b\u3061\u306f\u3002"
    request = build_translation_request(
        text=source_text,
        source_language="Japanese",
        target_language="English",
    )

    asyncio.run(provider.translate(prompt=request.text, model="google/gemma-4-31b-it", request=request, max_tokens=64))

    messages = nvidia_settings["json"]["messages"]
    assert [message["role"] for message in messages] == ["system", "user"]
    assert messages[0]["content"].strip()
    assert messages[1]["content"].strip()
    assert "English" in messages[0]["content"]
    assert "English" in messages[1]["content"]
    assert messages[1]["content"].count(source_text) == 1
    assert nvidia_settings["json"]["max_tokens"] == 64
    assert nvidia_settings["json"]["chat_template_kwargs"] == {"enable_thinking": False}


def test_nvidia_provider_parses_usage(nvidia_settings: dict[str, Any]) -> None:
    provider = NVIDIAProvider()

    result = asyncio.run(provider.translate("Translate this.", model="google/gemma-4-31b-it"))

    assert result["metadata"]["provider"] == "nvidia"
    assert result["metadata"]["model"] == "google/gemma-4-31b-it"
    assert result["metadata"]["usage"]["prompt_tokens"] == 10
    assert result["metadata"]["usage"]["completion_tokens"] == 5
    assert result["metadata"]["usage"]["total_tokens"] == 15


def test_nvidia_provider_maps_429_to_rate_limited(nvidia_settings: dict[str, Any]) -> None:
    request = httpx.Request("POST", "https://integrate.api.nvidia.com/v1/chat/completions")
    response = httpx.Response(
        429,
        request=request,
        headers={"retry-after": "17"},
        json={"error": {"message": "rate limit exceeded", "type": "rate_limit"}},
    )
    nvidia_settings["raise"] = httpx.HTTPStatusError("429 rate limit", request=request, response=response)
    provider = NVIDIAProvider()

    with pytest.raises(ProviderError) as caught:
        asyncio.run(provider.translate("hello"))

    assert caught.value.provider_error_code == ProviderErrorCode.RATE_LIMITED
    assert caught.value.provider_key == "nvidia"
    assert caught.value.provider_model == "google/gemma-4-31b-it"
    assert caught.value.retry_after_seconds == 17
    assert caught.value.cooldown_until is not None


def test_nvidia_provider_maps_daily_quota_to_quota_exhausted(nvidia_settings: dict[str, Any]) -> None:
    request = httpx.Request("POST", "https://integrate.api.nvidia.com/v1/chat/completions")
    response = httpx.Response(
        429,
        request=request,
        json={"error": {"message": "daily quota exceeded", "type": "quota"}},
    )
    nvidia_settings["raise"] = httpx.HTTPStatusError("429 quota", request=request, response=response)
    provider = NVIDIAProvider()

    with pytest.raises(ProviderError) as caught:
        asyncio.run(provider.translate("hello"))

    assert caught.value.provider_error_code == ProviderErrorCode.QUOTA_EXHAUSTED
    assert caught.value.exhausted_until is not None


def test_nvidia_provider_does_not_log_api_key(nvidia_settings: dict[str, Any], caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    provider = NVIDIAProvider()

    asyncio.run(provider.translate("Translate this."))

    assert "nvidia-test-key" not in caplog.text
