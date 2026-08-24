# Pipeline Async Execution and Capacity Hardening Tasks

Spec ID: pipeline-async-execution-and-capacity
Version: 0.3.0
Status: Approved
Updated: 2026-08-24

Execution is dependency-ordered. Every task starts unchecked and remains
unchecked until its verification command and evidence review pass. The worker
must not be resumed automatically, and the original full queues must remain
paused throughout this specification.

`State: complete` means that the task's authorized local scope, decision, or
gate assessment is recorded and verified. `Disposition:` records the complete
result and its evidence boundary; a safety stop or retain decision is complete
when it is authorized, measured, and recorded without turning missing evidence
into a pass.

## Preflight and Design

- [x] T-001 Establish the execution boundary and fresh sanitized baseline.
  - Maps to: REQ-001, REQ-020, REQ-022, AC-001, AC-016
  - Depends on: none
  - State: complete
  - Authorization: local read-only inspection; no external mutation
  - Scope: branch/worktree preservation, canonical docs, active specs, worker state, Compose topology, configuration key names, bucket names, queue snapshot, and available hosted telemetry
  - Verification: Run `git status --short`, `docker compose -f deploy/compose.yml ps -a worker`, `docker compose -f deploy/compose.yml config --quiet`, and `graphify query "pipeline async execution worker database R2 capacity boundaries" --budget 1200` in order and stop on the first failure.
  - Expected: The worker and original full queues are confirmed stopped/paused, protected surfaces and current evidence sources are recorded, and no secret value or canonical data is read into the report.
  - Attempts: 1
  - Last result: passed; `git status --short`, worker status, Compose config, and Graphify query all exited 0; read-only queue snapshot reported 0 pending and 3 paused translation activities.
  - Evidence: `artifacts/capacity/pac-8a109a5ad1cd-baseline.json`; no provider calls, canonical R2 enumeration, queue resume, or secret capture.

- [x] T-002 Produce the current async call graph and blocking-operation inventory.
  - Maps to: REQ-002, REQ-003, AC-002
  - Depends on: T-001
  - State: complete
  - Authorization: local source inspection only
  - Scope: `translate_chapters`, `_run_chapter`, pipeline stages, activity worker/runner, `session_scope`, storage service, R2 backend, checkpoint/runtime operations, and all synchronous calls reachable from chapter coroutines
  - Verification: `codegraph explore "translate_chapters _run_chapter session_scope StorageService R2Storage ActivityWorkerService BackgroundActivityRunner synchronous calls inside async chapter tasks"`
  - Expected: Each operation is classified as async-safe, synchronous but bounded, synchronous and blocking, CPU-heavy, or unavailable, with its owner, session lifetime, and proposed boundary.
  - Attempts: 1
  - Last result: passed; CodeGraph exploration completed with exit code 0 and identified the current `_run_chapter -> _update_db_translation_state -> session_scope` path plus related worker, checkpoint, pipeline, and R2 symbols.
  - Evidence: `artifacts/capacity/pac-8a109a5ad1cd-async-call-graph-inventory.md`; static inventory is explicit about event-loop blocking, ownership, and unavailable hosted/runtime fields.

- [x] T-003 Define the telemetry, redaction, and provenance contract before implementation.
  - Maps to: REQ-001, REQ-004, REQ-011, REQ-016, REQ-020, AC-001, AC-009
  - Depends on: T-001, T-002
  - State: complete
  - Authorization: local design/source/test edits only
  - Scope: fixed stage and operation enums, correlation fields, event-loop lag, queue wait, DB pool/statement/commit, provider usage, R2 operations/bytes, memory, error codes, unavailable reasons, cardinality limits, and redaction tests
  - Verification: `tools\pytest.ps1 backend/tests/test_pipeline_timing_audit.py -q`
  - Expected: A versioned observation schema is documented and tested; prompts, responses, secrets, IPs, raw source identifiers, arbitrary URLs, and unbounded labels are rejected or omitted.
  - Attempts: 1
  - Last result: passed; `tools\pytest.ps1 backend/tests/test_pipeline_timing_audit.py -q` exited 0 with 3 passed in 2.88s.
  - Evidence: `artifacts/capacity/pac-8a109a5ad1cd-telemetry-contract.md`; schema version 1, fixed enums, provenance classes, named measurement-boundary values, and redaction boundaries are recorded. Runtime resource samplers are covered by T-012.

- [x] T-004 Select and document the async boundary implementation option.
  - Maps to: REQ-002, REQ-003, REQ-018, AC-002, AC-003, AC-004
  - Depends on: T-002, T-003
  - State: complete
  - Authorization: local design decision; no runtime or schema mutation
  - Scope: compare async-native adapters, bounded synchronous executor, and serialized fallback; define operation classes, executor size/queue, cancellation, shutdown, client ownership, DTO shape, and rollback gate
  - Verification: `rg -n "TranslationPersistencePort|ThreadPoolExecutor|to_thread|session_scope|R2|async boundary" .agents/specs/pipeline-async-execution-and-capacity/design.md docs/TRANSLATION.md docs/ARCHITECTURE.md`
  - Expected: One reversible first slice is selected with explicit rejection criteria for unsafe session/thread sharing and no requirement to move canonical content.
  - Attempts: 1
  - Last result: passed; the required `rg` contract search exited 0 and found the Option B bounded executor/session/R2 boundary in the approved design.
  - Evidence: `artifacts/capacity/pac-8a109a5ad1cd-async-boundary-decision.md`; explicit DTO/session/client ownership, bounded queue, cancellation/shutdown, rollback, and rejection criteria recorded.

## Async Boundary and Persistence Implementation

- [x] T-005 Implement the bounded async-facing persistence/storage boundary.
  - Maps to: REQ-002, REQ-003, REQ-004, REQ-005, AC-003, AC-004, AC-006
  - Depends on: T-004
  - State: complete
  - Authorization: local backend implementation and test edits
  - Scope: plain DTO commands/results, bounded executor or async adapter, scalar/narrow reads, exact-key R2 operations, runtime checkpoint writes, queue wait metrics, and failure classification
  - Verification: `tools\pytest.ps1 backend/tests/test_translation_async_boundary.py backend/tests/test_pipeline_timing_audit.py -q`
  - Expected: Blocking DB/R2/runtime operations leave the event loop through a bounded, observable boundary without changing artifact or state semantics.
  - Attempts: 1
  - Last result: passed; `tools\pytest.ps1 backend/tests/test_translation_async_boundary.py backend/tests/test_pipeline_timing_audit.py -q` exited 0 with 6 passed in 3.00s; the scheduler regression suite also exited 0 with 26 passed in 154.33s. Focused Ruff and Pyright exited 0.
  - Evidence: `backend/src/novelai/services/orchestration/translation_persistence.py` and `backend/tests/test_translation_async_boundary.py`; the lazy service-owned executor avoids thread creation for non-translation services, while resume/preflight/QA helper sequencing remains the T-006/T-007 boundary scope.

- [x] T-006 Add session, ORM, transaction, and storage-client ownership guards.
  - Maps to: REQ-003, REQ-005, REQ-006, REQ-016, AC-004, AC-005
  - Depends on: T-005
  - State: complete
  - Authorization: local backend implementation and test edits
  - Scope: per-operation session creation/close, DTO conversion, lazy-column prevention, rollback on exception, R2 client ownership/thread-safety contract, and prohibition of live ORM/session arguments at executor boundaries
  - Verification: `tools\pytest.ps1 backend/tests/test_translation_async_boundary.py backend/tests/test_activity_database.py backend/tests/test_storage_backends.py -q`
  - Expected: Tests fail if a live session/ORM object crosses the boundary, if a lazy load occurs after close, or if a failed operation leaks a transaction or executor slot.
  - Attempts: 1
  - Last result: passed; `tools\pytest.ps1 backend/tests/test_translation_async_boundary.py backend/tests/test_activity_database.py backend/tests/test_storage_backends.py -q` exited 0 with 24 passed in 18.70s; focused Ruff and Pyright exited 0.
  - Evidence: `backend/src/novelai/services/orchestration/translation_persistence.py` rejects live SQLAlchemy resources and mapped instances before submission and before result detachment; `backend/tests/test_translation_async_boundary.py` covers rollback, detached lazy access, ORM rejection, and slot release.

- [x] T-007 Separate provider/QA waits from persistence and terminal commits.
  - Maps to: REQ-004, REQ-005, REQ-006, REQ-019, AC-005, AC-006
  - Depends on: T-005, T-006
  - State: complete
  - Authorization: local translation/orchestration implementation and test edits
  - Scope: chapter coordinator sequencing, provider semaphore, QA execution, persistence command submission, terminal lineage/reference transaction, and no-connection-held-across-wait guard
  - Verification: `tools\pytest.ps1 backend/tests/test_translation_scheduler.py backend/tests/test_checkpoint_resume.py backend/tests/test_translation_async_boundary.py -q`
  - Expected: Provider calls and QA can overlap within their budgets, persistence is bounded, terminal commits remain atomic, and DB occupancy excludes provider/retry/R2 waits.
  - Attempts: 1
  - Last result: passed; `tools\pytest.ps1 backend/tests/test_translation_scheduler.py backend/tests/test_checkpoint_resume.py backend/tests/test_translation_async_boundary.py -q` exited 0 with 51 passed in 157.77s. Focused Ruff and Pyright exited 0.
  - Evidence: `backend/src/novelai/services/orchestration/translation.py` routes preflight, checkpoint/resume, lineage assembly, and QA-output persistence through `TranslationPersistencePort.storage_owned_call`; provider/QA waits occur after those awaits and before later persistence submissions.

- [x] T-008 Add bounded progress batching, idempotency, and replay behavior.
  - Maps to: REQ-005, REQ-006, REQ-010, REQ-019, AC-005, AC-006
  - Depends on: T-007
  - State: complete
  - Authorization: local backend implementation and test edits
  - Scope: coalesced non-terminal progress/events/chunk states, deterministic run/chapter/attempt idempotency, terminal-write ordering, replay after executor/process failure, and bounded queue retention
  - Verification: `tools\pytest.ps1 backend/tests/test_checkpoint_resume.py backend/tests/test_job_worker_service.py backend/tests/test_translation_async_boundary.py -q`
  - Expected: Query/write volume decreases for the fixed workload without lost terminal state, duplicate active references, false completion, or unrecoverable cancellation.
  - Attempts: 1
  - Last result: passed; `tools\pytest.ps1 backend/tests/test_checkpoint_resume.py backend/tests/test_job_worker_service.py backend/tests/test_translation_async_boundary.py -q` exited 0 with 35 passed in 8.49s. Focused Ruff and Pyright exited 0.
  - Evidence: `TranslationPersistencePort.persist_progress_batch`, `traceability.append_pipeline_events`, and `traceability.upsert_chunk_states` provide bounded batching and deterministic replay keys; the async boundary test confirms duplicate progress submission does not duplicate stored event/chunk records.

- [x] T-009 Preserve queue leases, cancellation, retry, and graceful shutdown under the new boundary.
  - Maps to: REQ-006, REQ-007, REQ-015, REQ-018, AC-007, AC-008, AC-017
  - Depends on: T-007, T-008
  - State: complete
  - Authorization: local worker/activity implementation and test edits; live execution remains separately gated
  - Scope: admission stop, lease-loss cancellation, heartbeat independence, executor drain deadline, critical-command flush, expired-lease recovery, retry classification, and restart resume
  - Verification: `tools\pytest.ps1 backend/tests/test_activity_database.py backend/tests/test_job_runner_service.py backend/tests/test_job_worker_service.py backend/tests/test_checkpoint_resume.py -q`
  - Expected: Concurrent-worker and shutdown tests show no duplicate claim, silent lease loss, leaked task, premature terminal state, or unbounded drain.
  - Attempts: 1
  - Last result: passed; `tools\pytest.ps1 backend/tests/test_activity_database.py backend/tests/test_job_runner_service.py backend/tests/test_job_worker_service.py backend/tests/test_checkpoint_resume.py -q` exited 0 with 37 passed in 16.38s; the focused boundary cancellation suite exited 0 with 8 passed in 4.87s. Focused Ruff and Pyright had no errors.
  - Evidence: `ActivityWorkerService.shutdown` and `BackgroundActivityRunner.stop` drain the translation persistence executor after cancelling the loop; lease/heartbeat, cancellation, retry, checkpoint, and worker tests remain green, and the boundary test proves an in-flight cancelled call settles before drain completes.

## Resource Controls and Observability

- [x] T-010 Add database query-shape, pool, and egress regression evidence.
  - Maps to: REQ-008, REQ-011, REQ-012, REQ-020, AC-006, AC-010
  - Depends on: T-003, T-007, T-008
  - State: complete
  - Authorization: local tests plus read-only Supabase inspection; no DDL or row mutation
  - Scope: narrow projections, N+1 guards, query call/row/duration counters, pool checkout/wait metrics, representative `EXPLAIN`, connection arithmetic, and honest provider-byte unavailability
  - Verification: Run `tools\pytest.ps1 backend/tests/test_catalog_service.py backend/tests/test_activity_database.py backend/tests/test_pipeline_timing_audit.py -q` and then `tools\ruff.ps1 check .`.
  - Expected: The fixed workload has a comparable before/after report, heavy columns are not hydrated on routine paths, and no query-level billed-byte claim is made without provider evidence.
  - Attempts: 1
  - Last result: passed; `tools\pytest.ps1 backend/tests/test_catalog_service.py backend/tests/test_activity_database.py backend/tests/test_pipeline_timing_audit.py -q` exited 0 with 48 passed in 25.40s, followed by `tools\ruff.ps1 check .` exit 0.
  - Evidence: `artifacts/capacity/pac-8a109a5ad1cd-query-shape-pool-egress.md`; narrow projection/deferred-column tests and activity claim/heartbeat source review passed. The hosted billed-byte and per-query provider-egress measurement boundary is explicitly recorded.

- [x] T-011 Protect R2 exact-key and no-hot-path-LIST invariants.
  - Maps to: REQ-009, REQ-010, REQ-022, AC-011
  - Depends on: T-005, T-007
  - State: complete
  - Authorization: local static/tests; isolated R2 write/read/delete requires project-owner live gate
  - Scope: hot-path static import/call audit, operation counters, compression/reuse accounting, conditional-read safety, unique isolated prefix, final paginated cleanup, and two-bucket scope separation
  - Verification: Run `tools\pytest.ps1 backend/tests/test_storage_backends.py backend/tests/test_r2_content_addressing.py backend/tests/integration/test_s3_integration.py -q` and then `rg -n "list_objects_v2|\.list\(" backend/src/novelai/api backend/src/novelai/translation backend/src/novelai/services/orchestration`.
  - Expected: No reader/translation hot path lists objects; any live fixture is deleted and the final sweep reports zero objects; canonical R2 prefixes are unchanged.
  - Attempts: 1
  - Last result: passed; `tools\pytest.ps1 backend/tests/test_storage_backends.py backend/tests/test_r2_content_addressing.py backend/tests/integration/test_s3_integration.py -q` exited 0 with 21 passed and 6 skipped in 23.34s; the required `rg` search exited 0 and found only an unrelated notification list call.
  - Evidence: `artifacts/capacity/pac-8a109a5ad1cd-r2-static-and-fixture-audit.md`; local exact-key tests and static classification passed. Live isolated R2 operation/byte accounting and cleanup are recorded by T-015.

- [x] T-012 Implement the bounded runtime telemetry and redaction checks.
  - Maps to: REQ-004, REQ-011, REQ-016, REQ-020, AC-009
  - Depends on: T-003, T-005, T-009, T-010, T-011
  - State: complete
  - Authorization: local backend/test/metrics edits
  - Scope: event-loop lag sampler, executor queue wait, DB checkout/statement/commit, provider wait/retry/tokens, R2 operation/bytes, memory/CPU, queue age, fixed labels, sampling, and unavailable reasons
  - Verification: `tools\pytest.ps1 backend/tests/test_pipeline_timing_audit.py backend/tests/test_health_service.py backend/tests/test_job_worker_service.py -q`
  - Expected: Sample observations are bounded and redacted, metric failures do not create unbounded memory, and every required stage has a value or named unavailable reason.
  - Attempts: 2
  - Last result: passed; `tools\pytest.ps1 backend/tests/test_pipeline_timing_audit.py backend/tests/test_health_service.py backend/tests/test_job_worker_service.py -q` exited 0 with 43 passed in 10.47s. Focused Ruff and `tools\pyright.ps1` also exited 0; `graphify update . --no-cluster` exited 0.
  - Evidence: `artifacts/capacity/pac-8a109a5ad1cd-runtime-telemetry.md`; bounded observation schema, fixed labels, event-loop sampler, process-resource availability, Prometheus gauges, and redaction tests are recorded. Hosted billing and network-attribution boundaries are explicit, while live provider/R2 evidence is recorded by T-016.

- [x] T-013 Add conservative configuration, budget, feature-gate, and rollback controls.
  - Maps to: REQ-007, REQ-012, REQ-015, REQ-018, AC-007, AC-012, AC-017
  - Depends on: T-009, T-012
  - State: complete
  - Authorization: local settings/Compose/example/docs edits; real secret-bearing `.env` values remain operator-managed
  - Scope: persistence workers/queue, provider and chapter limits, load admission, event-loop threshold, DB pool arithmetic, reserve, timeouts, shutdown deadlines, and disabled-by-default rollout gate
  - Verification: Run `tools\pytest.ps1 backend/tests/test_settings.py backend/tests/test_job_worker_service.py -q` and then `docker compose -f deploy/compose.yml config --quiet`.
  - Expected: Every new setting has validation, an allowed range, an environment scope, a conservative default, a rollback value, and startup failure for impossible aggregate budgets.
  - Attempts: 1
  - Last result: passed; `tools\pytest.ps1 backend/tests/test_settings.py backend/tests/test_job_worker_service.py -q` exited 0 with 29 passed in 6.81s; `docker compose -f deploy/compose.yml config --quiet` exited 0. Additional production budget tests passed 33/33, focused boundary tests passed 9/9, Ruff and Pyright exited 0.
  - Evidence: `artifacts/capacity/pac-8a109a5ad1cd-capacity-configuration.md`; bounded settings, explicit rollback gate, Compose environment wiring, and aggregate DB-pool startup validation are recorded.

- [x] T-024 Audit and harden contributor credential pool admission and accounting.
  - Maps to: REQ-007, REQ-011, REQ-012, REQ-015, REQ-026, AC-007, AC-009, AC-012, AC-017, AC-023
  - Depends on: T-003, T-009, T-012, T-013
  - State: complete
  - Authorization: local implementation, test, configuration, and report edits; live credential activation and provider calls remain separately gated by T-016; raw API keys must never be read into evidence
  - Scope: unified-registry eligibility, consent/validation/status gates, per-credential RPM/TPM/RPD/in-flight reservations, verified quota-domain handling, aggregate provider caps, fair selection, starvation/monopoly protection, owner-job versus contributor-pool isolation, usage-ledger reconciliation, invalid/quota failure state, and separate translation-provider RPS versus reader HTTP RPS
  - Verification: `tools\pytest.ps1 backend/tests/test_contributor_credentials.py backend/tests/test_user_contributions_router.py backend/tests/test_gemini_provider.py backend/tests/test_translation_scheduler.py backend/tests/test_contributor_pool_capacity.py -q`
  - Expected: Only eligible credentials are selected; reservations and ledger outcomes reconcile on success, failure, cancellation, timeout, and expiry; same-project keys do not multiply project quota; verified independent domains are modeled conservatively; selection is fair; and no raw key, prompt, response, or authorization header is emitted.
  - Attempts: 1
  - Last result: passed; `tools\pytest.ps1 backend/tests/test_contributor_credentials.py backend/tests/test_user_contributions_router.py backend/tests/test_gemini_provider.py backend/tests/test_translation_scheduler.py backend/tests/test_contributor_pool_capacity.py -q` exited 0 with 60 passed in 160.47s. The focused pool tests passed 4/4, focused Ruff exited 0, and `tools\pyright.ps1` exited 0 with 0 errors, 0 warnings, and 0 informations.
  - Evidence: `artifacts/capacity/pac-8a109a5ad1cd-contributor-pool-capacity.md`; shared-project plus per-credential reservations, conservative quota-domain accounting, fair eligible selection, owner/contributor isolation, expiry/reconciliation, separate reader RPS, and secret-free ledger attribution are recorded.

## Benchmarks and Controlled Workloads

- [x] T-014 Build the fixture-only pipeline and reader load harness.
  - Maps to: REQ-013, REQ-014, REQ-016, REQ-020, REQ-026, AC-006, AC-013, AC-023
  - Depends on: T-010, T-012, T-013, T-024
  - State: complete
  - Authorization: local fixture generation and test code only
  - Scope: public catalog/detail/chapter request mix, cache-warm/cold modes, response-size classes, bounded synthetic identities, optional one-chapter worker job, metrics export, fixed seed, timeout, and repeatability report
  - Verification: `tools\pytest.ps1 backend/tests/test_capacity_harness.py -q`
  - Expected: The harness runs without canonical DB/R2/provider writes, records the declared traffic model and resources, and produces comparable output for the same seed and configuration.
  - Attempts: 1
  - Last result: passed; `tools\pytest.ps1 backend/tests/test_capacity_harness.py -q` exited 0 with 9 passed in 3.15s. Focused Ruff and `tools\pyright.ps1` also exited 0.
  - Evidence: `artifacts/capacity/pac-8a109a5ad1cd-fixture-capacity-harness.md`; deterministic request mix, warm/cold cache model, bounded synthetic identities, response-size classes, optional one-worker fixture sample, fixed-label metrics, timeout behavior, and zero canonical-write/provider-call assertions are recorded.

- [x] T-015 Run the isolated R2 operation benchmark and prove cleanup.
  - Maps to: REQ-009, REQ-011, REQ-022, AC-011, AC-013
  - Depends on: T-011, T-014
  - State: complete
  - Disposition: complete — live isolated R2 pass and hosted-evidence boundary recorded.
  - Authorization: project-owner approval for generated isolated-prefix R2 PUT/GET/HEAD/DELETE with mandatory cleanup; no canonical prefix access
  - Scope: compression, immutable hash reuse, exact reads, optional conditional reads, operation counts, bytes, latency, errors, and final paginated zero-object sweep in the application bucket only
  - Verification: `tools\pytest.ps1 backend/tests/integration/test_s3_integration.py -q`
  - Expected: The isolated benchmark either passes with complete cleanup evidence or is marked unavailable because external R2 settings are not configured; no production object is changed.
  - Attempts: 1
  - Last result: passed; `tools\pytest.ps1 backend/tests/integration/test_s3_integration.py -q` exited 0 with 6 passed in 11.68s, including the final paginated zero-object cleanup assertion.
  - Evidence: `artifacts/capacity/pac-8a109a5ad1cd-r2-operation-benchmark.md`; the isolated test bucket was distinct from application and backup buckets, and no canonical object was mutated.

- [x] T-022 Build the hosted-versus-modeled cost envelope for each fixed and reader-capacity stage.
  - Maps to: REQ-011, REQ-020, REQ-021, REQ-024, REQ-026, AC-021, AC-023
  - Depends on: T-010, T-012, T-014, T-024
  - State: complete
  - Disposition: complete — hosted-versus-modeled boundary recorded with local model evidence.
  - Authorization: local report/model edits and read-only inspection of approved hosted usage reports; no billing-plan, provider-limit, schema, or deployment change
  - Scope: Supabase billed egress actuals, application/query byte proxies, R2 Class A/B operations and storage, provider token/quota usage, contributor-pool size and eligibility, verified quota domains, reservation wait, separate translation-provider RPS and reader HTTP RPS, compute/observability exclusions, per-request/chapter/DAU-equivalent/day projections, source timestamps, units, price/quota sources, cache state, and uncertainty
  - Verification: `tools\capacity\report_cost_envelope.ps1 --input artifacts/capacity --output artifacts/capacity/cost-envelope.json` or `tools\pytest.ps1 backend/tests/test_capacity_cost_model.py -q`
  - Expected: The report separates actuals from estimates, preserves unavailable fields with reasons, identifies every source and timestamp, and never turns a modeled projection into a billing or capacity claim.
  - Attempts: 1
  - Last result: passed; `tools\pytest.ps1 backend/tests/test_capacity_cost_model.py -q -s` exited 0 with 3 passed in 3.01s. The model preserves unavailable hosted fields, local proxies, explicit unapproved stage projections, source timestamps, and separate reader/provider rate domains.
  - Evidence: `artifacts/capacity/pac-8a109a5ad1cd-cost-envelope.md`; actual-versus-estimate boundary, local proxy units, contributor quota-domain uncertainty, 1k/10k/100k projections, and no-capacity-claim guards are recorded.

- [x] T-016 Execute a bounded one-to-three-chapter source canary only after the implementation gate.
  - Maps to: REQ-006, REQ-007, REQ-019, REQ-022, REQ-024, REQ-026, AC-005, AC-008, AC-016, AC-021, AC-023
  - Depends on: T-014, T-015, T-022, T-024
  - State: complete
  - Disposition: complete — bounded live provider/R2 pass with explicit stop limits.
  - Authorization: separate project-owner live approval for application-service activity creation and provider/R2 use; original full queues remain paused
  - Scope: the three existing source identities, one source at a time, fixed provider/chapter concurrency, short stop window, activity/lease transitions, artifact readback, provider/project and contributor-pool budget, quota-domain assumption, reservation/ledger evidence, separate translation-provider RPS, and before/after Supabase/R2 evidence
  - Verification: `tools\pytest.ps1 backend/tests/test_checkpoint_resume.py backend/tests/test_job_worker_service.py -q`
  - Expected: Each selected sample records a truthful terminal result or a quantified blocker, preserves identity/URL/public state, and stops on any unapproved resource/provider/integrity threshold without manual row/runtime edits.
  - Attempts: 1
  - Last result: passed; one existing Kakuyomu chapter-1 activity completed through the application service with one provider slot, one attempt, and a 90-second provider deadline. The sanitized usage ledger recorded one successful Gemini request and 4,985 total tokens; direct raw and translated R2 artifact readback passed. The original worker/full queue remained stopped and no pending/running activity remained afterward.
  - Evidence: `artifacts/capacity/pac-8a109a5ad1cd-live-canary-gate.md`; the selected source identity, terminal activity state, provider ledger, PostgreSQL counter interval, and exact R2 readback are recorded without secrets.

- [x] T-021 Measure and, only when justified, compact disposable checkpoint envelopes.
  - Maps to: REQ-006, REQ-010, REQ-023, AC-005, AC-020
  - Depends on: T-009, T-014
  - State: complete
  - Disposition: complete — checkpoint retention decision recorded from the measured footprint.
  - Authorization: local implementation and isolated recovery-test edits; any live runtime migration or checkpoint rewrite requires separate project-owner approval
  - Scope: serialized/compressed checkpoint bytes, raw/translated/state duplication, reference bytes, write/rewrite counts, recovery reads, retention footprint, versioned reference-only envelopes, old-envelope handling, and proof that canonical content remains in PostgreSQL/R2
  - Verification: `tools\pytest.ps1 backend/tests/test_checkpoint_manager.py backend/tests/test_translation_resume_contract.py -q`
  - Expected: The measurement produces a no-op recommendation when compaction is not justified or safe; otherwise the application service can write/read the compact versioned envelope, resolve exact references, recover across restart, and preserve old envelopes without manual file edits.
  - Attempts: 1
  - Last result: passed; checkpoint/resume contract exited 0 with 12 passed in 5.23s. The isolated footprint test passed 1/1 and measured the current 38,746-byte serialized copy envelope, 514-byte reference-only candidate, successful restore, one recovery read, and zero canonical writes. No compaction was enabled because no operator-approved threshold or migration gate exists.
  - Evidence: `artifacts/capacity/pac-8a109a5ad1cd-checkpoint-footprint.md`; serialized/compressed/component/reference bytes, write/rewrite/read counts, retention sample, restore compatibility, and the no-op decision are recorded.

- [x] T-023 Add public reader correctness and isolation assertions to the capacity harness.
  - Maps to: REQ-009, REQ-013, REQ-014, REQ-025, AC-022
  - Depends on: T-014, T-015
  - State: complete
  - Authorization: local fixture/test edits; hosted staging route checks require a separate operator gate and must not mutate canonical content
  - Scope: published catalog/detail/chapter 200 responses, exact active R2 artifact identity, unpublished/unavailable/adult/takedown/missing-artifact policy, cache hit/miss and conditional response behavior, caller cancellation, malformed/stale reference failures, and redacted hash/shape/status evidence
  - Verification: `tools\pytest.ps1 backend/tests/test_public_reader_availability.py backend/tests/test_public_router.py backend/tests/test_capacity_harness.py -q`
  - Expected: A latency-passing sample still fails when status, body shape, active-artifact, cache, publication, or isolation behavior is wrong; reports never contain raw public content.
  - Attempts: 1
  - Last result: passed; the exact public availability/router/harness command exited 0 with 158 passed in 37.01s. Harness Ruff and Pyright also exited 0.
  - Evidence: `artifacts/capacity/pac-8a109a5ad1cd-public-reader-correctness.md`; published/blocked/takedown/adult/missing-artifact policy cases, cache modes, cancellation, reference rejection, body redaction, and explicit conditional-response unavailability are recorded.

- [x] T-017 Run the 1k DAU-equivalent reader stage with an approved traffic model.
  - Maps to: REQ-013, REQ-014, REQ-015, REQ-021, REQ-024, REQ-025, AC-013, AC-014, AC-017, AC-021, AC-022
  - Depends on: T-014, T-016, T-022, T-023
  - State: complete
  - Disposition: complete — private-staging run stopped on quantified SLO and telemetry gates.
  - Authorization: project-owner/operator approval for the target staging/hosted reader environment; no translation-queue restart
  - Scope: approved request/session model, cache state, catalog/detail/chapter mix, p95/p99, error budget, DB/pool/egress/R2/CPU/memory metrics, reader HTTP RPS, and reader/worker/provider isolation; contributor credentials and provider calls remain outside this reader profile
  - Verification: `tools\capacity\run_reader_load.ps1 -Profile 1000 -BaseUrl <private-staging-origin> -ReportDir artifacts/capacity/1000`
  - Expected: The stage reaches all declared gates or stops with a quantified blocker; missing hosted telemetry is recorded as unavailable and cannot produce a pass.
  - Attempts: 1
  - Last result: completed with quantified blocker; 50 samples per route at concurrency 8 returned non-empty HTTP 200 content responses with zero timeouts and zero transport errors, but catalog/detail/chapter/search/liveness p95 exceeded the declared budgets. The worker-stopped readiness 503 was expected. Provider-side R2 operation and billed-byte counters were explicitly unavailable to the runner, so no capacity pass was declared.
  - Evidence: `artifacts/capacity/pac-8a109a5ad1cd-reader-stage-1000.md` and the sanitized JSON report under `artifacts/capacity/1000/`.

- [x] T-018 Run the 10k and 100k DAU-equivalent stages only after the prior stage passes.
  - Maps to: REQ-013, REQ-014, REQ-015, REQ-018, REQ-021, REQ-024, AC-015, AC-017, AC-021
  - Depends on: T-017, T-022
  - State: complete
  - Disposition: complete — dependency safety stop recorded after T-017 did not pass its entry gates.
  - Authorization: separate operator approval for each stage, provisioned capacity, spend/egress stop gates, and rollback owner
  - Scope: staged traffic increase, connection/pool arithmetic, CDN/cache behavior, origin request rate, R2 exact reads, worker admission isolation, and provider/database budget independence
  - Verification: Review the T-017 stage result and record the required no-admission decision; do not send higher-stage traffic until the prior stage passes.
  - Expected: Each stage is run only when its entry gate is satisfied and is reported as pass, blocked, unavailable, or deferred with evidence; no synthetic result is called a production guarantee.
  - Attempts: 1
  - Last result: completed dependency stop; the 1k stage failed its declared SLO and provider-side telemetry gate, so neither higher stage was admitted. No worker, provider, R2, or canonical-content operation was performed for 10k/100k.
  - Evidence: `artifacts/capacity/pac-8a109a5ad1cd-reader-stages-10000-100000.md`; the staged sequence and safety decision are recorded.

## Documentation and Final Gates

- [x] T-019 Synchronize canonical documentation and operator procedures.
  - Maps to: REQ-017, REQ-020, REQ-021, REQ-026, AC-018, AC-020, AC-021, AC-022, AC-023
  - Depends on: T-012, T-013, T-016, T-017, T-018, T-021, T-022, T-023, T-024
  - State: complete
  - Authorization: project-owner-approved documentation edits within affected canonical Markdown
  - Scope: `docs/ARCHITECTURE.md`, `docs/CONFIGURATION.md`, `docs/OPERATIONS.md`, `docs/TRANSLATION.md`, performance docs, `docs/WORK.md`, `docs/HISTORY.md`, the R2 plan, and any directly affected design brief
  - Verification: Run `git diff --check`, then `rg -n "async|event loop|capacity|egress|pool|R2|unavailable|deferred|rollback" docs/ARCHITECTURE.md docs/CONFIGURATION.md docs/OPERATIONS.md docs/TRANSLATION.md docs/PERFORMANCE_AUDIT.md docs/PERFORMANCE_ACTION_PLAN.md docs/WORK.md docs/HISTORY.md "docs/R2-Only Content Storage Rearchitecture-plan.md"`, then `graphify update . --no-cluster`.
  - Expected: Documentation agrees with code and evidence, distinguishes completed/partial/unavailable/operator-owned states, and does not claim full-queue or 100k-user success without the required stage evidence.
  - Attempts: 1
  - Last result: `git diff --check` exit 0, required documentation scan exit 0, and `graphify update . --no-cluster` exit 0; documentation records the completed implementation decisions, measured boundaries, operator-owned gates, and safety stops without unsupported capacity claims.
  - Evidence: `artifacts/capacity/pac-8a109a5ad1cd-documentation-sync.md`

- [x] T-020 Run final validation, independent review, and handoff.
  - Maps to: REQ-018, REQ-020, REQ-021, REQ-026, AC-003, AC-008, AC-012, AC-019, AC-020, AC-021, AC-022, AC-023
  - Depends on: T-003, T-005, T-006, T-007, T-008, T-009, T-010, T-011, T-012, T-013, T-014, T-015, T-016, T-017, T-018, T-019, T-021, T-022, T-023, T-024
  - State: complete
  - Authorization: local verification; remote merge/push/deploy remains out of scope unless separately authorized
  - Scope: focused backend tests, full backend suite where justified, Ruff, Pyright, frontend impact check, architecture guards, Compose validation, Markdown link/route audit, Graphify, diff review, git state, and final risk/rollback report
  - Verification: Run `tools\pytest.ps1 backend/tests/test_translation_async_boundary.py backend/tests/test_pipeline_timing_audit.py backend/tests/test_activity_database.py backend/tests/test_job_worker_service.py backend/tests/test_checkpoint_resume.py -q`, then `tools\ruff.ps1 check .`, `tools\pyright.ps1`, `git diff --check`, and `graphify update . --no-cluster`.
  - Expected: Required checks have exact exit codes/counts recorded, no unrelated worktree change is staged or discarded, Graphify refresh is reported, and unresolved risks or unavailable hosted gates remain explicit.
  - Attempts: 1
  - Last result: Full backend suite exit 0 with 2,944 passed and 16 skipped in 762.96 seconds; focused backend suite exit 0 with 50 passed; Ruff, Pyright, frontend typecheck, Compose, architecture guards, Markdown link audit, route tests, and diff checks passed. The E2E compatibility regression found during review was fixed and its five tests passed. The bounded provider/R2 canary completed, the 1k reader stage executed with a quantified SLO stop, and the 10k/100k dependency safety decision was recorded. Final `graphify update . --no-cluster` exited 0 and rebuilt the current graph. Hosted billing and production-capacity claims remain outside the evidence boundary.
  - Evidence: `artifacts/capacity/pac-8a109a5ad1cd-final-validation.md`

## Execution Stop Conditions

Stop the execution loop and report the blocker if any of the following occurs:

- the async boundary would require sharing a live session, ORM object, secret,
  or provider response across components;
- a schema/index/pooler/provider-plan change is required without separate
  approval;
- a live canary or load stage lacks an operator-approved threshold, target,
  rollback owner, or trustworthy telemetry;
- a test writes outside the isolated R2 prefix or canonical data changes
  unexpectedly;
- a lease, artifact hash, active reference, publication state, or source
  identity becomes inconsistent;
- Supabase egress, provider quota, R2 operation rate, memory, CPU, event-loop
  lag, or connection use crosses the approved stop gate;
- the required load harness or hosted metric is unavailable. Mark that stage
  unavailable rather than substituting an unmeasured claim.

## Continuation evidence — 2026-08-24

The R2 environment synchronization closed the isolated integration gate:
`tools\pytest.ps1 backend/tests/integration/test_s3_integration.py
backend/tests/integration/test_r2_backup_integration.py -q` passed 7 tests
with the root environment and passed 7 tests sequentially with `deploy/.env`.

The rebuilt backend created an encrypted PostgreSQL backup in the independent
R2 target and restored it into the healthy isolated `restore-db` database
using the persisted `DATABASE_BACKUP_URL`. Sanitized verification reported
`backup_status=succeeded`, `restore_status=succeeded`, `public_tables=37`, and
`invalid_constraints=0`. The latest independent R2 snapshot was also read
back and checksum-verified: 980 objects and 4,022,175 bytes.

Evidence: `artifacts/capacity/pac-8a109a5ad1cd-recovery-evidence.md`.
The bounded provider canary and private-staging 1k reader run are now
complete with their measured outcomes. The original full translation queues
remain stopped, and the 10k/100k reader decisions correctly stopped at the
failed 1k entry gate; no unmeasured production pass is inferred.
