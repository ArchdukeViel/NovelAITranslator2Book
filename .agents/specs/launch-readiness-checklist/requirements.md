# Launch Acceptance Requirements

Spec ID: launch-readiness-checklist
Version: 1.0.0
Status: Approved
Updated: 2026-08-24

## Context and Problem

The repository needs one operator-owned launch decision record that uses the
existing gates in `docs/WORK.md` and the procedures in the canonical operations
and deployment documents. A launch packet must distinguish an actual pass from
an unresolved blocker, an approved waiver, and a gate that is not applicable.

## Goal

Produce a defensible `GO` or `NO-GO` decision from hosted evidence without
duplicating the operator checklist or exposing sensitive information.

## Scope and Boundaries

In scope: candidate identification, owner assignment, product and security
gates, legal propagation, accessibility, performance, SEO, monitoring and
alerts, recovery, rollback, sanitized evidence, waivers, and the final decision.

Generated reader downloads are not applicable and require no acceptance work.
Remote merge, deployment, production data mutation, and secret management are
operator actions outside this document.

## Requirements

- REQ-001: The acceptance run MUST use the operator gates in `docs/WORK.md`
  and MUST NOT create a second competing checklist.
- REQ-002: Each evidence record MUST identify the exact candidate, environment,
  UTC time, operator, command or URL, sanitized result, blocker, and waiver
  details when applicable.
- REQ-003: The run MUST evaluate product flow, auth and security, legal
  propagation, accessibility, performance, SEO, monitoring and alerts,
  recovery, and rollback using the allowed gate statuses.
- REQ-004: A `GO` decision MUST have zero unwaived blockers and named launch,
  rollback, and monitoring owners. Unresolved blockers MUST produce `NO-GO`.
- REQ-005: Evidence MUST exclude secrets, private content, connection strings,
  raw paths, traces, and other sensitive payloads.

## Acceptance Criteria

- AC-001: The final packet identifies one candidate and records completion of
  the `docs/WORK.md` operator gates without duplicating them.
  Maps to: REQ-001
- AC-002: Every evaluated gate has a sanitized evidence record with the
  candidate, environment, UTC time, operator, exact command or URL, result,
  blocker state, and waiver details where needed.
  Maps to: REQ-002
- AC-003: Product, security, legal, accessibility, performance, SEO,
  monitoring, recovery, and rollback gates each have an allowed status and
  supporting evidence or an explicit not-applicable reason.
  Maps to: REQ-003
- AC-004: The recorded decision is `GO` only when the zero-unwaived-blocker
  condition and named-owner condition are both satisfied; otherwise it is
  `NO-GO` or an explicitly approved waiver state.
  Maps to: REQ-004
- AC-005: A review of the packet finds no secret, private content, connection
  string, raw path, trace, or generated-reader-download acceptance claim.
  Maps to: REQ-005

## Acceptance Coverage

| Acceptance criterion | Planned task(s) |
| --- | --- |
| AC-001 | T-002 |
| AC-002 | T-003, T-004 |
| AC-003 | T-002 |
| AC-004 | T-001, T-003, T-004 |
| AC-005 | T-003, T-005 |
