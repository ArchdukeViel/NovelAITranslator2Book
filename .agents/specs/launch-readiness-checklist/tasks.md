# Launch Acceptance Tasks

Spec ID: launch-readiness-checklist
Version: 0.2.0
Status: Blocked
Updated: 2026-08-30

- [x] T-001 Assign sanitized gate ownership
  - Maps to: REQ-001, AC-001, AC-005
  - Depends on: none
  - State: complete
  - Authorization: Project-owner-authorized launch-readiness documentation
  - Scope: Record owners without personal contact details or secret data.
  - Verification: `rg -n "owner|reviewer|launch|rollback|monitoring|security|recovery|accessibility|performance|SEO|legal" docs/WORK.md`
  - Expected: Every required gate has a named owner or an explicit missing-owner blocker.
  - Attempts: 1
  - Last result: Owner rows are present; a backup reviewer/second-owner waiver remains unresolved.
  - Evidence: `docs/WORK.md`; `artifacts/operations/reader-capacity-follow-up/recovery-owner-and-rotation.md`

- [ ] T-002 Freeze and reconcile the exact candidate
  - Maps to: REQ-002, AC-002
  - Depends on: T-001
  - State: blocked
  - Authorization: Requires project-owner release authorization for a production candidate.
  - Scope: Reconcile current hosted and manual evidence to one exact candidate without changing production resources.
  - Verification: `docs/WORK.md` candidate and gate rows plus hosted/manual evidence links.
  - Expected: Every completed gate is current-candidate, sanitized, and reproducible.
  - Attempts: 1
  - Last result: Current repository candidate is documented, but required production hosted/manual evidence is missing.
  - Evidence: `docs/WORK.md`; `docs/HISTORY.md`; current CI artifacts where explicitly labeled.

- [ ] T-003 Resolve blockers or record formal waivers
  - Maps to: REQ-003, AC-003
  - Depends on: T-001, T-002
  - State: blocked
  - Authorization: Requires the project owner and appropriate gate approvers; no waiver is inferred.
  - Scope: Resolve or formally waive SMTP, monitoring/alerts, recovery, rollback, accessibility, performance, SEO, legal, and other listed gates.
  - Verification: Each row in `docs/WORK.md` has independent evidence or an owner/approver/expiry waiver.
  - Expected: No unwaived required blocker remains.
  - Attempts: 0
  - Last result: Not executed because the required hosted/manual evidence and formal approvals are unavailable.
  - Evidence: `docs/WORK.md` current NO-GO register.

- [x] T-004 Record current final decision and monitoring ownership
  - Maps to: REQ-004, REQ-005, AC-004, AC-005
  - Depends on: T-002, T-003
  - State: complete
  - Authorization: Project-owner-authorized factual status documentation.
  - Scope: Preserve `NO-GO` while required evidence or ownership remains open; do not imply launch approval.
  - Verification: `rg -n "NO-GO|production_capacity_claim|monitoring|rollback" docs/WORK.md docs/HISTORY.md`
  - Expected: The decision rule and sanitized evidence boundary are explicit.
  - Attempts: 1
  - Last result: Current decision is `NO-GO`; monitoring ownership and remaining gates are recorded as open where unverified.
  - Evidence: `docs/WORK.md`; `docs/HISTORY.md`; this specification.

- [ ] T-005 Archive only after verified GO
  - Maps to: REQ-004, AC-004
  - Depends on: T-002, T-003, T-004
  - State: blocked
  - Authorization: Requires explicit project-owner authorization after all launch gates pass.
  - Scope: Summarize verified evidence in `docs/HISTORY.md` and archive this spec only after a real `GO`.
  - Verification: `Test-Path docs/HISTORY.md` and `Test-Path docs/archive/specs/launch-readiness-checklist`
  - Expected: No archive occurs while status is `Blocked` or decision is `NO-GO`.
  - Attempts: 0
  - Last result: Correctly not executed because launch acceptance is not complete.
  - Evidence: Active spec remains under `.agents/specs/launch-readiness-checklist/`; `docs/WORK.md` remains NO-GO.
