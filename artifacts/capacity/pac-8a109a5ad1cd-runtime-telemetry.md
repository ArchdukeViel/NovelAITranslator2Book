# Bounded runtime telemetry evidence

Run/design evidence: `pac-8a109a5ad1cd`
Scope: local implementation and tests only

## Implemented contract

- `BoundedRuntimeTelemetry` retains a fixed-size deque (default: 256
  observations) and exposes snapshot, latest, clear, and unavailable-count
  operations. Metric failures cannot grow an unbounded in-process buffer.
- `RuntimeObservation` accepts only fixed stage, operation, and outcome enums
  plus non-negative numeric fields for duration, queue wait, event-loop lag,
  tokens, retries, rows, R2 operations/bytes, CPU, memory, and network.
- The event-loop sampler is an explicit async task with start/stop ownership
  and a conservative default interval of 250 ms. Process CPU time is sampled
  portably; process memory uses the standard-library resource API where
  available and otherwise emits `process_memory_sampler_unavailable`.
- Network byte attribution emits the named
  `network_bytes_unavailable` reason. DB pool checkout and hosted billed-byte
  attribution have named unavailable reasons rather than guessed values.
- The Prometheus exporter now exposes latest event-loop lag, process CPU and
  memory availability, bounded-buffer depth, and unavailable-sample count.
  Values contain no prompts, responses, URLs, credentials, identities, or
  exception text.

## Coverage and provenance

The fixed inventory covers fetch, raw normalization, metadata, glossary,
selection, segmentation, provider wait/retry/execution, QA, persistence,
PostgreSQL commit, activity state, R2, queue age, and process resources.
Existing provider, activity-database, R2, and pipeline timing counters remain
their own interval/application sources; this artifact does not convert them
into hosted billing evidence.

## Verification

- `tools\pytest.ps1 backend/tests/test_pipeline_timing_audit.py backend/tests/test_health_service.py backend/tests/test_job_worker_service.py -q` — exit 0; 43 passed in 10.47s.
- Focused Ruff over the telemetry module, metrics exporter, three app
  lifespans, and timing tests — exit 0; all checks passed.
- `tools\pyright.ps1` — exit 0; 0 errors, 0 warnings, 0 informations.
- `graphify update . --no-cluster` — exit 0; graph refreshed successfully.
  The refresh continues to report six zero-node non-code/generated files;
  this does not affect the code graph or the telemetry tests.

Live provider, R2, hosted database billing, and load-stage evidence remain
operator-gated and are not claimed here.
