from __future__ import annotations

import re


def normalize_text(text: str) -> str:
    """Normalize story/text bodies.

    - Normalize line endings to LF
    - Trim trailing spaces on lines
    - Collapse runs of blank lines to at most two
    - Strip leading/trailing whitespace
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # remove trailing spaces before newlines
    text = re.sub(r"[ \t]+\n", "\n", text)

    lines = [line.strip(" \t") for line in text.split("\n")]
    normalized: list[str] = []
    for line in lines:
        if line:
            normalized.append(line)
        elif normalized and normalized[-1] != "":
            # preserve a single blank line, avoid >1 consecutive
            normalized.append("")

    return "\n".join(normalized).strip()
