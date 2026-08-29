# Launch Acceptance Design

Spec ID: launch-readiness-checklist
Version: 0.2.0
Status: Blocked
Updated: 2026-08-30

## Source of truth mapping

- `docs/WORK.md` is the live status and decision record.
- `docs/OPERATIONS.md` owns operator procedures, health, backup, and recovery
  details.
- `docs/DEPLOYMENT.md` owns topology, release, and rollback procedures.
- `docs/HISTORY.md` owns completed historical evidence.
- `.agents/specs/launch-readiness-checklist/` owns this contract and its
  traceability; it does not override the canonical operational register.

## System architecture

The launch decision is a documentation-and-evidence workflow. The operator
freezes the candidate, gathers sanitized evidence for each gate, records the
result in `docs/WORK.md`, and makes a final decision. Local tests may validate
implementation but cannot substitute for hosted or manual acceptance.

## Data contracts and schemas

Each gate record must identify the candidate, environment, UTC observation time,
operator, exact command or URL, sanitized outcome, blocker, waiver if any, and
the responsible owner. Secret values, raw provider responses, connection
strings, private content, credentials, cookies, and traces are excluded.

Allowed gate statuses are `not_started`, `in_progress`, `passed`, `blocked`,
`waived`, and `not_applicable`. `passed_with_notes` is not a launch decision;
notes must resolve to `passed`, `blocked`, or an explicit waiver.

## State machine

```text
not_started -> in_progress -> passed
                         \-> blocked
                         \-> waived
not_applicable is terminal only when the requirement explicitly permits it.
```

`GO` is reachable only when all required gates are `passed`, all required
owners are named, and no unwaived blocker remains. Missing, stale, conflicting,
or provider-limited evidence keeps the decision at `NO-GO`/`Blocked`.

## Failure modes and invariants

- A local test or successful workflow is not production acceptance evidence.
- Historical evidence is never silently reused for a new candidate.
- Missing owner, reviewer, hosted telemetry, email delivery, alert delivery,
  recovery, rollback, accessibility, legal, performance, or SEO evidence is a
  blocker until independently resolved or formally waived.
- Production resources, secrets, GitHub settings, and deployment state are not
  changed by this specification.
- Generated reader downloads remain out of scope and are not a missing gate.

## Traceability

| Requirement | Acceptance criterion | Planned task | Evidence owner |
| --- | --- | --- | --- |
| REQ-001 | AC-001 | T-001 | Project owner / implementation agent |
| REQ-002 | AC-002 | T-002 | Project owner / implementation agent |
| REQ-003 | AC-003 | T-003 | Project owner / implementation agent |
| REQ-004 | AC-004 | T-004 | Project owner / implementation agent |
| REQ-005 | AC-005 | T-001, T-004 | Project owner / implementation agent |
