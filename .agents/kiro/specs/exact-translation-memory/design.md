# Design: Exact Translation Memory

## Overview

Add exact-match translation memory at the translation service/scheduler boundary. Use existing storage/database boundaries. Keep implementation boring: hash normalized source and translation settings, look up before provider call, save after QA-approved output.

## Architecture

### Affected Areas

| Area | Expected change |
|---|---|
| `backend/src/novelai/translation/` | Lookup before provider call; save after QA pass |
| `backend/src/novelai/storage/` or `backend/src/novelai/db/` | Translation cache repository |
| `backend/src/novelai/services/` | Activity counters for hit/miss |
| `backend/tests/` | Cache hit/miss/provider-call tests |

## Component Design

### 1. Cache Key

Canonical key fields:

```text
sha256(
  normalized_source_text
  + source_language
  + target_language
  + prompt_version
  + provider_key
  + provider_model
  + glossary_hash
)
```

Normalization trims line-ending differences only. Do not lowercase Japanese text or collapse meaningful whitespace until tests prove it safe.

### 2. Repository

Minimal methods:

- `get(cache_key)` -> cached translation or `None`
- `put(cache_key, metadata, translated_text)` -> persisted cache record

ponytail: no eviction policy in first pass; add LRU/TTL only when storage growth appears in metrics.

### 3. Translation Flow

```text
build chunk metadata
-> compute cache key
-> cache lookup
-> hit: return cached output and emit hit event
-> miss: call provider
-> QA validates output
-> save successful output
-> return output
```

### 4. Safety

Cache records store prompt/provider identifiers and hashes, not secrets. Provider request records remain absent on hits because no external request happened.

## Acceptance Criteria

1. Duplicate exact segment translates with one provider call.
2. Changing glossary hash or prompt version causes a miss.
3. QA-rejected output is never returned from cache.
4. Activity output includes hit/miss counts.