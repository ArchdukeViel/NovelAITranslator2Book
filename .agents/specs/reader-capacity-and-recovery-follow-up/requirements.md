# Reader Capacity and Recovery Operational Follow-up Requirements

Spec ID: reader-capacity-and-recovery-follow-up
Version: 0.4.1
Status: Approved
Updated: 2026-08-29
Requester: Project owner
Owner: Project owner with implementation agent
Target project or release: Current split deployment after the quantified 1k reader-stage stop

## Context and Problem

The follow-up now has a confirmation-gated disposable execution path. Workflow
rerun [33251479814](https://github.com/ArchdukeViel/NovelAITranslator2Book/actions/runs/33251479814)
seeded the explicit published reader fixture into the managed test database and
dedicated test R2 bucket, started an isolated runtime, captured a safety
baseline, waited for an ephemeral Cloudflare quick tunnel to return HTTP 200
from `/health/live`, and completed cleanup. The report validators accepted the
resulting 60-cell matrix and twenty cold-reset proofs. The 20 Cloudflare cells
attempted 1,000 read-only requests with 850 valid samples, zero transport
errors, 144 timeouts, and over-budget/incomplete required cells. The 20 Caddy
loopback diagnostic cells attempted another 1,000 requests with 750 valid
samples and 180 timeouts. The result is therefore a quantified stop rather
than a capacity pass:
`reader_slo_status=blocked`, `path_profile_status=blocked`,
`telemetry_status=unavailable`, `recovery_status=not_assessed`, and
`production_capacity_claim=not_established`. The worker remained stopped;
queue/writer observation remained unknown; and production content, R2, and
provider surfaces were not used. The readiness gate removes the prior tunnel
startup ambiguity but does not establish route-budget or production capacity.

## Goal

Produce a reproducible, sanitized, operator-owned evidence package for five
operational follow-ups: route-level reader profiling, latency attribution,
evidence-backed remediation with a gated 1k-profile rerun, timestamped hosted
telemetry, and recurring backup/recovery operations. The `1k` label identifies
the existing 1,000-DAU-equivalent profile; it is not a claim that 1,000 users
or sustained production traffic were generated. The result must distinguish a
reader SLO disposition from telemetry availability and production-capacity
admission. It must either pass the declared reader route budgets after
remediation or leave a quantified, actionable blocker, and it must never
convert unavailable telemetry or a bounded stop into a production-capacity
claim.

## Scope & Boundaries

### In Scope

- Profile liveness, catalog, novel detail, chapter, and search route families
  separately through the direct service boundary, Caddy, and the Cloudflare
  Tunnel/CDN path. Readiness is a diagnostic health signal because a
  deliberately stopped worker may make it degraded; it is not a reason to
  resume the worker.
- Attribute elapsed time across proxy connection/upstream handling, backend or
  reader request handling, database pool checkout and statement execution,
  exact R2 reads, cache/fallback behavior, response serialization, and the
  measured network remainder.
- Select and implement only the smallest safe local code or configuration
  correction supported by the measured bottleneck, with focused regression
  coverage, then rerun only the 1k reader stage.
- Capture timestamped application, Caddy, container CPU/memory, database and
  pooler, Supabase, R2, provider, and Redis/queue observations where they are
  available. Mark unavailable fields explicitly with a reason and provenance.
- Establish recurring backup freshness checks, stale-backup alerts, isolated
  restore verification, credential least-privilege and rotation procedures,
  and an assigned recovery owner recorded without personal secret data.
- Update the affected canonical operational/performance documents and create
  sanitized evidence artifacts after the operational tasks actually run.
- Create machine-checkable evidence and postcondition validation for every
  artifact-producing task; a file's existence or a planning checkbox is not
  evidence of valid content.

### Out of Scope

- 10k or 100k reader stages, the original full translation queue, provider
  volume testing, or worker resumption before the 1k gate and explicit owner
  approval pass.
- Production billing, provider quota, R2 Class A/B, egress, or reader-capacity
  claims when the underlying provider does not expose the required counters.
- Bucket reset, bucket rename, canonical R2 prefix deletion, PostgreSQL data
  edits, schema migration, or production restore. An isolated restore is
  allowed only under the authorization and safety gates in the design.
- Secret values, connection strings, `.env` contents, tokens, cookies, raw
  provider responses, prompts, source text, translated text, raw IP addresses,
  or personal contact details in code, logs, artifacts, or documentation.
- Editing `.env`, `deploy/.env`, deployment secrets, or credential values is
  forbidden; any non-secret runtime override must be separately named and
  owner-authorized outside the evidence package.
- Broad dependency upgrades, frontend redesign, public API contract changes,
  speculative cache redesign, or unrelated cleanup.
- Treating the existing active specs' checked task ledgers or historical
  checkpoint language as evidence that this new follow-up has run.

## Requirements

### Functional Requirements

1. **REQ-001: Truthful operational baseline**: Before measurement, record the
   UTC interval, campaign/run identifier, baseline revision, current topology, route and
   fixture binding method, cache-control method, worker and original-queue pause
   state, effective configuration key names without values, authorized traffic
   profile, required/diagnostic route sets, gate topology, stop thresholds, and
   protected-surface boundaries. Preserve unrelated worktree changes.
2. **REQ-002: Layer-separated reader profile**: Produce comparable samples for
   the required route families through direct service, Caddy loopback, and the
   Cloudflare Tunnel/CDN path. The current campaign selects
   `cloudflare_tunnel` as the non-production reader-facing Caddy-routed SLO
   gate; loopback is diagnostic and requires an explicit Host binding. Keep
   route, path, cache state, status, payload size,
   sample count, and percentile calculations separate. Collect at least 50
   attempted and 50 valid latency samples for each required route/path/cache
   cell; a warmup request does not count. If a controlled cold state cannot be
   established, record that dimension as unavailable rather than calling it
   cold.
3. **REQ-003: Latency attribution**: Measure or explicitly mark unavailable
   proxy connect/upstream time, application time, database pool checkout,
   database statement/commit time, exact R2 operation time and bytes, cache or
   fallback counts, serialization time, and network remainder using bounded
   fixed-label telemetry correlated by opaque campaign/run/request identifiers.
   Each comparable layer reports its aggregation and clock boundary; nested
   intervals are not added twice.
4. **REQ-004: Evidence provenance and hosted boundary**: Every number states
   its campaign/run linkage, UTC interval, source, workload, sample count,
   aggregation method, topology, cache state, and provenance such as
   `application_interval`, `reader_http_sample`, `database_cumulative`,
   `hosted_billing_actual`, `provider_dashboard`, `local_synthetic`, or
   `unavailable`. Database
   cumulative counters and local byte proxies must not be presented as
   provider billing attribution. Hosted snapshots must be joinable to the
   reader run by an opaque identifier and interval without copying secrets.
5. **REQ-005: Evidence-backed remediation**: Identify the largest actionable
   contributor, implement the smallest reversible correction that preserves
   public isolation, exact R2-reference semantics, database/pool invariants,
   cache correctness, and response contracts, or document why no safe local
   correction can be made when the contributor is hosted or unavailable.
6. **REQ-006: Gated 1k-profile rerun and independent dispositions**: Rerun the
   fixed 1k profile only after the baseline, attribution, remediation decision,
   and safety gates pass. The baseline must select exactly one Caddy-routed
   acceptance topology (`caddy_loopback` or `cloudflare_tunnel`) as the reader
   SLO gate; the current baseline selects `cloudflare_tunnel` because it is the
   reader-facing non-production Cloudflare Caddy path. Direct service and the other path are
   comparison evidence and do not silently change the SLO budget. The
   post-remediation candidate revision
   may differ from the baseline revision, but every cell in one comparison run
   must use the same candidate revision and the report must preserve the
   baseline-to-candidate link. Use the declared budgets: liveness p95
   <= 100 ms, catalog and search p95 <= 500 ms, novel detail p95 <= 300 ms,
   and chapter p95 <= 750 ms. Record p50, p95, p99, status/error/timeout
   counts, payload sizes, cache state, and unavailable dimensions.

   The report must contain independent statuses:

   - `reader_slo_status`: `passed` only when every required Caddy route/cache
     cell has complete valid samples, correct responses, no timeout/transport
     errors, and passes its p95 budget; `failed` when complete evidence exceeds
     a budget; `blocked` when required evidence is incomplete or unavailable.
   - `path_profile_status`: `complete`, `partial`, or `blocked` for the direct,
   Caddy, and Cloudflare comparison matrix.
   - `telemetry_status`: `complete`, `partial`, or `unavailable` for the hosted
     and local telemetry matrix. Hosted billing/quota visibility is not required
     to call a route SLO result `passed`, but its absence prevents any capacity
     admission claim.
   - `recovery_status`: `complete`, `partial`, `blocked`, or `not_assessed` for
     freshness, alert, ownership, scope-review, and restore evidence. A stage
     report before T-008 through T-010 uses `not_assessed`; the final handoff
     must replace it with the current recovery disposition.
   - `overall_follow_up_disposition`: `complete`, `complete_with_quantified_blocker`,
     or `blocked`, based on the authorized follow-up gates and recovery work.
   - `production_capacity_claim`: always `not_established` in this spec.

   A zero-transport-error result is insufficient for any pass status.
7. **REQ-007: Timestamped hosted telemetry**: Capture provider/dashboard or
   operator evidence for Supabase pool/query/egress visibility, R2 operation
   and billed-byte visibility, provider quota visibility, application and
   proxy metrics, container CPU/memory/network snapshots, database pool
   occupancy, and Redis/queue state. Separate `translation_provider_rps`
   from `reader_http_rps`; do not infer quota or capacity from key count.
8. **REQ-008: Recurring recovery controls**: For database and R2 backups,
   verify durable last-success timestamps, manifest/checksum/reference
   validation, retention behavior, freshness thresholds derived from the
   configured schedule, stale/failure alerting, and isolated restore evidence.
   Verify that any hosted workflow or runbook references the current test and
   service paths before accepting its result. A missing or stale verification
   record is degraded/unavailable, never success.
9. **REQ-009: Recovery ownership and credential safety**: Record an assigned
   recovery owner and escalation path before any alert-delivery or restore
   task begins. Perform a least-privilege review of application CRUD,
   snapshot-read, database-backup, and backup-target-write credentials, and
   maintain a rotation procedure. Actual production token rotation requires a
   separately named operator action and must be performed without recording
   token values. Session, provider, and unrelated credentials are out of scope
   unless a separate authorization names them.
10. **REQ-010: Safe execution gate**: Keep the dedicated worker and original
    full translation queue stopped/paused throughout profiling, remediation,
    hosted telemetry collection, and the 1k reader rerun. Do not admit 10k or
    100k traffic unless the prior stage passes and a new explicit authorization
    names the traffic, stop thresholds, telemetry window, and rollback owner.
11. **REQ-011: Documentation and validation**: Record evidence and decisions in
    the canonical performance, operations, work/history, and R2-plan records
    only after verification. Every task verification command must be runnable
    at the task's completion and must assert the expected artifact schema and
    semantic postconditions, not merely a path or whitespace condition. Run
    focused tests, affected type/lint checks, documentation and workflow-path
    checks, and Graphify refresh; report exact unavailable or blocked outcomes
    without inventing completion.

### Non-Functional & Operational Requirements

1. **NFR-001: Redaction**: Telemetry and evidence use fixed bounded labels and
   opaque internal identifiers only. They omit credentials, authorization
   headers, cookies, source/translated content, raw URLs, SQL text, object
   keys, stack traces, IP addresses, and arbitrary provider metadata.
2. **NFR-002: Reproducibility**: The same revision within a comparison run,
   route fixture, cache state, traffic profile, sample target, finite
   maximum-attempt bound, concurrency, timeout, cold-cache method, and
   aggregation method can be rerun from a documented command without relying
   on hidden state. A remediation revision change is explicit and never hidden
   by comparing it as if it were the baseline revision.
3. **NFR-003: Fail closed**: Missing hosted metrics, unavailable pool/R2
   timings, stale backups, alert-delivery failure, or unresolved owner
   assignment produce a named blocker or degraded result. They cannot be
   substituted with zero, a local estimate, or a checked planning box.
4. **NFR-004: Reversibility and isolation**: Any application/configuration
   change has a recorded before/after/rollback value and is validated against
   disposable or isolated targets where it can affect data, storage, or
   recovery.
5. **NFR-005: Deterministic aggregation**: Percentiles use one documented
   method, one time unit, and one sample inclusion rule. Completed requests,
   timeout/error counts, and incomplete samples are reported separately; a
   missing percentile is never replaced with zero or an estimate.
6. **NFR-006: Quantified blocker schema**: Every blocker records an opaque
   blocker id, observed UTC interval, affected route/path/layer or control,
   measured value and budget when applicable, unavailable source/reason,
   owner, next action, retry or admission condition, and safety disposition.

## Acceptance Criteria

- AC-001: A sanitized baseline records the campaign/run identifier, revision,
  UTC window, topology, route/fixture binding, cache-control method, worker/
  queue safety state, route sets, stop thresholds, and protected-surface
  boundaries without secret values.
  - Maps to: REQ-001, REQ-004, REQ-010
- AC-002: A route matrix contains at least 50 valid warm and 50 valid cold
  samples for liveness, catalog, detail, chapter, and search through each
  declared direct-service, Caddy, and Cloudflare Tunnel/CDN path, or records a
  quantified unavailable cell. The selected Caddy-routed path is explicitly
  identified as the non-production reader-facing SLO gate; loopback requires
  an explicit Host binding and warmup requests are not counted as samples.
  - Maps to: REQ-002, REQ-004
- AC-003: For each slow route, the evidence identifies proxy, application,
  database pool/query, exact R2, serialization, and network-remainder timing
  with aggregation/count semantics and non-overlapping clock boundaries, or
  names the unavailable source and why it cannot be observed.
  - Maps to: REQ-003, REQ-004, REQ-007
- AC-004: A timestamped hosted-telemetry matrix joins to the reader campaign/
  run and interval, separates provider-visible actuals, cumulative database
  indicators, application intervals, local synthetic values, and unavailable
  fields, and makes no billing or quota claim from a proxy metric.
  - Maps to: REQ-004, REQ-007, REQ-011
- AC-005: The largest actionable contributor has either a smallest-safe
  remediation with focused regression evidence and rollback values, or a
  blocker record containing the measured value, source/reason, owner, next
  action, retry/admission condition, and safety disposition, with no
  speculative code change.
  - Maps to: REQ-005, REQ-011
- AC-006: The post-remediation 1k-profile report records the declared workload,
  gate topology, cache-state samples, required route p50/p95/p99/error/timeout/
  payload results, `reader_slo_status`, `path_profile_status`,
  `telemetry_status`, `overall_follow_up_disposition`, and
  `production_capacity_claim`. A reader SLO can be `passed` when route gates
  pass even if hosted billing is unavailable, but the overall record must then
  preserve the telemetry blocker and `production_capacity_claim` remains
  `not_established`.
  - Maps to: REQ-006, REQ-010
- AC-007: The worker remains stopped and the original full queue remains paused;
  no 10k/100k traffic, provider-volume work, canonical content mutation, or
  unapproved R2 operation occurs while this spec is executed.
  - Maps to: REQ-010
- AC-008: Database and R2 backup operations expose timestamped freshness,
  manifest/checksum/reference, retention, stale/failure alert, owner, and
  isolated restore evidence with explicit unavailable states; the owner is
  assigned before the recovery task begins.
  - Maps to: REQ-008, REQ-011
- AC-009: The operator record names a recovery owner/escalation path, and a
  least-privilege plus credential-rotation review is recorded without token
  values or personal contact details in the repository.
  - Maps to: REQ-009, REQ-011
- AC-010: Canonical performance, operations, work/history, and R2-plan records
  distinguish this spec's completed evidence, quantified blockers, historical
  provenance, and remaining gates.
  - Maps to: REQ-011
- AC-011: Focused tests, artifact/schema postcondition validators, affected
  Ruff/Pyright/frontend checks when applicable, documentation checks, and
  Graphify refresh pass with exact commands, exit codes, paths, and remaining
  risks recorded. A quantified blocker is valid evidence only when its schema
  is valid and its safety disposition is explicit.
  - Maps to: REQ-005, REQ-011

## Acceptance Coverage

| Acceptance criterion | Planned task coverage | Evidence boundary |
|---|---|---|
| AC-001 | T-000, T-001 | Baseline JSON/Markdown with sanitized configuration-key and safety state |
| AC-002 | T-000, T-002 | Route/path/cache matrix and raw-sample summary for the 1k profile |
| AC-003 | T-003, T-005 | Attribution records plus bottleneck classification |
| AC-004 | T-000, T-004, T-007, T-012 | Timestamped joined hosted/local/unavailable telemetry matrix |
| AC-005 | T-005, T-006 | Decision record, focused tests, and rollback evidence |
| AC-006 | T-000, T-007 | One post-remediation 1k-profile report or quantified blocker |
| AC-007 | T-001, T-007 | Worker/queue snapshots and no-admission record |
| AC-008 | T-008, T-009, T-010 | Freshness/alert, ownership, and isolated restore evidence |
| AC-009 | T-001, T-010 | Sanitized operator record and credential-scope review |
| AC-010 | T-012 | Canonical documentation synchronization |
| AC-011 | T-000, T-011, T-012 | Validation log, artifact postconditions, and Graphify result |

## Open Decisions and Dependencies

- The operator must authorize the hosted telemetry window, Cloudflare
  development-host traffic source, route fixture, stop thresholds, and isolated restore target
  before T-001 proceeds beyond read-only inspection.
- T-001 must select exactly one Caddy-routed `slo_gate_topology` and record why
  it represents the intended reader acceptance surface. The current approved
  baseline selection is `cloudflare_tunnel`; direct service is never an SLO
  gate. The selected topology must remain unchanged for the campaign unless a
  new baseline is captured.
- The fixture binding is an opaque `fixture-<16 lowercase hex>` identifier
  derived from the explicitly supplied published fixture and chapter. The
  preflight must record that exact identifier, and the runner must reject a
  runtime fixture that does not match the baseline. Raw slugs, chapter ids,
  hosts, and credentials remain outside evidence.
- `caddy_loopback` is diagnostic only unless `READER_CADDY_HOST_HEADER` (or
  the equivalent explicit runner argument) is supplied. A configured loopback
  URL without that binding is unavailable, not a valid fast-path sample.
- The runtime must name the direct, Caddy, and Cloudflare target aliases and the
  controlled warm/cold method. The cold state remains unavailable until a
  disposable reader/cache reset can be independently verified. If cold-cache
  control or a path cannot be
  established safely, the corresponding cell is unavailable and cannot be
  represented as a passing sample.
- The selected Caddy-routed topology is the reader SLO gate. Direct/Cloudflare
  comparisons and hosted telemetry are separate dispositions and must be joined by campaign,
  run, revision, and UTC interval before they can support remediation claims.
- The exact largest contributor is intentionally undecided until T-002 through
  T-005 produce comparable attribution. No implementation choice is implied by
  the current latency numbers.
- A successful 1k rerun does not authorize 10k/100k or worker/full-queue work;
  those remain a separate approval-gated stage.
