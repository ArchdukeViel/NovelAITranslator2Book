---
trigger: always_on
description: Repository documentation structure, allowed subdirectories, front-matter schemas, and tools/docs-check.ps1 compliance.
---

# Documentation Contract & Structure Rules

This rule enforces the Dokushodo documentation contract and directory governance checked by `tools/docs-check.ps1`.

## Allowed Directory Whitelist

Under `docs/`, only three subdirectories are permitted:
- `docs/archive/` &mdash; historical provenance only; never active authority.
- `docs/design/` &mdash; design specs, route briefs, and architecture diagrams (e.g. `docs/design/diagrams/`).
- `docs/plans/` &mdash; non-canonical execution instructions.

> [!CAUTION]
> Creating any other directory directly under `docs/` (such as `docs/diagrams/`, `docs/specs/`, `docs/temp/`) immediately triggers `unapproved_docs_directory` and fails repository documentation validation.

## Canonical Documents & Concern Ownership

The 9 canonical root documents in `docs/` own one concern each:
1. `ARCHITECTURE.md` &mdash; architecture, trust boundaries, subsystem responsibilities.
2. `CONFIGURATION.md` &mdash; configuration variables, secret classification, connection budgets.
3. `DEPLOYMENT.md` &mdash; Compose topologies, production environments, rollback.
4. `DESIGN.md` &mdash; design tokens, UI layouts, color modes, typography.
5. `EVIDENCE.md` &mdash; historical verified test outcomes, sanitized benchmarks.
6. `OPERATIONS.md` &mdash; health checks, runbooks, backup, restore, dead-letter queue operations.
7. `STATUS.md` &mdash; active unfinished work, operator gates (no completed-work narrative).
8. `STORAGE.md` &mdash; R2 object keys, retention, PostgreSQL persistence invariants.
9. `TRANSLATION.md` &mdash; translation pipeline, glossary format, prompt structures, QA quotas.

## Front-Matter Standards

Every canonical document must start with valid YAML front-matter containing:
- `title` (string)
- `document_role` (`normative`, `reference`, `procedural`, `status`, `evidence`)
- `authority` (string)
- `scope` (string)
- `audience` (list of strings)
- `update_triggers` (list of strings)
- `owned_concerns` (list of unique strings)

### Plan Front-Matter Standards (`docs/plans/`)

Every non-canonical execution plan under `docs/plans/` must include in its YAML front-matter:
- `title` (string)
- `canonical_truth: false`

> [!IMPORTANT]
> Omitting `canonical_truth: false` on any file under `docs/plans/` causes `tools/docs-check.ps1` to fail with a `plan_canonical_truth` violation.

## Mandatory Verification Command

Whenever documentation is touched or created, run:
```powershell
powershell -ExecutionPolicy Bypass -File tools\docs-check.ps1
```
Ensure exit code is `0` with `violation_count: 0`.
