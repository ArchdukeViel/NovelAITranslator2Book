# Fixture-only capacity harness evidence

Run/design evidence: `pac-8a109a5ad1cd`
Scope: deterministic local simulation; no application-service, database, R2,
provider, or canonical-content access

## Harness contract

- `tests.capacity_harness.FixtureOnlyCapacityHarness` accepts a bounded named
  configuration: fixed seed, request count, synthetic identity-slot bound,
  catalog/detail/chapter mix, cache-warm ratio, response-size classes,
  concurrency/timeout inputs, and an optional one-chapter worker sample.
- Each run models warm hits and cold misses, fixed response-size classes,
  deterministic latency samples, DB-read and exact-R2-read counters, public
  status/body-shape/active-reference correctness counters, and separate
  modeled `reader_http_rps` from zero translation-provider RPS.
- The optional worker sample uses one local executor worker and performs only a
  pure fixture operation. The report records zero provider calls and zero
  canonical DB/R2 writes. Synthetic identities are counted as bounded slots;
  identity values, response bodies, and source text are not emitted.
- Metrics export uses fixed route labels only. Runtime CPU/elapsed values are
  recorded for local context, while memory and network attribution are marked
  unavailable with a named reason. The repeatability digest excludes those
  variable runtime values and is stable for the same seed and configuration.
- Invalid or ambiguous traffic inputs are rejected, and a timeout produces a
  truthful `timed_out` result without external cleanup or mutation.

## Verification

- `tools\pytest.ps1 backend/tests/test_capacity_harness.py -q` - exit 0; 9
  passed in 3.15s.
- Focused Ruff over `backend/tests/capacity_harness.py` and
  `backend/tests/test_capacity_harness.py` - exit 0; all checks passed.
- `tools\pyright.ps1` - exit 0; 0 errors, 0 warnings, 0 informations.
- `graphify update . --no-cluster` - exit 0; graph refreshed successfully.

This is fixture/model evidence only. It does not establish a 1k, 10k, or
100k-DAU hosted capacity result, database/R2 egress result, provider quota
result, or production SLO.
