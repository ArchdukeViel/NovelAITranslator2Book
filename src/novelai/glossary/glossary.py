from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class GlossaryTerm:
    source: str
    target: str
    notes: Optional[str] = None


@dataclass
class Glossary:
    """A glossary of terms used to enforce consistent translations."""

    terms: Dict[str, GlossaryTerm] = field(default_factory=dict)

    def add_term(self, source: str, target: str, notes: Optional[str] = None) -> None:
        self.terms[source] = GlossaryTerm(source=source, target=target, notes=notes)

    def translate(self, text: str) -> str:
        """Apply glossary term substitutions to translated text."""
        for src, term in self.terms.items():
            text = text.replace(src, term.target)
        return text
