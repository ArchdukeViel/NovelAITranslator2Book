"""Optional tests for the operations router request schema."""

from __future__ import annotations

from novelai.api.routers.operations import TranslateRequest


def test_translate_request_defaults_skip_glossary_gate_to_false() -> None:
    request = TranslateRequest.model_validate({"source_key": "kakuyomu"})
    assert request.skip_glossary_gate is False


def test_translate_request_round_trips_skip_glossary_gate_true() -> None:
    request = TranslateRequest.model_validate({"source_key": "kakuyomu", "skip_glossary_gate": True})
    assert request.skip_glossary_gate is True