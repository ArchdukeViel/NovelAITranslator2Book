"""Central prompt templates for translation stages."""

from __future__ import annotations


def translation_prompt(text: str) -> str:
    """Return a prompt formatted for translation providers."""
    return (
        "Translate the following Japanese web novel text into natural, fluent English. "
        "Preserve meaning and context, keep proper nouns consistent, and keep line breaks where appropriate.\n\n"
        f"{text}"
    )
