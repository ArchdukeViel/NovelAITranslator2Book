# Tasks: Smart Chunking Context

## Task List

- [ ] 1. Inspect current segmentation
  - [ ] 1.1 Locate `SmartSegmentStage` and chunk contract types (REQ-1.1)
  - [ ] 1.2 Identify current max-size settings and provider constraints (REQ-2.1)

- [ ] 2. Add boundary-aware grouping
  - [ ] 2.1 Preserve deterministic paragraph IDs (REQ-1.1)
  - [ ] 2.2 Group whole paragraphs under max size (REQ-1.2)
  - [ ] 2.3 Prefer scene break boundaries when available (REQ-1.3)
  - [ ] 2.4 Avoid splitting dialogue paragraphs under max size (REQ-1.4)

- [ ] 3. Handle oversized paragraphs
  - [ ] 3.1 Split oversized paragraphs by safe sentence/dialogue boundaries (REQ-2.1)
  - [ ] 3.2 Add hard split fallback with continuation metadata (REQ-2.2)
  - [ ] 3.3 Preserve original paragraph mapping for all splits (REQ-2.3)

- [ ] 4. Add context window handling
  - [ ] 4.1 Add previous context to chunk metadata (REQ-3.1)
  - [ ] 4.2 Ensure prompt marks context as non-translatable (REQ-3.2)
  - [ ] 4.3 Ensure final save excludes context text (REQ-3.3)

- [ ] 5. Verify
  - [ ] 5.1 Test paragraph and scene break samples (REQ-4.1)
  - [ ] 5.2 Test dialogue-heavy samples (REQ-4.1)
  - [ ] 5.3 Test oversized paragraph fallback (REQ-4.1)
  - [ ] 5.4 Test refs/order/deterministic IDs (REQ-4.2, REQ-4.3)