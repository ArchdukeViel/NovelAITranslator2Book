"""Tests for semantic cache and LLM QA disabled-by-default configuration.

These tests verify REQ-4.3: both features must be disabled by default.
"""

from __future__ import annotations

import pytest

from novelai.config.settings import settings


def test_semantic_cache_disabled_by_default() -> None:
    """REQ-4.3: Semantic cache must be disabled by default."""
    assert settings.SEMANTIC_CACHE_ENABLED is False


def test_llm_qa_disabled_by_default() -> None:
    """REQ-4.3: LLM QA must be disabled by default."""
    assert settings.LLM_QA_ENABLED is False


def test_semantic_cache_threshold_bounds() -> None:
    """REQ-1.3: Semantic cache similarity threshold must be bounded 0-1."""
    assert 0.0 <= settings.SEMANTIC_CACHE_SIMILARITY_THRESHOLD <= 1.0


def test_semantic_cache_context_guard_default() -> None:
    """REQ-1.3: Context guard must be enabled by default."""
    assert settings.SEMANTIC_CACHE_CONTEXT_GUARD_ENABLED is True


def test_llm_qa_cost_tracking_default() -> None:
    """REQ-3.4: LLM QA cost tracking must be enabled by default."""
    assert settings.LLM_QA_COST_TRACKING_ENABLED is True


def test_semantic_cache_embedding_provider_default() -> None:
    """REQ-2.1: Embedding provider must default to a known provider."""
    assert settings.SEMANTIC_CACHE_EMBEDDING_PROVIDER == "gemini"


def test_llm_qa_provider_default() -> None:
    """LLM QA provider must default to a known provider."""
    assert settings.LLM_QA_PROVIDER == "gemini"