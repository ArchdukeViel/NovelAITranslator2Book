# Requirements: Glossary Management Consolidation

## Introduction

Technical audit 5 flags split glossary handling. Existing architecture has `novelai.glossary`, storage/db boundaries, admin UI, and prior glossary specs. This spec consolidates runtime glossary resolution around one backend service with explicit scope and conflict rules.

## Requirements

### REQ-1: Unified Glossary Resolution

Translation must receive one resolved glossary view.

- REQ-1.1: A backend glossary service must merge global and novel-scoped terms.
- REQ-1.2: Novel-scoped approved terms must override global approved terms for the same source term.
- REQ-1.3: Unapproved candidate terms must not affect translation prompts.
- REQ-1.4: Resolved glossary output must include a deterministic `glossary_hash`.

### REQ-2: Scope and Status Model

Glossary entries must have clear lifecycle metadata.

- REQ-2.1: Each entry must have scope: `global` or `novel`.
- REQ-2.2: Novel-scoped entries must include `novel_id`.
- REQ-2.3: Each entry must have status: `candidate`, `approved`, or `rejected`.
- REQ-2.4: Backend must enforce owner-only mutations for glossary administration.

### REQ-3: Admin API and UI Consistency

Admin surfaces must use backend contracts.

- REQ-3.1: Admin API must list entries with scope, status, conflict info, and audit metadata.
- REQ-3.2: Admin UI must not implement glossary merge policy in React.
- REQ-3.3: Admin UI must allow review/approve/reject where backend routes exist.

### REQ-4: Translation Integration

Prompts and cache keys must consume resolved glossary data.

- REQ-4.1: Prompt builders must receive resolved glossary entries, not raw mixed sources.
- REQ-4.2: Translation cache key must include `glossary_hash`.
- REQ-4.3: Provider request records must store glossary hash/version, not full secrets or credentials.

### REQ-5: Tests

Glossary behavior must be deterministic.

- REQ-5.1: Tests must cover global-only, novel-only, and novel-overrides-global cases.
- REQ-5.2: Tests must cover candidate/rejected terms being excluded from prompts.
- REQ-5.3: Tests must cover API authorization for owner-only mutations.

## Non-Goals

- No public-user glossary contribution credentials.
- No LLM auto-approval.
- No frontend-only conflict resolution.