# Design: Glossary Management Consolidation

## Overview

Introduce one backend resolution path for glossary terms. Admin UI edits entries; backend service resolves terms for translation. Conflict and approval rules live server-side.

## Architecture

### Affected Areas

| Area | Expected change |
|---|---|
| `backend/src/novelai/glossary/` | Resolution rules and hash generation |
| `backend/src/novelai/services/orchestration/` | Use resolved glossary for translation |
| `backend/src/novelai/api/` | Admin glossary routes stay thin |
| `frontend/` | Display backend conflict/status fields only |
| `backend/tests/` | Resolution, prompt, auth tests |

## Component Design

### 1. Glossary Entry Shape

Canonical fields:

- `term_id`
- `source_text`
- `target_text`
- `scope`
- `novel_id`
- `status`
- `notes`
- `created_at`
- `updated_at`
- `created_by_user_id`

### 2. Resolution Rules

Order:

1. Load approved global entries.
2. Load approved novel entries for `novel_id`.
3. Replace global entries when novel entry has same normalized source term.
4. Sort deterministically by source term, then target term.
5. Hash resolved entries to produce `glossary_hash`.

ponytail: one-level override only; add per-chapter scope only when product needs it.

### 3. Translation Flow

```text
novel_id
-> GlossaryService.resolve(novel_id)
-> prompt builder
-> translation cache key includes glossary_hash
-> provider request metadata records glossary_hash
```

### 4. Frontend Contract

React displays backend-provided status/conflict fields. It does not decide merge priority.

## Acceptance Criteria

1. Translation prompt receives one resolved glossary view.
2. Novel-approved terms override global-approved terms.
3. Candidate/rejected terms never enter prompts.
4. Admin glossary mutations require owner session.