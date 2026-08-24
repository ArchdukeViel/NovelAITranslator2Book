# Launch Acceptance Tasks

Spec ID: launch-readiness-checklist
Version: 1.0.0
Status: Approved
Updated: 2026-08-24

- [ ] T-001 Assign launch and operational owners
  - Maps to: REQ-004, AC-004
  - Depends on: none
  - State: pending
  - Authorization: Project-owner approval for hosted launch-gate ownership
  - Scope: launch, rollback, monitoring, security, recovery, accessibility, performance, SEO, and legal owners
  - Verification: Review the owner list in the candidate launch record
  - Expected: Every required domain has one named accountable owner and the rollback and monitoring owners are explicit
  - Attempts: 0
  - Last result: not run
  - Evidence: Pending: attach a sanitized owner list to the launch record

- [ ] T-002 Evaluate the canonical operator gates
  - Maps to: REQ-001, REQ-003, AC-001, AC-003
  - Depends on: T-001
  - State: pending
  - Authorization: Project-owner approval for read-only hosted acceptance checks
  - Scope: Exact candidate and every applicable `docs/WORK.md` gate across product, security, legal, accessibility, performance, SEO, monitoring, recovery, and rollback
  - Verification: Review `docs/WORK.md` against the exact candidate and record one allowed status per applicable gate
  - Expected: The run uses the canonical checklist once and every required domain has evidence or an explicit not-applicable reason
  - Attempts: 0
  - Last result: not run
  - Evidence: Pending: attach the sanitized gate matrix and candidate identifier

- [ ] T-003 Resolve blockers and record waivers
  - Maps to: REQ-002, REQ-004, REQ-005, AC-002, AC-004, AC-005
  - Depends on: T-002
  - State: pending
  - Authorization: Project-owner and named approver authorization for each waiver or remediation decision
  - Scope: Unresolved blockers, waiver owner, approver, rationale, expiry, and sensitive-data review of the evidence packet
  - Verification: Review each blocked or waived gate and run the sanitized-evidence review
  - Expected: Every blocker is resolved or has a formal time-bounded waiver, and the packet contains no protected data
  - Attempts: 0
  - Last result: not run
  - Evidence: Pending: attach blocker resolutions or approved waiver records

- [ ] T-004 Record the final decision and monitoring handoff
  - Maps to: REQ-002, REQ-004, AC-002, AC-004
  - Depends on: T-003
  - State: pending
  - Authorization: Project-owner authorization to record the launch decision
  - Scope: Final `GO` or `NO-GO`, remaining notes, rollback owner, monitoring owner, and post-launch observation window
  - Verification: Review the decision against the zero-unwaived-blocker and named-owner conditions
  - Expected: `GO` is recorded only when its conditions pass; otherwise `NO-GO` identifies the next safe action
  - Attempts: 0
  - Last result: not run
  - Evidence: Pending: attach the signed sanitized decision record

- [ ] T-005 Update history and archive after an approved `GO`
  - Maps to: REQ-002, REQ-005, AC-002, AC-005
  - Depends on: T-004
  - State: pending
  - Authorization: Project-owner authorization for the post-`GO` documentation and archive operation
  - Scope: Sanitized summary in `docs/HISTORY.md` and the approved archive location for this specification
  - Verification: Review the history entry, archive path, and secret-safety scan after the decision is `GO`
  - Expected: The history entry links the evidence boundary and the archived specification without exposing sensitive data
  - Attempts: 0
  - Last result: not run
  - Evidence: Pending: attach the history entry and archive review
