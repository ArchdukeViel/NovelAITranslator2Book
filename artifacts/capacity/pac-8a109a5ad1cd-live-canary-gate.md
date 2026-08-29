# Bounded source canary evidence

Run/design evidence: `pac-8a109a5ad1cd`
Scope: one application-service source canary with the original worker queue
stopped; no full-queue capacity claim.

## Gate result

The bounded canary completed on 2026-08-24. The application selected one
existing non-terminal Kakuyomu chapter-1 record, created one translation
activity through `ActivityQueueService`, and ran it once through
`ActivityWorkerService`. The process-scoped canary limits were one chapter,
one provider concurrency slot, one persistence/concurrency slot, one attempt,
and a 90-second provider deadline.

Sanitized result:

| Field | Result |
| --- | --- |
| Candidate found | yes |
| Source key | `kakuyomu` |
| Chapter | `1` |
| Activity created | yes; identifier retained only in the database |
| Final activity state | `completed` |
| Retry count | `0` |
| Error | absent |
| Provider usage window | 1 successful Gemini request; 4,985 total tokens; estimated cost `0.00997` USD |
| Contributor credential activated | no |
| Original worker/full queue | stopped; no pending or running activity after the canary |
| Raw artifact reference | present |
| Translated artifact reference | present |
| Exact R2 readback | raw and translated artifact reads passed |

The read-only Supabase counter sample immediately before and after the canary
changed from 1,549,196 to 1,550,118 cumulative statement calls, from
571,219.262 ms to 571,419.817 ms cumulative execution time, and from
16,918,545 to 16,920,385 cumulative rows. Statement-shape count changed from
1,987 to 1,989. These are cumulative PostgreSQL counters, not billed egress.

## Safety and identity checks

- The original worker container remained stopped.
- The activity table ended with 5 completed, 11 failed, 3 paused, and 1
  cancelled translation activity; there were no pending or running rows.
- The three existing source-novel records remained present, one per
  `kakuyomu`, `novel18_syosetu`, and `syosetu_ncode`.
- The canary used the normal queue, lease, persistence, provider, and R2
  services. No PostgreSQL row, runtime file, queue state, or R2 object was
  edited by hand.

## Supporting checks

- `tools\\ruff.ps1 check tools/capacity/run_source_canary.py` — exit 0.
- `tools\\pyright.ps1 tools/capacity/run_source_canary.py` — exit 0 with 0
  errors, 0 warnings, and 0 informations.
- Direct R2 artifact readback — raw and translated references both present.

This closes the bounded provider/R2 canary task. It does not establish reader
capacity, provider-project capacity, Supabase billed egress, or production SLO
compliance.
