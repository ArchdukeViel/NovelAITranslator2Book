# Launch Acceptance Design

Spec ID: launch-readiness-checklist
Version: 1.0.0
Status: Approved
Updated: 2026-08-24

## Source of Truth and Ownership

`docs/WORK.md` is the live status and decision record. `docs/OPERATIONS.md`
owns operating procedures; `docs/DEPLOYMENT.md` owns topology, release, and
rollback procedures. Evidence may be linked from release records but must stay
sanitized. The operator owns hosted checks and the final decision.

Allowed statuses are `not_started`, `in_progress`, `passed`,
`passed_with_notes`, `blocked`, `waived`, and `not_applicable`.

## Decision Flow

1. Identify the exact candidate, environment, UTC window, and responsible
   owners.
2. Evaluate the existing `docs/WORK.md` gates and record one status plus
   sanitized evidence for each applicable domain.
3. Resolve blockers or record an owner, approver, rationale, and expiry for
   each accepted waiver.
4. Record `GO` only when the zero-unwaived-blocker and named-owner conditions
   are true. Otherwise record `NO-GO` and the next reversible action.

## Evidence and Safety Invariants

- Evidence contains references and redacted outcomes, not secrets, private
  content, connection strings, raw paths, traces, or generated downloads.
- A missing or untrusted hosted signal is recorded as unavailable or blocked;
  it is never silently converted into a pass.
- Rollback ownership and post-launch monitoring ownership are explicit before
  a `GO` decision.

## Traceability

| Requirement | Acceptance criterion | Planned task IDs |
| --- | --- | --- |
| REQ-001 | AC-001 | T-002 |
| REQ-002 | AC-002 | T-003, T-004 |
| REQ-003 | AC-003 | T-002 |
| REQ-004 | AC-004 | T-001, T-003, T-004 |
| REQ-005 | AC-005 | T-003, T-005 |
