from __future__ import annotations

from types import SimpleNamespace

from pydantic import SecretStr

from novelai.config.settings import settings
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
    state: dict[str, object] = {}
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
    state: dict[str, object] = {}
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
