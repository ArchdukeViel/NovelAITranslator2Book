"""Unit tests for GlossaryEditorQAService.

Covers REQ-1 through REQ-5, REQ-15, REQ-16.1-16.10.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from novelai.services.glossary_editor_qa_service import (
    CODE_FORBIDDEN_VARIANT,
    CODE_MISSING_APPROVED,
    CODE_MISSING_REQUIRED,
    CODE_NO_SOURCE,
    CODE_NON_APPROVED,
    SEVERITY_ADVISORY,
    SEVERITY_ERROR,
    SEVERITY_WARNING,
    STATUS_ADVISORY,
    STATUS_BLOCKED,
    STATUS_OVERRIDDEN,
    STATUS_PASSED,
    STATUS_WARNING,
    GlossaryEditorQAService,
    make_advisory_unavailable,
)

# ---------------------------------------------------------------------------
# Fake glossary entry
# ---------------------------------------------------------------------------


@dataclass
class FakeAlias:
    alias_text: str = ""
    alias_type: str = "observed"


@dataclass
class FakeEntry:
    id: int = 1
    canonical_term: str = "魔王"
    approved_translation: str | None = "Demon King"
    aliases: list[FakeAlias] = field(default_factory=list)
    status: str = "approved"
    owner_locked: bool = False
    enforcement_level: str = "warning"


class FakeRepo:
    """Minimal GlossaryRepository stub."""

    def __init__(self, entries: list[FakeEntry] | None = None, revision: int = 1):
        self._entries = entries or []
        self._revision = revision
        self.db = type("FakeDB", (), {"get": lambda self, *a, **kw: None})()

    def list_glossary_entries_for_novel(self, novel_id, *, status=None, **kw):
        return [e for e in self._entries if status is None or e.status == status]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGlossaryEditorQAService:
    def _service(self, entries=None, revision=1):
        return GlossaryEditorQAService(repository=FakeRepo(entries, revision))  # type: ignore[arg-type]

    def test_empty_glossary_returns_passed(self) -> None:
        svc = self._service(entries=[])
        result = svc.check_edit(
            platform_novel_id=1,
            novel_slug="n",
            chapter_id="c",
            edited_text="anything",
            source_text="anything",
        )
        assert result.status == STATUS_PASSED
        assert result.checked_terms == 0
        assert result.issue_count == 0

    def test_approved_term_present_passes(self) -> None:
        entry = FakeEntry(canonical_term="魔王", approved_translation="Demon King")
        svc = self._service([entry])
        result = svc.check_edit(
            platform_novel_id=1,
            novel_slug="n",
            chapter_id="c",
            edited_text="The Demon King appeared.",
            source_text="魔王が現れた。",
        )
        assert result.status == STATUS_PASSED
        assert result.issue_count == 0

    def test_approved_term_missing_emits_warning(self) -> None:
        entry = FakeEntry(canonical_term="魔王", approved_translation="Demon King", enforcement_level="warning")
        svc = self._service([entry])
        result = svc.check_edit(
            platform_novel_id=1,
            novel_slug="n",
            chapter_id="c",
            edited_text="The dark lord appeared.",
            source_text="魔王が現れた。",
        )
        assert result.status == STATUS_WARNING
        assert result.issue_count == 1
        assert result.issues[0].code == CODE_MISSING_APPROVED
        assert result.issues[0].severity == SEVERITY_WARNING

    def test_owner_locked_emits_blocking(self) -> None:
        entry = FakeEntry(canonical_term="魔王", approved_translation="Demon King", owner_locked=True)
        svc = self._service([entry])
        result = svc.check_edit(
            platform_novel_id=1,
            novel_slug="n",
            chapter_id="c",
            edited_text="The dark lord appeared.",
            source_text="魔王が現れた。",
        )
        assert result.status == STATUS_BLOCKED
        assert result.issues[0].code == CODE_MISSING_REQUIRED
        assert result.issues[0].severity == SEVERITY_ERROR

    def test_strict_enforcement_emits_blocking(self) -> None:
        entry = FakeEntry(canonical_term="魔王", approved_translation="Demon King", enforcement_level="strict")
        svc = self._service([entry])
        result = svc.check_edit(
            platform_novel_id=1,
            novel_slug="n",
            chapter_id="c",
            edited_text="The dark lord appeared.",
            source_text="魔王が現れた。",
        )
        assert result.status == STATUS_BLOCKED
        assert result.issues[0].severity == SEVERITY_ERROR

    def test_required_enforcement_emits_blocking(self) -> None:
        entry = FakeEntry(canonical_term="魔王", approved_translation="Demon King", enforcement_level="required")
        svc = self._service([entry])
        result = svc.check_edit(
            platform_novel_id=1,
            novel_slug="n",
            chapter_id="c",
            edited_text="The dark lord appeared.",
            source_text="魔王が現れた。",
        )
        assert result.status == STATUS_BLOCKED

    def test_blocking_enforcement_emits_blocking(self) -> None:
        entry = FakeEntry(canonical_term="魔王", approved_translation="Demon King", enforcement_level="blocking")
        svc = self._service([entry])
        result = svc.check_edit(
            platform_novel_id=1,
            novel_slug="n",
            chapter_id="c",
            edited_text="The dark lord appeared.",
            source_text="魔王が現れた。",
        )
        assert result.status == STATUS_BLOCKED

    def test_advisory_enforcement_emits_advisory(self) -> None:
        entry = FakeEntry(canonical_term="魔王", approved_translation="Demon King", enforcement_level="advisory")
        svc = self._service([entry])
        result = svc.check_edit(
            platform_novel_id=1,
            novel_slug="n",
            chapter_id="c",
            edited_text="The dark lord appeared.",
            source_text="魔王が現れた。",
        )
        assert result.status == STATUS_ADVISORY
        assert result.issues[0].severity == SEVERITY_ADVISORY

    def test_soft_enforcement_emits_advisory(self) -> None:
        entry = FakeEntry(canonical_term="魔王", approved_translation="Demon King", enforcement_level="soft")
        svc = self._service([entry])
        result = svc.check_edit(
            platform_novel_id=1,
            novel_slug="n",
            chapter_id="c",
            edited_text="The dark lord appeared.",
            source_text="魔王が現れた。",
        )
        assert result.status == STATUS_ADVISORY

    def test_unknown_enforcement_defaults_to_warning(self) -> None:
        entry = FakeEntry(canonical_term="魔王", approved_translation="Demon King", enforcement_level="weird")
        svc = self._service([entry])
        result = svc.check_edit(
            platform_novel_id=1,
            novel_slug="n",
            chapter_id="c",
            edited_text="The dark lord appeared.",
            source_text="魔王が現れた。",
        )
        assert result.issues[0].severity == SEVERITY_WARNING

    def test_forbidden_variant_detected(self) -> None:
        entry = FakeEntry(
            canonical_term="魔王",
            approved_translation="Demon King",
            aliases=[FakeAlias(alias_text="Devil Lord", alias_type="banned")],
        )
        svc = self._service([entry])
        result = svc.check_edit(
            platform_novel_id=1,
            novel_slug="n",
            chapter_id="c",
            edited_text="The Devil Lord appeared.",
            source_text="魔王が現れた。",
        )
        codes = [i.code for i in result.issues]
        assert CODE_FORBIDDEN_VARIANT in codes

    def test_non_approved_variant_detected(self) -> None:
        entry = FakeEntry(
            canonical_term="魔王",
            approved_translation="Demon King",
            aliases=[FakeAlias(alias_text="Dark Lord", alias_type="observed")],
        )
        svc = self._service([entry])
        result = svc.check_edit(
            platform_novel_id=1,
            novel_slug="n",
            chapter_id="c",
            edited_text="The Dark Lord appeared.",
            source_text="魔王が現れた。",
        )
        codes = [i.code for i in result.issues]
        assert CODE_NON_APPROVED in codes

    def test_alias_relevance_matching(self) -> None:
        entry = FakeEntry(
            canonical_term="魔王",
            approved_translation="Demon King",
            aliases=[FakeAlias(alias_text="魔王様")],
        )
        svc = self._service([entry])
        # Source contains alias but not canonical
        result = svc.check_edit(
            platform_novel_id=1,
            novel_slug="n",
            chapter_id="c",
            edited_text="The Demon King appeared.",
            source_text="魔王様が来た。",
        )
        assert result.checked_terms == 1
        assert result.status == STATUS_PASSED

    def test_no_source_context_advisory(self) -> None:
        entry = FakeEntry(canonical_term="魔王", approved_translation="Demon King")
        svc = self._service([entry])
        result = svc.check_edit(
            platform_novel_id=1,
            novel_slug="n",
            chapter_id="c",
            edited_text="The dark lord appeared.",
            source_text=None,
        )
        assert CODE_NO_SOURCE in result.notes
        # Without source, all entries are checked but blocking is suppressed
        assert result.status in (STATUS_ADVISORY, STATUS_WARNING)

    def test_max_terms_cap(self) -> None:
        entries = [FakeEntry(id=i, canonical_term=f"term{i}", approved_translation=f"trans{i}") for i in range(1, 11)]
        svc = self._service(entries)
        result = svc.check_edit(
            platform_novel_id=1,
            novel_slug="n",
            chapter_id="c",
            edited_text="nothing",
            source_text=None,
            max_terms=3,
        )
        assert result.cap_reached is True
        assert result.cap_limit == 3
        assert result.checked_terms == 3

    def test_deterministic_issue_ids(self) -> None:
        entry = FakeEntry(id=42, canonical_term="魔王", approved_translation="Demon King", owner_locked=True)
        svc = self._service([entry])
        r1 = svc.check_edit(
            platform_novel_id=1,
            novel_slug="n",
            chapter_id="c",
            edited_text="The dark lord appeared.",
            source_text="魔王が現れた。",
        )
        r2 = svc.check_edit(
            platform_novel_id=1,
            novel_slug="n",
            chapter_id="c",
            edited_text="The dark lord appeared.",
            source_text="魔王が現れた。",
        )
        assert r1.issues[0].issue_id == r2.issues[0].issue_id

    def test_normalization_case_insensitive(self) -> None:
        entry = FakeEntry(canonical_term="魔王", approved_translation="Demon King")
        svc = self._service([entry])
        result = svc.check_edit(
            platform_novel_id=1,
            novel_slug="n",
            chapter_id="c",
            edited_text="the DEMON king appeared.",
            source_text="魔王が現れた。",
        )
        assert result.status == STATUS_PASSED

    def test_normalization_whitespace_collapse(self) -> None:
        entry = FakeEntry(canonical_term="魔王", approved_translation="Demon King")
        svc = self._service([entry])
        result = svc.check_edit(
            platform_novel_id=1,
            novel_slug="n",
            chapter_id="c",
            edited_text="The  Demon  King  appeared.",
            source_text="魔王が現れた。",
        )
        assert result.status == STATUS_PASSED

    def test_apply_override_marks_blocked_as_overridden(self) -> None:
        entry = FakeEntry(canonical_term="魔王", approved_translation="Demon King", owner_locked=True)
        svc = self._service([entry])
        result = svc.check_edit(
            platform_novel_id=1,
            novel_slug="n",
            chapter_id="c",
            edited_text="The dark lord appeared.",
            source_text="魔王が現れた。",
        )
        assert result.status == STATUS_BLOCKED
        overridden = svc.apply_override(result)
        assert overridden.status == STATUS_OVERRIDDEN

    def test_apply_override_noop_on_non_blocked(self) -> None:
        entry = FakeEntry(canonical_term="魔王", approved_translation="Demon King")
        svc = self._service([entry])
        result = svc.check_edit(
            platform_novel_id=1,
            novel_slug="n",
            chapter_id="c",
            edited_text="The Demon King appeared.",
            source_text="魔王が現れた。",
        )
        assert result.status == STATUS_PASSED
        assert svc.apply_override(result).status == STATUS_PASSED

    def test_to_dict_serializable(self) -> None:
        entry = FakeEntry(canonical_term="魔王", approved_translation="Demon King", owner_locked=True)
        svc = self._service([entry])
        result = svc.check_edit(
            platform_novel_id=1,
            novel_slug="n",
            chapter_id="c",
            edited_text="The dark lord appeared.",
            source_text="魔王が現れた。",
        )
        import json

        d = result.to_dict()
        json.dumps(d)
        assert d["status"] == STATUS_BLOCKED
        assert d["checked_terms"] == 1
        assert d["issue_count"] == 1

    def test_no_repository_returns_advisory(self) -> None:
        svc = GlossaryEditorQAService(repository=None)
        result = svc.check_edit(
            platform_novel_id=1,
            novel_slug="n",
            chapter_id="c",
            edited_text="anything",
            source_text="anything",
        )
        assert result.status == STATUS_PASSED
        assert result.checked_terms == 0

    def test_make_advisory_unavailable(self) -> None:
        result = make_advisory_unavailable("n", "c", platform_novel_id=1, glossary_revision=5)
        assert result.status == STATUS_ADVISORY
        assert result.platform_novel_id == 1
        assert result.glossary_revision == 5
        assert "Glossary not available" in result.notes[0]
