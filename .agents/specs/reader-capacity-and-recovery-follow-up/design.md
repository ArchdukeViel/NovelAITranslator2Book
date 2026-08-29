# Reader Capacity and Recovery Operational Follow-up Design

Spec ID: reader-capacity-and-recovery-follow-up
Version: 0.4.1
Status: Approved
Updated: 2026-08-29

## Source of Truth Mapping

- Primary architecture: `AGENTS.md` and `docs/ARCHITECTURE.md`.
- Operational contracts: `docs/OPERATIONS.md`, `docs/CONFIGURATION.md`, and
  `docs/DEPLOYMENT.md`.
- Performance budgets and prior method: `docs/PERFORMANCE_AUDIT.md` and
  `docs/PERFORMANCE_ACTION_PLAN.md`.
- R2 and recovery boundaries: `docs/STORAGE.md`, `docs/R2-ONLY-CONFORMANCE.md`,
  and `docs/R2-Only Content Storage Rearchitecture-plan.md`.
- Existing implementation inputs: `backend/tests/run_phase6_acceptance.py`,
  `backend/tests/capacity_harness.py`, `tools/capacity/run_reader_load.ps1`,
  `novelai.services.runtime_telemetry`,
  the public reader services/routers, `R2Storage`,
  `R2IncrementalBackupTarget`, `BackupService`,
  `DatabaseBackupService`, `SchedulerService`, `OperatorAlertService`, and
  the spec-owned evidence validator under `tools/capacity/`, plus the
  managed-services verification workflow (whose referenced test paths must be
  checked at the candidate revision before its result is accepted).
- Related approved specs used for boundary context only:
  `.agents/specs/pipeline-async-execution-and-capacity/` and
  `.agents/specs/pipeline-resource-efficiency-audit/`. Their historical
  completion records do not satisfy this new spec's tasks.

Architecture wins if any source conflicts. This design does not authorize a
production deployment, secret mutation, schema migration, bucket operation,
worker restart, full-queue run, or higher-stage load.

## System Architecture & Component Interaction

```text
direct service probe ───────────────┐
Caddy loopback probe ───────────────┼─> route profile harness
Cloudflare Tunnel/CDN probe
                                            ├─> Caddy access/proxy evidence
                                            ├─> reader/backend request telemetry
                                            ├─> DB pool/query and exact-R2 timing
                                            └─> sanitized stage report

hosted dashboards + container snapshots ───> timestamped telemetry matrix

backup scheduler ─> R2/DB backup services ─> manifest/checksum/restore checks
       │                                      │
       └────────> stale/failure alert ───────┴─> recovery owner/escalation
```

The public reader remains a GET-only public surface. Measurement is performed
by an external or operator-controlled probe and by internal redacted metrics;
it does not add tracing data to public responses. The direct and Caddy probes
must use the same revision, route fixture, request shape, timeout, concurrency,
and cache state for comparison. The Cloudflare probe uses the owner-approved
non-production development hostname and must not expose that target in
committed evidence.

`backend/tests/capacity_harness.py` is a deterministic synthetic contract
harness. Its tests can prove configuration, boundedness, and redaction rules,
but its generated latency values are not live reader evidence and cannot be
used as the route-profile or 1k-stage result.

### Route and path matrix

| Route family | Canonical request shape | Direct boundary | Caddy boundary | Cloudflare boundary | Gate |
|---|---|---|---|---|---|
| Liveness | `/health/live` | Reader/backend process | Caddy public path | Cloudflare HTTPS tunnel path | p95 <= 100 ms |
| Catalog | `/api/public/catalog?page=1&page_size=24` | Reader | Caddy public path | Cloudflare HTTPS tunnel path | p95 <= 500 ms |
| Detail | Published novel detail by opaque fixture slug | Reader | Caddy public path | Cloudflare HTTPS tunnel path | p95 <= 300 ms |
| Chapter | Published translated chapter by opaque fixture identifiers | Reader | Caddy public path | Cloudflare HTTPS tunnel path | p95 <= 750 ms |
| Search | Catalog query and tag-search route families | Reader | Caddy public path | Cloudflare HTTPS tunnel path | p95 <= 500 ms |

The exact fixture slug, chapter identifier, host, and credentials are supplied
at runtime through protected operator configuration and never copied into the
report. The selected campaign fixture is an existing published record, bound
by an opaque `fixture-<16 lowercase hex>` digest derived from the supplied
slug/chapter pair. The preflight and runner must carry the same digest; a
missing or mismatched binding blocks the run. Readiness is sampled as a
diagnostic and retains its expected degraded state while the worker is stopped;
it is not substituted for liveness or a reader-content route.

### Execution identities and gate semantics

Each execution is a `campaign_id` containing one or more `run_id` values. The
campaign records `baseline_revision` and, after T-006, an optional
`candidate_revision`. A run is bound to one route family, topology, cache
state, and one revision. The same opaque
`fixture_binding_id` must be supplied to every topology run; the runner must
pass the fixture explicitly and must not auto-select the first catalog item
per URL. The binding is verified at runtime without writing the slug, chapter
identifier, response body, or host into evidence.

The topology aliases have these meanings:

| Alias | Measurement meaning | Evidence role |
|---|---|---|
| `direct_service` | Controlled request to the reader service boundary, bypassing Caddy | Diagnostic attribution |
| `caddy_loopback` | Request through the local Caddy public route with an explicit Host binding | Diagnostic; unavailable when the binding is absent |
| `cloudflare_tunnel` | Request through the owner-approved HTTPS Cloudflare Tunnel/CDN development route to Caddy | Current non-production reader SLO gate |

The runtime command must record the target alias, a redacted target class, and
TLS verification mode. A comparison target may be omitted only when the
report contains an explicit allowlisted unavailable reason; the selected SLO
gate target may never be omitted. The command must never copy a host, URL,
token, certificate detail, or IP into the report.

Allowlisted unavailable reasons include `target_not_configured`,
`caddy_host_binding_unavailable`,
`cloudflare_tunnel_unavailable`, `direct_service_unavailable`,
`tls_verification_unavailable`, `cold_cache_control_unavailable`,
`provider_metric_unavailable`, `pooler_metric_unavailable`,
`r2_metric_unavailable`, and `alert_delivery_unavailable`. Free-form reasons
may be stored only in a separately redacted operator note; they are not report
labels.
Exactly one Caddy-routed alias is selected as `slo_gate_topology` in the
baseline. That selected route is the only route used to decide
`reader_slo_status`; direct service is never a gate. The other Caddy/Cloudflare
result and direct result are required comparison evidence but do not silently
create a second SLO budget.

Required route families are exactly `health_live`, `catalog`, `detail`,
`chapter`, and `search`. `health_ready`, `ranking_daily`,
`ranking_weekly`, `ranking_monthly`, and `home` are diagnostic auxiliary
routes. Auxiliary failures are reported and can create a quantified blocker,
but they do not change the required-route SLO calculation unless the owner
explicitly promotes one into a new named gate.

Warm and cold are controlled states, not labels chosen after the run:

- `warm` means the declared warmup and cache-readiness procedure completed
  before the counted samples.
- `cold` means the approved disposable-stage cache reset, isolated cache
  namespace, or other documented cache-miss procedure completed before the
  counted samples. A single first request is not sufficient evidence.
- `unknown` means the state could not be controlled or verified. It is an
  unavailable cell and cannot be counted as warm or cold.

The default target is at least 50 valid latency samples for each required
route, topology, and cache state. The runner may attempt more than 50 requests
to reach that target, but it must record a finite `max_attempts_per_cell` and
stop with an incomplete-cell blocker when the target is not reached. A warmup
request is excluded from `sample_count`. The selected Caddy-routed SLO gate
uses its cells; all other cells are comparison evidence.

## Measurement Protocol

1. Capture the baseline and confirm the worker service, original full queue,
   and other writers are stopped/paused. Verify the current image/revision,
   route inventory, gate topology, fixture binding, and declared stop
   thresholds.
2. Establish the approved cache-state method. Run the warm procedure and the
   controlled cold procedure separately; never infer cold from the first
   request or from a cache header that was not verified by the serving layer.
3. For each available topology alias, run the same required route set with the
   same fixture binding, revision, request shape, timeout, concurrency, and
   sample targets. An unavailable direct/Cloudflare target produces an explicit
   unavailable matrix cell, not a process failure. Keep topology and
   cache-state samples in separate reports and do not merge their percentile
   distributions. The disposable Cloudflare workflow must first obtain HTTP
   200 from the isolated `/health/live` route through the ephemeral tunnel;
   the same run may collect Caddy loopback cells with an explicit Host binding
   as diagnostic comparison evidence.
4. Use a deterministic percentile method (nearest-rank over completed request
   durations in milliseconds). Record attempted, completed, valid-latency,
   status, error, timeout, and transport-error counts separately, plus coarse
   sanitized error-class counts when the runner exposes error names. Any
   timeout, transport error, incorrect response, or incomplete required cell
   prevents that Caddy gate cell from passing even if its p95 is below budget.
5. Capture application, proxy, database, storage, container, and hosted
   snapshots over the same UTC interval. T-004 may create a pre-remediation
   telemetry window joined to T-002; T-007 must append a post-remediation
   stage window joined to its run. Link each snapshot to the campaign, run,
   revision, topology, phase, and workload. A snapshot is not a billing
   attribution unless the provider labels it as such for that interval.
6. Compare route layers using non-overlapping timing fields and classify the
   largest contributor before changing code or configuration. If the evidence
   is mixed or unavailable, record the uncertainty and stop the remediation
   branch.
7. Validate the generated artifact schema and semantic postconditions before
   changing a task state. A valid `blocked` result is evidence of a safety
   decision only when its quantified blocker record is complete.

## Data Contracts & Schemas

### Reader route sample

The sanitized sample/report contract is additive and internal. It uses fixed
enums, deterministic aggregation, and bounded values. A route record describes
one campaign/run/topology/cache-state cell:

```json
{
  "schema_version": 1,
  "campaign_id": "opaque-campaign-id",
  "run_id": "opaque-run-id",
  "fixture_binding_id": "opaque-fixture-binding",
  "interval_start": "UTC timestamp",
  "interval_end": "UTC timestamp",
  "revision": "immutable revision label",
  "topology": "direct_service|caddy_loopback|cloudflare_tunnel",
  "tls_verification_mode": "verified|approved_disposable_insecure|not_applicable",
  "gate_role": "slo_gate|diagnostic",
  "route": "health_live|catalog|detail|chapter|search",
  "cache_state": "warm|cold|unknown",
  "cache_control_method": "warmup_only|disposable_reader_reset|unavailable",
  "cache_reset_proof_id": "opaque-reset-proof-or-null",
  "max_attempts_per_cell": 100,
  "sample_target": 50,
  "sample_count": 50,
  "completed_count": 50,
  "valid_latency_count": 50,
  "error_count": 0,
  "timeout_count": 0,
  "transport_error_count": 0,
  "error_class_counts": {
    "connect": 0,
    "transport": 0,
    "timeout": 0,
    "redirect": 0,
    "other": 0
  },
  "status_counts": {"200": 50},
  "expected_status": 200,
  "response_contract_status": "valid|invalid|unavailable",
  "body_nonempty": true,
  "percentile_method": "nearest_rank_completed_ms",
  "p50_ms": 0,
  "p95_ms": 0,
  "p99_ms": 0,
  "response_bytes_p95": 0,
  "layer_timings_ms": {
    "proxy_connect": {"p50": 0, "p95": 0, "p99": 0, "count": 50},
    "proxy_upstream": {"p50": 0, "p95": 0, "p99": 0, "count": 50},
    "application": {"p50": 0, "p95": 0, "p99": 0, "count": 50},
    "db_checkout": {"p50": 0, "p95": 0, "p99": 0, "count": 50},
    "db_statement": {"p50": 0, "p95": 0, "p99": 0, "count": 50},
    "db_commit": {"p50": 0, "p95": 0, "p99": 0, "count": 50},
    "r2_exact_read": {"p50": 0, "p95": 0, "p99": 0, "count": 50},
    "serialization": {"p50": 0, "p95": 0, "p99": 0, "count": 50},
    "network_remainder": {"p50": 0, "p95": 0, "p99": 0, "count": 50}
  },
  "r2_exact_read_count_p95": 0,
  "r2_bytes_read_p95": 0,
  "unavailable_fields": [],
  "provenance": "application_interval"
}
```

Every layer timing object must either contain the same aggregation/count
semantics or be represented in `unavailable_fields` with a bounded reason. A
network remainder is valid only when its operands use the same clock and
non-overlapping boundaries; negative or otherwise invalid values are
unavailable. The sample contract does not carry a raw path, query, slug,
chapter id, SQL statement, storage key, body, cookie, request header, host, or
IP address. The report stores route-family enums and opaque identifiers only.

### Hosted telemetry snapshot

Each source record contains `campaign_id`, `reader_run_id` when applicable,
`phase` (`pre_remediation` or `stage_1000`), `source`, `source_timestamp`,
`interval_start` and `interval_end`, `revision`, `topology`, `workload`,
`metric_name`, `value` or `unavailable_reason`, `sample_count`,
`aggregation`, `collection_status`, and `provenance`. Allowed provenance is:

```text
hosted_billing_actual | database_cumulative | application_interval |
reader_http_sample | provider_dashboard | local_synthetic | unavailable
```

`metric_name` is an allowlisted fixed label, not arbitrary provider metadata.
The minimum names are `reader_http_rps`, `translation_provider_rps`,
`db_pool_wait_ms`, `db_statement_ms`, `db_pool_occupancy`, `r2_read_count`,
`r2_read_bytes`, `r2_read_ms`, `r2_operation_count`, `r2_billed_bytes`,
`provider_quota_remaining`, `caddy_upstream_errors`, `caddy_upstream_retries`,
`application_request_count`, `container_cpu`, `container_memory`,
`container_network_bytes`, `redis_queue_depth`, and `worker_state`. A source
may mark an allowlisted metric unavailable, but it may not introduce an
unbounded label to avoid the unavailable state.

Supabase query count/rows and `pg_stat_*` data remain cumulative database
indicators. R2 operation/billed-byte values remain unavailable unless the R2
provider or operator dashboard exposes them for the exact interval. Provider
quota data is recorded separately from reader HTTP data; no provider call is
generated by a reader-only run. A hosted record with no matching campaign,
interval, revision, or topology is `unavailable` for attribution and cannot be
joined by assumption.

### Recovery control record

The recovery evidence uses one record per database or R2 backup class:

```text
control_class, observed_at, schedule_source, schedule_timezone,
freshness_max_age_seconds, last_success_at, next_due_at, freshness_status,
manifest_verified, checksum_verified, referenced_objects_verified,
retention_status, last_restore_verified_at, alert_failure_threshold,
alert_cooldown_seconds, alert_status, alert_delivery_status, owner_role,
credential_scope_review, cleanup_status, unavailable_reason
```

`control_class` is a fixed enum such as `database_backup`, `r2_snapshot`, or
`database_restore_verification`. `owner_role` is a role or operator-record
reference, not an email address. `schedule_timezone` and
`freshness_max_age_seconds` show how the threshold was derived rather than
inventing a fixed age. Alert records distinguish transition state from
delivery state and record the configured threshold/cooldown without recipient
details. Credential review records scope and result, never a token,
fingerprint that can identify a secret, or connection URL.

### 1k stage result

The stage result is a sampled profile report, not a 1,000-user load claim. It
contains the baseline/candidate revision link, profile model, sample targets,
route-level p50/p95/p99, budget,
pass/fail/block status, status counts, transport errors, timeouts,
response-size summaries, resource snapshots, linked telemetry snapshot ids,
and the full evidence provenance.

Its disposition contract is:

```text
reader_slo_status          = passed | failed | blocked
path_profile_status        = complete | partial | blocked
telemetry_status           = complete | partial | unavailable
recovery_status            = complete | partial | blocked | not_assessed
overall_follow_up_disposition = complete | complete_with_quantified_blocker | blocked
production_capacity_claim  = not_established
```

`reader_slo_status=passed` requires every required selected Caddy-routed
route/cache cell to
have complete valid samples, correct responses, no timeout/transport errors,
and a p95 within budget. `reader_slo_status=failed` means complete evidence
shows a budget or correctness failure. `reader_slo_status=blocked` means the
required evidence is incomplete or unavailable. Hosted billing or provider
quota visibility affects `telemetry_status`, not the route SLO calculation,
but any unavailable hosted field must remain a quantified blocker and the
production-capacity claim remains unestablished.

Before T-008 through T-010, the stage report uses
`recovery_status=not_assessed` and cannot claim
`overall_follow_up_disposition=complete`. The final handoff replaces
`not_assessed` with the current recovery disposition after freshness, alert,
ownership, scope-review, and restore evidence are validated.

The `blockers` array uses the NFR-006 fields: opaque id, UTC interval,
affected route/path/layer or recovery control, measured value and budget when
applicable, unavailable source/reason, owner, next action, retry/admission
condition, and safety disposition. There is no `passed_with_notes` status.

## API / Endpoint Contracts

- Existing internal `/metrics`: reuse fixed-label owner metrics. It must not be
  routed through the public reader path merely to simplify collection.
- Existing `GET /api/admin/health`: use only as owner-authenticated, redacted
  diagnostics; no secret-bearing or raw-trace output is added.
- Existing `GET /api/admin/maintenance/status`: use durable scheduler state to
  distinguish `never_run`, `running`, `succeeded`, `failed`, and `disabled`.
- Existing backup and restore controls: exercise only approved isolated targets
  and normal service paths. No new public endpoint is required.
- Any new operator-only endpoint required by implementation must be
  owner-authenticated, CSRF-protected where cookie-authenticated, redacted, and
  covered by focused tests. A public response contract change is out of scope.

The existing `run_reader_load.ps1` may be reused only after its result logic is
adapted to the contracts above. In particular, a fixed pair of known telemetry
blockers must not be treated as a successful overall result merely because the
workload process exited zero. Runner process success, reader SLO status,
telemetry status, and overall follow-up disposition are separate fields and
must be computed independently.

## Latency Attribution and Remediation Decision

The report compares non-overlapping intervals where the implementation permits
it. It must not add nested timings twice. A network remainder may be computed
only when all operands are measured on the same clock and have a documented
boundary; otherwise it is `unavailable`.

The bottleneck classification is:

| Class | Evidence pattern | Allowed action |
|---|---|---|
| Local application | Direct service is slow and internal stage time explains the delay | Small code/config fix with focused regression tests |
| Proxy or deployment | Direct service is within budget but Caddy/Cloudflare path adds the delay | Reversible proxy/deployment correction after owner approval |
| Hosted dependency | DB/R2/Cloudflare edge interval dominates and provider evidence is available | Operator/provider action or quantified blocker; no speculative app rewrite |
| Mixed/unavailable | Measurements overlap, conflict, or required hosted data is missing | Preserve current behavior and record an explicit blocker |

Any correction records the before value, after value, environment scope,
rollback value, expected effect, and validation result. It must preserve
projection-first public reads, exact R2 references, no-hot-path `LIST`, health
contracts, database connection arithmetic, cache invalidation, and public
availability/isolation behavior.

## State Machines & Transitions

```text
Draft
  -> EvidenceContractsVerified
  -> BaselineCaptured
  -> Profiled
  -> Attributed
  -> RemediationVerified
  -> RerunDispositioned
       |-> RecoveryControlsVerified -> HandoffComplete
       `-> QuantifiedBlocked --------> RecoveryControlsVerified -> HandoffComplete
```

`RerunDispositioned` is not synonymous with an SLO pass. It is reached only
after the report contains the independent SLO, path, telemetry, recovery, and
production-capacity statuses. A quantified blocker may complete the authorized
decision branch, but it cannot transition to `reader_slo_status=passed` or
`production_capacity_claim` other than `not_established`.

The operational safety state is independent:

```text
WorkerPaused / FullQueuePaused / WritersPausedAsDeclared
  -> remains true during T-000..T-012
  -> WorkerResumeAuthorized only by a separate owner decision after
     RerunDispositioned and outside this spec
```

Recovery controls use:

```text
Fresh -> Due -> Succeeded -> Fresh
  \-> Stale or Failed -> Alerted -> Restored/Verified -> Fresh
                                      \-> Blocked
```

No checked task, historical paragraph, or local fixture can transition a
runtime gate to `passed` without the required current evidence.

## Backup, Restore, and Credential Operations

- Use the existing `BackupService`, `DatabaseBackupService`, scheduler,
  `R2IncrementalBackupTarget`, and alert service boundaries. Do not bypass them
  with direct SQL, direct object deletion, or hand-edited runtime state.
- The recovery owner and escalation role must be recorded in the baseline before
  T-008 or T-009 begins. If no accountable owner is assigned, the recovery
  branch is blocked even when backup objects exist.
- Derive freshness thresholds from the configured schedule and record the
  schedule source. Do not invent a shorter threshold merely to create an alert
  or a longer threshold to avoid one.
- A database restore targets a disposable isolated PostgreSQL database. R2
  restore targets an isolated prefix or test bucket. Verify manifest-last
  commit, checksums, byte lengths, referenced objects, Alembic head, tables,
  constraints, representative application queries, and public isolation.
- The restore record must identify the committed snapshot/backup by a
  redacted opaque reference, the isolated target class, the verifier method,
  UTC start/end, and cleanup status. It must separately record backup creation
  freshness and restore-verification freshness.
- The managed-services workflow is an evidence producer only when its checkout
  test paths exist and its run is tied to the candidate revision. A workflow
  that names a missing or renamed test is a CI-evidence blocker; local test
  success must not be relabeled as hosted restore success.
- The managed-services workflow must invoke the current backup and isolated
  restore integration paths and use the credential variable names consumed by
  those tests. The current PostgreSQL contract expects migration head
  `e7f1a9c3b5d2`; an older head is a stale-database failure, not a pass.
- A stale or failed alert must be tested through the configured operator
  delivery path when the owner authorizes a real delivery test. If delivery is
  unavailable, retain the alert record and mark delivery evidence unavailable.
- Review separate application CRUD, snapshot-read, database-backup, and
  backup-target-write scopes. Session, provider, and unrelated credentials are
  excluded unless separately authorized.
  Actual rotation is a maintenance-window operation: pause affected writers,
  rotate one scope at a time, validate masked health/readback, retain rollback
  authority until verification, and record only the sanitized result.

## Failure Modes & Invariants

- **Worker unexpectedly running**: stop the worker using the documented bounded
  command, capture the state, and do not continue the reader run until the
  original queue and writer state are reviewed.
- **Caddy connection refusal or stale upstream**: classify as deployment
  availability evidence, not route latency; stop the comparison and repair the
  current revision before rerunning.
- **Database pool or R2 provider failure**: record status/error class and the
  relevant provider interval; do not retry indefinitely or convert it into a
  latency percentile.
- **Hosted metric unavailable**: emit `unavailable` with source and reason;
  never use zero or a local estimate as billing/capacity evidence.
- **Unexpected mutation or content exposure**: stop immediately, preserve
  evidence, disable the affected operation if possible, and follow the
  incident/rollback runbook.
- **Restore or credential-scope failure**: keep the production target
  untouched, preserve the isolated target for review, and record a blocked
  recovery gate.
- **Alert delivery failure**: retain durable failure/freshness state and do not
  call the recovery control complete.
- **Fixture or path mismatch**: stop the campaign, discard no evidence, mark
  the affected cell invalid, and do not compare percentiles from different
  fixtures or target classes.
- **Incomplete sample cell**: preserve attempted/error/timeout counts, mark the
  cell unavailable, and do not fill a missing percentile with zero or a local
  estimate.
- **Invalid artifact postcondition**: keep the task pending or blocked until
  the schema/semantic validator passes; a successful process exit alone is not
  sufficient.

System invariants:

- The worker and original full translation queue remain stopped/paused.
- Public reader reads remain projection/manifest-first and never use R2 `LIST`
  on the hot path.
- PostgreSQL owns exact artifact references; R2 owns immutable content; local
  runtime files are disposable.
- `translation_provider_rps` and `reader_http_rps` are separate measures.
- No secret, raw content, private row, storage key, IP address, or trace is
  emitted into evidence.
- Historical records remain historical; current status is supported only by
  current timestamped evidence.

## Traceability

| Requirement | Acceptance criterion | Planned tasks | Design element |
|---|---|---|---|
| REQ-001, REQ-004, REQ-011 | AC-001, AC-004, AC-011 | T-000, T-001, T-004 | Evidence schemas, baseline, and provenance protocol |
| REQ-002 | AC-002 | T-000, T-002 | Executable route, path, and cache-state matrix |
| REQ-003, REQ-004, REQ-007 | AC-003, AC-004 | T-003, T-004 | Non-overlapping layer timings and hosted snapshot contracts |
| REQ-005 | AC-005 | T-005, T-006 | Bottleneck classification and rollback decision |
| REQ-006, REQ-010 | AC-006, AC-007 | T-007 | Independent 1k-profile dispositions and safety state machine |
| REQ-008 | AC-008 | T-008, T-009, T-010 | Recovery control, owner, and restore flow |
| REQ-009 | AC-009 | T-001, T-010 | Credential and ownership procedure |
| REQ-011 | AC-010, AC-011 | T-011, T-012 | Validation and documentation handoff |
