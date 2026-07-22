"""Deterministic glossary QA service for editor translation saves.

Compares edited translated text against approved glossary entries using
stable normalized matching. No LLM calls. Returns structured results
suitable for API responses and persisted summaries.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from novelai.db.models.glossary import NovelGlossaryEntry
from novelai.db.models.novel import Novel
from novelai.services.glossary_repository import GlossaryRepository

# ---------------------------------------------------------------------------
# Issue codes  (REQ-3)
# ---------------------------------------------------------------------------

CODE_MISSING_APPROVED = "missing_approved_translation"
CODE_MISSING_REQUIRED = "missing_required_term"
CODE_FORBIDDEN_VARIANT = "forbidden_variant"
CODE_NON_APPROVED = "non_approved_translation"
CODE_AMBIGUOUS = "ambiguous_match"
CODE_NO_SOURCE = "missing_source_context"
CODE_GLOSSARY_UNAVAILABLE = "glossary_unavailable"

# ---------------------------------------------------------------------------
# Severity / status  (REQ-5)
# ---------------------------------------------------------------------------

SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"
SEVERITY_ADVISORY = "advisory"

STATUS_PASSED = "passed"
STATUS_ADVISORY = "advisory"
STATUS_WARNING = "warning"
STATUS_BLOCKED = "blocked"
STATUS_OVERRIDDEN = "overridden"

_BLOCKING_ENFORCEMENT = {"strict", "required", "blocking"}
_NON_BLOCKING_ENFORCEMENT = {"advisory", "soft"}
_UNKNOWN_ENFORCEMENT = {"none", ""}
_FORBIDDEN_ALIAS_TYPES = {"banned", "rejected", "deprecated"}
_KNOWN_ALIAS_TYPES = {"allowed", "observed", "source_variant"}

# ---------------------------------------------------------------------------
# Data contracts  (REQ-1.7, Tasks 2-3)
# ---------------------------------------------------------------------------


@dataclass
class GlossaryQAIssue:
    issue_id: str
    entry_id: int | None
    canonical_term: str
    approved_translation: str | None
    matched_variant: str | None
    severity: str
    code: str
    owner_locked: bool
    context_hint: str


@dataclass
class GlossaryQAResult:
    status: str
    novel_id: str
    platform_novel_id: int | None
    chapter_id: str
    glossary_revision: int | None
    checked_terms: int
    issue_count: int
    has_errors: bool
    has_warnings: bool
    source_context: str  # "provided" | "missing"
    notes: list[str] = field(default_factory=list)
    issues: list[GlossaryQAIssue] = field(default_factory=list)
    cap_reached: bool = False
    cap_limit: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "novel_id": self.novel_id,
            "platform_novel_id": self.platform_novel_id,
            "chapter_id": self.chapter_id,
            "glossary_revision": self.glossary_revision,
            "checked_terms": self.checked_terms,
            "issue_count": self.issue_count,
            "has_errors": self.has_errors,
            "has_warnings": self.has_warnings,
            "source_context": self.source_context,
            "notes": list(self.notes),
            "issues": [
                {
                    "issue_id": i.issue_id,
                    "entry_id": i.entry_id,
                    "canonical_term": i.canonical_term,
                    "approved_translation": i.approved_translation,
                    "matched_variant": i.matched_variant,
                    "severity": i.severity,
                    "code": i.code,
                    "owner_locked": i.owner_locked,
                    "context_hint": i.context_hint,
                }
                for i in self.issues
            ],
            "cap_reached": self.cap_reached,
            "cap_limit": self.cap_limit,
        }


# ---------------------------------------------------------------------------
# Normalization  (REQ-4)
# ---------------------------------------------------------------------------

_WHITESPACE_RE = re.compile(r"\s+")


def _normalize(text: str) -> str:
    if not text:
        return ""
    n = unicodedata.normalize("NFKC", text)
    n = n.strip()
    n = _WHITESPACE_RE.sub(" ", n)
    return n.casefold()


def _contains(haystack: str, needle: str) -> bool:
    if not needle:
        return False
    return needle in haystack


# ---------------------------------------------------------------------------
# Severity mapping  (REQ-5)
# ---------------------------------------------------------------------------


def _severity_for_entry(entry: NovelGlossaryEntry) -> str:
    """Map a glossary entry to a severity level."""
    enforcement = entry.enforcement_level or ""
    enforcement = str(enforcement).strip().lower()
    owner_locked = bool(entry.owner_locked)

    if owner_locked:
        return SEVERITY_ERROR
    if enforcement in _BLOCKING_ENFORCEMENT:
        return SEVERITY_ERROR
    if enforcement in _NON_BLOCKING_ENFORCEMENT:
        return SEVERITY_ADVISORY
    if enforcement in _UNKNOWN_ENFORCEMENT:
        return SEVERITY_WARNING
    # Unknown enforcement level → warning
    return SEVERITY_WARNING


def _is_blocking(severity: str) -> bool:
    return severity == SEVERITY_ERROR


# ---------------------------------------------------------------------------
# Issue ID generation  (REQ-3.9)
# ---------------------------------------------------------------------------


def _make_issue_id(entry_id: int | None, code: str, term: str) -> str:
    safe_term = re.sub(r"[^A-Za-z0-9]+", "_", term or "term")[:32].strip("_") or "term"
    eid = entry_id if entry_id is not None else 0
    return f"gqa_{eid}_{code}_{safe_term}"


# ---------------------------------------------------------------------------
# Service  (REQ-1)
# ---------------------------------------------------------------------------


class GlossaryEditorQAService:
    """Deterministic glossary QA for editor translation saves."""

    def __init__(self, repository: GlossaryRepository | None = None) -> None:
        self._repository = repository

    def check_edit(
        self,
        *,
        platform_novel_id: int | None,
        novel_slug: str,
        chapter_id: str,
        edited_text: str,
        source_text: str | None,
        user_id: int | None = None,
        max_terms: int = 50,
    ) -> GlossaryQAResult:
        """Run deterministic QA against edited text.

        Returns a GlossaryQAResult with status, issues, and metadata.
        """
        glossary_revision = self._resolve_revision(platform_novel_id)
        entries = self._load_entries(platform_novel_id)

        if not entries:
            return GlossaryQAResult(
                status=STATUS_PASSED,
                novel_id=novel_slug,
                platform_novel_id=platform_novel_id,
                chapter_id=chapter_id,
                glossary_revision=glossary_revision,
                checked_terms=0,
                issue_count=0,
                has_errors=False,
                has_warnings=False,
                source_context="provided" if source_text else "missing",
                notes=[],
                issues=[],
            )

        # Determine relevant entries
        relevant, notes = self._select_relevant(entries, source_text)

        # Cap
        cap_reached = False
        cap_limit = max_terms
        if len(relevant) > max_terms:
            relevant = relevant[:max_terms]
            cap_reached = True
            notes.append(f"Term cap reached: checked first {max_terms} of {len(entries)} entries.")

        # Run checks
        issues = self._detect_issues(relevant, edited_text)

        # Compute status
        has_errors = any(_is_blocking(i.severity) for i in issues)
        has_warnings = any(i.severity == SEVERITY_WARNING for i in issues)
        has_advisory = any(i.severity == SEVERITY_ADVISORY for i in issues)

        if has_errors:
            status = STATUS_BLOCKED
        elif has_warnings:
            status = STATUS_WARNING
        elif has_advisory or notes:
            status = STATUS_ADVISORY
        else:
            status = STATUS_PASSED

        return GlossaryQAResult(
            status=status,
            novel_id=novel_slug,
            platform_novel_id=platform_novel_id,
            chapter_id=chapter_id,
            glossary_revision=glossary_revision,
            checked_terms=len(relevant),
            issue_count=len(issues),
            has_errors=has_errors,
            has_warnings=has_warnings,
            source_context="provided" if source_text else "missing",
            notes=notes,
            issues=issues,
            cap_reached=cap_reached,
            cap_limit=cap_limit,
        )

    def apply_override(self, result: GlossaryQAResult) -> GlossaryQAResult:
        """Mark a blocked result as overridden."""
        if result.status != STATUS_BLOCKED:
            return result
        return GlossaryQAResult(
            status=STATUS_OVERRIDDEN,
            novel_id=result.novel_id,
            platform_novel_id=result.platform_novel_id,
            chapter_id=result.chapter_id,
            glossary_revision=result.glossary_revision,
            checked_terms=result.checked_terms,
            issue_count=result.issue_count,
            has_errors=result.has_errors,
            has_warnings=result.has_warnings,
            source_context=result.source_context,
            notes=list(result.notes),
            issues=list(result.issues),
            cap_reached=result.cap_reached,
            cap_limit=result.cap_limit,
        )

    # -----------------------------------------------------------------------
    # Internals
    # -----------------------------------------------------------------------

    def _resolve_revision(self, platform_novel_id: int | None) -> int | None:
        if platform_novel_id is None or self._repository is None:
            return None
        try:
            novel = self._repository.db.get(Novel, platform_novel_id)
            if novel is not None:
                return int(novel.glossary_revision)
        except Exception:
            return None
        return None

    def _load_entries(self, platform_novel_id: int | None) -> list[NovelGlossaryEntry]:
        if platform_novel_id is None or self._repository is None:
            return []
        try:
            return list(self._repository.list_glossary_entries_for_novel(platform_novel_id, status="approved"))
        except Exception:
            return []

    def _select_relevant(
        self, entries: list[NovelGlossaryEntry], source_text: str | None
    ) -> tuple[list[NovelGlossaryEntry], list[str]]:
        notes: list[str] = []
        if not source_text:
            notes.append(CODE_NO_SOURCE)
            return list(entries), notes

        norm_source = _normalize(source_text)
        relevant: list[NovelGlossaryEntry] = []
        for entry in entries:
            terms = [entry.canonical_term]
            terms.extend(alias.alias_text for alias in entry.aliases if alias.alias_text)
            if any(_contains(norm_source, _normalize(t)) for t in terms if t):
                relevant.append(entry)
        return relevant, notes

    def _detect_issues(self, entries: Iterable[NovelGlossaryEntry], edited_text: str) -> list[GlossaryQAIssue]:
        norm_edited = _normalize(edited_text)
        issues: list[GlossaryQAIssue] = []

        for entry in entries:
            entry_id = entry.id
            canonical = entry.canonical_term
            approved = entry.approved_translation
            approved_str = str(approved) if approved else None
            severity = _severity_for_entry(entry)
            owner_locked = bool(entry.owner_locked)

            # 1. Forbidden variants
            forbidden_aliases = (alias for alias in entry.aliases if alias.alias_type in _FORBIDDEN_ALIAS_TYPES)
            for alias in forbidden_aliases:
                v_text = alias.alias_text
                if v_text and _contains(norm_edited, _normalize(str(v_text))):
                    issues.append(
                        GlossaryQAIssue(
                            issue_id=_make_issue_id(entry_id, CODE_FORBIDDEN_VARIANT, canonical),
                            entry_id=entry_id,
                            canonical_term=canonical,
                            approved_translation=approved_str,
                            matched_variant=str(v_text),
                            severity=severity,
                            code=CODE_FORBIDDEN_VARIANT,
                            owner_locked=owner_locked,
                            context_hint=f"Remove forbidden variant '{v_text}'; use approved translation.",
                        )
                    )

            # 2. Known non-approved variants
            known_aliases = (alias for alias in entry.aliases if alias.alias_type in _KNOWN_ALIAS_TYPES)
            for alias in known_aliases:
                v_text = alias.alias_text
                if not v_text:
                    continue
                if _contains(norm_edited, _normalize(str(v_text))):
                    # Only flag if approved translation is absent
                    if not approved_str or not _contains(norm_edited, _normalize(approved_str)):
                        issues.append(
                            GlossaryQAIssue(
                                issue_id=_make_issue_id(entry_id, CODE_NON_APPROVED, canonical),
                                entry_id=entry_id,
                                canonical_term=canonical,
                                approved_translation=approved_str,
                                matched_variant=str(v_text),
                                severity=severity,
                                code=CODE_NON_APPROVED,
                                owner_locked=owner_locked,
                                context_hint=f"Replace '{v_text}' with approved translation: {approved_str or '(unset)'}.",
                            )
                        )

            # 3. Missing approved translation
            if approved_str:
                if not _contains(norm_edited, _normalize(approved_str)):
                    code = CODE_MISSING_REQUIRED if _is_blocking(severity) else CODE_MISSING_APPROVED
                    issues.append(
                        GlossaryQAIssue(
                            issue_id=_make_issue_id(entry_id, code, canonical),
                            entry_id=entry_id,
                            canonical_term=canonical,
                            approved_translation=approved_str,
                            matched_variant=None,
                            severity=severity,
                            code=code,
                            owner_locked=owner_locked,
                            context_hint=f"Add approved translation: {approved_str}.",
                        )
                    )

        return issues


def make_advisory_unavailable(
    novel_slug: str,
    chapter_id: str,
    platform_novel_id: int | None = None,
    glossary_revision: int | None = None,
) -> GlossaryQAResult:
    """Build an advisory result when glossary data is unavailable."""
    return GlossaryQAResult(
        status=STATUS_ADVISORY,
        novel_id=novel_slug,
        platform_novel_id=platform_novel_id,
        chapter_id=chapter_id,
        glossary_revision=glossary_revision,
        checked_terms=0,
        issue_count=0,
        has_errors=False,
        has_warnings=False,
        source_context="missing",
        notes=["Glossary not available for this novel."],
        issues=[],
    )


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
