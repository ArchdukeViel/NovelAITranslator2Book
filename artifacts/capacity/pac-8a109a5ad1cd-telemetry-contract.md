# Sanitized pipeline observation contract

Contract version: `1`
Run/design evidence: `pac-8a109a5ad1cd`

This contract is the allowlist for pipeline and capacity evidence. It records
bounded measurements and provenance, never request contents. It applies to
local tests, worker observations, and future hosted reports.

## Fixed enums

Allowed stages:

`source_fetch`, `raw_normalize`, `metadata_load`, `glossary_load`, `selection`,
`segment`, `provider_wait`, `qa`, `persistence`, `r2_read`, `r2_write`,
`db_commit`, `activity_state`, `checkpoint`, `shutdown`.

Allowed operation classes:

`DB_READ_SCALAR`, `DB_READ_BUNDLE`, `DB_WRITE_PROGRESS`, `DB_WRITE_TERMINAL`,
`R2_EXACT_READ`, `R2_IMMUTABLE_WRITE`, `RUNTIME_CHECKPOINT`, `PROVIDER_WAIT`,
`QA`, `ACTIVITY_STATE`, `SHUTDOWN`.

Allowed outcomes are `started`, `completed`, `reused`, `skipped`, `queued`,
`rejected`, `cancelled`, `retryable_failure`, `permanent_failure`, and
`unavailable`.

## Observation fields

Every observation may contain only these fields:

```text
schema_version, audit_run_id, activity_id, job_id, novel_id, chapter_id,
stage, operation_class, outcome, duration_ms, queue_wait_ms, retry_count,
concurrency, input_bytes, compressed_bytes, rows, db_checkout_ms,
db_statement_ms, db_commit_ms, r2_operation_count, r2_bytes_read,
r2_bytes_written, input_tokens, output_tokens, translation_provider_rps,
reader_http_rps, credential_pool_size, eligible_credential_count,
quota_domain_count, credential_reservation_count, credential_pool_wait_ms,
event_loop_lag_ms, memory_bytes, error_code, unavailable_reason, timestamp.
```

Numeric values are non-negative and bounded by the producer's configured
sample limits. Identifiers are canonical opaque ids with a fixed maximum
length. Labels are the enums above or fixed allowlisted error codes. Counts
and percentiles include their interval and sample count; a percentile is
`unavailable` when the sample is too small or the provider does not expose the
field.

## Provenance and unavailable values

Each report labels every number as one of:

- `hosted_billing_actual`
- `database_cumulative`
- `application_interval`
- `provider_dashboard`
- `local_synthetic`
- `unavailable`

The report also records UTC start/end, revision, topology, cache state,
workload profile, sample count, aggregation method, and source timestamp.
Supabase query-level billed bytes remain `unavailable` unless the provider
exposes them directly; local query rows, duration, and byte proxies do not
replace hosted billing evidence.

## Redaction rules

Rejected or omitted from observations and reports:

- raw prompts, provider responses, source or translated text;
- API keys, authorization headers, cookies, session tokens, connection URLs;
- IP addresses, email addresses, arbitrary source URLs, and full database rows;
- unbounded labels, exception text, stack traces, SQL, object keys, and raw
  credential-owner/requester identifiers.

Credential attribution uses only the allowlisted opaque `credential_id`,
`credential_owner_user_id`, and `requesting_user_id` fields when the caller
already supplies bounded internal ids. Provider/project quota domains are
counts or fixed names, not raw configuration.

The focused contract tests are
`backend/tests/test_pipeline_timing_audit.py`: they verify versioned stage
timing, named unavailable fields, numeric filtering, and omission of API-key
and provider-response fields. Runtime event-loop and process-resource samples
are implemented in `novelai.services.runtime_telemetry`; DB-pool checkout,
hosted billed bytes, and network attribution remain explicitly unavailable
when the underlying provider does not expose them.
