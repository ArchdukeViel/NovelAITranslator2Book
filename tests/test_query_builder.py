"""Tests for query builder."""

import shutil
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from novelai.core.chapter_state import ChapterState
from novelai.services.query_builder import ChapterQueryBuilder
from novelai.services.storage_service import StorageService
from tests.conftest import TESTS_TMP_ROOT


@pytest.fixture
def storage():
    """Provide temporary storage."""
    TESTS_TMP_ROOT.mkdir(parents=True, exist_ok=True)
    data_dir = TESTS_TMP_ROOT / f"query_{uuid4().hex}"
    data_dir.mkdir(parents=True, exist_ok=False)
    store = StorageService(data_dir)
    
    # Add test data
    store.update_chapter_state("novel1", "ch1", ChapterState.SCRAPED)
    store.update_chapter_state("novel1", "ch2", ChapterState.PARSED)
    store.update_chapter_state("novel1", "ch3", ChapterState.TRANSLATED)
    store.update_chapter_state("novel1", "ch4", ChapterState.TRANSLATED)
    store.update_chapter_state("novel1", "ch5", ChapterState.EXPORTED)
    store.update_chapter_state("novel1", "ch6", ChapterState.TRANSLATED, error="API Error")
    
    yield store
    shutil.rmtree(data_dir, ignore_errors=True)


def test_query_by_state(storage):
    """Test filtering by state."""
    results = storage.query_chapters("novel1").by_state(ChapterState.TRANSLATED).execute()
    
    assert len(results) == 3
    assert all(r.current_state == ChapterState.TRANSLATED for r in results)


def test_query_by_multiple_states(storage):
    """Test filtering by multiple states."""
    results = (
        storage.query_chapters("novel1")
        .by_states([ChapterState.TRANSLATED, ChapterState.EXPORTED])
        .execute()
    )
    
    assert len(results) == 4


def test_query_has_errors(storage):
    """Test filtering chapters with errors."""
    results = storage.query_chapters("novel1").has_errors().execute()
    
    assert len(results) >= 1
    assert any(r.error_count > 0 for r in results)


def test_query_no_errors(storage):
    """Test filtering chapters without errors."""
    results = storage.query_chapters("novel1").no_errors().execute()
    
    assert len(results) >= 4
    assert all(r.error_count == 0 for r in results)


def test_query_error_count_filtering(storage):
    """Test error count range filtering."""
    results_gte = storage.query_chapters("novel1").error_count_gte(1).execute()
    results_lte = storage.query_chapters("novel1").error_count_lte(0).execute()
    
    assert len(results_gte) >= 1
    assert len(results_lte) >= 4


def test_query_sort_by_state(storage):
    """Test sorting by state."""
    results = storage.query_chapters("novel1").sort_by("state").execute()
    
    assert len(results) > 0
    states = [r.current_state.value for r in results]
    assert states == sorted(states)


def test_query_sort_by_updated(storage):
    """Test sorting by updated time."""
    results = storage.query_chapters("novel1").sort_by("updated").execute()
    
    assert len(results) > 0
    timestamps = [r.last_updated for r in results]
    assert timestamps == sorted(timestamps)


def test_query_sort_reverse(storage):
    """Test reverse sorting."""
    forward = storage.query_chapters("novel1").sort_by("state").execute()
    reverse = storage.query_chapters("novel1").sort_by("state", reverse=True).execute()
    
    forward_states = [r.current_state.value for r in forward]
    reverse_states = [r.current_state.value for r in reverse]
    
    assert forward_states == list(reversed(reverse_states))


def test_query_limit(storage):
    """Test limiting results."""
    results = storage.query_chapters("novel1").limit(3).execute()
    
    assert len(results) == 3


def test_query_offset(storage):
    """Test offsetting results."""
    all_results = storage.query_chapters("novel1").sort_by("state").execute()
    offset_results = storage.query_chapters("novel1").offset(2).sort_by("state").execute()
    
    assert len(offset_results) == len(all_results) - 2
    assert offset_results[0].chapter_id == all_results[2].chapter_id


def test_query_paginate(storage):
    """Test pagination."""
    page1 = storage.query_chapters("novel1").paginate(page=1, per_page=2).execute()
    page2 = storage.query_chapters("novel1").paginate(page=2, per_page=2).execute()
    
    assert len(page1) == 2
    assert len(page2) == 2
    assert page1[0].chapter_id != page2[0].chapter_id


def test_query_count(storage):
    """Test getting count without pagination."""
    count = storage.query_chapters("novel1").by_state(ChapterState.TRANSLATED).count()
    
    assert count == 3


def test_query_exists(storage):
    """Test checking if results exist."""
    exists = storage.query_chapters("novel1").by_state(ChapterState.TRANSLATED).exists()
    not_exists = storage.query_chapters("novel1").by_state(ChapterState.SEGMENTED).exists()
    
    assert exists is True
    assert not_exists is False


def test_query_chaining(storage):
    """Test method chaining."""
    results = (
        storage.query_chapters("novel1")
        .no_errors()
        .by_state(ChapterState.TRANSLATED)
        .sort_by("updated", reverse=True)
        .limit(2)
        .execute()
    )
    
    assert len(results) == 2
    assert all(r.current_state == ChapterState.TRANSLATED for r in results)
    assert all(r.error_count == 0 for r in results)


def test_query_result_attributes(storage):
    """Test query result attributes."""
    results = storage.query_chapters("novel1").by_state(ChapterState.TRANSLATED).execute()
    
    result = results[0]
    assert hasattr(result, "chapter_id")
    assert hasattr(result, "current_state")
    assert hasattr(result, "last_updated")
    assert hasattr(result, "error_count")
    assert hasattr(result, "retry_count")
    assert hasattr(result, "transitions_count")
    
    # Test to_dict
    result_dict = result.to_dict()
    assert result_dict["chapter_id"] == result.chapter_id
    assert result_dict["current_state"] == result.current_state.value


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
