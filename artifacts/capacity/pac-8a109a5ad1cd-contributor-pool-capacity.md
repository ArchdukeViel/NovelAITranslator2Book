# Contributor credential pool capacity evidence

Run/design evidence: `pac-8a109a5ad1cd`
Scope: local admission, quota accounting, selection, and ledger tests only

## Admission and accounting contract

- Contributor selection remains limited to the unified registry rows that are
  active, enabled, validated, and explicitly eligible for the contributor
  pool. Owner-job rows are not selected by the contributor lease path.
- Each contributor lease now carries a composite quota controller. One shared
  project controller accounts for aggregate Gemini RPM/TPM/RPD/in-flight
  capacity, and one per-credential controller accounts for the credential
  allowance. A rejected second reservation immediately reconciles the first;
  success, failure, cancellation, timeout, and expiry reconciliation fans out
  to both reservations.
- The pool snapshot reports one shared project quota domain and zero verified
  independent domains until an operator-approved/provider-supported mapping is
  available. Contributor keys therefore do not multiply project capacity by
  default. Reader HTTP RPS remains a separate budget from translation-provider
  RPS.
- Selection uses the existing least-recently-used ordering with deterministic
  identity tie-breaking. The local synthetic test demonstrates alternating
  selection without exposing credential identifiers or key material in the
  aggregate snapshot.
- Usage ledger attribution is limited to bounded identifiers, provider/model
  metadata, status, token estimates, and error categories. Tests assert that
  API keys, authorization text, prompts, and responses are absent.

## Verification

- `tools\pytest.ps1 backend/tests/test_contributor_pool_capacity.py -q` - exit
  0; 4 passed in 3.17s.
- `tools\pytest.ps1 backend/tests/test_contributor_credentials.py backend/tests/test_user_contributions_router.py backend/tests/test_gemini_provider.py backend/tests/test_translation_scheduler.py backend/tests/test_contributor_pool_capacity.py -q` - exit 0; 60 passed in 160.47s.
- Focused Ruff over the changed quota, credential, and capacity-test files -
  exit 0; all checks passed.
- `tools\pyright.ps1` - exit 0; 0 errors, 0 warnings, 0 informations.
- `graphify update . --no-cluster` - exit 0; graph refreshed successfully.

No live credential was activated, no provider request was made, no canonical
database or R2 data was changed, and no raw key was read into evidence. Live
provider/project quota-domain verification remains separately operator-gated
by T-016.
