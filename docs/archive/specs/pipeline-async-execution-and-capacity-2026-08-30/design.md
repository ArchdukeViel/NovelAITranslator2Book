# Pipeline Async Execution and Capacity Hardening Design

Spec ID: pipeline-async-execution-and-capacity
Version: 0.3.0
Status: Complete
Updated: 2026-08-24

## Source of Truth Mapping

- Primary architecture: `AGENTS.md` and `docs/ARCHITECTURE.md`.
- Active requirements: `.agents/specs/pipeline-async-execution-and-capacity/requirements.md`.
- Translation contract: `docs/TRANSLATION.md`.
- Operational and configuration contracts: `docs/OPERATIONS.md` and
  `docs/CONFIGURATION.md`.
- Existing evidence and deferred gates: `docs/PERFORMANCE_AUDIT.md`,
  `docs/PERFORMANCE_ACTION_PLAN.md`, and
  `docs/R2-Only Content Storage Rearchitecture-plan.md`.
- Supabase operational references: [egress usage](https://supabase.com/docs/guides/platform/manage-your-usage/egress),
  [connection pooling](https://supabase.com/docs/guides/database/connecting-to-postgres),
  and the project's `pg_stat_statements` view.
- Cloudflare R2 operational references: [pricing](https://developers.cloudflare.com/r2/pricing/)
  and [S3 API compatibility](https://developers.cloudflare.com/r2/api/s3/api/).

Architecture documentation wins if it conflicts with this design. This design
does not authorize a schema migration, a production queue restart, a bucket
cutover, or a provider-plan change.

## Current Evidence and Assumptions

The previous audit has already implemented narrow ORM projections, atomic
activity claims, idle polling backoff, timestamp-only heartbeats, bounded
invocation caching, and R2 bucket `HEAD` readiness. The new work MUST not
reimplement those changes or claim their production byte impact without a new
fixed interval.

The current asynchronous risk is visible in the orchestration path:

- `translate_chapters()` creates a chapter semaphore and gathers chapter
  coroutines.
- `_run_chapter()` performs synchronous chapter-cache/R2 reads, state writes,
  checkpoint operations, catalog projection refreshes, translation-version
  persistence, and database state updates around awaited provider work.
- `session_scope()` owns synchronous SQLAlchemy transactions, while storage
  services may combine R2 operations with PostgreSQL projection updates.
- Worker lease renewal is independent, which limits lease starvation but does
  not make the event loop or database pool efficient.
- The R2 rearchitecture plan still has an open checkpoint-footprint gate:
  current disposable checkpoints can duplicate raw, translated, and state
  payloads. This is a runtime-footprint and recovery concern, not permission
  to make local files canonical.
- The current performance plan also leaves hosted cost attribution and public
  translated-chapter read acceptance separate from local latency evidence.

The current production-shaped route is Supabase Session Pooler on port 5432,
with application-side SQLAlchemy pool settings controlled separately by
`DB_CONNECTION_MODE` and the pool settings. The implementation MUST treat the
endpoint route, application pool, and deployment-wide budget as separate
dimensions.

## System Architecture

### Existing logical flow

```text
ActivityDatabaseBackend.claim_next_activity
        -> ActivityWorkerService.run_claimed_activity
        -> NovelOrchestrationService.translate_chapters
        -> chapter semaphore / asyncio.gather
        -> fetch, parse, segment, provider, QA, lineage
        -> StorageService + R2 + PostgreSQL state/projection writes
        -> activity terminal state and checkpoint
```

### Target flow

```text
Activity claim (short DB transaction)
        |
        v
Async coordinator -- bounded provider semaphore --> provider adapter
        |                         |
        |                         +--> provider usage / retry telemetry
        |
        +--> immutable ChapterWorkItem / plain DTOs
                  |
                  v
       bounded persistence and storage executor
          |                         |
          |                         +--> exact-key R2 HEAD/GET/PUT
          +--> per-operation DB session/transaction
                  |
                  v
       terminal lineage + active reference + checkpoint
                  |
                  v
       activity state / lease result (short DB transaction)
```

The async coordinator owns scheduling and cancellation. The provider adapter
owns provider network waits. The persistence/storage boundary owns blocking
database, R2 SDK, serialization, and runtime-file operations. No component
holds a database connection while another component waits on a provider,
retry timer, R2 network request, or CPU-heavy QA operation.

### Component responsibilities

| Component | Owns | Must not own |
| --- | --- | --- |
| `ActivityDatabaseBackend` | Claim, lease, cancellation, terminal activity transactions | Provider calls or chapter artifact bodies |
| `ActivityWorkerService` | Activity lifecycle, bounded admission, shutdown, truthful status | Cross-thread ORM/session reuse |
| `translate_chapters()` coordinator | Plain work-item scheduling and result aggregation | Direct unbounded synchronous DB/R2 calls |
| Provider adapter/stage | Async provider call, retry, response validation, token usage | Database transactions or R2 artifact activation |
| Persistence adapter | Per-operation session, projection/state writes, terminal lineage | Provider waits or request scheduling policy |
| R2 storage adapter | Exact-key object operations, hashes, compression, operation counters | Database identity or public routing |
| Reader API | Compact PostgreSQL projection reads and exact active R2 reads | Translation-worker admission or content enumeration |
| Load harness | Synthetic traffic and isolated fixtures | Canonical data mutation or production queue repair |

## Async Boundary Decision

### Options

| Option | Description | Benefits | Risks | Decision |
| --- | --- | --- | --- | --- |
| A | Convert SQLAlchemy and R2 facades to fully async-native adapters | Lowest event-loop blocking after completion | Broad rewrite, transaction semantic drift, async driver/client compatibility, large review surface | Long-term option; not the first slice |
| B | Add a bounded synchronous I/O boundary with per-operation sessions and plain DTOs | Small reversible change, preserves current SQLAlchemy/S3 behavior, isolates blocking work | Thread/executor capacity must be bounded and instrumented; some serialization remains synchronous | Recommended first slice |
| C | Serialize all chapter persistence on the event loop | Simple ordering and low concurrency risk | Keeps blocking I/O on the event loop, poor throughput, does not solve the root problem | Rejected |

### Recommended implementation

Implement an explicit `TranslationPersistencePort` or equivalent service
facade with an async-facing API and a bounded synchronous implementation. The
implementation may use a dedicated `ThreadPoolExecutor` or a bounded
`asyncio.to_thread` wrapper only if all of the following are true:

1. The callable receives immutable scalar/DTO input, never a live ORM object,
   SQLAlchemy `Session`, transaction, or lazy relationship.
2. The callable creates or acquires its session inside the worker boundary,
   performs one short operation or transaction, commits/rolls back, and closes
   before returning.
3. A storage client is either proven safe for the selected concurrency or is
   created/owned within the same boundary. The design must not assume that a
   test double's thread safety proves the production client's thread safety.
4. The executor has a fixed upper bound, a bounded queue, cancellation rules,
   queue-wait telemetry, and a shutdown drain/timeout policy.
5. Provider calls and QA do not occupy an executor slot or database connection
   while waiting for unrelated work.
6. The result is a plain immutable DTO containing only the fields the caller
   needs; a returned ORM object is forbidden.

The first implementation slice should move the highest-volume read and write
boundaries separately. It should not wrap the entire `_run_chapter()` method in
one thread: doing so would hide provider concurrency, make cancellation
untruthful, and prevent stage-level resource attribution.

### Operation classes

| Class | Examples | Boundary policy |
| --- | --- | --- |
| `DB_READ_SCALAR` | Novel id, glossary revision, chapter state, active reference | Narrow projection, short per-operation session, DTO result |
| `DB_READ_BUNDLE` | One invocation metadata/glossary/raw reference bundle | Explicit bounded batch, no history/media/version hydration unless required |
| `DB_WRITE_PROGRESS` | Non-terminal chapter state, event, chunk progress | Coalescible bounded queue; drop/replay policy documented |
| `DB_WRITE_TERMINAL` | Translation version, active reference, lineage, final state | One atomic transaction; never dropped or reordered |
| `R2_EXACT_READ` | Raw/translation/media object by exact key | Exact key, operation counter, bounded timeout |
| `R2_IMMUTABLE_WRITE` | New raw/translation/media object | Hash-addressed idempotent write; no overwrite |
| `RUNTIME_CHECKPOINT` | Checkpoint/state JSON under disposable runtime root | Executor-bound file operation and inter-process lock as required |

## Data Contracts and Schemas

### Immutable work item

The coordinator passes a plain data object such as:

```python
ChapterWorkItem(
    novel_id: str,
    chapter_id: str,
    sequence_number: int | None,
    source_text_hash: str,
    source_structure_hash: str | None,
    source_image_manifest_hash: str | None,
    raw_artifact_key: str | None,
    translation_contract: TranslationContract,
    activity_id: str | None,
    job_id: str | None,
)
```

The actual implementation may use existing project types. The contract is
that it contains canonical identifiers and hashes, not source text, secrets,
ORM instances, mutable sessions, or provider responses. Provider prompt text
may exist only in the provider call's local scope and must never enter a
telemetry DTO.

### Persistence command/result

```text
PersistenceCommand:
  operation_class: fixed enum
  novel_id / chapter_id / activity_id: canonical identifiers
  expected_version_or_hash: optional optimistic-concurrency guard
  artifact_references: exact R2 keys and hashes only
  scalar_state: bounded status/progress/error code fields
  idempotency_key: deterministic run/chapter/attempt key

PersistenceResult:
  outcome: committed | reused | skipped | conflict | retryable_failure | permanent_failure
  rows_affected: bounded integer
  db_duration_ms: numeric
  r2_operation_count: bounded integer
  bytes_written/read: numeric when available
  error_code: allowlisted code or unavailable
```

No command/result may contain full row serialization, prompt/response text,
raw URLs, credentials, authorization headers, or a complete provider error
payload.

### Stage observation

Use the existing pipeline timing event shape where possible and extend it only
with fixed fields:

```text
schema_version, audit_run_id, activity_id, job_id, novel_id, chapter_id,
stage, operation_class, outcome, duration_ms, queue_wait_ms, retry_count,
concurrency, input_bytes, compressed_bytes, rows, db_checkout_ms,
db_statement_ms, db_commit_ms, r2_operation_count, r2_bytes_read,
r2_bytes_written, input_tokens, output_tokens, translation_provider_rps,
reader_http_rps, credential_pool_size, eligible_credential_count,
quota_domain_count, credential_reservation_count, credential_pool_wait_ms,
event_loop_lag_ms, memory_bytes, error_code, unavailable_reason
```

Allowed stage values are `source_fetch`, `raw_normalize`,
`metadata_load`, `glossary_load`, `selection`, `segment`, `provider_wait`,
`qa`, `persistence`, `r2_read`, `r2_write`, `db_commit`,
`activity_state`, `checkpoint`, and `shutdown`. Labels are enums or bounded
identifiers. Percentiles MUST include count and interval; no percentile is
reported for a sample too small to support it.

## Transaction, Lease, and State Design

### Activity lifecycle

```text
pending
  -> claimed (short atomic claim transaction)
  -> running (lease owner established)
  -> paused       [operator/provider/resource gate]
  -> cancelling   [explicit cancellation]
  -> completed    [all terminal writes committed]
  -> failed       [truthful terminal failure]

running -> pending       [expired lease recovery, only through queue service]
running -> failed        [permanent provider/QA/data failure]
cancelling -> cancelled  [checkpoint and state persisted]
```

Chapter states remain separately durable. A chapter can be `fetching`,
`translating`, `translated_partial`, `needs_retry`, `qa_failed`,
`needs_review`, `complete`, or `failed` according to existing domain rules.
The new boundary must not collapse these states into a generic success/failure
flag.

### Required transaction rules

- Claim and lease ownership use the existing atomic/locked queue contract.
- Provider calls occur outside DB transactions.
- Progress/event writes may be coalesced only after a checkpoint/replay rule
  is specified and tested.
- Terminal translation version, source/translation hashes, active reference,
  lineage, and chapter state are committed atomically in the existing domain
  service boundary.
- A retry after a timeout is idempotent by chapter/run/attempt/hash. It may
  reuse an immutable object but may not overwrite it or create a second active
  reference for the same expected contract.
- Lease renewal failure stops admission of new work and returns a truthful
  retryable activity outcome; it must not continue unbounded provider work.
- Cancellation stops new provider/R2 work, drains or marks persistence
  commands according to their class, records a checkpoint, and releases every
  semaphore/executor slot.

## Resource Budgets and Backpressure

### Database connection arithmetic

The deployment budget is evaluated across all long-lived pool owners:

```text
max_long_lived_connections =
  sum(process_count_i * (pool_size_i + max_overflow_i))
  + migration/readiness/operator reserve
```

The worker's persistence executor limit MUST be no greater than the worker's
admitted database write slots, and the total across backend, reader, worker,
replicas, migration, readiness, and operator reserve MUST fit
`DB_CONNECTION_BUDGET`. `NullPool` or a pooler does not remove the need to
measure concurrent server-side usage.

### Provider and I/O admission

Admission is bounded by the minimum of:

```text
effective translation-provider capacity across eligible credentials
verified provider/project/global RPM/TPM/RPD and in-flight limits
credential/owner policy limits
translation chapter/chunk concurrency
DB persistence slots
R2 request slots and byte rate
process memory/CPU safety budget
operator-selected workload cap
```

The effective translation-provider capacity is calculated conservatively:

```text
effective_translation_capacity = min(
  eligible_credential_headroom_summed_only_by_verified_quota_domain,
  verified_provider_project_or_global_cap,
  worker_db_r2_process_and_cost_budgets,
)
```

If a credential's upstream quota domain is unknown, it is placed in the
conservative shared domain rather than treated as independent. The provider
project limit is authoritative for Gemini capacity. Adding keys from the same
project MUST NOT be treated as multiplying project quota. A reservation is
released on success, failure, cancellation, timeout, or process restart after
its TTL. For a measured token mix and provider latency, the observed provider
request rate is bounded by the lowest applicable dimension:

```text
translation_provider_rps <= min(
  aggregate_RPM / 60,
  aggregate_TPM / (tokens_per_request * 60),
  aggregate_in_flight / provider_p95_latency_seconds,
  sustainable_RPD / measurement_window_seconds,
  local_worker_db_r2_process_and_cost_caps,
)
```

The `RPD` term is a sustainability ceiling over the selected measurement
window, not permission to burst beyond RPM, TPM, or in-flight limits. The
report must use observed token distributions and latency intervals, not a
single optimistic average.

### Contributor credential pool and rate domains

The unified credential registry is the only source for owner- and
user-contributed Gemini keys. Pool selection requires an active, validated,
consented row with `contributor_pool_eligible=true`; revoked, paused, invalid,
or unhealthy rows are excluded immediately. Owner-only jobs use only rows with
`owner_job_eligible=true` and never consume contributor-pool capacity by
accident.

The scheduler reserves RPM, TPM, RPD, and in-flight capacity for the selected
credential before the provider call, then reconciles actual tokens, status,
retry, estimated cost, and release/expiry. Selection must be fair and bounded
across eligible credentials, avoid one credential or contributor monopolizing
the queue, and make a credential unavailable on invalid-key or quota failure
according to the existing provider state contract. The usage ledger records
credential ID, credential owner, requesting user, provider/model, request/job,
status, token usage, estimated cost, and timestamps; raw keys and provider
payloads never enter the ledger, metrics, logs, or responses.

There are two separate rate domains:

1. `translation_provider_rps`: outbound Gemini/provider admission, which may
   increase only when verified independent credential quota domains and all
   local/provider budgets permit it.
2. `reader_http_rps`: public catalog/detail/chapter traffic, governed by the
   reader process, CDN/cache, PostgreSQL projection, R2 exact reads, pool, and
   origin budgets. Contributor keys do not increase this rate.

Capacity reports and stop gates MUST keep these domains separate. A larger
contributor pool may reduce translation queue wait, but it cannot be used as
evidence that the public reader supports a higher HTTP request rate.

### Backpressure behavior

- The provider work queue and persistence queue are bounded.
- Queue-full behavior is explicit: wait with a deadline for critical work;
  reject/defer non-critical progress with a metric; never allocate an
  unbounded list of tasks.
- Admission order is deterministic enough to prevent starvation and does not
  hold a DB connection while waiting for another resource.
- Contributor-key selection is fair, bounded, and observable through aggregate
  pool size, eligible count, quota-domain count, reservation outcomes, and
  pool wait; credential identifiers are not high-cardinality metric labels.
- The worker exposes queue depth, queue wait, rejected/deferred count, and
  oldest item age.
- A stop gate fires on database-capacity errors, provider quota/auth failure,
  R2 error spikes, event-loop lag, memory growth, lease loss, or egress rate
  above the approved threshold.

## PostgreSQL and Supabase Design

### Query policy

- Keep `load_only()`/`defer()` on routine state/projection reads and add a
  regression test for every protected heavy column.
- Load novel metadata, approved glossary data, and raw references once per
  invocation only when invalidation/lifetime is explicit.
- Replace loops that repeatedly select the same novel/glossary/activity rows
  with one bounded batch or DTO cache. Do not introduce a process-global cache
  without a separate lifecycle contract.
- Use `pg_stat_statements` for calls, rows, total/mean execution, and shared
  block indicators. Use `EXPLAIN (FORMAT JSON)` or equivalent for
  representative shapes. Never export raw query text if it can include data.
- Treat Supabase's Shared Pooler Egress report as billing authority for the
  current route. Local counters and query rows are supporting evidence only.
- Review unused-index advisor notices but do not drop indexes or add a
  migration in this spec without a separate approval.

### DB instrumentation boundary

Instrumentation should measure checkout wait, statement duration, commit
duration, rows affected/returned, and transaction outcome at a sanitized
application boundary. If provider-side response bytes are unavailable, record
`unavailable_reason=provider_does_not_expose_query_bytes` rather than selecting
rows solely to estimate them.

## R2 Design

- PostgreSQL stores exact active keys and hashes; R2 stores immutable content.
- Reader and translation hot paths use exact-key reads and hash-addressed
  immutable writes. They never enumerate a prefix.
- `LIST` remains restricted to inventory, backup, GC, migration, and cleanup
  jobs. A static import guard and focused tests protect this rule.
- Compression and deduplication are measured as operation/payload metrics, not
  inferred from object count alone.
- Conditional reads may be introduced only when the active reference and
  client/cache semantics prove that a `304`/not-modified result is safe. A
  failed conditional request must not be treated as a missing artifact.
- Isolated R2 load tests use a unique non-canonical prefix and clean it via
  paginated listing/deletion after the test. The final zero-object sweep is
  part of the test result.
- The two production buckets remain `dokushodo` and `dokushodo-backup`, with
  independent credential scopes. This spec does not alter either bucket.

## Checkpoint Payload and Runtime Footprint

Checkpoint measurement MUST distinguish the disposable recovery envelope from
canonical content. For each selected chapter and checkpoint version, record:

```text
serialized_bytes, compressed_bytes, raw_copy_bytes, translated_copy_bytes,
state_copy_bytes, reference_bytes, write_count, rewrite_count,
recovery_reads, recovery_read_bytes, retention_age, envelope_version
```

The preferred compact envelope contains scalar state, hashes, canonical
identifiers, exact PostgreSQL/R2 references, stage completion, attempt/run
identity, and bounded error/checkpoint metadata. It does not contain a second
canonical copy of raw or translated content after the durable artifact is
available. If an in-flight stage requires temporary text, that text remains
process-local or disposable and is not treated as a durable content source.

Compaction is conditional rather than automatic. It may be enabled only when
the measured duplicate bytes, write amplification, recovery-read cost, or
retention footprint crosses an operator-approved threshold. The envelope must
be versioned, readable across restart, and able to resolve its exact R2/PG
references before resuming. Old envelopes are either read once and rewritten
through the application service or remain supported until their retention
expires; no raw runtime-file rewrite is allowed.

## Cost Envelope and Correctness Gates

### Cost accounting

Every fixed workload and reader stage produces two clearly separated sections:

1. **Hosted actuals**: Supabase Usage/Observability egress, R2 provider
   operation/storage reports when available, and provider dashboard usage.
2. **Modeled estimates**: application counters multiplied by the named price,
   quota, or unit source captured at the run timestamp.

The report uses formulas rather than a single blended number:

```text
supabase_estimated_egress_gb = measured_pooler_bytes / 1_000_000_000
r2_operation_estimate = class_a_ops * class_a_unit_price
                       + class_b_ops * class_b_unit_price
r2_storage_estimate = average_stored_gb * storage_unit_price * billing_fraction
provider_estimate = input_tokens * input_rate + output_tokens * output_rate
```

Actual Supabase billed egress remains authoritative when available. Query
statistics, container network counters, and application byte proxies cannot
replace that report. R2 egress, storage, and Class A/B operation units remain
separate. Provider free-tier/quota usage is reported as quota consumption when
there is no monetary rate. Compute and observability are listed as unavailable
or separately sourced rather than hidden inside database cost.

Each estimate includes unit, source URL or dashboard name, source timestamp,
currency if applicable, interval, sample size, cache state, and uncertainty.
The model must expose per-request, per-chapter, per-DAU-equivalent, and
per-day projections only as projections. Translation estimates also identify
eligible credential count, verified quota-domain count, reservation wait, and
the provider/project cap used; they must not linearly extrapolate from API-key
count. The model must never change a plan, credential state, or provider
setting automatically.

### Public reader correctness

The load harness validates the existing public contract in addition to timing:

- published catalog/detail/chapter responses resolve the expected compact
  projection and exact active R2 artifact;
- unpublished, unavailable, adult/takedown, and missing-artifact cases follow
  the existing policy and do not leak content;
- cache hits, misses, conditional responses, and caller cancellation preserve
  the same status/body contract;
- a malformed, stale, or missing active reference is a failed correctness
  sample even if the HTTP latency is within budget;
- sampled response bodies are validated by hashes/shape/status, never stored
  as raw public content in the load report.

## Reader Capacity Model

### Traffic derivation

DAU is converted into request rate only after the operator records:

```text
daily_reader_requests = DAU * sessions_per_user_per_day * requests_per_session
peak_reader_rps = daily_reader_requests * peak_window_fraction / peak_window_seconds
```

The harness also records catalog/detail/chapter mix, average and p95 response
size, cache-warm ratio, concurrent connections, and cancellation rate. The
traffic model is a named input artifact, not an implicit assumption.

### Stages

| Stage | Purpose | Entry gate | Required evidence |
| --- | --- | --- | --- |
| Fixture/local | Prove harness, DTOs, metrics, and no canonical mutation | Focused tests pass | Repeatability, redaction, event-loop, query/R2 counters |
| 1k DAU-equivalent | Establish the first reader budget and tune cache/projection behavior | Operator-approved traffic model and healthy baseline | Latency/error/Supabase/R2/pool/CPU/memory report |
| 10k DAU-equivalent | Validate scale step and isolation | 1k passes with no unwaived gate | Same report plus saturation/queue evidence |
| 100k DAU-equivalent | Planning evidence only unless hosted capacity is explicitly provisioned | 10k passes and explicit operator approval | Separate reader and worker capacity decision; no production guarantee |

Worker translation tests run separately with a bounded chapter sample and a
provider budget. Reader profiles do not silently start the full translation
queues, do not consume contributor credentials or provider quota, and
translation profiles do not count as reader traffic. A pooled-key result is
therefore reported as translation-provider capacity evidence only; it cannot
raise or substitute for the reader HTTP-RPS stage.

### Stop and rollback thresholds

Threshold values are operator-owned inputs and must be recorded before a live
stage. At minimum, stop when any of these occur:

- database capacity errors, pool exhaustion, unbounded connection growth, or
  transaction lock/checkout waits above the approved budget;
- provider quota/authentication failure, unexpected model/provider identity,
  or token/request rate above the project budget;
- R2 error rate, operation rate, or bytes above the approved budget;
- event-loop lag, memory growth, CPU saturation, error rate, or p95/p99
  latency beyond the declared stage SLO;
- lease loss, duplicate claim, failed terminal commit, artifact/reference
  mismatch, or unauthorized mutation;
- Supabase egress rises faster than the approved interval budget without a
  trustworthy attribution.
- checkpoint duplicate bytes, recovery reads, or retention exceed the
  approved footprint threshold;
- modeled cost exceeds the stage ceiling or the price/quota source is missing
  for a required cost component;
- the contributor pool has no eligible credential, cannot reserve capacity,
  violates fairness/ownership isolation, or observes a quota-domain conflict;
- a public status, availability, active-artifact, cache, or isolation
  assertion fails even when latency remains within SLO.

Rollback order is: stop new load, stop worker admission, allow critical
terminal transactions to settle within a deadline, cancel/defer non-critical
progress, restore the previous feature/config gate, verify queue/lease state,
and record the result. Never repair by hand-editing runtime JSON or database
rows.

## Failure Modes and Invariants

| Failure mode | Required behavior | Invariant protected |
| --- | --- | --- |
| Persistence executor full | Apply bounded backpressure; retain critical terminal work; reject/defer safe progress | No unbounded memory or silent terminal loss |
| DB checkout/statement timeout | Roll back, classify capacity/retryable error, release slot, stop if threshold persists | No leaked session or half-committed lineage |
| Deadlock or serialization failure | Retry only the short idempotent transaction with bounded jitter and an attempt cap; otherwise classify retryable capacity failure | No lock storm or duplicate terminal reference |
| R2 timeout/5xx | Retry only within operation budget and idempotency contract; never overwrite immutable object | R2 exact-key and immutability |
| Provider quota/auth failure | Stop or pause admission, release reservation, expose truthful status | No quota storm or key leakage |
| Contributor pool starvation/monopoly | Bound selection wait, rotate fairly, pause unhealthy credentials, and preserve owner/contributor scope | No key monopolization or false pooled-capacity claim |
| Event-loop lag | Stop raising concurrency; record lag and inspect blocking boundary | Async reader/worker responsiveness |
| Lease lost | Cancel new work, checkpoint/drain safely, do not report completion | Single owner per activity |
| Process shutdown | Stop admission, drain critical commands, persist checkpoint, release resources | Resumable activity and bounded restart |
| Async task cancellation during sync I/O | Mark the task cancelled, allow the underlying bounded operation to settle, prevent new side effects, and reconcile the result through its idempotency key | Cancellation is truthful without abandoning a transaction or leaking a worker slot |
| Cache miss/corruption | Re-read authoritative PG/R2 source, rebuild disposable cache | Cache is never canonical truth |
| Checkpoint version mismatch | Read through the application service, validate exact references, migrate or retain the old envelope according to policy | Recovery never treats an untrusted local payload as canonical |
| Cost telemetry unavailable | Mark the affected actual or estimate unavailable and stop any gate that requires it | No false cost pass from missing billing data |
| Public reader contract failure | Fail the sample and stop the stage even if transport latency passes | Availability and content isolation are part of capacity |
| Metrics exporter unavailable | Continue core work with bounded local counters or stop per policy; mark telemetry unavailable | No false pass from missing evidence |
| Load harness failure | Stop stage and preserve fixture cleanup path | No canonical external mutation |

Non-negotiable invariants:

1. No raw content, secrets, or provider response enters observability output.
2. No live SQLAlchemy session or ORM object crosses a thread boundary.
3. No database connection remains open across provider/R2/QA waits.
4. No reader/translation hot path calls R2 `LIST`.
5. No immutable R2 object is overwritten or deleted by this work.
6. No chapter is terminal before its required artifact/reference/state commit.
7. No capacity stage passes when a required metric is unavailable.
8. No full-queue run is used as a 100k-user capacity claim.
9. A checkpoint is never a second canonical content store; references must
   resolve before recovery.
10. Cost estimates never masquerade as provider billing actuals.
11. Reader correctness and isolation are required for a capacity pass.
12. Contributor-key count never becomes a public-reader HTTP-RPS or
    independent-provider-quota claim without verified quota-domain evidence.
13. Every provider reservation has one usage-ledger outcome or an explicit
    bounded expiry/reconciliation result; raw credentials never enter evidence.

## Traceability

| Requirement | Acceptance criteria | Planned task IDs | Design evidence |
| --- | --- | --- | --- |
| REQ-001, REQ-020, REQ-022 | AC-001, AC-016 | T-001, T-003, T-016 | Baseline/provenance and external-state gates |
| REQ-002, REQ-003 | AC-002, AC-003, AC-004 | T-002, T-004, T-005, T-006 | Async boundary and ownership model |
| REQ-004, REQ-011, REQ-016 | AC-003, AC-009 | T-003, T-012, T-020 | Fixed stage observation schema and redaction |
| REQ-005, REQ-006, REQ-010, REQ-019 | AC-005, AC-006, AC-008 | T-007, T-008, T-009 | Transaction, checkpoint, lease, and cache invariants |
| REQ-007, REQ-012, REQ-015 | AC-007, AC-012, AC-017 | T-009, T-013, T-016, T-024 | Admission, aggregate pool budget, and provider isolation |
| REQ-008, REQ-020 | AC-006, AC-010 | T-010, T-014 | Query/plan/egress evidence |
| REQ-009, REQ-010, REQ-022 | AC-011 | T-011, T-015 | Exact-key R2 and isolated cleanup |
| REQ-013, REQ-014, REQ-021 | AC-013, AC-014, AC-015 | T-014, T-017, T-018 | Fixture and staged load model |
| REQ-017, REQ-018, REQ-020, REQ-021 | AC-012, AC-018, AC-019 | T-019, T-020 | Documentation, validation, and handoff |
| REQ-023, REQ-006, REQ-010 | AC-005, AC-020 | T-021, T-020 | Checkpoint footprint, envelope version, and recovery |
| REQ-024, REQ-011, REQ-020, REQ-021 | AC-021 | T-022, T-016, T-017, T-018, T-020 | Hosted-versus-modeled cost envelope |
| REQ-025, REQ-009, REQ-013, REQ-014 | AC-022 | T-023, T-017, T-018, T-020 | Public response, artifact, cache, and isolation assertions |
| REQ-026, REQ-007, REQ-011, REQ-012, REQ-015 | AC-007, AC-009, AC-012, AC-017, AC-023 | T-024, T-014, T-022, T-016, T-019, T-020 | Contributor pool selection, quota domains, fairness, ledger, and isolation |

## Rollout and Reversibility

1. Land tests and telemetry contracts before enabling a new execution path.
2. Run the path in a disabled/shadow or one-chapter mode where possible;
   compare stage, query, R2, lease, and artifact evidence with the existing
   bounded sample.
3. Enable bounded persistence workers and provider admission only after the
   local fixture gate passes.
4. Validate contributor credential eligibility, quota-domain assumptions,
   reservation/reconciliation, fairness, and owner/contributor isolation in a
   bounded provider profile; keep provider and reader RPS reports separate.
5. Run one-to-three chapters per source only with the separate live gate; keep
   the original full queues paused.
6. Measure checkpoint footprint and cost-envelope sources before the 1k stage;
   compact only if the approved evidence threshold requires it.
7. Run reader capacity stages independently, beginning at 1k, and stop at the
   first unwaived threshold or correctness failure.
8. Roll back by disabling the new boundary/configuration and returning to the
   prior known-good bounded path. If the prior path is still blocking or
   unsafe, keep the worker stopped rather than forcing a throughput claim.

## Operational Handoff

The final implementation report must include:

- files and settings changed, feature/config gate, and rollback command;
- exact test commands, exit codes, counts, durations, and paths;
- fresh Supabase report window, sanitized query/pool evidence, and fields that
  remain unavailable;
- R2 operation/byte/reuse evidence and isolated-prefix cleanup proof;
- provider model/project limit evidence without keys or prompts;
- contributor-pool size, eligible credential count, verified quota domains,
  reservation/fairness outcomes, owner/contributor scope checks, and usage
  ledger reconciliation without raw credentials;
- separate `translation_provider_rps` and `reader_http_rps` results, with no
  key-count-based quota or reader-capacity extrapolation;
- checkpoint envelope sizes, duplicate-byte/recovery-read evidence, and
  version/rollback result;
- hosted cost actuals versus modeled Supabase/R2/provider/compute/
  observability estimates with sources and timestamps;
- 1k/10k/100k stage status, traffic model, cache state, and stop-gate result;
- public response/availability/artifact/cache/isolation correctness results;
- queue/lease/activity state and whether the worker remains stopped;
- all canonical Markdown updates, Graphify result, and remaining risks.
