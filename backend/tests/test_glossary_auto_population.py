"""Tests for glossary auto-population: SuggestionExtractor, GlossarySuggestionService."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from novelai.services.glossary.suggestion_extractor import SuggestionExtractor
from novelai.services.glossary.suggestion_service import (
    GlossarySuggestion,
    GlossarySuggestionService,
)

# ── SuggestionExtractor tests ──────────────────────────────────────────────


class TestSuggestionExtractor:
    def test_extract_cjk_terms(self) -> None:
        chapters = [
            {"chapter_id": "ch1", "translated_text": "太郎は公園で花子に会った。太郎は嬉しかった。"},
            {"chapter_id": "ch2", "translated_text": "花子が太郎に手紙を書いた。"},
        ]
        extractor = SuggestionExtractor(min_frequency=2)
        results = extractor.extract(0, chapters)
        terms = [r.source_term for r in results]
        assert "太郎" in terms
        assert "花子" in terms

    def test_extract_latin_terms(self) -> None:
        chapters = [
            {"chapter_id": "ch1", "translated_text": "John walked to the store. John bought milk."},
            {"chapter_id": "ch2", "translated_text": "Mary met John at the park."},
        ]
        extractor = SuggestionExtractor(min_frequency=2)
        results = extractor.extract(0, chapters)
        terms = [r.source_term for r in results]
        assert "John" in terms

    def test_min_frequency_filter(self) -> None:
        chapters = [
            {"chapter_id": "ch1", "translated_text": "Alice met Bob."},
            {"chapter_id": "ch2", "translated_text": "Charlie met David."},
        ]
        extractor = SuggestionExtractor(min_frequency=3)
        results = extractor.extract(0, chapters)
        assert len(results) == 0

    def test_excludes_existing_terms(self) -> None:
        chapters = [
            {"chapter_id": "ch1", "translated_text": "Hero fought the dragon. Hero won."},
        ]
        extractor = SuggestionExtractor(min_frequency=1)
        results = extractor.extract(0, chapters, existing_terms={"Hero"})
        assert all(r.source_term != "Hero" for r in results)

    def test_graceful_failure(self) -> None:
        extractor = SuggestionExtractor()
        with patch.object(extractor, "_extract", side_effect=RuntimeError("boom")):
            results = extractor.extract(0, [{"chapter_id": "ch1", "translated_text": "test"}])
        assert results == []

    def test_max_suggestions(self) -> None:
        chapters = [
            {"chapter_id": "ch1", "translated_text": "Alice Bob Charlie David Eve Frank Grace Henry " * 5},
        ]
        extractor = SuggestionExtractor(min_frequency=1, max_suggestions=3)
        results = extractor.extract(0, chapters)
        assert len(results) <= 3

    def test_context_snippets(self) -> None:
        chapters = [
            {"chapter_id": "ch1", "translated_text": "The brave Hero saved the village. Hero was celebrated."},
        ]
        extractor = SuggestionExtractor(min_frequency=1)
        results = extractor.extract(0, chapters)
        hero = next((r for r in results if r.source_term == "Hero"), None)
        if hero:
            assert len(hero.context_snippets) > 0
            assert "brave Hero" in hero.context_snippets[0]


# ── GlossarySuggestionService tests ────────────────────────────────────────


class TestGlossarySuggestionService:
    @pytest.fixture
    def svc(self, tmp_path: Path) -> GlossarySuggestionService:
        return GlossarySuggestionService(base_dir=tmp_path)

    def test_add_and_list(self, svc: GlossarySuggestionService) -> None:
        suggestions = [
            GlossarySuggestion(id="", source_term="Hero", occurrence_count=3, chapter_count=2),
            GlossarySuggestion(id="", source_term="Dragon", occurrence_count=2, chapter_count=1),
        ]
        svc.add_suggestions("novel_1", suggestions)
        all_sugs = svc.list_suggestions("novel_1")
        assert len(all_sugs) == 2
        assert all(s.status == "pending" for s in all_sugs)

    def test_dedup_same_term(self, svc: GlossarySuggestionService) -> None:
        s1 = [GlossarySuggestion(id="", source_term="Hero", occurrence_count=3, chapter_count=2)]
        s2 = [GlossarySuggestion(id="", source_term="Hero", occurrence_count=5, chapter_count=3)]
        svc.add_suggestions("novel_1", s1)
        svc.add_suggestions("novel_1", s2)
        all_sugs = svc.list_suggestions("novel_1")
        assert len(all_sugs) == 1
        # occurrence count should be max of both
        assert all_sugs[0].occurrence_count == 5

    def test_accept_flow(self, svc: GlossarySuggestionService) -> None:
        svc.add_suggestions("novel_1", [
            GlossarySuggestion(id="", source_term="Hero", occurrence_count=3, chapter_count=2),
        ])
        sug = svc.list_suggestions("novel_1")[0]
        accepted = svc.accept("novel_1", sug.id, modified_translation="主人公")
        assert accepted is not None
        assert accepted.status == "accepted"
        assert accepted.approved_translation == "主人公"
        # Verify persistence
        accepted_list = svc.list_suggestions("novel_1", status="accepted")
        assert len(accepted_list) == 1

    def test_reject_flow(self, svc: GlossarySuggestionService) -> None:
        svc.add_suggestions("novel_1", [
            GlossarySuggestion(id="", source_term="Hero", occurrence_count=3, chapter_count=2),
        ])
        sug = svc.list_suggestions("novel_1")[0]
        rejected = svc.reject("novel_1", sug.id, reason="Not relevant")
        assert rejected is not None
        assert rejected.status == "rejected"
        assert rejected.rejection_reason == "Not relevant"

    def test_rejected_not_re_suggested(self, svc: GlossarySuggestionService) -> None:
        """Rejected terms should be skipped on subsequent add_suggestions."""
        svc.add_suggestions("novel_1", [
            GlossarySuggestion(id="", source_term="Hero", occurrence_count=3, chapter_count=2),
        ])
        sug = svc.list_suggestions("novel_1")[0]
        svc.reject("novel_1", sug.id)
        # Try adding same term again
        added = svc.add_suggestions("novel_1", [
            GlossarySuggestion(id="", source_term="Hero", occurrence_count=5, chapter_count=3),
        ])
        assert len(added) == 0  # should skip since it's rejected

    def test_accept_all(self, svc: GlossarySuggestionService) -> None:
        svc.add_suggestions("novel_1", [
            GlossarySuggestion(id="", source_term="Hero", occurrence_count=3, chapter_count=2),
            GlossarySuggestion(id="", source_term="Dragon", occurrence_count=2, chapter_count=1),
        ])
        results = svc.accept_all("novel_1")
        assert len(results) == 2
        assert all(s.status == "accepted" for s in results)

    def test_reject_all(self, svc: GlossarySuggestionService) -> None:
        svc.add_suggestions("novel_1", [
            GlossarySuggestion(id="", source_term="Hero", occurrence_count=3, chapter_count=2),
            GlossarySuggestion(id="", source_term="Dragon", occurrence_count=2, chapter_count=1),
        ])
        results = svc.reject_all("novel_1")
        assert len(results) == 2
        assert all(s.status == "rejected" for s in results)

    def test_filter_by_status(self, svc: GlossarySuggestionService) -> None:
        svc.add_suggestions("novel_1", [
            GlossarySuggestion(id="", source_term="Hero", occurrence_count=3, chapter_count=2),
        ])
        sug = svc.list_suggestions("novel_1")[0]
        svc.accept("novel_1", sug.id)
        pending = svc.list_suggestions("novel_1", status="pending")
        accepted = svc.list_suggestions("novel_1", status="accepted")
        assert len(pending) == 0
        assert len(accepted) == 1

    def test_add_suggestions_rejects_duplicate_ids(self, svc: GlossarySuggestionService) -> None:
        """Adding same suggestion twice should merge not duplicate."""
        s = GlossarySuggestion(id="", source_term="UniqueTerm", occurrence_count=2, chapter_count=1)
        svc.add_suggestions("novel_1", [s])
        svc.add_suggestions("novel_1", [s])
        all_sugs = svc.list_suggestions("novel_1")
        assert len(all_sugs) == 1

    def test_count_pending(self, svc: GlossarySuggestionService) -> None:
        assert svc.count_pending("novel_1") == 0
        svc.add_suggestions("novel_1", [
            GlossarySuggestion(id="", source_term="Hero", occurrence_count=2, chapter_count=1),
        ])
        assert svc.count_pending("novel_1") == 1

    def test_get_nonexistent(self, svc: GlossarySuggestionService) -> None:
        assert svc.get_suggestion("novel_1", "999") is None

    def test_accept_nonexistent(self, svc: GlossarySuggestionService) -> None:
        assert svc.accept("novel_1", "999") is None

    def test_reject_nonexistent(self, svc: GlossarySuggestionService) -> None:
        assert svc.reject("novel_1", "999") is None


# ── API endpoint tests ─────────────────────────────────────────────────────


class TestSuggestionAPI:
    """Test suggestion API endpoints via TestClient.

    Uses direct route testing since the admin router depends on
    Starlette session middleware, CSRF, and owner auth which are
    complex to mock in isolation.
    """

    def test_list_via_service(self, tmp_path: Path) -> None:
        svc = GlossarySuggestionService(base_dir=tmp_path)
        svc.add_suggestions("test_novel", [
            GlossarySuggestion(id="", source_term="Hero", occurrence_count=3, chapter_count=2),
        ])
        items = svc.list_suggestions("test_novel")
        assert len(items) == 1
        assert items[0].source_term == "Hero"

    def test_list_empty(self, tmp_path: Path) -> None:
        svc = GlossarySuggestionService(base_dir=tmp_path)
        items = svc.list_suggestions("test_novel")
        assert items == []

    def test_list_filter_status(self, tmp_path: Path) -> None:
        svc = GlossarySuggestionService(base_dir=tmp_path)
        svc.add_suggestions("test_novel", [
            GlossarySuggestion(id="", source_term="Hero", occurrence_count=3, chapter_count=2),
        ])
        sug = svc.list_suggestions("test_novel")[0]
        svc.accept("test_novel", sug.id)
        pending = svc.list_suggestions("test_novel", status="pending")
        accepted = svc.list_suggestions("test_novel", status="accepted")
        assert len(pending) == 0
        assert len(accepted) == 1

    def test_list_filter_source(self, tmp_path: Path) -> None:
        svc = GlossarySuggestionService(base_dir=tmp_path)
        svc.add_suggestions("test_novel", [
            GlossarySuggestion(id="", source_term="Hero", occurrence_count=3, chapter_count=2, source="frequency"),
        ])
        freq = svc.list_suggestions("test_novel", source="frequency")
        llm = svc.list_suggestions("test_novel", source="llm")
        assert len(freq) == 1
        assert len(llm) == 0

    def test_accept_suggestion(self, tmp_path: Path) -> None:
        svc = GlossarySuggestionService(base_dir=tmp_path)
        svc.add_suggestions("test_novel", [
            GlossarySuggestion(id="", source_term="Hero", occurrence_count=3, chapter_count=2),
        ])
        sug = svc.list_suggestions("test_novel")[0]
        result = svc.accept("test_novel", sug.id)
        assert result is not None
        assert result.status == "accepted"

    def test_accept_with_translation(self, tmp_path: Path) -> None:
        svc = GlossarySuggestionService(base_dir=tmp_path)
        svc.add_suggestions("test_novel", [
            GlossarySuggestion(id="", source_term="Hero", occurrence_count=3, chapter_count=2),
        ])
        sug = svc.list_suggestions("test_novel")[0]
        result = svc.accept("test_novel", sug.id, modified_translation="主人公")
        assert result is not None
        assert result.approved_translation == "主人公"

    def test_reject_suggestion(self, tmp_path: Path) -> None:
        svc = GlossarySuggestionService(base_dir=tmp_path)
        svc.add_suggestions("test_novel", [
            GlossarySuggestion(id="", source_term="Hero", occurrence_count=3, chapter_count=2),
        ])
        sug = svc.list_suggestions("test_novel")[0]
        result = svc.reject("test_novel", sug.id, reason="Not relevant")
        assert result is not None
        assert result.status == "rejected"
        assert result.rejection_reason == "Not relevant"

    def test_accept_nonexistent(self, tmp_path: Path) -> None:
        svc = GlossarySuggestionService(base_dir=tmp_path)
        assert svc.accept("test_novel", "999") is None

    def test_reject_nonexistent(self, tmp_path: Path) -> None:
        svc = GlossarySuggestionService(base_dir=tmp_path)
        assert svc.reject("test_novel", "999") is None

    def test_accept_all(self, tmp_path: Path) -> None:
        svc = GlossarySuggestionService(base_dir=tmp_path)
        svc.add_suggestions("test_novel", [
            GlossarySuggestion(id="", source_term="Hero", occurrence_count=3, chapter_count=2),
            GlossarySuggestion(id="", source_term="Dragon", occurrence_count=2, chapter_count=1),
        ])
        results = svc.accept_all("test_novel")
        assert len(results) == 2
        assert all(s.status == "accepted" for s in results)

    def test_reject_all(self, tmp_path: Path) -> None:
        svc = GlossarySuggestionService(base_dir=tmp_path)
        svc.add_suggestions("test_novel", [
            GlossarySuggestion(id="", source_term="Hero", occurrence_count=3, chapter_count=2),
            GlossarySuggestion(id="", source_term="Dragon", occurrence_count=2, chapter_count=1),
        ])
        results = svc.reject_all("test_novel")
        assert len(results) == 2
        assert all(s.status == "rejected" for s in results)
