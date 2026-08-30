# Launch Acceptance Requirements

Spec ID: launch-readiness-checklist
Version: 0.2.0
Status: Blocked
Updated: 2026-08-30
Requester: Project owner
Owner: Project owner with implementation agent

## Goal

Produce a defensible `GO` or `NO-GO` decision from current hosted and manual
evidence without treating local checks or historical evidence as launch proof.

## Requirements

### REQ-001: Canonical gate ownership

Use the operator gates in `docs/STATUS.md` as the live launch register. Keep
launch, rollback, monitoring, security, recovery, accessibility, performance,
SEO, and legal ownership explicit and sanitized.

### REQ-002: Evidence provenance

Every accepted gate records the exact candidate commit or version, environment,
UTC time, operator, exact command or URL, sanitized result, blocker, and waiver
where applicable. Historical evidence is labeled historical and does not prove
the current candidate.

### REQ-003: Required launch surfaces

Assess product flow, authentication and security, legal propagation,
accessibility, performance, SEO, monitoring and alerts, recovery, and rollback.
Generated reader downloads are not applicable and require no acceptance work.

### REQ-004: Decision rule

`GO` requires zero unwaived blockers, a current candidate, and named
launch/rollback/monitoring owners. Any missing required evidence keeps the
decision at `NO-GO` or `Blocked`.

### REQ-005: Evidence safety

Never include secrets, private content, connection strings, raw credentials,
raw paths, request bodies, cookies, or traces in launch records.

## Non-functional requirements

- NFR-001: Do not claim production readiness, capacity admission, recovery
  completeness, or alert delivery without independent evidence.
- NFR-002: Preserve pre-existing worktree changes and do not commit, push,
  merge, change GitHub settings, or alter production resources as part of this
  specification.

## Acceptance Criteria

- AC-001: The live launch register identifies each required gate and its
  current owner or explicitly records the missing owner/reviewer.
  - Maps to: REQ-001
- AC-002: Each completed gate links to sanitized, current-candidate evidence;
  missing or historical evidence is labeled accordingly.
  - Maps to: REQ-002
- AC-003: The launch register covers all required launch surfaces and records
  unavailable or blocked evidence without inventing results.
  - Maps to: REQ-003
- AC-004: The final decision is `NO-GO` while any required gate or owner is
  missing, and can become `GO` only after the decision rule is satisfied.
  - Maps to: REQ-004
- AC-005: The specification and launch records contain no prohibited secret or
  raw operational data.
  - Maps to: REQ-005

## Acceptance Coverage

| Acceptance criterion | Requirement | Tasks | Current evidence |
| --- | --- | --- | --- |
| AC-001 | REQ-001 | T-001 | `docs/STATUS.md` owner row; backup reviewer remains open |
| AC-002 | REQ-002 | T-002 | Current candidate reconciliation remains open |
| AC-003 | REQ-003 | T-003 | `docs/STATUS.md` lists hosted/manual blockers |
| AC-004 | REQ-004 | T-004 | Current decision is `NO-GO` |
| AC-005 | REQ-005 | T-001, T-004 | Sanitized records only; no launch approval |

## Current decision

`NO-GO` / `Blocked`. The repository has a current factual register, but
production acceptance remains open because exact current-candidate hosted and
manual evidence, owner/reviewer confirmation, email delivery, monitoring and
alert delivery, recovery and rollback acceptance, and other gates remain
unverified. This status must not be changed by local validation alone.
