# Reader Capacity and Recovery Operational Follow-up Tasks

Spec ID: reader-capacity-and-recovery-follow-up
Version: 0.4.0
Status: Approved
Updated: 2026-08-29

Execution is dependency-ordered. Every task starts unchecked and remains
unchecked until its verification command and evidence review pass. This spec
does not resume the worker, original full queue, or higher reader stages.

`State: complete` will mean that the authorized task, measurement, blocker, or
safety decision is current and evidenced. A failed SLO or unavailable hosted
metric may complete a decision record only when the quantified blocker and
next action are recorded; it must not be relabeled as a capacity pass. A
validator may return success for a well-formed `blocked` disposition because
the safety decision is valid; it must return failure for malformed or
under-specified evidence.

## Approved contract amendment (2026-08-29)

This revision tightens the executable contracts only. At amendment time it did
not start the 1k reader profile, a hosted restore, the translation worker, the
original full queue, or a higher capacity stage. The later bounded Cloudflare
read-only profile is recorded separately below.

- The selected SLO gate is `cloudflare_tunnel`, the non-production
  reader-facing Cloudflare HTTPS Caddy route. `caddy_loopback` is diagnostic
  and requires an explicit Host binding; a missing binding is unavailable.
- The published fixture is supplied explicitly at runtime and represented in
  evidence by the matching opaque `fixture-<16 lowercase hex>` binding. The
  preflight and runner must agree on that binding.
- Cold-cache cells remain unavailable until an independently verified
  disposable reader/cache reset exists. Warmup traffic is not cold evidence.
- The managed-services workflow now names the existing backup integration and
  a dedicated isolated-prefix restore integration, with the credential names
  those tests consume. The managed PostgreSQL assertion tracks the current
  migration head.
- The workflow repair was source-level at amendment time. The confirmation-
  gated disposable reader workflow subsequently executed at run
  `33246036636`; its accepted blocked result and cleanup verification are
  recorded below. Hosted restore and production evidence remain pending.

The disposition rows below retain the original evidence wording for
provenance. In this amendment, the stale workflow reference is repaired in
source; the bounded reader result and the separate managed recovery result are
recorded without promoting either to production capacity.

## Current execution disposition

The task `State` records whether the authorized artifact, decision, or safety
action was completed. It does not mean that the corresponding hosted or live
operation passed. The current operational dispositions are:

| Tasks | Disposition | Meaning |
|---|---|---|
| T-000 | Complete | Semantic validator and contract self-test are implemented. |
| T-001 | Complete with blockers | Baseline is valid with the selected Cloudflare gate and opaque fixture binding; the worker is stopped, while queue/writer state remains unavailable. |
| T-002 | Complete with quantified unavailable cells | The executable matrix contract is valid; the disposable Cloudflare run recorded 1,000 error/transport outcomes across 20 selected warm/cold cells and ten cold-reset proofs, with zero valid latency samples. |
| T-003 | Blocked | Layer attribution is structurally recorded, but all layer timings are unavailable. |
| T-004 | Complete with unavailable telemetry | All required snapshots are joinable and explicitly unavailable. |
| T-005–T-006 | Complete as safe no-op | No evidence-backed local remediation was authorized or applied. |
| T-007 | Blocked admission decision | Workflow run `33246036636` completed and its 60-cell report validated with 30 quantified blockers. The selected Cloudflare cells recorded 1,000 error/transport outcomes, zero valid latency samples, and ten cold-reset proofs; admission remains blocked. |
| T-008–T-009 | Blocked operational evidence | Local tests pass, but current freshness/alert and isolated hosted restore evidence are absent. |
| T-010 | Complete as procedure-only | Actual credential rotation is deferred to a separately authorized maintenance action. |
| T-011–T-012 | Complete with handoff blocker | Local quality and documentation gates pass; Cloudflare-only access is validated, but fixture, cold-cache, telemetry, and operational blockers remain. |

## Evidence Contract and Validator

- [x] **T-000 Define evidence schemas and semantic postcondition validation**
  - Maps to: REQ-002, REQ-003, REQ-004, REQ-006, REQ-011, AC-001, AC-002, AC-003, AC-004, AC-006, AC-011
  - Depends on: none
  - State: complete
  - Authorization: Local tooling and tests only; no runtime, hosted, secret, storage, or database access.
  - Scope: Create `tools/capacity/validate_reader_follow_up.ps1` with fixed schemas for baseline, route-profile, latency-attribution, hosted-telemetry, remediation-decision, backup-controls, restore-verification, stage-1000, recovery-owner, validation, and handoff artifacts. Validate required keys, enums, campaign/run joins, interval ordering, sample counts, percentile rules, independent statuses, NFR-006 blocker fields, redaction constraints, and the rule that `blocked` is valid only with a complete quantified blocker. The validator must return nonzero for missing files, malformed data, invalid joins, fake warm/cold labels, missing postconditions, or production-capacity claims.
  - Verification: `powershell -NoProfile -File tools/capacity/validate_reader_follow_up.ps1 -SelfTest`
  - Expected: The self-test proves valid passed and valid quantified-blocked fixtures are accepted, while malformed, incomplete, secret-bearing, and falsely promoted capacity fixtures are rejected. No fixture contains real secrets or content.
  - Attempts: 1
  - Last result: complete; validator and self-test implemented and verified.
  - Evidence: recorded in `artifacts/operations/reader-capacity-follow-up/evidence-validator.md`.

## Preflight and Safety

- [x] **T-001 Establish authorization, revision, and safety baseline**
  - Maps to: REQ-001, REQ-004, REQ-009, REQ-010, AC-001, AC-007, AC-009
  - Depends on: T-000
  - State: complete
  - Authorization: Project-owner approval is required for hosted traffic, Cloudflare development-host targets, and isolated recovery targets; local read-only inspection is allowed before that approval. The recovery owner role and escalation path must be assigned in this baseline before T-008 or T-009.
  - Scope: Create or extend `tools/capacity/run_reader_follow_up_preflight.ps1` to record current revision, worktree state, Compose topology, target aliases and gate topology, required/diagnostic route sets, explicit fixture binding method, cache warm/cold control method, effective configuration key names without values, authorized profile/sample/timeout/concurrency values, stop thresholds, worker state, original queue state, other writer state, recovery owner role, and protected data/storage boundaries. Capture before/after safety snapshots for the later run without printing secrets, invoke the T-000 validator, and fail closed if worker/queue/writer state or owner assignment cannot be proven.
  - Verification: `powershell -NoProfile -File tools/capacity/run_reader_follow_up_preflight.ps1 -ReadOnly -OutputPath artifacts/operations/reader-capacity-follow-up/baseline.json`
  - Expected: The validator confirms a sanitized baseline with campaign id, revision, UTC interval, target aliases, same-fixture binding, cache-control method, route sets, stop thresholds, owner/escalation record, and explicit worker/full-queue/writer safety states. The worker and original full queue are confirmed stopped/paused; no secret value, canonical content, or raw target is read into evidence.
  - Attempts: 1
  - Last result: complete with safety blockers; the disposable workflow observed the worker as stopped and carried the opaque fixture binding, but queue/writer state remained unavailable.
  - Evidence: recorded in `artifacts/operations/reader-capacity-follow-up/baseline.json`.

- [x] **T-002 Build the executable separated reader route and cache-state profile**
  - Maps to: REQ-002, REQ-004, REQ-006, AC-002, AC-006
  - Depends on: T-001
  - State: complete
  - Authorization: Read-only public GET traffic against an approved disposable or published fixture; no translation enqueue and no canonical mutation.
  - Scope: Reuse or extend `backend/tests/run_phase6_acceptance.py`, `backend/tests/capacity_harness.py`, and `tools/capacity/run_reader_load.ps1`, and create the spec-owned wrapper `tools/capacity/run_reader_profile.ps1`, so the required five routes are sampled separately through `direct_service`, `caddy_loopback`, and `cloudflare_tunnel`. Add `backend/tests/test_reader_profile_contract.py` for the wrapper contract. The command contract must accept explicit target aliases, one explicit fixture binding, `WarmSamples >= 50`, `ColdSamples >= 50`, finite `MaxAttemptsPerCell`, concurrency, timeout, a declared `ColdCacheMode`, `SloGateTopology`, `BaselinePath`, and a report directory. Direct/Cloudflare targets may be unavailable only through an explicit allowlisted reason; the selected SLO target is mandatory. It must run separate topology/cache-state cells, use deterministic percentile aggregation, identify exactly one Caddy-routed SLO gate from the baseline, classify auxiliary routes as diagnostic, and return nonzero for runner failure without confusing a valid quantified blocker with a process failure. It must not inherit the existing fixed-two-telemetry-blocker-as-pass logic. The disposable execution path must use the guarded synthetic fixture seeder and, for cold cells, the isolated reader/cache reset proof rather than a first-request label.
  - Verification: `tools/pytest.ps1 backend/tests/test_capacity_harness.py backend/tests/test_reader_profile_contract.py -q`
  - Expected: The harness produces a complete matrix or explicit quantified unavailable cells with campaign/run/fixture joins, path/route/cache-state records, attempted/valid/error/timeout counts, p50/p95/p99, status counts, payload summaries, and no raw request data. Readiness remains diagnostic while the worker is stopped.
  - Attempts: 1
  - Last result: complete with quantified unavailable cells; the accepted 60-cell disposable artifact contains 20 Cloudflare warm/cold cells with 1,000 error/transport outcomes and zero valid latency samples, plus ten independently recorded cold-reset proofs.
  - Evidence: recorded in `artifacts/operations/reader-capacity-follow-up/route-profile.json`.

## Attribution and Remediation

- [x] **T-003 Implement bounded latency attribution and focused contract tests**
  - Maps to: REQ-003, REQ-004, REQ-007, AC-003, AC-004
  - Depends on: T-002
  - State: complete
  - Authorization: Local source/test changes and read-only metrics collection; no new public response fields.
  - Scope: Add `backend/tests/test_reader_latency_attribution.py` and correlate the profile with Caddy proxy/connect evidence, reader/backend request timing, database pool checkout and statement timing, exact R2 read count/latency/bytes, cache/fallback counts, serialization timing, and a documented network remainder. Use existing runtime telemetry, internal metrics, R2 instrumentation, and fixed labels; report p50/p95/p99/count for comparable layer timings; mark unsupported layers unavailable. Define the same-clock and non-overlap rules in the test contract.
  - Verification: `tools/pytest.ps1 backend/tests/test_reader_latency_attribution.py -q`
  - Expected: Attribution records do not double-count nested intervals and contain no credentials, headers, prompts, bodies, SQL, object keys, IPs, or arbitrary labels. Missing pooler or provider fields carry an explicit unavailable reason, and an invalid clock boundary cannot be reported as a numeric remainder.
  - Attempts: 1
  - Last result: complete with attribution blocked; all layer timings remain unavailable, so no largest contributor is established.
  - Evidence: recorded in `artifacts/operations/reader-capacity-follow-up/latency-attribution.json`.

- [x] **T-004 Capture timestamped hosted and process telemetry**
  - Maps to: REQ-004, REQ-007, REQ-011, AC-004
  - Depends on: T-001, T-002
  - State: complete
  - Authorization: Project-owner approval for dashboard access and the declared UTC collection window; provider and hosted values must be observed without changing plans, credentials, buckets, or data.
  - Scope: Capture the exact interval and provenance for Supabase pool/query/egress visibility, R2 operation/billed-byte visibility, provider quota visibility, application/reader/backend/Caddy metrics, Docker CPU/memory/network, database pool occupancy, Redis/queue state, and separate `translation_provider_rps` and `reader_http_rps` fields. Record a `pre_remediation` window joined to T-001/T-002; T-007 appends its `stage_1000` window to the same artifact. Join each record to the campaign, relevant run, revision, topology, workload, phase, and interval. Record unavailable hosted fields explicitly; do not trigger provider traffic to manufacture a metric.
  - Verification: `powershell -NoProfile -File tools/capacity/validate_reader_follow_up.ps1 -Kind hosted-telemetry -Path artifacts/operations/reader-capacity-follow-up/hosted-telemetry.json`
  - Expected: `artifacts/operations/reader-capacity-follow-up/hosted-telemetry.json` contains timestamped source records, exact join fields, sample/aggregation/provenance/collection-status fields, and explicit unavailable values. Local counters are not labeled as hosted billing or quota actuals, and an unjoinable snapshot is rejected by the validator.
  - Attempts: 1
  - Last result: complete with hosted telemetry unavailable; all required snapshots are joinable and explicitly marked unavailable.
  - Evidence: recorded in `artifacts/operations/reader-capacity-follow-up/hosted-telemetry.json`.

- [x] **T-005 Classify the largest contributor and choose the remediation boundary**
  - Maps to: REQ-004, REQ-005, REQ-011, AC-003, AC-005
  - Depends on: T-003, T-004
  - State: complete
  - Authorization: Project-owner review of the attribution report before any production-like configuration or code change.
  - Scope: Compare direct/Caddy/Cloudflare layers and non-overlapping backend, database, R2, serialization, and network timings. Classify the result as local application, proxy/deployment, hosted dependency, or mixed/unavailable. Name one largest actionable contributor, rollback boundary, stop condition, and expected effect, or record an NFR-006 blocker without speculative remediation. The decision must link baseline revision to the proposed candidate revision, state whether the selected Caddy SLO gate is affected, and state whether T-006 is authorized.
  - Verification: `powershell -NoProfile -File tools/capacity/validate_reader_follow_up.ps1 -Kind remediation-decision -Path artifacts/operations/reader-capacity-follow-up/remediation-decision.md`
  - Expected: `artifacts/operations/reader-capacity-follow-up/remediation-decision.md` records the measured rationale, campaign/run references, before value, intended after value, environment scope, rollback value, stop condition, owner, next action, and whether T-006 is authorized. A mixed/unavailable result remains a quantified blocker rather than a speculative code change.
  - Attempts: 1
  - Last result: complete as a no-op safety decision; remediation is deferred until non-overlapping layer evidence exists.
  - Evidence: recorded in `artifacts/operations/reader-capacity-follow-up/remediation-decision.md`.

- [x] **T-006 Implement the smallest safe remediation and focused regression coverage**
  - Maps to: REQ-005, REQ-011, AC-005, AC-011
  - Depends on: T-005
  - State: complete
  - Authorization: Explicit project-owner approval recorded in T-005; production secret, schema, bucket, and data changes remain forbidden.
  - Scope: Apply only the approved local code or non-secret configuration correction; do not edit `.env`, `deploy/.env`, credentials, or deployment secrets. Preserve public isolation, exact R2 references, no-hot-path `LIST`, database connection arithmetic, cache invalidation, health behavior, and response contracts, and add focused tests. If the contributor is hosted or unavailable, leave implementation unchanged and complete the NFR-006 blocker branch instead. Do not change the runner's status semantics merely to obtain a pass.
  - Verification: `tools/pytest.ps1 backend/tests/test_reader_latency_attribution.py backend/tests/test_capacity_harness.py -q`
  - Expected: Focused tests prove the changed behavior and rollback remains available; the evidence states whether the code/config path changed or was intentionally a no-op because the bottleneck was not safely actionable. Runner correctness and independent result statuses remain covered.
  - Attempts: 1
  - Last result: complete as an authorized no-op; no code/configuration remediation was justified or applied.
  - Evidence: recorded in `artifacts/operations/reader-capacity-follow-up/remediation-evidence.md`.

## 1k Rerun and Recovery Operations

- [x] **T-007 Run the gated 1k-profile rerun and record independent dispositions**
  - Maps to: REQ-006, REQ-010, REQ-011, AC-006, AC-007
  - Depends on: T-006
  - State: complete
  - Authorization: Project-owner approval after T-006; read-only content traffic only; worker and original full queue must remain stopped.
  - Scope: Run only the 1k DAU-equivalent sampled profile using the approved candidate revision and one explicitly supplied fixture binding across direct, Caddy, and Cloudflare paths. Collect at least 50 valid warm and 50 valid controlled-cold samples per required route/path cell, with a finite maximum attempt bound, concurrency 8, and a 20-second request timeout unless an owner-approved change is recorded. Capture the five required routes plus fixed diagnostic auxiliary routes, status/error/timeout/transport counts, payloads, process snapshots, joined pre/post telemetry references, and unavailable fields. Do not run 10k/100k, sustained capacity traffic, or translation traffic. The wrapper must recheck worker/queue/writer safety after the run and fail closed on drift. An unavailable comparison path is a quantified matrix blocker, not a runner crash.
  - Verification: `powershell -NoProfile -File tools/capacity/run_reader_profile.ps1 -ReadOnly -Profile 1000 -ReportDir artifacts/operations/reader-capacity-follow-up/reader-stage-1000 -BaselinePath artifacts/operations/reader-capacity-follow-up/baseline.json`
  - Expected: The report contains baseline/candidate revision linkage, `reader_slo_status`, `path_profile_status`, `telemetry_status`, `recovery_status`, `overall_follow_up_disposition`, and `production_capacity_claim`. Before recovery tasks run, `recovery_status=not_assessed` and the overall disposition cannot be `complete`. `reader_slo_status=passed` requires every required selected-gate route/cache cell to pass its budget with complete valid evidence; hosted billing/quota unavailability is recorded as a telemetry blocker and never becomes a capacity claim. Worker/queue/writer state remains paused and no canonical content or provider operation is performed. The validator accepts a quantified blocked disposition only when all NFR-006 fields are present.
  - Attempts: 1
  - Last result: blocked with quantified admission decision; workflow run `33246036636` seeded the explicit fixture in disposable managed DB/R2, validated the complete report, recorded 1,000 Cloudflare transport errors with zero valid latency samples, and produced ten cold-reset proofs. Cleanup completed and production capacity remains unestablished.
  - Evidence: [workflow run 33246036636](https://github.com/ArchdukeViel/NovelAITranslator2Book/actions/runs/33246036636) and its seven-day sanitized artifact `reader-capacity-nonproduction-33246036636`.

- [x] **T-008 Verify recurring backup freshness, retention, and stale/failure alert controls**
  - Maps to: REQ-008, REQ-011, AC-008
  - Depends on: T-001
  - State: complete
  - Authorization: Read-only inspection and local tests; any real alert delivery requires explicit owner approval and an operator-controlled delivery target. This task does not implement a missing production control; a missing control becomes an explicit blocker and requires a separately authorized implementation task.
  - Scope: Verify the existing `BackupService`, `DatabaseBackupService`, `SchedulerService`, `SchedulerRuntimeState`, `R2IncrementalBackupTarget`, and `OperatorAlertService` paths. Record schedule-derived freshness thresholds, last successful backup, manifest/checksum/reference checks, retention result, stale/failure state, alert transition, durable maintenance status, recovery owner, and alert-delivery evidence. If a real alert test is authorized, use the configured operator path and record only the sanitized result. Object Lock retention debt remains distinct from application backup failure.
  - Verification: `tools/pytest.ps1 backend/tests/test_backup_service.py backend/tests/test_database_backup_crypto.py backend/tests/test_health_service.py backend/tests/test_operator_alert_service.py backend/tests/test_scheduler_service.py -q`
  - Expected: Both database and R2 backup classes expose current or explicitly unavailable freshness/alert evidence, with schedule source and owner assignment; Object Lock retention debt is not misclassified as an application backup failure; no production object is deleted or overwritten.
  - Attempts: 1
  - Last result: complete with recovery evidence unavailable; local control tests pass, but current freshness and alert state were not observed.
  - Evidence: recorded in `artifacts/operations/reader-capacity-follow-up/backup-controls.json`.

- [x] **T-009 Execute an isolated restore verification**
  - Maps to: REQ-008, REQ-011, AC-008
  - Depends on: T-008
  - State: complete
  - Authorization: Explicit project-owner authorization naming the disposable database and isolated R2 target; production restore and canonical target writes are forbidden.
  - Scope: Use the documented service paths and the managed-services recovery procedure to select a committed backup, verify manifest/checksum/reference evidence, restore the encrypted database into the dedicated `restore` target, restore representative R2 material into an isolated prefix or test bucket, verify migration head/tables/constraints/row counts and representative application reads, run isolated public-boundary smoke checks, and record operator/time/result without secrets. Before relying on hosted workflow evidence, verify that the workflow's referenced integration-test paths exist at the candidate revision; a stale workflow path is a named CI-evidence blocker, not a passing restore result. Capture cleanup status only after evidence is committed.
  - Verification: `tools/pytest.ps1 backend/tests/test_database_backup_crypto.py backend/tests/test_r2_backup.py backend/tests/test_backup_service.py -q`
  - Expected: The isolated restore either passes all declared checks or records the exact blocked step, workflow/commit/UTC evidence, target-isolation proof, and cleanup status. Restore freshness is timestamped separately from backup creation freshness. Production database, canonical R2 content, and public production routes remain untouched.
  - Attempts: 1
  - Last result: blocked; local restore-related tests pass, but no independently authorized hosted restore target or current restore evidence was available.
  - Evidence: recorded in `artifacts/operations/reader-capacity-follow-up/restore-verification.md`.

- [x] **T-010 Complete least-privilege and credential-rotation procedure**
  - Maps to: REQ-009, REQ-011, AC-009
  - Depends on: T-001, T-008, T-009
  - State: complete
  - Authorization: Project-owner and recovery-owner approval for the operator procedure; actual production token rotation is a separately named maintenance action.
  - Scope: Review only application CRUD, snapshot-source read, database-backup, and backup-target-write scopes. Confirm the recovery owner/escalation record from T-001, rotation order, rollback retention, masked validation, expiry/review cadence, and failure handling without email addresses, tokens, fingerprints, or connection URLs. Session, provider, and unrelated credentials are excluded.
  - Verification: `powershell -NoProfile -File tools/capacity/validate_reader_follow_up.ps1 -Kind recovery-owner -Path artifacts/operations/reader-capacity-follow-up/recovery-owner-and-rotation.md`
  - Expected: The operator record retains an accountable recovery owner and escalation route; recovery credential scopes are separate and least-privilege; the rotation procedure is executable but no secret is changed by this task unless the separately authorized action is recorded.
  - Attempts: 1
  - Last result: complete as procedure-only evidence; actual credential rotation remains deferred to a separately authorized maintenance action.
  - Evidence: recorded in `artifacts/operations/reader-capacity-follow-up/recovery-owner-and-rotation.md`.

## Validation and Handoff

- [x] **T-011 Run affected implementation and documentation quality gates**
  - Maps to: REQ-005, REQ-011, AC-005, AC-011
  - Depends on: T-006, T-007, T-008, T-009, T-010
  - State: complete
  - Authorization: Local validation only; use the canonical project wrappers and preserve unrelated changes.
  - Scope: Create or extend `tools/capacity/run_reader_follow_up_quality_gates.ps1` as a fail-fast orchestrator that runs affected backend tests, `tools/pyright.ps1`, affected Ruff checks, frontend typecheck/lint/build only if frontend files changed, Markdown/link/path and workflow-reference checks, the router import guard, the spec validator, and the evidence validator over every generated artifact. It must record each command, timeout, exit code, result count, exact path, and whether a failure is pre-existing or introduced; one failure must make the orchestrator fail without hiding later output. A missing workflow-referenced test path must be reported as a CI-evidence blocker.
  - Verification: `powershell -NoProfile -File tools/capacity/run_reader_follow_up_quality_gates.ps1 -SpecPath .agents/specs/reader-capacity-and-recovery-follow-up -ArtifactPath artifacts/operations/reader-capacity-follow-up`
  - Expected: All applicable checks pass or each failure is recorded as a concrete blocker with command/exit code/path evidence; no unrelated pre-existing error is silently attributed to this spec. A successful validator run does not erase an operational SLO or hosted-telemetry blocker.
  - Attempts: 1
  - Last result: complete with an operational blocker; local checks and the accepted remote evidence validators pass, while reader admission, hosted telemetry, and queue/writer observation remain blocked.
  - Evidence: recorded in `artifacts/operations/reader-capacity-follow-up/validation.md`.

- [x] **T-012 Synchronize canonical documentation and close the handoff**
  - Maps to: REQ-004, REQ-007, REQ-011, AC-004, AC-010, AC-011
  - Depends on: T-011
  - State: complete
  - Authorization: Project-owner review of evidence and status wording; historical checkpoint paragraphs remain intact and are labeled historical where needed.
  - Scope: Update only the affected sections of `docs/PERFORMANCE_ACTION_PLAN.md`, `docs/PERFORMANCE_AUDIT.md`, `docs/OPERATIONS.md`, `docs/WORK.md`, `docs/HISTORY.md`, and the R2 plan. Distinguish completed evidence, quantified blockers, unavailable hosted metrics, recovery ownership, and the still-paused worker/higher stages. Do not mark production capacity or billing ready.
  - Verification: `graphify update . --no-cluster`
  - Expected: Canonical documents, evidence artifacts, this spec's task states, and the Graphify index agree on the current disposition; the final handoff names the independent SLO/telemetry/recovery statuses, next practical action, production-capacity non-claim, and safety stop where applicable.
  - Attempts: 1
  - Last result: handoff recorded as blocked after the disposable Cloudflare evidence run; canonical documents preserve the distinction between this valid non-production package and unperformed hosted/production operations.
  - Evidence: recorded in `artifacts/operations/reader-capacity-follow-up/handoff.md`.
