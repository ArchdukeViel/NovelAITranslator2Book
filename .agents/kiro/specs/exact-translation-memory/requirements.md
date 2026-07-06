# Requirements: Exact Translation Memory

## Introduction

Technical audit 5 flags repeated LLM calls for identical text. The canonical architecture already lists translation cache as a runtime record. This spec adds an exact-match translation memory before provider calls, with safe cache keys and provider/prompt/glossary awareness.

## Requirements

### REQ-1: Exact Cache Lookup

Translation must reuse prior successful translations for identical inputs.

- REQ-1.1: Before a provider call, translation code must compute a deterministic cache key from source text plus relevant translation context.
- REQ-1.2: On cache hit, translation code must return cached translated text without calling the provider.
- REQ-1.3: On cache miss, translation code must call the provider normally and save successful output.
- REQ-1.4: Failed, refused, empty, or QA-rejected outputs must not be cached as successful translations.

### REQ-2: Cache Key Correctness

Cache keys must prevent unsafe reuse.

- REQ-2.1: Cache key must include normalized source text hash.
- REQ-2.2: Cache key must include source language, target language, prompt version, provider key, provider model, and glossary hash where available.
- REQ-2.3: Cache key must not include API keys, auth headers, cookies, or raw secrets.
- REQ-2.4: Cache lookup must preserve paragraph/chunk mapping metadata.

### REQ-3: Observability

Cache behavior must be visible without leaking content.

- REQ-3.1: Activity/progress events must count cache hits and misses.
- REQ-3.2: Logs must include cache hit/miss and key prefix, not full source text.
- REQ-3.3: Provider request records must not be created for cache hits.

### REQ-4: Tests

Cache behavior must have provider-call regression coverage.

- REQ-4.1: Unit tests must prove duplicate source text calls provider once.
- REQ-4.2: Unit tests must prove prompt version or glossary hash differences miss cache.
- REQ-4.3: Unit tests must prove rejected outputs are not cached.

## Non-Goals

- No semantic/fuzzy cache.
- No embeddings.
- No Redis dependency unless already required by current worker architecture.
- No cross-user credential sharing beyond provider/prompt/glossary-safe exact reuse.