# 1k DAU-equivalent reader stage evidence

Run/design evidence: `pac-8a109a5ad1cd`
Stage report: `artifacts/capacity/1000/reader-stage-1000-20260824T053432Z.json`
Provenance: private staging HTTP sample; no production-capacity claim.

## Execution

The repeatable runner completed with 50 samples per route, concurrency 8,
one warmup request per route, and a 20-second request timeout. The traffic
model was 1,000 DAU-equivalent, 8,000 modeled requests/day, 0.444444 modeled
peak requests/second, and an 1,800-second peak window. The public reader used
an existing published novel and did not seed fixtures or enqueue translation.

All 50 samples for each content route returned HTTP 200 with non-empty bodies;
there were zero client timeouts and zero transport errors. Public readiness
returned the expected HTTP 503 because the worker was intentionally stopped;
public liveness returned HTTP 200.

## Measured p95/p99 and gate result

| Route | p95 ms | p99 ms | SLO budget | Result |
| --- | ---: | ---: | ---: | --- |
| Liveness | 118.116 | 123.380 | 100 | over budget |
| Catalog | 1,515.508 | 2,161.666 | 500 | over budget |
| Detail | 4,432.031 | 5,444.064 | 300 | over budget |
| Chapter | 16,871.242 | 17,492.327 | 750 | over budget |
| Search | 1,543.877 | 1,803.862 | 500 | over budget |
| Daily/weekly/monthly ranking | 52.114 / 63.281 / 57.120 | 54.317 / 65.688 / 60.561 | 500 | within budget |
| Home | 290.079 | 382.336 | 1,500 | within budget |

The stage therefore completed with a quantified SLO stop. It is not a
capacity pass: detail and chapter latency fail the declared reader budgets,
and the stage runner cannot expose provider-side R2 operation or billed-byte
counters. The runner recorded internal fixed-label metrics and point-in-time
Docker CPU/memory/network snapshots; these are supporting process evidence,
not hosted billing attribution.

## Resource and isolation evidence

- Reader Docker snapshot changed from approximately 420.4 MiB / 0.34% CPU to
  427.5 MiB / 0.38% CPU at the captured endpoints.
- Backend changed from approximately 377.1 MiB / 0.52% CPU to 377.2 MiB /
  0.52% CPU at the captured endpoints.
- Queue metrics reported zero pending, queued, and running activities at the
  captured post-run sample.
- No provider calls, worker admission, canonical writes, or R2 mutations were
  performed by this reader-only stage.

This closes the 1k stage execution and records the failed entry gates without
turning a failed or unmeasured metric into a success claim.
