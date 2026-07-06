# Requirements: Semantic Cache and LLM QA Roadmap

## Introduction

Technical audit 5 proposes semantic translation memory, LLM-assisted QA, and multi-provider quality strategies. These are high-cost future features. This spec captures gates and constraints so they do not land as unsafe shortcuts.

## Requirements

### REQ-1: Semantic Cache Readiness Gate

Semantic reuse must not ship until exact cache and evaluation exist.

- REQ-1.1: Exact translation memory must exist and expose hit/miss metrics first.
- REQ-1.2: A validation dataset must exist with accepted and rejected fuzzy matches.
- REQ-1.3: Semantic cache must have a similarity threshold and context guard.
- REQ-1.4: Semantic cache must be disabled by default until measured precision is acceptable.

### REQ-2: Embedding and Index Safety

Embedding storage must follow privacy and cost rules.

- REQ-2.1: Embedding provider credentials must remain backend-only.
- REQ-2.2: Stored embeddings must link to cache IDs, not expose raw provider secrets.
- REQ-2.3: Index writes must be idempotent for retries.
- REQ-2.4: Metrics must report embedding calls and semantic hit acceptance rate.

### REQ-3: LLM QA Gate

LLM QA must be advisory before it blocks output.

- REQ-3.1: Deterministic QA must run before LLM QA.
- REQ-3.2: LLM QA must produce structured findings with severity and evidence.
- REQ-3.3: Initial LLM QA must mark chapters for review, not block publishing by default.
- REQ-3.4: LLM QA cost must be tracked separately from translation cost.

### REQ-4: Tests and Evaluation

Future AI-assisted behavior must be measurable.

- REQ-4.1: Semantic cache must have precision/recall evaluation against fixtures.
- REQ-4.2: LLM QA must have parser tests for valid/invalid model output.
- REQ-4.3: Both features must have disabled-by-default config tests.

## Non-Goals

- No implementation in this spec.
- No blocking LLM QA before deterministic QA is complete.
- No fuzzy translation reuse without an evaluation dataset.