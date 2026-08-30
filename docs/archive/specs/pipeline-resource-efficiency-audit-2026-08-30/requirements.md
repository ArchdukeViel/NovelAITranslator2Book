# Pipeline Runtime, Supabase, and R2 Efficiency Audit Requirements

Spec ID: pipeline-resource-efficiency-audit
Version: 0.2.0
Status: Complete
Updated: 2026-08-23
Requester: Project owner
Owner: Project owner with implementation agent
Target project or release: PR113 R2-only pipeline and controlled three-novel validation

## Context and Problem

The translation worker and R2-only storage cutover need an evidence-backed
runtime audit before the worker is resumed. The repository already contains
projection, queue-claim, cache, heartbeat, and polling improvements, but their
impact must be measured against the live Supabase/PostgreSQL and Cloudflare R2
resource boundaries. The previous incident recorded unusually high Supabase
egress while the worker repeatedly queried large ORM rows. The worker is
intentionally stopped until the audit and verification gate is satisfied.

The audit must cover the three existing source URLs without changing their
PostgreSQL identities, public URLs, publication state, adult-content state, or
takedown state:

- <https://kakuyomu.jp/works/16817330655991571532>
- <https://novel18.syosetu.com/n3266mn/>
- <https://ncode.syosetu.com/n2056dn/>

Governing architecture and operational constraints are documented in
[`docs/ARCHITECTURE.md`](../../../docs/ARCHITECTURE.md),
[`docs/PERFORMANCE_AUDIT.md`](../../../docs/PERFORMANCE_AUDIT.md),
[`docs/PERFORMANCE_ACTION_PLAN.md`](../../../docs/PERFORMANCE_ACTION_PLAN.md),
[`docs/TRANSLATION.md`](../../../docs/TRANSLATION.md),
[`docs/OPERATIONS.md`](../../../docs/OPERATIONS.md), and the
[`R2-only rearchitecture plan`](../../../docs/R2-Only%20Content%20Storage%20Rearchitecture-plan.md).

## Goal

Produce a reproducible, sanitized latency and resource-usage profile for one
controlled bulk workload, implement only evidence-backed local optimizations,
and leave a prioritized action list that identifies egress reduction, latency
benefit, implementation effort, remaining operator gates, and measured
uncertainty.

## Scope and Boundaries

### In Scope

- Per-stage timing for source fetch, metadata and glossary loading, provider
  translation, QA, R2 operations, PostgreSQL transactions, and activity state
  updates.
- Worker event-loop, lease, queue-claim, polling, retry, and blocking-operation
  analysis.
- SQLAlchemy projection review, query counts, heavy-column reads, query plans,
  pool usage, and direct-versus-pooler connection-path evidence.
- R2 operation counts, payload sizes, compression, content-address reuse,
  redundant reads or writes, and the no-hot-path-`LIST` invariant.
- Local code and configuration changes in the named pipeline, activity,
  database, R2, settings, Compose, test, and documentation surfaces when the
  audit provides sufficient evidence.
- A bounded, one-novel-at-a-time validation workload for the three supplied
  URLs after the worker rebuild gate passes.

### Out of Scope

- Emptying, resetting, deleting, or renaming `dokushodo` or
  `dokushodo-backup`.
- Production recovery acceptance beyond the authorized encrypted backup and
  isolated restore evidence; the completed recovery evidence is recorded in
  the continuation checkpoint.
- New product features, frontend changes, provider migrations, billing
  changes, or a new metrics platform.
- Production-scale claims based only on local tests or cumulative PostgreSQL
  counters.
- Database schema or index migrations unless a separate approval names the
  migration and target environment after the audit proves they are required.
- Remote Git, pull request, deployment, bucket-policy, or secret-rotation
  actions.

### Affected Surfaces

- `backend/src/novelai/translation/`
- `backend/src/novelai/services/orchestration/`
- `backend/src/novelai/activity/worker.py`
- `backend/src/novelai/activity/database.py`
- `backend/src/novelai/activity/runner.py`
- `backend/src/novelai/db/` and the database engine or query helpers used by
  the measured paths
- `backend/src/novelai/storage/backends/r2.py`
- `backend/src/novelai/storage/r2_catalog.py`
- `backend/src/novelai/config/settings.py`
- `deploy/compose.yml`, environment templates, and only the necessary local
  environment variable names or values
- Focused backend tests, isolated R2 integration tests, and sanitized audit
  evidence kept outside canonical novel content
- Affected Markdown under `docs/`, including performance, configuration,
  operations, architecture, translation, work, history, and the R2 plan

### Forbidden or Protected Surfaces

- Raw secret values, API keys, authorization headers, database URLs, R2
  credentials, prompts, provider responses, IP addresses, and private tokens
  in logs, evidence, documentation, tests, or chat.
- PostgreSQL novel identity rows, canonical R2 objects, runtime JSON, and
  `data/runtime/` contents except through the application’s normal service
  boundaries during the explicitly approved canary.
- Production novel prefixes in R2 integration tests.
- The two project bucket resources themselves. The required names remain
  `dokushodo` and `dokushodo-backup`; unrelated Cloudflare account buckets are
  outside this specification.
- Existing unrelated working-tree changes, branches, commits, and remote
  operations.

## Constraints, Assumptions, and Decisions

- The worker remains stopped until the query, cache, claim, polling, and
  heartbeat work is verified and a controlled resume gate is recorded.
- PostgreSQL owns mutable state and exact artifact references. R2 owns
  immutable content-addressed artifacts. Redis/Valkey owns transient
  coordination. Local disk is disposable runtime state only.
- Reader hot paths use exact R2 keys and must not enumerate prefixes.
- `pg_stat_statements` and database counters are attribution evidence, not a
  direct substitute for the Supabase billing-period egress report. Supabase's
  `pg_stat_statements` extension and view are the preferred query-statistics
  source when access is available.
- Measurements must identify their time window, process topology, workload,
  sample size, and whether the observation is local, hosted, or provider-shaped.
- Timing labels and metric dimensions are bounded to fixed stage, operation,
  provider, model, activity type, and error-code values. They must not include
  arbitrary URLs, prompts, tokens, or chapter text.
- Configuration changes require a before/after value description, rationale,
  rollback value, and environment scope. Secret-bearing values are operator
  inputs and never belong in this specification.
- A failed or unavailable external measurement is recorded as unavailable,
  not converted into a success claim.

## Decision Log

| ID | Decision | Alternatives considered | Rationale | Owner | Date |
| --- | --- | --- | --- | --- | --- |
| D-001 | Use existing provider, R2, activity, and application metrics first, adding only bounded stage timers required to close an evidence gap | Rely on unstructured logs or introduce a new telemetry platform | Existing instrumentation is already part of the runtime and keeps the change small and auditable | Project owner | 2026-08-23 |
| D-002 | Capture a read-only baseline before resuming the worker | Resume the worker and measure after the fact | The worker was stopped because its previous workload was associated with excessive Supabase egress | Project owner | 2026-08-23 |
| D-003 | Apply `load_only()` or `defer()` and per-job caching only when the measured consumer contract and regression tests prove the selected fields are sufficient | Globally change ORM defaults or remove columns | Narrow projections reduce egress without silently breaking write or serialization paths | Project owner | 2026-08-23 |
| D-004 | Treat query-plan or index changes as a separate database-change approval | Add indexes opportunistically during an operational audit | Schema changes have migration, lock, rollback, and production-impact consequences beyond configuration tuning | Project owner | 2026-08-23 |
| D-005 | Use isolated R2 prefixes for any integration writes and never use production novel prefixes | Exercise destructive operations against canonical objects | The audit must measure R2 behavior without risking the R2-only content set | Project owner | 2026-08-23 |
| D-006 | Rank recommendations by measured egress reduction first, latency second, and implementation effort third | Rank by code convenience or intuition | The stated objective is cost and resource containment while preserving correctness | Project owner | 2026-08-23 |
| D-007 | Require a controlled canary before processing all three URLs | Start the entire bulk queue immediately after rebuild | A bounded workload limits provider, database, and R2 exposure while the measurements are still being validated | Project owner | 2026-08-23 |
| D-008 | Use the current Supabase billing cycle plus a fresh bounded UTC before/after workload window, with Supabase Reports as billing authority and `pg_stat_statements` as supporting query evidence | Use cumulative counters alone or infer billing egress from local tests | The two sources answer different questions and must remain separately labeled | Project owner | 2026-08-23 |
| D-009 | Use conservative canary stops: stop immediately for integrity, unauthorized mutation, R2 hot-path `LIST`, provider quota/auth failure, or database failure; stop for sustained resource rates above twice the pre-canary baseline across two five-minute observations | Set an arbitrary absolute GB limit or allow retries to continue indefinitely | Relative thresholds adapt to the measured deployment while protecting the currently exhausted egress budget | Project owner | 2026-08-23 |
| D-010 | Permit generated isolated-prefix R2 test writes, require cleanup after each test and a final zero-object sweep, and never write production novel prefixes | Keep all R2 testing read-only or test canonical objects | The owner authorized read/write testing, but cleanup and prefix isolation prevent test artifacts from becoming content or cost debt | Project owner | 2026-08-23 |
| D-011 | Document missing-index findings and defer schema changes to a separately approved migration | Create indexes during the audit without a migration gate | Query-plan evidence can be preserved without expanding this operational/configuration change into an unapproved schema change | Project owner | 2026-08-23 |
| D-012 | Stop the full-queue canary at a safe checkpoint and replace it with a bounded per-source sample before any scale projection | Let a long retry-heavy queue run until terminal and treat elapsed time as a capacity test | The fourth run reached only one source, added little terminal progress, and consumed an hour-scale observation window without isolating stage or query cost; a small sample produces more useful evidence with bounded provider and database exposure | Project owner | 2026-08-23 |

## Requirements

### Functional Requirements

1. REQ-001: Baseline evidence — record the worker state, Compose topology, relevant configuration key names, measurement window, current project bucket names, and available Supabase/R2 telemetry without exposing secrets or mutating data.
2. REQ-002: Pipeline timing — measure source fetch, raw parsing, metadata loading, glossary loading, provider request and retry time, chunk concurrency, token usage, QA, R2 transfer, PostgreSQL commit, and activity-state update durations with activity/job/chapter correlation.
3. REQ-003: Worker behavior — identify event-loop blocking calls, queue claim time, idle polling, lease renewal, retry waits, synchronous provider or storage work, and activity queue age for the measured workload.
4. REQ-004: Supabase/PostgreSQL usage — identify high-call or high-payload queries, large JSON-column hydration, repetitive novel/glossary/activity reads, pool checkout or saturation signals, connection route, and index/query-plan risks.
5. REQ-005: R2 usage — count `PUT`, `GET`, `HEAD`, and `LIST` operations, measure logical and compressed bytes, record content-address reuse and redundant operations, prove that reader hot paths do not use `LIST`, and delete every generated audit-prefix test object after verification.
6. REQ-006: Evidence-backed optimization — verify or implement the smallest safe projection, metadata/glossary cache, atomic claim, idle-backoff, and timestamp-only heartbeat improvements required by the evidence, preserving lease, retry, transaction, and artifact-reference semantics.
7. REQ-007: Configuration changes — adjust only justified settings or environment mappings for concurrency, batch size, timeouts, polling, lease, pool, or R2 behavior, with environment scope, rollback values, and no fabricated external credentials.
8. REQ-008: Safe observability — keep timing and resource evidence bounded, sanitized, reproducible, and free of prompts, provider responses, credentials, raw viewer identifiers, IP addresses, and arbitrary high-cardinality labels.
9. REQ-009: Verification — add or update focused tests for changed behavior, run the relevant backend lint/type/test checks, exercise R2 only through an isolated namespace when enabled, and record each result separately.
10. REQ-010: Documentation — synchronize affected Markdown and the R2 plan with measured evidence, completed versus incomplete checklist items, configuration rationale, operational limits, and the ranked action list.
11. REQ-011: Controlled three-novel validation — after the worker rebuild gate, process the supplied URLs one at a time or under an explicitly bounded concurrency limit, preserve identities and URLs, reach truthful terminal activity outcomes where the source/provider permits, and stop on an unapproved resource or provider threshold.

### Quality and Operational Requirements

12. REQ-012: No destructive cutover — the audit and optimization work must not empty, reset, delete, or rename either project bucket or canonical novel prefix, perform the deferred restore drill, hand-edit PostgreSQL rows, or treat a partial measurement as production acceptance. Deleting objects created under the generated isolated audit prefix after verification is explicitly allowed and required.
13. REQ-013: Evidence provenance — every measured number must state its source, interval, workload, sample size, aggregation method, and whether it is local, hosted, provider-shaped, or unavailable.

## Acceptance Criteria

- AC-001: A sanitized baseline record identifies the stopped worker, service topology, relevant configuration key names, two project bucket names, telemetry window, and protected-data boundaries; no secret value is present.
  - Maps to: REQ-001, REQ-008, REQ-012, REQ-013
  - Evidence: dated baseline report, `docker compose -f deploy/compose.yml ps -a worker` output, redacted key inventory, and recorded dashboard/query observations.
- AC-002: The audit report contains per-stage duration, count, error, concurrency, and token fields for the supplied workload, with percentile values when the sample size supports them and explicit unavailable fields otherwise.
  - Maps to: REQ-002, REQ-013
  - Evidence: sanitized timing report correlated by activity/job/chapter identifiers.
- AC-003: The worker report identifies blocking operations and records queue claim, polling, lease, retry, and heartbeat behavior, including the reason the worker may safely resume.
  - Maps to: REQ-003, REQ-006, REQ-011
  - Evidence: source trace, focused regression tests, and controlled worker observation.
- AC-004: The database report identifies top query shapes by call volume and payload risk, heavy JSON columns, repetitive reads, connection route, pool evidence, and representative query plans without exposing credentials or private row contents.
  - Maps to: REQ-004, REQ-013
  - Evidence: sanitized `pg_stat_statements` or equivalent report, Supabase billing-period egress observation, pool/query-plan captures, and query-shape tests.
- AC-005: The R2 report counts operations and bytes by operation and workload, records compression and reuse ratios, and demonstrates no `LIST` on reader or translation hot paths.
  - Maps to: REQ-005, REQ-012, REQ-013
  - Evidence: R2 operation statistics, isolated-prefix integration output, source audit, operation-count tests, and a final zero-object sweep for the generated audit prefix.
- AC-006: Measured code changes either prove the existing projections, per-job caches, atomic claims, polling backoff, and heartbeat updates are sufficient or implement the smallest missing correction, with regression coverage for required fields and state transitions.
  - Maps to: REQ-006
  - Evidence: focused diff, SQL/projection assertions, cache reuse test, claim/lease tests, and worker-loop tests.
- AC-007: Every configuration adjustment has a before value, after value, environment scope, measured rationale, rollback value, and validation result; secret values remain operator-managed and unrecorded.
  - Maps to: REQ-007, REQ-012
  - Evidence: sanitized configuration matrix, changed templates/settings, and controlled canary result.
- AC-008: Observability output has bounded labels and contains no secret, prompt, response, raw token, IP, or arbitrary URL/chapter text.
  - Maps to: REQ-008, REQ-012
  - Evidence: metric/log schema review, redaction tests, and sanitized sample output.
- AC-009: Focused backend tests, Ruff, Pyright, relevant broader tests, Markdown link checks, and isolated R2 checks when configured pass with exact results recorded; no recovery-drill success is claimed.
  - Maps to: REQ-009, REQ-012
  - Evidence: command log with exit codes, counts, skipped external checks, and test paths.
- AC-010: All affected Markdown and the R2 plan agree with the measured implementation, list completed and incomplete items with timestamps, and contain the prioritized action table.
  - Maps to: REQ-010, REQ-013
  - Evidence: final Markdown audit, plan checkpoint, relative-link audit, and documentation diff.
- AC-011: The controlled validation preserves all three existing identities and URLs, records terminal activity outcomes and truthful chapter failures, and stops before any unapproved egress/provider/data threshold is exceeded.
  - Maps to: REQ-011, REQ-012
  - Evidence: application-service activity records, URL/identity checks, sanitized chapter projections, and canary stop/resume log.

## Acceptance Coverage

| Acceptance criterion | Task ID(s) | Evidence | Status |
| --- | --- | --- | --- |
| AC-001 | T-001 | Stopped-worker baseline, protected-surface inventory, two bucket names, sanitized telemetry, and no canonical mutation recorded. | Complete |
| AC-002 | T-002 | Bounded stage timing schema and explicit unavailable reasons are covered by timing tests; live percentiles remain unavailable outside a terminal sample. | Complete — unavailable fields named |
| AC-003 | T-003, T-010 | Claim, polling, lease, retry, heartbeat, and synchronous blocking risks are documented and tested; the bounded one-chapter samples completed through the worker path and the full-queue safety decision is recorded. | Complete — full-queue safety decision |
| AC-004 | T-004 | Query-family, heavy-column, pool-route, plan, and Supabase Shared Pooler Egress evidence is recorded; the exact query-level byte boundary is explicit. | Complete — query-level byte boundary |
| AC-005 | T-005 | Isolated R2 operation/byte/reuse counters, cleanup sweep, and no-hot-path-LIST audit passed. | Complete |
| AC-006 | T-006, T-007 | Narrow ORM projections, one-job cache reuse, activity-row reuse, claim recovery flush, and R2 readiness HEAD have focused and full regression coverage; the bounded impact boundary is recorded. | Complete — bounded optimization decision |
| AC-007 | T-008 | Sanitized before/after configuration matrix records an evidence-backed no-op and rollback as no action. | Complete |
| AC-008 | T-002, T-009 | Bounded timing fields, redaction tests, full suite, and static review passed without protected values. | Complete |
| AC-009 | T-009, T-012 | Focused/full backend validation, Ruff, Pyright, link audit, architecture guard, Compose validation, isolated R2 cleanup, encrypted restore, and independent R2 readback are recorded. | Complete |
| AC-010 | T-011, T-012 | Active performance, work, translation, and R2-plan documentation records the measured route, projections, recovery evidence, canary outcome, staged reader decision, and safety boundaries. | Complete |
| AC-011 | T-010 | The three existing identities were preserved; one application-service sample activity per source reached `completed`, and application-service artifact readback returned present for all three selected chapters. The original full-queue activities remain paused by the scale decision. | Complete — bounded validation and safety stop |

## Open Questions and Approval

- OQ-001: Resolved — use the current Supabase billing cycle and a fresh bounded
  UTC before/after workload window. Supabase Reports is billing authority;
  database counters and `pg_stat_statements` are supporting evidence.
- OQ-002: Resolved — the extension is PostgreSQL `pg_stat_statements`, which
  exposes the `pg_stat_statements` view. Check access in the target project;
  fall back to sanitized application instrumentation if privileges prevent
  reading it.
- OQ-003: Resolved — stop immediately for integrity failure, unauthorized
  mutation, hot-path `LIST`, provider quota/auth failure, or database failure.
  Stop for resource rates above twice the pre-canary baseline across two
  five-minute observations.
- OQ-004: Resolved — generated isolated-prefix R2 reads and writes are
  authorized. Delete test objects after each test and perform a final
  zero-object sweep before completion.
- OQ-005: Resolved — document missing-index findings only. A schema/index
  migration requires a separate approval and specification.
- Approval condition: The project owner approves this Draft specification and
  resolves the operational open questions before T-010 or any external
  mutation.
- Continuation result: encrypted backup creation, isolated restore validation,
  and independent R2 snapshot readback are complete and recorded. Production
  readiness acceptance remains outside this bounded audit and is reported by
  its measured gate result rather than silently waived.
