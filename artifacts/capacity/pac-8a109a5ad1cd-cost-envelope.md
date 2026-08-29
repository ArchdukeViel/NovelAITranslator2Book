# Hosted-versus-modeled cost envelope evidence

Run/design evidence: `pac-8a109a5ad1cd`
Scope: local model and fixture proxies; hosted billing/provider/R2 reports
unavailable

## Actuals versus estimates

The cost model consumes only the fixture harness report. In the sampled run it
recorded 80 local requests, 8,192,000 synthetic response bytes, 44 modeled DB
reads, and 15 modeled exact-R2 reads. These are local counters, not hosted
egress or billing attribution.

The following actual fields remain unavailable with the named reason
`no_approved_hosted_report_in_environment`: Supabase billed egress, R2 Class A
and Class B operations, R2 storage bytes, provider token/quota usage, compute,
and observability. No price or quota source was invented.

The model keeps the two rate domains separate: fixture translation-provider RPS
is 0 because no provider call ran, while fixture reader HTTP RPS is a modeled
peak input of 12.0. Contributor pool size and eligible count remain null for
this report; the quota-domain assumption is conservatively
`shared_project_unverified` with zero verified independent domains.

## Explicit projection example

Using a declared but unapproved local traffic input of two sessions per user
per day, four requests per session, a 10% peak-window fraction, and a
1,800-second peak window, the model produces projections only:

- 1k DAU-equivalent: 8,000 daily requests, 0.4444 modeled peak reader RPS,
  819,200,000 modeled response bytes/day, and 3,000 modeled exact reads/day.
- 10k DAU-equivalent: 80,000 daily requests, 4.4444 modeled peak reader RPS,
  8,192,000,000 modeled response bytes/day, and 30,000 modeled exact
  reads/day.
- 100k DAU-equivalent: 800,000 daily requests, 44.4444 modeled peak reader
  RPS, 81,920,000,000 modeled response bytes/day, and 300,000 modeled exact
  reads/day.

Every projection is marked `unavailable_hosted_gate` and
`is_capacity_claim=false`. The assumptions are not operator-approved and do
not establish an SLO, billing amount, egress budget, quota, or production
capacity result.

## Verification

- `tools\pytest.ps1 backend/tests/test_capacity_cost_model.py -q -s` - exit 0;
  3 passed in 3.01s and emitted a JSON-safe sanitized envelope.
- Focused Ruff over `backend/tests/capacity_cost_model.py` and
  `backend/tests/test_capacity_cost_model.py` - exit 0; all checks passed.
- `tools\pyright.ps1` - exit 0; 0 errors, 0 warnings, 0 informations.
- `graphify update . --no-cluster` - exit 0; graph refreshed successfully.

No billing dashboard, provider account, R2 endpoint, canonical database, or
production storage was accessed.
