# Requirements: Smart Chunking Context

## Introduction

Technical audit 5 flags fixed-size chunks that ignore story boundaries. Current architecture says `SmartSegmentStage` owns segmentation and chunks preserve paragraph IDs. This spec hardens context-aware chunking around paragraph, scene, and dialogue boundaries.

## Requirements

### REQ-1: Boundary-Aware Segmentation

Chunking must prefer natural story boundaries.

- REQ-1.1: Split chapter text into deterministic paragraphs with stable `paragraph_id` values.
- REQ-1.2: Build chunks from whole paragraphs where possible.
- REQ-1.3: Prefer scene breaks and paragraph boundaries over raw token/character boundaries.
- REQ-1.4: Preserve dialogue paragraphs without splitting inside quotes unless a single paragraph exceeds hard limits.

### REQ-2: Hard Limit Handling

Oversized text must still be translated safely.

- REQ-2.1: If one paragraph exceeds provider limits, split by sentence/dialogue-safe boundaries.
- REQ-2.2: If no safe boundary exists, split by character window with explicit continuation metadata.
- REQ-2.3: Every split must preserve mapping to original `paragraph_id`.

### REQ-3: Context Windows

Chunks must carry enough context without duplicating final output.

- REQ-3.1: Each chunk may include previous-context text for prompt conditioning.
- REQ-3.2: Previous-context text must be marked as context, not content to translate.
- REQ-3.3: Context text must not be saved as translated output for the current chunk.

### REQ-4: Tests

Chunking must be deterministic and mapping-safe.

- REQ-4.1: Tests must cover paragraph, scene break, dialogue-heavy, and oversized paragraph samples.
- REQ-4.2: Tests must verify `paragraph_refs` preserve source order.
- REQ-4.3: Tests must verify chunk IDs are deterministic for the same input.

## Non-Goals

- No semantic scene detection using LLMs.
- No provider-specific tokenizer dependency unless already installed.
- No change to final API response shape.