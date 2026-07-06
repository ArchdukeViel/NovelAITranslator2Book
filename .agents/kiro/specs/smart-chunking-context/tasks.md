# Tasks: Smart Chunking Context

## Task List

- [x] 1. Inspect current segmentation
  - [x] 1.1 Locate `SmartSegmentStage` and chunk contract types (REQ-1.1)
  - [x] 1.2 Identify current max-size settings and provider constraints (REQ-2.1)

- [x] 2. Add boundary-aware grouping
  - [x] 2.1 Preserve deterministic paragraph IDs (REQ-1.1)
  - [x] 2.2 Group whole paragraphs under max size (REQ-1.2)
  - [x] 2.3 Prefer scene break boundaries when available (REQ-1.3)
  - [x] 2.4 Avoid splitting dialogue paragraphs under max size (REQ-1.4)

- [x] 3. Handle oversized paragraphs
  - [x] 3.1 Split oversized paragraphs by safe sentence/dialogue boundaries (REQ-2.1)
  - [x] 3.2 Add hard split fallback with continuation metadata (REQ-2.2)
  - [x] 3.3 Preserve original paragraph mapping for all splits (REQ-2.3)

- [x] 4. Add context window handling
  - [x] 4.1 Add previous context to chunk metadata (REQ-3.1)
  - [x] 4.2 Ensure prompt marks context as non-translatable (REQ-3.2)
  - [x] 4.3 Ensure final save excludes context text (REQ-3.3)

- [x] 5. Verify
  - [x] 5.1 Test paragraph and scene break samples (REQ-4.1)
  - [x] 5.2 Test dialogue-heavy samples (REQ-4.1)
  - [x] 5.3 Test oversized paragraph fallback (REQ-4.1)
  - [x] 5.4 Test refs/order/deterministic IDs (REQ-4.2, REQ-4.3)