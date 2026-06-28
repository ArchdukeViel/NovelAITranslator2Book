from __future__ import annotations

from typing import Any


def normalize_source_blocks(blocks: Any) -> list[dict[str, Any]]:
    """Normalize source-layout blocks to the public storage contract."""
    if not isinstance(blocks, list):
        return []

    normalized: list[dict[str, Any]] = []
    line_index = 0
    break_index = 0
    source_order = 0
    previous_type: str | None = None

    for item in blocks:
        if not isinstance(item, dict):
            continue
        block_type = item.get("type")
        if block_type == "break":
            if previous_type == "break" or not normalized:
                continue
            break_index += 1
            source_order += 1
            normalized.append(
                {
                    "type": "break",
                    "source_block_id": str(item.get("source_block_id") or f"b{break_index:04d}"),
                    "source_order": source_order,
                }
            )
            previous_type = "break"
            continue

        if block_type != "line":
            continue
        text = item.get("text")
        if not isinstance(text, str) or not text.strip():
            continue
        line_index += 1
        source_order += 1
        normalized.append(
                {
                    "type": "line",
                    "source_block_id": f"s{line_index:04d}",
                    "paragraph_id": f"p{line_index:04d}",
                    "text": text.strip("\n"),
                    "source_order": source_order,
                }
        )
        previous_type = "line"

    if normalized and normalized[-1].get("type") == "break":
        normalized.pop()
    return normalized


def source_blocks_from_text_blocks(text_blocks: list[str], *, add_break_between_blocks: bool = False) -> list[dict[str, Any]]:
    """Build source-layout blocks from source text units."""
    raw_blocks: list[dict[str, Any]] = []
    for block in text_blocks:
        if not isinstance(block, str):
            continue
        text = block.strip("\n")
        if text.strip():
            raw_blocks.append({"type": "line", "text": text})
            if add_break_between_blocks:
                raw_blocks.append({"type": "break"})
        else:
            raw_blocks.append({"type": "break"})
    return normalize_source_blocks(raw_blocks)
