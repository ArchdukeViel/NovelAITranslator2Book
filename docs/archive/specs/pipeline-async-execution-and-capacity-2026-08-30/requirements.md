# Pipeline Async Execution and Capacity Hardening Requirements

Spec ID: pipeline-async-execution-and-capacity
Version: 0.3.0
Status: Complete
Updated: 2026-08-24
Requester: Project owner
Owner: Project owner with implementation agent
Target project or release: Post-PR113 R2-only translation worker, cost envelope, and staged reader-capacity validation

## Context and Problem

The previous pipeline resource audit reduced several avoidable reads, narrowed
ORM projections, improved queue claims, and completed a bounded one-chapter
sample for each of the three existing source identities. It did not establish
that the translation worker is economical or that the public reader can serve
large traffic. The original full-queue run was stopped because it remained in
an hour-scale window while only one source made limited progress.

The current repository has a more specific risk than a simple choice between
PostgreSQL and R2. PostgreSQL is intentionally the owner of compact catalog
projections, scalar chapter state, hashes, active artifact references, leases,
and bounded progress. R2 is intentionally the owner of immutable raw,
translated, media, and asset artifacts. However, the async chapter coordinator
still invokes synchronous database, filesystem-runtime, and R2 facade methods
from concurrent async chapter tasks. Those calls can block the event loop,
hold resources longer than necessary, multiply transaction overhead, and make
increasing chapter concurrency an unsafe substitute for real capacity work.

The latest read-only evidence is directional rather than a billing allocation:

| Evidence | Observation | Interpretation |
| --- | --- | --- |
| Supabase Shared Pooler Egress | The operator report shows about 66.7 GB in the billing window | This is provider-side billing evidence, not a per-query attribution |
| `pg_stat_statements` | About 63.8k novel-row calls and 152k chapter-row calls in the current cumulative view | Repetition and returned-row volume require a fresh bounded interval before a workload claim |
| Query shape | Novel and chapter projections remain prominent, while exact response bytes are unavailable | Narrow projections and batching must be measured; a wholesale content-storage move is not implied |
| Worker observation | A bounded three-source sample completed sequentially; the original full queues remain paused | The sample proves bounded correctness only, not worker throughput or reader capacity |
| R2 boundary | `dokushodo` stores immutable application artifacts and `dokushodo-backup` stores independent recovery material | Exact-key reads and PostgreSQL references remain the content contract |

The numbers above are staleable operational observations. Every execution must
capture a new timestamped baseline and must label cumulative counters,
provider dashboards, local metrics, and synthetic load results separately.

## Governing References

- `AGENTS.md` and the repository project instructions.
- [`docs/ARCHITECTURE.md`](../../../docs/ARCHITECTURE.md) for dependency
  direction, PostgreSQL/R2 ownership, worker leases, provider isolation, and
  connection budgets.
- [`docs/TRANSLATION.md`](../../../docs/TRANSLATION.md) for translation
  identity, cache, lineage, QA, and runtime resource boundaries.
- [`docs/PERFORMANCE_AUDIT.md`](../../../docs/PERFORMANCE_AUDIT.md) and
  [`docs/PERFORMANCE_ACTION_PLAN.md`](../../../docs/PERFORMANCE_ACTION_PLAN.md)
  for the previous audit evidence and staged-capacity gate.
- [`docs/CONFIGURATION.md`](../../../docs/CONFIGURATION.md) and
  [`docs/OPERATIONS.md`](../../../docs/OPERATIONS.md) for pool, worker, R2,
  telemetry, stop, and rollback procedures.
- [`docs/R2-Only Content Storage Rearchitecture-plan.md`](../../../docs/R2-Only%20Content%20Storage%20Rearchitecture-plan.md)
  for the PR113 content-storage completion boundary.
- Supabase's [egress guidance](https://supabase.com/docs/guides/platform/manage-your-usage/egress)
  for the distinction between Database Egress and Shared Pooler Egress.
- Cloudflare's [R2 pricing](https://developers.cloudflare.com/r2/pricing/)
  and S3-compatible operation guidance for cost and operation categories.

## Goal

Make translation execution resource-safe under bounded concurrency and produce
reproducible evidence for reader capacity at 1,000, 10,000, and 100,000
DAU-equivalent profiles without blocking the event loop, exhausting the
Supabase pooler, multiplying R2 operations, leaking sensitive telemetry, or
misrepresenting synthetic results as production capacity.

User-contributed API keys are a potential translation-provider capacity pool,
not a public-reader capacity multiplier. The plan MUST report translation
provider request rate separately from public HTTP request rate. Additional keys
may raise translation admission only when their quota domains are verified as
independent and the provider/project, database, R2, process, and cost budgets
still permit it.

## Scope and Boundaries

### In Scope

- The async execution boundary in
  `services/orchestration/translation.py`, translation pipeline stages,
  `activity/worker.py`, `activity/runner.py`, and the services they call.
- Safe ownership of SQLAlchemy sessions, ORM instances, R2 clients, and
  runtime file operations when work crosses an async/thread boundary.
- Bounded persistence, checkpoint, progress, lease, cancellation, retry, and
  graceful-shutdown behavior for durable activities.
- Provider admission, project/key quota accounting, provider wait time,
  chapter/chunk concurrency, contributor-key pooling, and backpressure.
- Contributor credential eligibility, per-credential reservations, aggregate
  provider/project caps, fairness, usage-ledger attribution, and owner versus
  contributor isolation. Raw keys remain outside evidence and telemetry.
- Sanitized stage telemetry for event-loop lag, provider, PostgreSQL, R2,
  runtime cache, queue, lease, and memory/CPU behavior.
- Read-only query-shape and plan review, projection/batching tests, and
  measured database egress reduction.
- R2 exact-key behavior, conditional reads where safe, no-hot-path-`LIST`,
  immutable artifact lineage, operation counts, and generated-prefix cleanup.
- A repeatable local/synthetic load harness and operator-gated staged reader
  load at 1k/10k/100k DAU-equivalent profiles.
- Checkpoint/runtime payload footprint measurement and, when justified by
  evidence, a versioned reference-only compaction path that preserves resume
  behavior.
- A cost envelope that separates actual Supabase billing evidence from local
  estimates for Supabase, R2, provider tokens, and observability.
- Public reader correctness checks during capacity stages, including existing
  publication/availability policy and exact active-artifact resolution.
- Necessary configuration, operational runbook, performance, architecture,
  translation, work, history, and R2-plan documentation updates after
  implementation evidence exists.

### Out of Scope

- Moving all novel metadata or any canonical raw/translated/media content from
  R2 to PostgreSQL, or moving all PostgreSQL projections into R2, without a
  separate architecture decision and migration specification.
- Editing, deleting, renaming, or bulk-rewriting `dokushodo`,
  `dokushodo-backup`, canonical PostgreSQL rows, source identities, public
  URLs, publication state, adult-content state, or takedown state.
- A PostgreSQL schema/index migration, dropping indexes, changing RLS, or
  changing the Supabase plan without separate approval and a migration/ops
  gate.
- Replacing Supabase, R2, Gemini, the current durable activity model, or the
  current Session Pooler route as an unmeasured optimization.
- Resuming the original unbounded three-novel queues or using them as a
  capacity benchmark.
- Real 100,000-user production traffic, a claim of production SLO compliance,
  or a provider quota increase based only on synthetic tests.
- New frontend product features, billing/subscriptions, a new observability
  vendor, or unrelated repository cleanup.
- Backup/restore acceptance, production recovery, or manual repair of runtime
  chapter state. Those remain separate operator-gated work.
- Committing secrets, raw prompts/responses, source text, IP addresses,
  connection strings, API keys, or full database rows to evidence.

## Architectural Constraints and Decisions

| ID | Decision | Rationale |
| --- | --- | --- |
| D-001 | Preserve PostgreSQL compact projections and exact artifact references; preserve R2 immutable content | The current R2-only conformance contract is already the source of truth. Egress evidence does not prove that content placement is wrong |
| D-002 | Remove blocking work from the async event loop before increasing concurrency | A higher semaphore value can multiply blocked sessions and R2 calls instead of improving throughput |
| D-003 | Prefer an explicit bounded persistence/I/O boundary with per-operation session ownership as the first implementation slice; evaluate async-native adapters separately | Existing synchronous SQLAlchemy and S3 facades must not be shared across threads; a bounded adapter is reversible and measurable |
| D-004 | Never pass a live SQLAlchemy `Session`, ORM instance with unloaded attributes, transaction, or mutable storage client across thread boundaries | SQLAlchemy sessions and ORM identity maps are not thread-safe; cross-thread lazy loads could reintroduce large-row egress and data races |
| D-005 | Do not hold a database connection while waiting for a provider call, R2 transfer, retry delay, or QA computation | Connection occupancy and pooler egress must be proportional to database work, not total chapter latency |
| D-006 | Persist terminal lineage and active references transactionally; coalesce only non-critical progress/events within bounded loss and replay rules | Correctness and resume behavior take priority over write-count reduction |
| D-007 | Capacity evidence requires a fresh interval, explicit workload shape, cache state, sample count, stop gates, and unavailable fields | DAU is not a request rate and cumulative `pg_stat_statements` is not billed-byte attribution |
| D-008 | Keep the worker stopped until the implementation and bounded canary gates pass; never auto-resume the paused full queues | The prior run demonstrated risk and incomplete terminal behavior |
| D-009 | Cost evidence separates provider billing reports from modeled estimates and records the price/quota source and timestamp | Supabase, R2, provider, compute, and observability costs have different units and authorities |
| D-010 | Checkpoint compaction is conditional, versioned, and reference-only; it is not a silent content migration | The current checkpoint envelope duplicates content, but resume correctness must not depend on local canonical storage |
| D-011 | Treat contributor-key pooling as translation-provider admission only; effective capacity is bounded by eligible credential headroom, verified quota domains, DB/R2/process budgets, and cost ceilings | More API keys do not automatically increase public HTTP RPS or provider project quota |
| D-012 | Enforce per-credential reservation, fair selection, usage-ledger attribution, and owner/contributor scope isolation | Pooling must not allow one key/user to monopolize capacity, leak credentials, or silently use contributor keys for owner-only work |

## Requirements

### Functional Requirements

1. **REQ-001: Baseline and reproducibility**: Each run MUST record an opaque
   run identifier, UTC start/end, revision, topology, enabled worker state,
   provider model identity, cache state, configured concurrency/budget names,
   workload profile, and evidence source. Secret values and connection
   strings MUST remain absent.
2. **REQ-002: Async execution boundary**: The chapter coordinator MUST
   distinguish async provider/network work from synchronous DB, R2, and
   runtime-file work. No synchronous operation that can block on network,
   disk, serialization, or database checkout may execute unbounded inside the
   event loop.
3. **REQ-003: Session and client ownership**: Every DB transaction and any
   thread-executed storage operation MUST have explicit ownership and lifetime.
   ORM objects crossing boundaries MUST be converted to immutable DTOs or
   scalar values, and lazy attribute access after a session closes MUST fail
   in tests rather than silently opening a query.
4. **REQ-004: Pipeline stage contract**: Fetch/raw normalization, metadata and
   glossary loading, selection/segmentation, provider wait/retry, QA,
   persistence, R2 operations, PostgreSQL commit, and activity-state updates
   MUST have a timing or truthful unavailable field with fixed bounded labels.
5. **REQ-005: Persistence and transaction efficiency**: The implementation
   MUST batch or coalesce safe progress, event, and chunk-state writes where
   semantics permit, keep terminal lineage/reference commits atomic, avoid
   redundant full-row reads, and prove idempotent retry behavior.
6. **REQ-006: Queue and lease safety**: Claim, lease renewal, heartbeat,
   cancellation, retry, checkpoint, pause, failure, and graceful shutdown
   MUST preserve current durable activity semantics. No job may be claimed by
   two workers, lose its lease silently, or be reported complete before its
   artifacts and references are durable.
7. **REQ-007: Provider admission and backpressure**: Provider and chapter/chunk
   concurrency MUST be bounded by the smallest applicable provider, database,
   R2, memory, and operator budget. Queue wait, provider retry delay, quota
   exhaustion, and admission rejection MUST be observable and must not create
   unbounded tasks.
8. **REQ-008: Database query and egress control**: Routine queries MUST use
   narrow projections, avoid N+1 novel/glossary/activity reads, and measure
   rows, calls, duration, and available byte proxies. Query-level billed bytes
   MUST be reported unavailable when the provider does not expose them.
9. **REQ-009: R2 operation discipline**: Reader and translation hot paths MUST
   use exact-key `HEAD`/`GET`/immutable `PUT` behavior as appropriate and MUST
   not use `LIST`. Inventory, backup, GC, and cleanup may paginate `LIST` only
   outside hot paths. Hash reuse, compression, conditional reads, and
   redundant transfers MUST be measured before being enabled broadly.
10. **REQ-010: Safe content and cache policy**: Runtime caches remain
    disposable and invocation-scoped unless their key, invalidation, memory
    bound, and failure behavior are specified. PostgreSQL active references
    and R2 immutable artifacts remain authoritative after cache loss.
11. **REQ-011: Resource telemetry**: Metrics and evidence MUST cover event-loop
    lag, queue age, stage latency, provider wait/retry/token fields, DB pool
    wait/checkout/statement/commit, query counts/rows, R2 operation counts and
    bytes, CPU, memory, network, and errors using bounded labels and redaction.
12. **REQ-012: Configuration budgets**: Any new or changed setting MUST define
    its default, allowed range, environment scope, aggregate DB-pool formula,
    provider/R2 interaction, rollback value, and operator stop threshold.
    Defaults MUST remain conservative until measured evidence justifies a
    change.
13. **REQ-013: Synthetic load harness**: The repository MUST provide a
    repeatable harness that models public catalog/detail/chapter reads,
    cache-warm and cache-cold behavior, realistic response-size classes, and
    optional bounded worker jobs without touching canonical content.
14. **REQ-014: Staged capacity validation**: The harness and operator procedure
    MUST support 1k, 10k, and 100k DAU-equivalent profiles derived from an
    explicit request/session model. Each stage requires SLO, pool, egress, R2,
    error, memory, and stop-gate evidence; an unavailable metric cannot be
    silently treated as a pass.
15. **REQ-015: Reader/worker isolation**: Public reader capacity MUST be
    measured independently from translation-worker capacity. Worker admission
    MUST not consume the entire web/reader DB connection budget, provider
    budget, or event-loop capacity.
16. **REQ-016: Security and privacy**: No metric, trace, log, load artifact,
    or report may contain secrets, authorization headers, prompts, provider
    responses, source text, raw user/session/IP identifiers, database URLs, or
    arbitrary high-cardinality labels. Synthetic identities MUST be generated
    and discarded within the test boundary.
17. **REQ-017: Documentation and operational handoff**: Implementation evidence
    MUST update all affected canonical Markdown, including architecture,
    configuration, operations, translation, performance audit/action plan,
    work/history, and the R2 plan. Documentation MUST distinguish completed,
    partial, unavailable, deferred, and operator-owned gates.
18. **REQ-018: Validation and rollback**: Focused tests, lint, type checks,
    relevant full tests, architecture guards, Compose/config validation,
    Markdown link checks, and Graphify refresh MUST be run. Every implementation
    slice MUST have a reversible feature/config gate or a documented rollback;
    failed thresholds MUST stop the workload without destructive cleanup.

### Non-Functional and Operational Requirements

19. **REQ-019: Correctness over throughput**: A slower but truthful terminal
    activity is preferable to a faster run that duplicates provider work,
    loses lineage, corrupts checkpoints, or inflates egress.
20. **REQ-020: Evidence provenance**: Every number MUST state whether it is
    hosted billing evidence, database cumulative evidence, interval application
    evidence, provider dashboard evidence, local synthetic evidence, or
    unavailable, along with sample size and aggregation method.
21. **REQ-021: No false capacity claim**: Passing a local or hosted synthetic
    profile MUST NOT be documented as a production guarantee. A capacity result
    is valid only for the tested revision, topology, traffic mix, cache state,
    provider budget, database budget, and observation window.
22. **REQ-022: Protected external state**: This specification may use
    read-only Supabase/R2 observations. Any generated R2 test object MUST be
    under a unique isolated prefix, deleted through the application/provider
    API after verification, and confirmed absent by a final paginated sweep.
23. **REQ-023: Checkpoint footprint and recovery**: The implementation MUST
    measure checkpoint serialized/compressed bytes, duplicate content fields,
    write frequency, recovery read amplification, and retention. If the
    measured footprint justifies change, it MUST use a versioned
    reference-only or compact envelope that resolves exact PostgreSQL/R2
    references before resume. It MUST preserve crash recovery, cancellation,
    retry, and older-envelope handling without making local runtime data
    canonical.
24. **REQ-024: Cost envelope**: Each fixed workload and capacity stage MUST
    report actual hosted billing evidence separately from estimates for
    Supabase pooler/database egress, R2 storage and Class A/B operations,
    provider tokens/quota, compute, and observability. Estimates MUST state
    units, price/quota source, source timestamp, workload interval, and
    uncertainty; no plan or price change may be inferred automatically.
25. **REQ-025: Public reader correctness**: Capacity traffic MUST assert the
    existing public availability contract for catalog, detail, chapter list,
    and chapter content, including published/unpublished/adult/takedown
    policy, exact active-artifact resolution, cache/revalidation behavior, and
    truthful unavailable responses. Load success MUST NOT be reported when
    latency passes but content or isolation checks fail.
26. **REQ-026: Contributor credential pool capacity and isolation**:
    Contributor-backed translation MUST select only active, validated,
    consented credentials explicitly eligible for the contributor pool. Each
    provider attempt MUST reserve and reconcile per-credential RPM, TPM, RPD,
    and in-flight capacity before and after the call. Effective translation
    admission MUST be bounded by the sum of eligible per-credential headroom
    only across verified independent quota domains, then by known provider or
    project caps and the worker, database, R2, process, and cost budgets. An
    API-key count MUST NOT be converted into a public-reader HTTP-RPS claim or
    a multiplied project quota. Selection MUST be fair and bounded, and the
    usage ledger MUST attribute credential, credential owner, requesting user,
    provider/model, request/job, status, token usage, estimated cost, and
    timestamps without storing raw keys, prompts, responses, or authorization
    headers. Owner-only jobs MUST remain isolated from contributor-pool
    credentials, and invalid, revoked, paused, or quota-failed credentials MUST
    leave the eligible pool truthfully.

## Acceptance Criteria

- AC-001: A fresh sanitized baseline records revision, topology, worker state,
  cache state, budgets, workload, UTC interval, evidence source, and protected
  boundaries without secrets.
  - Maps to: REQ-001, REQ-020, REQ-022
  - Evidence: dated baseline artifact and command/report output with secret-free review.
- AC-002: A call-graph and hotspot inventory names every blocking DB, R2,
  runtime-file, serialization, and provider boundary in the chapter path,
  including whether it runs on the event loop or a bounded executor.
  - Maps to: REQ-002, REQ-003
  - Evidence: source map, design decision, and static regression guard.
- AC-003: The chosen async boundary has no unbounded blocking I/O on the event
  loop, and a regression test fails if a synchronous persistence/storage call is
  invoked directly from a chapter coroutine.
  - Maps to: REQ-002, REQ-004, REQ-018
  - Evidence: focused async boundary tests and event-loop-lag test output.
- AC-004: Session, ORM, transaction, and R2-client ownership is explicit;
  thread execution never shares a live SQLAlchemy session or lazy ORM object,
  and rollback/commit behavior is covered by tests.
  - Maps to: REQ-003, REQ-005, REQ-006
  - Evidence: ownership tests, transaction tests, and source review.
- AC-005: A successful chapter preserves the existing artifact hash, lineage,
  active-reference, checkpoint, and terminal-state contracts; a failed or
  cancelled chapter remains resumable and truthful.
  - Maps to: REQ-005, REQ-006, REQ-010, REQ-019
  - Evidence: checkpoint/resume, cancellation, idempotency, and artifact-readback tests.
- AC-006: Progress/event/chunk writes are reduced or coalesced only where safe,
  terminal writes remain atomic, and before/after query counts and rows are
  recorded for a fixed workload.
  - Maps to: REQ-005, REQ-008, REQ-020
  - Evidence: bounded benchmark and query-shape report.
- AC-007: Provider, chapter, chunk, DB, R2, and memory admission is bounded;
  saturation causes queueing or truthful rejection rather than unbounded task
  creation, and provider project limits are not inferred from API-key count.
  - Maps to: REQ-007, REQ-012, REQ-015
  - Evidence: limiter tests, configuration matrix, and admission metrics.
- AC-008: Queue claims, leases, heartbeats, cancellation, retries, graceful
  shutdown, and restart recovery pass under concurrent-worker tests without
  duplicate claims or premature completion.
  - Maps to: REQ-006, REQ-018, REQ-019
  - Evidence: activity/database/worker test results and a shutdown trace.
- AC-009: Timing and resource telemetry reports all required stages or gives a
  named unavailable reason, with bounded labels and no protected values.
  - Maps to: REQ-004, REQ-011, REQ-016, REQ-020
  - Evidence: schema test, redaction test, sample record, and metric inventory.
- AC-010: Database evidence demonstrates narrow projections, no newly
  introduced N+1 path, pool checkout/connection budget behavior, and query-plan
  review; exact billed bytes remain explicitly unavailable when Supabase cannot
  attribute them per query.
  - Maps to: REQ-008, REQ-012, REQ-020
  - Evidence: sanitized `pg_stat_statements`, plan output, pool metrics, and Supabase report comparison.
- AC-011: R2 evidence demonstrates exact-key hot paths, no hot-path `LIST`,
  operation/byte/compression/reuse counters, and cleanup of any isolated test
  prefix without changing canonical buckets.
  - Maps to: REQ-009, REQ-010, REQ-022
  - Evidence: static `LIST` guard, isolated R2 test, operation report, and zero-object sweep.
- AC-012: Configuration changes, if any, include allowed ranges, aggregate
  connection/provider/R2 budgets, stop thresholds, environment scope, and a
  tested rollback.
  - Maps to: REQ-012, REQ-018
  - Evidence: sanitized config matrix and rollback test or dry run.
- AC-013: The synthetic harness runs reproducibly against isolated fixtures
  for cache-warm and cache-cold public reads and bounded worker samples,
  reporting latency, errors, bytes, DB/R2 operations, and resource usage.
  - Maps to: REQ-013, REQ-014, REQ-020
  - Evidence: fixture-only run artifacts and repeatability comparison.
- AC-014: The 1k DAU-equivalent stage reaches its declared SLO and resource
  gates, or stops with a quantified blocker; no stage is marked successful from
  missing telemetry.
  - Maps to: REQ-014, REQ-015, REQ-021
  - Evidence: stage report with traffic model, sample counts, stop gates, and result.
- AC-015: The 10k and 100k DAU-equivalent stages are attempted only after the
  previous stage passes, with operator approval, explicit rollback/stop gates,
  and separate reader versus worker budgets.
  - Maps to: REQ-014, REQ-015, REQ-018, REQ-021
  - Evidence: staged run records and operator decisions; an unrun stage is marked unavailable/deferred.
- AC-016: The three supplied source identities remain unchanged and the
  original unbounded queues are not used as capacity evidence; any bounded
  canary has truthful terminal outcomes and isolated stop conditions.
  - Maps to: REQ-006, REQ-019, REQ-022
  - Evidence: application-service readback and queue-state report without manual row/runtime edits.
- AC-017: A final review confirms reader requests do not depend on translation
  worker event-loop capacity or worker pool exhaustion, and connection-budget
  arithmetic accounts for every long-lived process plus reserve.
  - Maps to: REQ-012, REQ-015, REQ-021
  - Evidence: topology/pool model, load report, and capacity decision.
- AC-018: All affected canonical Markdown is synchronized with implementation
  evidence and explicitly lists completed, partial, unavailable, deferred,
  operator-owned, and rollback states.
  - Maps to: REQ-017, REQ-020, REQ-021
  - Evidence: documentation diff, link/route audit, and R2-plan checkpoint.
- AC-019: Required focused and broader quality gates pass with exact commands,
  exit codes, counts, paths, Graphify result, and remaining risks recorded.
  - Maps to: REQ-018, REQ-020
  - Evidence: final validation record and clean review of the scoped diff.
- AC-020: Checkpoint footprint is measured and either compacted through a
  versioned reference-only envelope with recovery tests or retained with a
  documented evidence-backed no-op decision; no checkpoint becomes canonical
  content storage.
  - Maps to: REQ-006, REQ-010, REQ-023
  - Evidence: before/after serialized and compressed sizes, recovery read-amplification report, envelope-version tests, and rollback decision.
- AC-021: Each workload report contains a cost envelope separating hosted
  actuals from estimates for Supabase, R2, provider, compute, and
  observability, with units, sources, timestamps, and uncertainty; missing
  billing fields remain unavailable.
  - Maps to: REQ-011, REQ-020, REQ-021, REQ-024
  - Evidence: cost model output reconciled to the Supabase Usage/Observability window and R2/provider operation/token counters.
- AC-022: Reader capacity stages verify public response status, availability
  policy, active-artifact correctness, cache/revalidation behavior, and
  isolation for the existing public routes in addition to latency and error
  budgets.
  - Maps to: REQ-009, REQ-013, REQ-014, REQ-025
  - Evidence: fixture and hosted route assertions, sampled response-class report, and failed-content/error isolation test results.
- AC-023: Contributor-backed translation demonstrates eligible-key selection,
  per-credential reservation/reconciliation, fair bounded pooling, usage-ledger
  attribution, owner/contributor isolation, and truthful invalid/quota failure
  handling. Reports separate translation-provider RPS from public-reader HTTP
  RPS and do not treat key count as independent provider/project quota without
  verified quota-domain evidence.
  - Maps to: REQ-007, REQ-011, REQ-012, REQ-015, REQ-026
  - Evidence: credential-pool tests, reservation/ledger records with secrets redacted, quota-domain decision, and separate worker-versus-reader capacity report.

## Acceptance Coverage

| Acceptance criterion | Task ID(s) | Evidence required | Status |
| --- | --- | --- | --- |
| AC-001 | T-001, T-003 | Fresh sanitized baseline and provenance record | Complete |
| AC-002 | T-002, T-004 | Call graph, hotspot table, and chosen boundary decision | Complete |
| AC-003 | T-005, T-006, T-020 | Async boundary tests and event-loop blocking guard | Complete |
| AC-004 | T-005, T-006, T-007 | Session/thread ownership and transaction tests | Complete |
| AC-005 | T-007, T-008, T-009 | Artifact, checkpoint, cancellation, and idempotency evidence | Complete |
| AC-006 | T-008, T-010, T-014 | Before/after fixed-workload query/write evidence | Complete |
| AC-007 | T-009, T-013 | Admission tests, limits, and backpressure evidence | Complete |
| AC-008 | T-009, T-020 | Queue/lease/shutdown/restart test record | Complete |
| AC-009 | T-003, T-012 | Telemetry schema, redaction, and bounded-label evidence | Complete |
| AC-010 | T-010, T-014 | Query/plan/pool/egress report | Complete |
| AC-011 | T-011, T-015 | R2 static and isolated-prefix evidence | Complete |
| AC-012 | T-013, T-020 | Configuration matrix and rollback result | Complete |
| AC-013 | T-014, T-015 | Fixture-only repeatable harness output | Complete |
| AC-014 | T-017 | 1k stage report or quantified blocker | Complete |
| AC-015 | T-018 | 10k/100k staged reports or completed dependency decision | Complete |
| AC-016 | T-001, T-016 | Identity and bounded-canary evidence | Complete |
| AC-017 | T-017, T-018, T-019 | Reader/worker isolation and pool arithmetic | Complete |
| AC-018 | T-019 | Markdown synchronization and R2-plan checkpoint | Complete |
| AC-019 | T-020 | Final quality and handoff record | Complete |
| AC-020 | T-021, T-020 | Checkpoint footprint and versioned recovery evidence | Complete |
| AC-021 | T-022, T-016, T-017, T-018, T-020 | Cost envelope and hosted/local reconciliation | Complete |
| AC-022 | T-023, T-017, T-018, T-020 | Public reader correctness under capacity traffic | Complete |
| AC-023 | T-024, T-014, T-022, T-016, T-019, T-020 | Contributor pool capacity, fairness, attribution, and isolation | Complete |

## Open Questions and Approval Gates

- OQ-001: Choose the first implementation boundary after the call-graph and
  session-ownership inventory: a bounded executor adapter, async-native
  SQLAlchemy/storage adapters, or a smaller staged combination. The choice
  must be evidence-backed and must not share sessions across threads.
- OQ-002: Confirm the operator's acceptable reader SLOs, request/session model,
  cache-warm ratio, peak concentration, and error budget before the 1k stage.
  DAU alone is not enough to derive requests per second.
- OQ-003: Confirm the deployment-wide DB connection budget and reserve for the
  target number of backend, reader, worker, migration, and operator processes.
- OQ-004: Confirm which hosted Supabase/R2/provider dashboards are available
  for the measurement window. Missing response-byte attribution remains an
  explicit unavailable field, not a reason to dump rows or secrets.
- OQ-005: Decide whether any large history JSON column needs a separate
  reference-only/schema migration after the async boundary and query-shape
  evidence. This spec does not authorize that migration.
- OQ-006: Approve each live workload gate independently. Creating an isolated
  R2 fixture object and running synthetic/local load are different authorities
  from running a bounded source canary or touching production queues.
- OQ-007: Set the checkpoint-size, duplicate-byte, recovery-read, and retention
  thresholds that would justify compacting the current disposable envelope.
- OQ-008: Set the stage cost ceilings and identify the authoritative price/quota
  source for Supabase, R2, Gemini, compute, and observability. A cost estimate
  is not a billing statement.
- OQ-009: Confirm the provider quota domain for each eligible credential or
  adopt the conservative shared-project assumption. Do not infer independent
  Gemini quota from the presence of distinct API keys alone; record how any
  verified independent domains are identified and how aggregate caps are
  enforced.

## Continuation decisions — 2026-08-24

All open questions are closed for this execution slice. The selected bounded
executor/session/storage boundary is Option B from the design. Reader budgets
use the canonical operations table: catalog 500 ms p95, detail 300 ms p95,
chapter 750 ms p95, and liveness 100 ms p95. The 1k model is 8,000 requests per
day, 0.444444 peak requests/second, and an 1,800-second peak window. The
deployment pool arithmetic remains the documented multi-process formula with
the worker stopped during reader measurement. Supabase cumulative
`pg_stat_statements` and provider usage-ledger counters were available; R2
provider operation and billed-byte counters were not exposed to the local
runner and remain explicitly named in the stage report. No schema, checkpoint,
quota, billing-plan, or credential-activation change was inferred from the
measurements. The checkpoint footprint remains an evidence-backed retain
decision. The bounded source canary was authorized and completed; the 10k/100k
reader stages were correctly not admitted after the 1k SLO stop.

## Approval

Owner decision (2026-08-24): `pipeline-async-execution-and-capacity` is
approved as a staged implementation and validation plan. The approval includes
the added checkpoint-footprint, hosted-versus-modeled cost, and public-reader
correctness gates and the contributor-key pooling capacity/isolation contract.
It does not authorize an automatic production queue restart, schema or
billing-plan change, checkpoint migration, credential activation, or unbounded
live load; those actions remain individually gated by the task-level
authorization and stop conditions below. The original full translation queues
remain paused until the execution gates in this spec are satisfied.
