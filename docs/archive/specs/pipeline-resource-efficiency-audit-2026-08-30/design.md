# Pipeline Runtime, Supabase, and R2 Efficiency Audit Design

Spec ID: pipeline-resource-efficiency-audit
Version: 0.2.0
Status: Complete
Updated: 2026-08-23

## Source and Current State

### Governing References

- `AGENTS.md` and the project instructions under the repository root.
- `docs/ARCHITECTURE.md` for dependency direction, storage boundaries, worker
  leases, R2-only content, and secret handling.
- `docs/PERFORMANCE_AUDIT.md` and `docs/PERFORMANCE_ACTION_PLAN.md` for prior
  findings, budgets, historical evidence, and open production gates.
- `docs/TRANSLATION.md`, `docs/CONFIGURATION.md`, and `docs/OPERATIONS.md` for
  provider, configuration, database, worker, and R2 operating contracts.
- `docs/R2-Only Content Storage Rearchitecture-plan.md` for the current PR113
  checkpoint, bucket names, three novel identities, and completion boundaries.
- Existing approved `.agents/specs/workspace-and-quality-hardening/` remains a
  separate workspace-quality contract and is not replaced by this audit.

### Current Behavior

The worker executes durable activities through `ActivityWorkerService`, the
database-backed activity implementation, and the runner's polling and lease
logic. Translation is staged through fetch, parse, segmentation, translation,
QA, cache flush, and post-processing components. `TranslateStage` controls
chunk concurrency and provider calls, while orchestration loads novel,
chapter, and glossary state. The R2 implementation already records operation
timings and the catalog layer contains selective ORM projections in several
read paths. Database activity claims and lease renewal also have optimized
paths that must be verified rather than assumed complete.

The relevant risk is cross-layer repetition: one bulk job can multiply large
ORM row hydration, novel/glossary reads, activity polling, provider retries,
R2 transfers, and transaction updates. A single source of truth for the audit
is therefore required so an optimization is not credited twice or measured
against a different workload.

The worker is currently required to remain stopped. Supabase billing-window
egress, cumulative PostgreSQL counters, R2 operation statistics, and provider
timing are different evidence sources and must not be conflated. The audit
must preserve this distinction.

## Proposed Behavior

### Phase A: Baseline and safety gate

1. Confirm the worker is stopped and capture the Compose service topology.
2. Record a sanitized configuration-key inventory and the two project bucket
   names without reading values into evidence.
3. Capture the current Supabase billing-cycle egress view plus a fresh bounded
   UTC before/after workload window, current activity/queue snapshot, provider
   availability, database route, pool settings, and existing metric counters.
4. Do not start the worker, write R2 objects, mutate PostgreSQL rows, or change
   `.env` values until the baseline is reviewed and the canary thresholds are
   recorded.

### Phase B: Timing and operation instrumentation

Use fixed, bounded stage and operation names. Reuse existing R2 operation
statistics, provider timing, activity timing, and application metrics where
they cover the needed fields. Add a small timing boundary only when a stage
has no trustworthy measurement.

Each observation carries only sanitized correlation fields:

```text
audit_run_id, activity_id, job_id, novel_id, chapter_id,
stage, operation, provider_key, provider_model, outcome, error_code,
duration_ms, retry_count, input_bytes, compressed_bytes,
input_tokens, output_tokens, db_rows, r2_operation_count
```

The `audit_run_id` and identifiers are evidence correlation values, not a
license to log prompts, source URLs, chapter text, authorization headers,
provider responses, credentials, or IP addresses. Percentiles are calculated
only when the sample count is stated. A stage that cannot be measured is
reported as unavailable with its reason.

The timing boundaries are:

```text
source fetch -> parse/raw normalization -> novel metadata/glossary
-> chapter selection/segmentation -> provider request/retry
-> QA -> translation persistence/cache flush -> R2 transfer
-> PostgreSQL transaction/activity state update
```

The report must also separate provider wait time, local CPU/event-loop wait,
database checkout/statement/commit time, R2 network time, retry delay, and
queue wait where the current instrumentation permits it.

### Phase C: Supabase/PostgreSQL audit

Take a read-only before/after snapshot around one controlled workload. Review
SQLAlchemy call sites and generated SQL for:

- full `Novel` and `Chapter` hydration of large JSON columns;
- repeated novel, glossary, chapter, and activity reads within a job;
- claim and lease queries that scan or hydrate more rows than needed;
- transaction duration, pool checkout wait, connection count, and idle
  transactions;
- direct PostgreSQL versus Supavisor/pooler route, without exposing hostnames
  or connection strings;
- query plans and index use for the highest-impact state lookups.

Use the PostgreSQL `pg_stat_statements` extension and its view when the target
project permits access. Supabase documents this extension as a query-statistics
source available in its database environment. If privileges prevent access,
use the dashboard or sanitized application instrumentation and record the
limitation. Label all counters as cumulative or interval-specific. Use the
Supabase Reports egress view for billing-period attribution. Use representative
`EXPLAIN (ANALYZE, BUFFERS)` only where the target permits it and record the
query shape, plan summary, and sanitized timing rather than row contents.

### Phase D: R2 audit

Review `R2Storage` operation accounting and storage call sites. Group results
by operation, stage, workload, and object class. Compare logical payload size,
compressed transfer size, content hash reuse, duplicate PUT/GET/HEAD activity,
and list operations.

Any integration write uses a generated isolated prefix and a verified cleanup
scope. The authorized test contract requires deletion after each test and a
final paginated zero-object sweep before completion. Production novel prefixes
are never used. Reader and translation hot paths must use exact keys; prefix
listing remains reserved for inventory, migration, backup, garbage-collection,
and the isolated audit cleanup sweep.

### Phase E: Optimization selection and implementation

Prioritize in this order:

1. egress and cost reduction;
2. latency and queue-throughput improvement;
3. implementation effort and operational complexity.

The first candidates are:

- selective `load_only()` or `defer()` projections for state-only reads;
- one in-memory novel/glossary/chapter cache per bounded job where the
  lifecycle and invalidation rules permit it;
- atomic `UPDATE ... RETURNING` activity claims with existing lease guards;
- exponential idle polling backoff without delaying lease renewal;
- timestamp-only heartbeat updates that preserve ownership checks;
- exact-key R2 reads and immutable-hash reuse instead of redundant transfer;
- measured concurrency, batch, timeout, pool, and polling configuration changes.

No candidate is accepted merely because it is listed here. Each must identify
the consumer fields, preserve state-transition semantics, and add a regression
test or an observable query/operation-budget check.

### Phase F: Controlled canary

After code and configuration checks pass, rebuild the worker image while it is
still stopped. Use these conservative stop rules: stop immediately for an
integrity failure, unauthorized mutation, R2 hot-path `LIST`, provider quota or
authentication failure, or database failure. Stop when any tracked resource
rate exceeds twice the pre-canary baseline across two five-minute observations.
Then process the three provided URLs one at a time or under the explicitly
recorded bounded concurrency. The application services own crawl, translation,
persistence, and activity transitions. The operator must not hand-edit
PostgreSQL rows or runtime JSON to manufacture terminal success.

At each novel boundary, capture identity/URL preservation, activity outcome,
chapter counts, provider errors, database/R2 counters, and egress observations.
Stop immediately on a threshold breach, unexpected writer, missing external
credential, or a data-integrity warning. A retryable or permanent chapter
failure is reported truthfully.

## Boundaries and Affected Components

### Components or Surfaces

- Translation stages, orchestration, glossary loading, and provider timing.
- Durable activity database, queue runner, worker lease, and polling logic.
- SQLAlchemy models, query helpers, database engine, and pool configuration.
- R2 client/backend, catalog exact-key reads, content-addressing, and operation
  statistics.
- Settings, Compose environment mappings, examples, operator documentation,
  focused tests, and sanitized audit artifacts.
- Supabase PostgreSQL reports and Cloudflare R2 account/bucket observations as
  external evidence sources.

### Allowed Changes

- Add or refine bounded timing/operation instrumentation in the named backend
  paths.
- Correct measured ORM projections, per-job caching, claim/heartbeat/polling
  behavior, and regression tests.
- Change `settings.py`, Compose mappings, and environment templates only when
  the audit supplies rationale and rollback values.
- Update affected Markdown and the R2 plan checkpoint.
- Use read-only Supabase/PostgreSQL inspection and generated isolated R2
  test-prefix operations with mandatory cleanup.

### Protected Changes

- No bucket reset or canonical object deletion.
- No backup restore drill or production recovery acceptance.
- No schema/index migration. Document missing-index findings for a separate
  approved migration.
- No raw secret or credential changes in this Draft stage.
- No hand edits to runtime JSON or PostgreSQL novel/activity state.
- No frontend, public API, provider-model, or legacy-compatibility expansion.

## Data Flow and Contracts

### Inputs and outputs

Inputs are the three existing source URLs, a bounded activity workload, code
and configuration state, the current Supabase billing-cycle egress view plus a
fresh bounded UTC before/after window, sanitized database statistics/query plans, existing
R2 operation statistics, and provider/runtime telemetry. Outputs are a
sanitized audit report, a ranked action table, tested local changes where
justified, configuration diffs with rollback values, and synchronized
documentation.

### API or event contracts

No new public API is required. Existing durable activity status and application
service boundaries remain authoritative for the canary. No client-supplied
identity or manual status mutation is introduced.

### Models or schemas

No schema change is part of the Draft design. If the audit demonstrates a
missing index or schema-level defect, it becomes a separately approved
migration task with its own lock, rollback, and validation evidence.

### Configuration

Existing controls are the primary surface, including translation concurrency
and chunking, provider limits and deadlines, worker polling and leases, DB pool
size/overflow/timeouts, R2 bucket/endpoint/operation settings, and runtime
feature flags. Actual secret-bearing `.env` values remain operator-managed.

### Persistence and migration behavior

Normal application services and existing migrations remain authoritative.
Instrumentation must not persist prompts, provider responses, raw credentials,
or arbitrary chapter text. No migration is created by this Draft.

### Compatibility with existing clients or data

Existing novel IDs, public URLs, R2 object identity, activity states, lease
guards, translation lineage, and current-only R2 storage behavior remain
compatible. Filesystem content compatibility is not restored.

## States and Transitions

```text
worker stopped
  --baseline and fixes verified--> rebuilt worker stopped
  --thresholds approved--> one-novel canary
  --safe terminal boundary--> next-novel canary
  --threshold breach or integrity warning--> worker stopped and incident evidence preserved
```

The worker cannot transition to the canary state while projections, claim,
heartbeat, and polling checks are unverified. A failed chapter may remain
failed with structured evidence; the process must not rewrite it to complete.
The canary is idempotent only through existing activity idempotency, content
addressing, lease, and activation contracts.

## Failure Handling and Invariants

- Provider timeout, quota, or invalid-key failure:
  - Detection: structured provider error and timing record.
  - Operator-visible behavior: activity remains truthful and the canary stops
    when the approved threshold or credential gate is reached.
  - Recovery or retry: use existing bounded retry and scheduler contracts; do
    not add an unbounded retry loop.
- Database pool exhaustion, slow query, or SSL/network failure:
  - Detection: query/checkout/commit timing and structured activity error.
  - Operator-visible behavior: pause the worker and preserve the evidence.
  - Recovery or retry: use existing lease recovery/application services; no
    direct row edits.
- R2 timeout, checksum mismatch, or unexpected list:
  - Detection: operation statistics, exact-key validation, and checksum/error
    records.
  - Operator-visible behavior: fail closed for activation and stop the canary.
  - Recovery or retry: use existing bounded storage retry and grace-period GC
    contracts without deleting canonical content.
- Security or privacy invariant: evidence contains no secrets, prompts,
  provider responses, raw viewer tokens, IP addresses, or arbitrary content.
- Data-integrity invariant: PostgreSQL references and existing novel identities
  remain authoritative; immutable R2 objects are not replaced in place.
- Cost invariant: Supabase billing egress attribution comes from the provider
  report, while application counters are labeled as supporting evidence.

## Rollout, Rollback, and Operations

- Rollout order: baseline, instrumentation, focused checks, measured code
  corrections, configuration review, worker image rebuild, one-novel canary,
  remaining novels, final documentation and evidence audit.
- Feature flag or compatibility window: use existing worker/configuration
  controls; do not add a legacy filesystem compatibility window.
- Rollback trigger and procedure: stop the worker, restore the last approved
  local configuration/code revision, preserve evidence, and verify the worker
  remains stopped. Do not reset buckets or mutate canonical data as rollback.
- Monitoring and evidence: Supabase Reports for billing egress, PostgreSQL
  query/pool observations, existing provider/R2/application metrics, activity
  status, and sanitized per-stage reports.
- Manual operator steps: provide missing external values and authorize the
  controlled worker resume after the local verification gate. Isolated R2
  test writes are already authorized by this specification and must be
  cleaned up after each test and at final completion.

## Verification Strategy

- Unit or component coverage: timing boundaries, projection fields, cache
  reuse/invalidation, activity claim/lease/heartbeat/polling, R2 operation
  accounting, redaction, and configuration validation.
- Integration or contract coverage: representative PostgreSQL query shapes,
  pool/transaction behavior, isolated R2 prefix operations, compression,
  checksums, pagination, and no-hot-list assertions.
- End-to-end or UI coverage: application-service canary for the three URLs,
  public catalog/detail/chapter identity and URL checks, and truthful activity
  terminal state. No frontend implementation is required by this spec.
- Performance, security, or operator checks: stage percentiles, operation
  counts, query plans, Supabase billing-window evidence, bounded labels,
  redaction, worker stop/resume gate, and provider/R2 availability.
- Documentation or artifact checks: Markdown link audit, active-document
  contradiction scan, R2 plan checkbox evidence, configuration matrix, and
  ranked recommendation report.

## Traceability

| Requirement | Acceptance criterion | Planned task(s) | Verification |
| --- | --- | --- | --- |
| REQ-001 | AC-001 | T-001 | Sanitized baseline and stopped-worker observation |
| REQ-002 | AC-002 | T-002 | Stage timing report with sample provenance |
| REQ-003 | AC-003 | T-003, T-010 | Worker source review, regression checks, and canary observation |
| REQ-004 | AC-004 | T-004 | Sanitized query, pool, plan, and Supabase report evidence |
| REQ-005 | AC-005 | T-005 | R2 operation report and isolated-prefix/source checks |
| REQ-006 | AC-006 | T-006, T-007 | Prioritization, focused diff, and state-transition tests |
| REQ-007 | AC-007 | T-008 | Configuration matrix and controlled validation |
| REQ-008 | AC-008 | T-002, T-009 | Bounded metric schema and redaction tests |
| REQ-009 | AC-009 | T-009, T-012 | Exact command results and isolated integration evidence |
| REQ-010 | AC-010 | T-011, T-012 | Final Markdown and plan audit |
| REQ-011 | AC-011 | T-010 | Application-service three-novel canary evidence |
| REQ-012 | AC-001, AC-005, AC-007, AC-008, AC-009, AC-011 | T-001, T-005, T-008, T-009, T-010 | Protected-surface and stop-gate review |
| REQ-013 | AC-001, AC-002, AC-004, AC-005, AC-010 | T-001, T-002, T-004, T-005, T-011 | Evidence provenance and documentation review |
