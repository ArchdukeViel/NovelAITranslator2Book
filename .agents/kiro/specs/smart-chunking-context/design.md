# Design: Smart Chunking Context

## Overview

Refine `SmartSegmentStage` to choose boundaries in this order: scene break, paragraph, sentence/dialogue, hard character split. Preserve canonical IDs and mapping metadata.

## Architecture

### Affected Areas

| Area | Expected change |
|---|---|
| `backend/src/novelai/translation/` | Smart segmentation logic |
| `backend/src/novelai/shared/` | Pipeline contract updates only if existing types need fields |
| `backend/tests/` | Deterministic chunking tests |

## Component Design

### 1. Boundary Priority

```text
chapter
-> paragraphs (`p0001`, `p0002`, ...)
-> scene groups (blank-line markers, separators)
-> chunks under max size
-> sentence fallback for oversized paragraph
-> hard split fallback
```

### 2. Chunk Shape

Preserve existing canonical contract:

- `chunk_id`
- `novel_id`
- `chapter_ids`
- `paragraph_ids`
- `source_text`
- `char_count`
- `previous_context`
- `paragraph_refs`

### 3. Oversized Paragraph Strategy

Use stdlib regex/string splitting first. Avoid adding tokenizer dependency. Mark split refs with offsets so QA can still map output to source paragraph.

ponytail: approximate character limits first; add provider tokenizers only when measured failures show char limits insufficient.

### 4. Determinism

IDs derive from ordered chunks only. Same chapter input and settings produce same paragraph/chunk IDs.

## Acceptance Criteria

1. Paragraphs and dialogue stay intact when under limit.
2. Oversized paragraphs split with preserved paragraph mapping.
3. Previous context is prompt-only and never saved as output.
4. Same input produces same chunk IDs.