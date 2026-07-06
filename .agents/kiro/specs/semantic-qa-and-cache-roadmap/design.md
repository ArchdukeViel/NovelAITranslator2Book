# Design: Semantic Cache and LLM QA Roadmap

## Overview

Keep semantic cache and LLM QA behind explicit gates. Exact cache and deterministic QA solve cheaper, safer problems first. Future features add cost, privacy, and false-positive risks, so they require metrics and fixtures before enablement.

## Architecture

### Future Affected Areas

| Area | Expected future change |
|---|---|
| `backend/src/novelai/translation/` | Optional semantic lookup and LLM QA stage |
| `backend/src/novelai/providers/` | Embedding and QA provider calls through provider registry |
| `backend/src/novelai/storage/` or `db/` | Embedding/index records |
| `backend/tests/fixtures/` | Evaluation datasets |

## Component Design

### 1. Semantic Cache Flow

```text
exact cache miss
-> semantic index query
-> threshold + context guard
-> accepted fuzzy candidate returns advisory hit
-> optional owner/profile setting permits reuse
```

Default: advisory only, no automatic reuse.

### 2. LLM QA Flow

```text
provider translation
-> deterministic QA
-> optional LLM QA
-> structured findings
-> review flags/activity output
```

### 3. Metrics

Track separately:

- exact cache hits
- semantic candidate hits
- semantic accepted hits
- embedding calls
- LLM QA calls
- LLM QA severity counts

ponytail: no vector DB choice yet; choose only after fixture size and deployment target demand it.

## Acceptance Criteria

1. Future semantic cache cannot enable without exact cache metrics and fixtures.
2. Future LLM QA cannot bypass deterministic QA.
3. Both features are disabled by default.
4. Provider credentials never reach frontend.