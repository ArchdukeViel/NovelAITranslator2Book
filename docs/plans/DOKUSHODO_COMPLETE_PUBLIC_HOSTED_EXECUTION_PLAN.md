---
plan_id: dokushodo-public-hosted-evidence
plan_version: 2.1.0
document_kind: execution_plan
canonical_truth: false
plan_role: execution
work_state: blocked
blocked_reason: predecessor_handoff_not_validated
predecessor: dokushodo-docs-standardization
predecessor_version: 2.1.0
predecessor_path: docs/plans/DOKUSHODO_AGENTS_AND_CANONICAL_DOCUMENTATION_STANDARDIZATION_PLAN.md
predecessor_handoff: artifacts/documentation-standardization/handoff.json
mutates_production: false
nonproduction_provider_mutations: separately_authorized_only
github_visibility_change: separately_authorized_only
production_capacity_claim: not_established
---

# Dokushodo public hosted CI and non-production evidence plan

## Predecessor contract - mandatory admission interface

This plan is Plan B. It must not begin mutation until Plan A has completed and this consumer-side contract validates:

| Interface field | Required value |
| --- | --- |
| predecessor | `dokushodo-docs-standardization` version `2.1.0` |
| handoff | `artifacts/documentation-standardization/handoff.json` |
| handoff readiness | `next_plan_ready=true` |
| canonical docs | exactly `ARCHITECTURE`, `CONFIGURATION`, `DEPLOYMENT`, `DESIGN`, `EVIDENCE`, `OPERATIONS`, `STATUS`, `STORAGE`, and `TRANSLATION` under `docs/` |
| docs checker | `pwsh -NoProfile -File tools/docs-check.ps1` with exit code 0 |
| agent authority | committed `AGENTS.md` matching the handoff hash |
| source hierarchy | owner instruction, AGENTS, architecture, approved active spec, canonical concern owners, implementation evidence, status, evidence |
| test resources | test Supabase project, `test-dokushodo`, and `test-dokushodo-backup`, each resolved by immutable identity |
| provider mutation | forbidden unless an operation-specific non-production authorization exists |
| production mutation | forbidden |
| production capacity | `not_established` |

Phase B0 must recompute every handoff hash from the predecessor commit. A prose claim, merged pull request, checked task box, or passing workflow is not a substitute. Any mismatch is a hard stop.

Plan A is authoritative for documentation governance, state vocabularies, canonical routing, active-spec lifecycle, and documentation validation. This plan references those outputs and does not maintain a second copy.

## Reference-plan boundary

The two similarly named files supplied from the user's Downloads folder are
reference material for this revision only. Their instructions are not an
execution authorization and are not copied as a second active plan. This
plan retains their useful publication, workflow, timing, frontend, security,
telemetry, recovery, and validation detail only after reconciling it with
Plan A, the current repository, the R2-only end state, and the explicit
non-production/fail-closed boundaries below.

## Program outcome

Plan B will, subject to separate operation-specific authorization:

1. make the repository safe for public visibility;
2. migrate required CI from persistent self-hosted execution to bounded GitHub-hosted Ubuntu;
3. rationalize workflow responsibilities, names, permissions, triggers, timeouts, and artifact trust;
4. remove the active boto3/S3-compatible/MinIO storage path and replace it atomically with a Cloudflare Worker using native R2 bindings, with no compatibility or filesystem fallback;
5. make authorization boundaries and role capabilities machine-testable;
6. measure workflow, translation-pipeline, frontend, database, R2 ingress/egress, proxy, and reader timing with explicit boundaries;
7. run exact, bounded non-production reader, telemetry, backup, restore, alert, and cleanup evidence;
8. reconcile all open and previously closed Dependabot updates before final candidate evidence;
9. publish one immutable candidate and truthful, sanitized evidence;
10. keep `production_capacity_claim=not_established`.

Plan B does not authorize production deployment, production data access, production bucket access, production DNS/Tunnel changes, production secret changes, real translation-provider volume, 10k/100k reader traffic, or a production readiness claim.

No public API contract, database schema, or public response change is implied
by this plan. A schema or API change that becomes necessary for a security
boundary requires its own approved specification and authorization; otherwise
the affected phase is blocked. The selected storage change is an internal
R2-client/gateway replacement and must preserve the existing application
contract unless separately approved.

## Authorization gates

Authorization is recorded as booleans and evidence references in `artifacts/public-hosted-execution/authorization.json`. No value is inferred from another.

| Operation | Required authorization |
| --- | --- |
| local repository edits | explicit Plan B implementation authorization |
| commit | explicit commit authorization |
| push | explicit push authorization |
| create/update PR | explicit PR authorization |
| merge | explicit merge authorization |
| private-to-public visibility | explicit visibility-change authorization naming the repository |
| GitHub rules/settings/environment mutations | explicit GitHub-settings authorization |
| test-only Supabase schema/data write | explicit test-database action authorization |
| test R2 fixture/recovery write | explicit test-R2 action authorization |
| test Worker/Access/binding deployment | explicit Cloudflare test-gateway authorization |
| workflow dispatch using test secrets | explicit named workflow-dispatch authorization |
| production mutation | never authorized by this plan |

Missing authorization blocks only dependent mutations. Read-only inventory and independent local work may continue when safe. A generic “implement the plan” does not imply visibility, merge, provider, or production authority.

## State and failure model

Use Plan A's namespaces exactly.

Work state: `planned`, `active`, `blocked`, `deferred`, `complete`, `superseded`.

Evidence disposition: `passed`, `failed`, `blocked`, `partial`, `unavailable`, `not_run`.

`complete_with_quantified_blocker` is allowed only for `overall_follow_up_disposition`.

### Hard safety stop

Stop the affected branch and all dependents when:

- Plan A handoff is invalid;
- target identity cannot be proven non-production;
- a target equals or resembles production;
- a secret or private payload is found in publishable material;
- untrusted code can reach a secret, write token, persistent runner, provider, deployment identity, or trusted artifact;
- fixture or recovery-prefix collision exists;
- required cleanup guard fails before a write;
- candidate identity changes without evidence invalidation;
- public protection state cannot be captured or safely restored;
- architecture/security authority is unresolved;
- production could be affected.

### Quantified blocker

Continue only independent safe work when a provider metric, test gateway, alert destination, controlled-cache layer, hosted queue, or permission is genuinely unavailable. Record blocker ID, UTC interval, target class, required evidence, fixed reason, owner role, next action, retry condition, and safety disposition.

### Test failure

A required check that ran and missed its contract is `failed`. A complete sample over budget is failed. An incomplete required sample is blocked. Neither becomes unavailable merely because fixing it is inconvenient.

## Candidate and evidence immutability

A candidate is:

- one commit SHA;
- exact workflow file hashes;
- container image digests;
- dependency and lockfile hashes;
- sanitized relevant configuration fingerprint;
- Plan B version;
- test-harness version.

All final evidence must name that candidate. Any evidence-affecting source, workflow, dependency, container, configuration, migration, or test-plan change creates a new candidate and invalidates affected evidence. Documentation-only edits may preserve runtime evidence only when runtime artifacts and workflow semantics are byte-identical and the exception is recorded.

Preliminary diagnostics may guide implementation before freeze; they are not final evidence.

## Non-production resource allowlist

### Supabase test project

- expected display name: `testingdatabase-dokushodo`;
- owner alias `testdatabase=dokushodo` is descriptive only;
- resolve through `mcp__codex_apps__supabase_list_projects`;
- require exactly one active match and record an immutable project ID in restricted evidence;
- public artifacts use a digest/class, not the raw ID;
- reject `Dokushodo`, ambiguity, inactivity, or an unverifiable connection target.

### R2

- application bucket: exactly `test-dokushodo`;
- backup bucket: exactly `test-dokushodo-backup`;
- reject `dokushodo`, `dokushodo-backup`, guessed names, or any other bucket;
- verify account and bucket identities read-only before writes;
- bind the application and recovery identities only to their named test buckets.

### Fixture

- fixture key: `reader-fixture-test-v1`;
- source key: `kakuyomu`;
- source novel ID: `test-novel-001`;
- novel ID: `123`;
- slug: `test-novel`;
- chapter IDs: `456` and `457`;
- published: true;
- adult: false;
- content present: true;
- runtime binding: `fixture-<16 lowercase hex>`;
- application prefix: `novels/123/` with generated binding-specific exact keys;
- recovery prefix: `recovery-<run-id>/`.

Resolve both sanitized display identity and immutable provider identity where safe. Display names alone never authorize a target.

## Secret and evidence boundary

Never print, upload, commit, or preserve:

- tokens, cookies, authorization headers, Access client secrets, connection strings, hostnames, private IPs, signed URLs, or environment dumps;
- SQL text, row contents, object payloads/keys beyond approved sanitized classes, request/response bodies, source/translated content, provider raw responses, or stack traces;
- user IDs, personal contact details, destination addresses, or correlation IDs derived from private data.

Use opaque run/request IDs. Evidence validators scan artifacts before upload and report fixed category/count only. Discovery commands must select names/metadata, never secret values.

## Phase record contract

Every phase below includes objective, inputs/dependencies, allowed and forbidden mutations, tasks, evidence, validation, hard stops, blockers, exit criteria, artifacts, canonical-doc updates, and next phase. No phase advances by intuition.

### Phase checkpoint contract

At the end of every phase, emit a sanitized checkpoint record containing
phase ID, candidate SHA/worktree state, changes made, commands and exit
codes, artifacts, exact allowed-target proof, unavailable evidence,
blockers, and next-phase eligibility: go, blocked, or
complete_with_quantified_blocker. A hard safety blocker stops that phase and
all dependent phases. The checkpoint is a progress record, not evidence that
the overall program passed.

## Phase B0 - Predecessor, workspace, authority, and target preflight

### Objective

Prove Plan A admission, freeze owner changes, resolve exact tool/resource identities, and establish side-effect gates.

### Inputs and dependencies

Plan A commit/handoff, current owner authorization, Git baseline, canonical docs, active specs, manifests, workflows, provider tool availability, and resource allowlist.

### Allowed mutations

Ignored sanitized preflight artifacts only. No tracked or provider mutation.

### Forbidden mutations

All Git index/remotes, GitHub settings, providers, secrets, runtime data, and production.

### Tasks

1. Parse the handoff and require its schema, plan/version, complete work state, readiness, canonical paths, zero documentation blockers, and invariant capacity claim.
2. Recompute every canonical and AGENTS hash from `git show <candidate_commit>:<path>`.
3. Run the declared docs checker and verify Plan B's predecessor metadata matches.
4. Record branch, HEAD, default branch, dirty status, predecessor commit, owner-changed paths, and UTC interval.
5. Preserve all pre-existing modifications and untracked files, including any untracked workflow draft.
6. Inventory active specs and classify work versus evidence state.
7. Resolve toolchain from manifests and wrappers; do not copy historical versions from prose.
8. Discover currently available MCP tool names. Preferred current names are:
   - `mcp__codex_apps__supabase_list_projects`;
   - `mcp__codex_apps__supabase_get_advisors`;
   - `mcp__codex_apps__supabase_execute_sql`;
   - `mcp__cloudflare_api__search`;
   - `mcp__cloudflare_api__execute`.
9. Resolve the test project and bucket classes read-only. Cloudflare `search` precedes each new API operation; `execute` is GET/read-only until a later authorization gate.
10. Verify required secrets/variables by name and availability only.
11. Independently prove the dedicated worker, original full translation queue, schedulers, importers, maintenance writers, and other data writers are stopped/paused. Worker absence alone is insufficient.
12. Generate the authorization matrix file with every operation defaulting false unless explicitly authorized.
13. Validate fixture and recovery prefix collision checks read-only.

### Required evidence

- `artifacts/public-hosted-execution/preflight.json`
- `artifacts/public-hosted-execution/authorization.json`
- `artifacts/public-hosted-execution/target-identity.json`
- `artifacts/public-hosted-execution/writer-state.json`
- `artifacts/public-hosted-execution/path-inventory.json`

### Validation

Handoff validator, docs checker, JSON schemas, target deny-list tests, `git diff --check`, and Graphify refresh if any tracked edit follows.

### Hard stops

Invalid predecessor, unowned dirty overlap, ambiguous/production-like target, fixture collision, unknown writer state before a write, or attempted secret value inspection.

### Quantified blockers

Unavailable read-only provider capability or missing operation-specific authorization.

### Exit criteria

Predecessor and identities are proven, owner changes are preserved, every mutation is gated, and no external state changed.

### Canonical-document updates

None.

### Next phase

B1 for read-only audit; mutations remain gated.

## Phase B1 - Publication, repository, workflow, and provider posture audit

### Objective

Prove what would become public, identify unsafe trust paths, and establish the current workflow/provider posture before modification.

### Inputs and dependencies

Passing B0, repository history/metadata, GitHub read APIs, current workflows, and read-only provider access.

### Allowed mutations

Sanitized ignored audit artifacts. No deletion or settings change.

### Forbidden mutations

History rewrite, run/artifact deletion, visibility change, workflow dispatch, provider writes, and secret reads.

### Tasks

#### Publication surface audit

Inspect counts/categories and sensitive context across:

- tracked files and untracked publication candidates;
- full reachable history, all local/remote branches, tags, reflogs relevant to publication, submodules, and Git LFS;
- releases/assets, packages/containers, Pages, wiki, discussions, issues, PRs, comments, Actions logs/artifacts, caches, deployments, and environment records;
- variables, secret metadata, Dependabot/Codespaces secret metadata, deploy keys, webhooks, installed Apps, OAuth/OIDC trusts, environments/protection rules, rulesets, branch protections, required checks, bypass actors, merge methods, and default token permissions;
- `pull_request_target`, `workflow_run`, `issue_comment`, reusable workflows, artifact handoffs, cache poisoning, Docker build contexts, network egress, and secret-bearing scheduled/manual workflows;
- source/content licenses and third-party redistribution obligations.

Automated secret scanning is necessary but insufficient. Manually review contextual false negatives without exposing values. If a historical secret is found: rotate/revoke first, block publication, and require separate history-rewrite authority. Deleting a log is not rotation.

#### Governance audit

Verify `LICENSE` exists and matches the manifest's GPL-3.0-or-later declaration. Review `SECURITY.md`, `CODEOWNERS`, pull-request template, issue templates, and whether `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, or `SUPPORT.md` are appropriate. Do not change license terms without explicit owner authorization.

#### Current workflow audit

Classify every current workflow before rename or consolidation:

| Current path | Target disposition |
| --- | --- |
| `.github/workflows/ci.yml` | keep name; hosted core validation and docs gate |
| `.github/workflows/build.yml` | rename to `.github/workflows/container-publish.yml` after required-check/workflow_run mapping |
| `.github/workflows/deploy.yml` | retain and harden; do not dispatch production |
| `.github/workflows/static-analysis.yml` | rename to `.github/workflows/security-static-analysis.yml` |
| `.github/workflows/dependency-review.yml` | retain; public/fork-safe |
| `.github/workflows/gitguardian.yaml` | rename to `.github/workflows/secret-scan.yml`; hosted and same-repository secret path only |
| `.github/workflows/reader-capacity-nonproduction.yml` | rename to `.github/workflows/nonproduction-reader-evidence.yml` |
| `.github/workflows/managed-services-verification.yml` | rename to `.github/workflows/nonproduction-managed-services.yml` |
| `.github/workflows/managed-services-test-migrate.yml` | rename to `.github/workflows/reusable-test-database-migration.yml` |
| `.github/workflows/managed-services-recovery-verification.yml` | rename to `.github/workflows/reusable-test-recovery.yml` |
| `.github/workflows/s3-integration.yml` | remove only in the atomic R2-native cutover; replace with `.github/workflows/r2-worker-integration.yml` |
| `.github/workflows/production-monitor.yml` | retain; audit public URL/permissions; do not treat disabled runs as evidence |
| `.github/workflows/opencode.yml` | remove from the public candidate because public issue comments can reach a secret-bearing privileged job |
| `.github/workflows/ai-review.yml` (untracked draft) | preserve as owner work during preflight; do not publish in current local-router/self-hosted form |
| `.github/workflows/codeql.yml` | create with pinned actions if GitHub default setup is not already the single authority |

Do not add a separate pre-commit workflow. `.pre-commit-config.yaml` remains a local commit gate; its Ruff/whitespace behavior is already covered by core CI. Duplicate hosted runs add cost without unique evidence.

Treat .pre-commit-config.yaml as a workflow dependency and audit it before
renaming or consolidating workflows: enumerate hooks, revisions, language
runtimes, network access, cache behavior, and whether each hook is safe on
untrusted fork code. The core CI pre-commit job runs the repository's
canonical hook set with pre-commit run --all-files and fails if the hook
leaves a dirty diff. Do not create a second standalone pre-commit workflow
unless a later audit proves a distinct required check with no duplicated
execution.

### Workflow necessity test

For every workflow, record its unique trigger, required-check name, owning
responsibility, trust class, secrets, artifacts, callers, and last
meaningful use. Keep only workflows with a distinct required validation,
security control, release operation, or authorized non-production evidence
purpose. Remove or merge unreachable, duplicate, superseded, or
secret-bearing workflows that cannot be made safe; record the reason and
required-check impact before deletion. A disabled workflow is not evidence
of safety or capacity.

#### Cloudflare read-only posture

Using MCP `search` then read-only `execute`, attempt to inspect:

- zone/DNS records and proxy state;
- approved Tunnel and connector state;
- origin exposure and route relationship;
- SSL mode, minimum TLS, TLS 1.3, Always Use HTTPS, HSTS state, HTTP/2/3, compression, and Early Hints;
- cache rules/status, WAF managed rules, rate limiting, bot/security settings available to the plan;
- DNSSEC/CAA;
- R2 public access, custom domains, CORS, lifecycle/Object Lock, and test bucket scope;
- available analytics datasets.

Record recommendations with current value class, proposed value, reason, risk, rollback, plan/tier availability, and `mutation_authorized=false`. Do not mutate. HSTS is never enabled speculatively because rollback is delayed by cached policy.

### Domain and edge posture recommendation record

For each observed zone, hostname class, Tunnel route, or R2 endpoint, write a
sanitized row with current state, evidence source, risk, proposed change,
prerequisite, rollback, tier/permission limitation, and mutation_authorized.
Review at least:

| Area | Required observation or recommendation |
| --- | --- |
| DNS/origin | proxied state, exact approved route relationship, origin exposure, DNSSEC, and CAA |
| TLS | minimum TLS version, TLS 1.3, origin mode, certificate coverage, and Always Use HTTPS |
| transport | HTTP/2, HTTP/3, compression, Early Hints, and 0-RTT implications for cookie mutations |
| caching | bypass for API/auth/user/admin/cookie-bearing responses; explicit immutable caching only for approved public assets/content |
| application security | managed WAF rules, rate limits, bot/security controls, and protected health/readiness boundaries |
| Tunnel | connector count/health, route/origin mapping, ephemeral versus persistent class, and no raw hostname in public evidence |
| R2 | public-access state, custom-domain state, CORS, lifecycle, Object Lock, bucket class, and account/binding scope |

No recommendation becomes an executed change in this plan. Origin TLS
hardening, HSTS, cache rules, WAF/rate limits, DNS, Tunnel, and R2
configuration require a separately authorized operation and before/after
verification. A Cloudflare-registered domain or healthy Tunnel alone does not
prove application routing, reader reachability, or production performance.

#### Supabase read-only posture

Use list-projects, security/performance advisors, migration inventory, and aggregate read-only SQL. Record RLS/grant coverage counts, security-definer/view findings, exposed-schema posture, pool/session aggregate state, and unavailable permissions. Never export SQL text, identities, hosts, URLs, or rows.

### Required evidence

- `publication-audit.json`
- `github-settings-baseline.json`
- `workflow-inventory.json`
- `governance-files.json`
- `cloudflare-posture.json`
- `supabase-posture.json`
- `recommendations.md`

### Validation

Evidence sanitization, complete surface checklist, every workflow exactly once, settings snapshot hashes, zero provider mutations, and docs checker after any later documentation edit.

### Hard stops

Sensitive publishable material, untrusted secret path, missing/inconsistent license, inaccessible protection baseline, production-like provider target, or inability to preserve owner work.

### Quantified blockers

Provider setting unavailable by tier/permission; public-surface API unavailable; optional governance file needing owner policy.

### Exit criteria

Every surface and workflow is classified, publication blockers are explicit, and current provider posture is recorded read-only.

### Canonical-document updates

`STATUS.md` may receive factual blockers only after tracked changes are authorized.

### Next phase

B2 when repository mutations are authorized; otherwise stop with a useful audit.

## Phase B2 - Hosted workflow rationalization and public-fork hardening

### Objective

Produce one minimal, bounded, public-fork-safe workflow set with explicit responsibilities and timing.

### Inputs and dependencies

B1 inventory, actual required-check names, current default-branch protections, and repository edit authorization.

### Allowed mutations

Workflow files, Dependabot configuration, security tooling config, and directly affected deployment documentation.

### Forbidden mutations

Workflow dispatch, GitHub settings, provider calls, visibility change, secret values, and persistent self-hosted runner provisioning.

### Tasks

1. Migrate required jobs to `ubuntu-24.04` or a manifest-resolved GitHub-hosted image. No required workflow may use `self-hosted`.
2. Apply the B1 target disposition table atomically. Update reusable-workflow callers, `workflow_run` names, required-check migration records, docs, and references.
3. Set top-level `permissions: {}` or minimum read permissions; elevate per job only.
4. Pin every action to a full commit SHA with a reviewed release comment. Pin containers by digest where deterministic.
5. Set a bounded `timeout-minutes` on every job and concurrency/cancellation on every workflow. Never cancel authoritative default-branch publication inputs.
6. Separate trust classes:
   - `public_pr_untrusted`: read-only token, no secrets, no provider, no artifact promotion;
   - `same_repo_trusted`: explicit branch/actor guard and least privilege;
   - `default_branch_publish`: immutable SHA, no untrusted artifact;
   - `manual_nonproduction`: environment/confirmation/target guards;
   - `production`: retained but never dispatched here.
7. For `workflow_run`, require same repository, successful trusted event, default branch, and checkout exact head SHA. Never consume untrusted artifacts.
8. For cache use, prevent untrusted writes to trusted cache scopes; key by lockfile/OS/runtime and use read-only or separate PR scope.
9. Bound matrix size, artifact paths/size, retention, network egress, container builds, manual dispatch frequency, and reusable callers.
10. Keep GitGuardian on hosted execution. Fork PRs receive no GitGuardian secret; built-in GitHub secret scanning/push protection is the publication control.
11. Remove public `issue_comment` automation and the unsafe AI-review draft from the target candidate. A future AI-review workflow requires a separate GitHub App/trust design.
12. Add CodeQL only if no existing GitHub default setup owns the same languages. Avoid duplicate scanning.
13. Add docs checker to core CI and required-check mapping.
14. Add workflow timing extraction from GitHub run/job/step timestamps:
    - queue duration;
    - workflow total;
    - job duration;
    - step duration;
    - critical path;
    - conclusion/cancellation;
    - runner image.
15. Set initial timeout using `max(10 minutes, ceil(observed successful p95 * 1.5))`, capped at 60 minutes unless the workflow has a reviewed exception. New jobs use the narrowest safe default and are tuned after three successful runs.
16. Test Dependabot PR behavior as untrusted: read-only token and Dependabot secrets only.

### Required resource-control contract

The workflow inventory and post-change evidence must expose these controls
per workflow and job; a prose assertion that the hosted runner is free is not
an abuse-control proof:

| Control | Required plan record |
| --- | --- |
| job duration | finite timeout, observed duration, and timeout margin |
| workflow concurrency | group key, cancellation policy, and whether default-branch evidence is protected from cancellation |
| matrix expansion | explicit matrix dimensions and bounded maximum job count |
| workflow recursion | no self-triggering loop; one bounded workflow_run hop; reusable workflow callers and maximum call depth are allowlisted |
| manual dispatch | enumerated inputs, validation/normalization, environment approval, and bounded dispatch frequency |
| scheduled execution | cadence, target class, per-run budget, and proof that it cannot create provider-volume traffic |
| fork execution | secretless job set, read-only token, concurrency bound, and no provider/deployment/artifact-promotion path |
| cache | OS/toolchain/lockfile key, trust scope, cache size/retention, and no fork write into a trusted cache |
| artifacts | allowlisted paths, maximum size/count, short retention, provenance, and sanitized upload |
| network egress | allowlisted destinations and explicit treatment of package/container registries; no unrestricted provider writes |
| container pulls | immutable image digest, bounded pull/build behavior, no mutable latest tag, and no privileged pull credentials on untrusted jobs |
| reusable callers | same-repository or explicitly trusted caller allowlist, input schema, and secret map |
| retries | finite and operation-specific; no retry loop may multiply reader, provider, recovery, or workflow volume |

The exact numeric limits are resolved from repository and GitHub policy during
B0/B2 and recorded in the evidence artifact; this plan does not invent a
provider billing allowance. Any unbounded, attacker-controlled, or
unverifiable control is a hard stop for public visibility.

### Toolchain and local-gate contract

Resolve the canonical Node, Python, package-manager, pre-commit, Wrangler,
Docker, and PowerShell versions from manifests, lockfiles, Dockerfiles, and
wrappers. If sources disagree, stop and resolve the contract before changing
CI. Verify the hosted image for Linux path/case sensitivity, executable bits,
Compose v2, artifact upload/download, cache isolation, and wrapper behavior.
The CI candidate must run pre-commit run --all-files and fail if it changes
the tree. Do not copy historical versions from either attached plan.

### Required evidence

- `workflow-change-map.json`
- `required-check-transition.json`
- `workflow-trust-matrix.json`
- `workflow-timing-schema.json`
- `workflow-security-review.md`

### Validation

- YAML parse;
- Zizmor/security analysis;
- no required self-hosted labels;
- no unguarded privileged triggers;
- all actions SHA-pinned;
- every job has timeout and permissions;
- all references resolve;
- docs checker, `git diff --check`, and Graphify refresh.

### Hard stops

A required check cannot be migrated without a protection gap, untrusted code reaches privileged context, or a renamed reusable workflow has an unresolved caller.

### Quantified blockers

Optional scanner cannot run on forks; hosted-runner queue unavailable; GitHub setting requires later authorization.

### Exit criteria

The candidate workflow graph is minimal, target names are consistent, fork paths are secretless, and private dry runs are possible.

### Canonical-document updates

`DEPLOYMENT.md` and `OPERATIONS.md` describe only implemented workflow behavior; `STATUS.md` records unresolved settings work.

### Next phase

B3.

## Phase B3 - Atomic native R2 Worker cutover in the repository

### Objective

Replace the active compatibility client with a native R2 binding gateway and eliminate all active S3-compatible, boto3, botocore, moto, MinIO, and filesystem fallback behavior.

This is an owner-selected Dokushodo architecture constraint. Cloudflare offers multiple R2 API surfaces, but this project selects the Workers API for the final application path.

References in this plan to boto3, S3-compatible APIs, MinIO, moto, or
filesystem storage are removal/deny-list terms only. They do not authorize a
compatibility mode, fallback, alias, dual write, or alternate test backend.
After this phase, active source, configuration, dependencies, tests,
workflows, and canonical docs must contain none of those legacy paths; only
this migration record and explicitly labeled historical provenance may retain
the terms.

### Inputs and dependencies

B2 safe workflows, approved architecture/spec delta, current storage implementation inventory, and optional test-gateway authorization.

### Allowed mutations

Worker source/config, backend storage interface/client, application configuration schema/examples, tests, local Workers test runtime, workflows, lockfiles, and affected canonical docs.

### Forbidden mutations

Production buckets, public unauthenticated object routes, generic object-store fallback, old-client compatibility shim, dual-write, production deploy, or Cloudflare provider change without a separate test-gateway authorization.

### Target architecture

- A Cloudflare Worker holds native R2 bindings.
- The external application calls a private versioned gateway over HTTPS.
- Cloudflare Access service-token authentication is the selected external service identity. Application and backup/recovery use separate least-privilege identities.
- The gateway maps fixed bucket classes to bindings; callers never provide an arbitrary bucket.
- Public clients never call R2 or the gateway directly.
- Exact-key read/head/write/delete are explicit operations. Listing is paginated and allowed only for inventory, backup, recovery, and guarded cleanup.
- The gateway emits fixed-label timing and request IDs but never object payloads, raw keys, credentials, or arbitrary metadata.
- No filesystem, MinIO, generic S3, or production R2 fallback exists.

If a protected test Worker/Access configuration does not already exist and provider deployment is not separately authorized, repository implementation may complete with local Workers binding tests, but live R2 evidence is `blocked`. Do not restore the old client to make tests green.

### Tasks

1. Write the architecture decision and request/response/error contract before code.
2. Implement native Workers R2 binding operations with exact bucket-class allowlisting.
3. Implement a backend HTTP client through the existing outbound-HTTP/SSRF boundary with timeouts, bounded retries only for idempotent operations, payload limits, and redacted errors.
4. Implement separate application and recovery identities; neither can select production resources.
5. Remove boto3, botocore, moto S3 extras, the `s3` optional dependency, old environment keys, old classes/modules/tests, the MinIO workflow, and compatibility docs in the same candidate.
6. Rename integrations and tests to R2 Worker terminology.
7. Replace compatibility mocks with Worker binding test doubles/local runtime. Local emulation proves contract behavior, not hosted Cloudflare timing.
8. Regenerate every lockfile through `deploy/update-lockfiles.ps1`.
9. Add deny tests for arbitrary buckets, list hot paths, path traversal, oversized objects, unsigned/unauthorized calls, replay/expired Access identity, production names, and public exposure.
10. Add exact-key, range/stream, checksum, cancellation, timeout, and cleanup tests.
11. If test-gateway deployment is authorized, deploy only the test Worker/bindings/Access identity named in authorization, verify route privately, and record immutable resource digests. Otherwise record the bounded blocker.
12. Run active-code/config/workflow/documentation scans for the removed compatibility terms. Clearly historical archives and this migration instruction are classified migration/history context only.

### Required evidence

- `r2-cutover-decision.md`
- `r2-removal-ledger.json`
- `r2-gateway-contract.json`
- `r2-security-tests.json`
- `r2-test-gateway-status.json`

### Validation

Focused Worker/backend tests, R2 contract tests, Ruff, Pyright, lockfile consistency, workflow checks, active-term zero scan, docs checker, `git diff --check`, and Graphify refresh.

### Hard stops

Old fallback remains reachable, test identity can address arbitrary/production buckets, gateway is public, Access identity is shared with recovery, or deployment authority is absent for a required provider write.

### Quantified blockers

Protected test gateway absent; Access/binding permission unavailable; provider timing unavailable.

### Exit criteria

The repository has one R2-native path with no active compatibility fallback. Live evidence may remain blocked, but no legacy path is reintroduced.

### Canonical-document updates

`ARCHITECTURE.md`, `CONFIGURATION.md`, `STORAGE.md`, `OPERATIONS.md`, and `DEPLOYMENT.md` in the same logical change. `STATUS.md` records live-gateway blockers; `EVIDENCE.md` records only verified outcomes.

### Next phase

B4.

## Phase B4 - Authorization, instrumentation, and preliminary timing diagnostics

### Objective

Make security and non-overlapping timing observable before final candidate freeze, then stabilize functionality using bounded diagnostics.

### Inputs and dependencies

B3 repository architecture and isolated test resources.

### Allowed mutations

Application instrumentation, tests, migrations required by an approved security contract, local tooling, and evidence schemas. Test-only reads/writes require their specific authorization.

### Forbidden mutations

Public response timing fields, identity-bearing metrics, production schema/data, real translation-provider traffic, and speculative optimization.

### Authorization matrix

The implementation, grants/RLS, tests, and canonical docs must agree:

| Identity | Allowed | Denied |
| --- | --- | --- |
| Guest | public auth endpoints, safe health, and published catalog/novel/chapter/search/ranking/review reads | user/private/owner/unpublished data and every mutation not explicitly public |
| Authenticated user | guest access plus own profile, library, progress/history, reviews, requests, notifications, and consented contributor credentials | other users, owner controls, unpublished/private data, queues, backups, and raw provider credentials |
| Owner | user capabilities plus documented users, audits, import/crawl, translation/glossary, takedown, provider, queue, scheduler, maintenance, analytics, backup, and recovery controls | bypass of CSRF, audit, target guards, least privilege, or production authorization; owner transfer/promotion when prohibited |
| Runtime database role | required application DML/functions only | DDL, role/grant changes, backup administration |
| Migration role | migrations and approved policy DDL | normal application/runtime use |
| R2 content identity | exact application objects in `test-dokushodo` during test | backup/production buckets and account administration |
| R2 recovery identity | snapshot-read/restore operations across the two test buckets as explicitly scoped | application runtime mutation and production |
| MCP/operator identity | read-only discovery/advisors/aggregate telemetry by default | unapproved DDL/data/provider settings |
| GitHub untrusted workflow | checkout and secretless validation | secrets, write token, provider, deploy, trusted cache |
| GitHub trusted workflow | only job-specific least privileges | implicit production/provider authority |

Identity comes from authenticated context, never client-supplied `user_id`. Exposed Supabase schemas require grants plus RLS. Views/security-definer functions receive explicit review and deny tests. Service-role material stays server-side and is never a frontend authorization mechanism.

The security evidence must include sanitized outcomes for these cases:
guest_user_route_401, guest_owner_route_401, user_owner_route_403,
user_a_user_b_read_denied, user_a_user_b_write_denied,
revoked_session_denied, csrf_required_cookie_mutation,
unpublished_public_read_denied, service_role_not_browser_equivalent, and
rls_server_check_consistent. Missing a test identity or permission is
blocked/unavailable; it is never treated as a passing omission.

### Timing model

Durations use process-local monotonic clocks. UTC is only for cross-system windows.

Parent/child intervals are recorded, not added blindly:

- `total_client`;
- `dns`, `tcp`, `tls`;
- `cloudflare_edge`;
- `tunnel`;
- `caddy`;
- `application_total`;
- `db_pool_checkout`;
- `sql_execution`;
- `r2_exact_read`;
- `r2_exact_write`;
- `cache_or_fallback`;
- `serialization`;
- `application_exclusive`;
- `network_remainder`.

`application_exclusive` subtracts the union of measured child intervals from `application_total` only when they share one monotonic clock. `network_remainder` is calculated only when one correlated request proves valid nesting. Residual time is never labeled as Cloudflare, Tunnel, Caddy, database, or R2 internal time.

Each span records source, parent, clock, start offset/duration, sample count, aggregation, availability, and fixed unavailable reason.

### Correlation contract

- opaque campaign, run, request, and recovery IDs;
- no user IDs, URLs, SQL, object keys, or secrets in IDs;
- monotonic duration source per process;
- UTC start/end and clock source per system;
- obvious drift check before cross-system correlation;
- one request ID through proxy/application/gateway where supported;
- unsafe or incomplete joins become unavailable.

### Pipeline and stage timing contract

CI timing is a separate evidence domain from reader HTTP timing. Where the
platform exposes timestamps, record queue wait, runner provisioning,
checkout, toolchain setup, dependency restore/install, change detection,
pre-commit, backend lint/type checking, backend tests, migration smoke,
frontend install/lint/typecheck/tests/build, Docker build, security scans,
artifact creation/upload, cleanup, workflow total, and critical path.

Translation-pipeline timing is also separate. Its fixed stage vocabulary is
intake/validation, source fetch, parsing, database persistence, queue
enqueue, queue wait, worker dequeue, provider request/wait/TTFB/body parse,
retry/backoff, translation, QA, R2 write, database commit, and notification.
Because this follow-up keeps the translation worker and full queue paused,
those stages are recorded as not_run or unavailable with a fixed reason, not
as zero-duration success.

Each stage record includes stage name, parent, clock, start offset/duration,
sample count, aggregation, availability, unavailable reason, and whether it
is on the critical path. Parent/child intervals are never summed twice.

### Database and R2 ingress/egress contract

Database cells record request preparation, serialized input bytes, pool
checkout, SQL client round trip, row mapping, commit/rollback, connection
release, serialized output bytes, and total client duration. Exact server
execution per request is not assumed; provider or PostgreSQL cumulative
statistics remain aggregate context and use database_cumulative provenance.

Native R2 cells record upload/download preparation, request connection,
gateway handling, exact binding operation, first byte, full body, bytes in and
out, checksum/ETag verification, decode/decompress, cache/fallback, and
serialization. Use separate payload-size and concurrency cells, including
4 KiB, 64 KiB, and 1 MiB where the authorized test harness supports them,
with concurrency 1 and 8. Provider-internal timing or billing not exposed at
that granularity is unavailable, never inferred from end-to-end duration.

### Security timing boundary

Internal-only timing may include session lookup, account validation,
role/relationship decisions, ownership checks, CSRF checks, rate limiting,
and R2 credential lookup. Do not expose role-specific timings to public
clients, use identity-bearing labels, or place timing data in public response
schemas.

### Tasks

1. Add fixed-label timing around application, pool checkout, SQL, R2 gateway calls, cache/fallback, serialization, and pipeline stages.
2. Add proxy timing/log schema without host, path parameters, or payloads.
3. Add evidence schemas and semantic validators before collecting final evidence.
4. Add authorization deny-by-default, cross-user, owner, runtime-role, migration-role, R2-identity, MCP, and workflow-identity tests.
5. Query Supabase security/performance advisors and aggregate `pg_stat_activity`/`pg_stat_statements` read-only. Query text and individual rows stay excluded.
6. Run preliminary database microprofile on the test project only:
   - 100 runtime-role fixture reads;
   - 20 isolated test writes plus verified cleanup when authorized;
   - pool checkout, SQL, commit, serialization, rows/bytes class;
   - concurrency 1 and 8 as separate cells;
   - no statement text.
7. Run preliminary native R2 microprofile only when the gateway is authorized:
   - payload classes 4 KiB, 64 KiB, and 1 MiB;
   - 20 PUT, HEAD, and GET operations per size/concurrency cell;
   - concurrency 1 and 8 separately;
   - exact generated keys under the run prefix;
   - client upload/download, gateway binding operation, bytes, status, checksum;
   - list only during cleanup verification.
8. Run a fixture-only translation-pipeline diagnostic with no external provider:
   - 3 warmups plus 30 measured two-chapter runs;
   - concurrency and queue mode fixed in artifact;
   - source fetch fixture, parse, raw persistence, DB transaction, R2 write, admission/queue, mock provider wait, QA, translated persistence, and final commit;
   - overlapping spans represented as intervals;
   - dedicated/full worker remains stopped.
9. Rank measured bottlenecks. Apply only the smallest reversible local fix supported by non-overlapping evidence.
10. If evidence is hosted, conflicting, overlapping, or unavailable, record a blocker and make no speculative fix.

### Required evidence

- `authorization-matrix.json`
- `timing-schema.json`
- `latency-attribution-preliminary.json`
- `database-microprofile.json`
- `r2-microprofile.json`
- `pipeline-timing-preliminary.json`
- `remediation-decision.json`

### Validation

Schema/validator self-tests, focused security/timing tests, Ruff, Pyright, migration checks if changed, redaction checks, zero residue, docs checker, diff check, and Graphify refresh.

### Hard stops

Overlapping spans counted twice, public telemetry leak, unsafe RLS/grant, provider/production target, writer safety unknown, or cleanup fails.

### Quantified blockers

Provider-internal timing unavailable; pooler granularity unavailable; gateway absent; safe cross-system correlation unavailable.

### Exit criteria

Security contracts pass, timing boundaries are honest, functionality is stable, and any remediation is evidence-backed.

### Canonical-document updates

All owning canonical docs for implemented security/instrumentation/config changes; current blockers to `STATUS.md`.

### Next phase

B5.

## Phase B5 - Dependency reconciliation, final candidate, and private validation

### Objective

Resolve dependency drift after functionality is stable, then freeze one candidate before final evidence or publication.

### Inputs and dependencies

B4 stable implementation, open/closed Dependabot inventory, manifests/lockfiles, and current upstream advisories.

### Allowed mutations

Dependencies, lockfiles, pinned action/container revisions, focused compatibility fixes, and exact-path Git operations when authorized.

### Forbidden mutations

Blind PR merge, unsupported latest-version claims, old R2 dependency restoration, final evidence reuse after candidate change, visibility/provider settings, and hook bypass.

### Tasks

1. Query all open Dependabot PRs and all closed/merged Dependabot PRs for every configured ecosystem.
2. Build `dependabot-ledger.json` with PR, ecosystem, dependency, proposed version, current manifest/lock version, newer available version, superseded-by, closure reason when knowable, security status, candidate action, and validation.
3. Treat closed-unmerged PRs as audit inputs. A closed PR is not proof the update was applied; compare the current manifest and latest supported release.
4. Remove/close as obsolete the boto3 update branch only after the R2 cutover removed that dependency; never merge it back.
5. Update each remaining dependency to the latest compatible release available at candidate time. Major updates require migration notes and focused/full affected tests. If the latest release is incompatible, record a concrete blocker and do not falsely claim “latest.”
6. Reconcile duplicate Dependabot ecosystems so one manifest is not updated by overlapping uv/pip jobs unnecessarily.
7. Consider grouping low-risk patch/minor development updates while keeping major/security/runtime updates reviewable.
8. Regenerate lockfiles with repository tooling; never edit generated locks manually.
9. Pin action and container revisions and record upstream release provenance.
10. Rerun B4 diagnostics affected by dependencies.
11. Run focused then justified broad backend/frontend/Worker/workflow checks.
12. Freeze:
    - commit SHA;
    - workflow hashes;
    - image digests;
    - lockfile hashes;
    - config fingerprint;
    - Plan B/test schema versions.
13. Re-run publication audit on that exact candidate while the repository is private.
14. Commit/push/PR/merge only when each is separately authorized. The validated default-branch candidate is the publication/evidence candidate; an unmerged feature branch is insufficient.

### Required evidence

- `dependabot-ledger.json`
- `dependency-validation.json`
- `candidate-manifest.json`
- `publication-audit-candidate.json`

### Validation

Lock consistency, dependency review, vulnerability scans, full affected test matrix, docs checker, hooks, cached/staged diff checks, Graphify refresh, and default-branch SHA verification.

### Hard stops

Unreviewed major/security update, lock drift, a closed update remains genuinely missed, candidate differs from validated files, or unrelated work is staged.

### Quantified blockers

Upstream incompatibility with current runtime; provider/runner unavailable for an affected integration test.

### Exit criteria

Every Dependabot proposal has a disposition, latest-compatible state is proven, tests pass, and one immutable private candidate exists.

### Canonical-document updates

`CONFIGURATION.md`/`DEPLOYMENT.md` for changed toolchain contracts, `STATUS.md` for blockers, and `EVIDENCE.md` only after verification.

### Next phase

B6.

## Phase B6 - Private hosted dry run and gated public visibility cutover

### Objective

Prove the exact default-branch candidate on hosted runners, then publish only under explicit visibility/settings authority and immediately verify protection.

### Inputs and dependencies

B5 candidate, clean publication audit, B2 workflows, GitHub settings baseline, and operation-specific authorizations.

### Allowed mutations

Private hosted workflow runs. GitHub settings/visibility changes only when their explicit authorization booleans are true.

### Forbidden mutations

Production deploy, provider changes, publication from a feature branch, untrusted fork secret access, and automatic history rewrite.

### Tasks

1. Run private default-branch hosted CI, security/static analysis, dependency review where applicable, docs gate, CodeQL/secret scanning, and container validation on the exact candidate.
2. Capture `workflow-timing.json` from run/job/step timestamps and compare queue, critical path, durations, cancellations, cache behavior, and timeout margins.
3. Require every protected workflow to pass or have a truthful non-release optional disposition.
4. Verify no required job uses a persistent/self-hosted runner.
5. Snapshot rulesets, branch protection, required check names, bypass actors, merge methods, conversation/review rules, force-push/deletion rules, Actions policy, default token permissions, fork approval, environments, Pages/packages, OIDC, Apps, hooks, and deployments.
6. Require explicit human owner acceptance of the publication surface and GPL license posture.
7. If visibility or settings authority is missing, set `public_repository_status=blocked` and do not publish. Independent non-public evidence may continue only if its workflow does not depend on publication.
8. If authorized, change private to public exactly once.
9. Immediately verify:
   - public visibility;
   - branch/tag rules;
   - all push rulesets restored/recreated because GitHub disables them on visibility change;
   - actual required checks from the new workflow revision;
   - default token restricted;
   - write tokens/secrets not sent to fork PRs;
   - fork approval behavior;
   - force-push/deletion/bypass/review/merge policy;
   - Actions allowed-action policy;
   - Pages/wiki/discussions/packages state;
   - secret scanning, push protection, Dependabot, and code scanning state.
10. Create a benign external fork PR with no secrets/provider calls, verify hosted execution and read-only permissions, then close it if authorized.
11. Retire/unregister the obsolete self-hosted runner only after hosted checks pass and an authorized runner-settings operation is independently verified. If that authority or proof is absent, do not infer that local shutdown removes repository eligibility: keep the repository private and set public_repository_status=blocked until repository access is disabled or the runner is removed by an authorized operation.
12. Rerun public default-branch CI/security and capture timing.
13. Never describe “make private again” as rollback. If exposure occurs, revoke/rotate, remove accessible artifacts where useful, assess forks/clones, and treat publication as irreversible disclosure.

### Required evidence

- `private-hosted-runs.json`
- `workflow-timing.json`
- `protection-before.json`
- `visibility-transition.json`
- `protection-after.json`
- `fork-safety.json`
- `public-main-runs.json`

### Validation

Exact candidate SHA on every run, settings before/after diff, required check enforcement, secretless fork proof, hosted runner labels, and sanitization.

### Hard stops

Publication audit not passed, authorization missing, protection cannot be restored, fork reaches privilege, candidate changes, or a secret is exposed.

### Quantified blockers

Hosted queue outage, GitHub feature unavailable by plan, optional scanner unavailable, or runner retirement permission absent.

### Exit criteria

When publication is authorized: repository is public, protections are verified, fork execution is safe, and public-main hosted runs complete. Without authorization: no visibility change and status remains blocked.

### Canonical-document updates

`DEPLOYMENT.md` and `OPERATIONS.md` with factual implemented behavior; `STATUS.md`/`EVIDENCE.md` with truthful state/evidence.

### Next phase

B7.

## Phase B7 - Final reader, frontend, pipeline, telemetry, security, and recovery evidence

### Objective

Collect exact-candidate, bounded, cancellation-safe non-production evidence without resuming the full worker/queue or generalizing to production.

### Inputs and dependencies

B5 candidate, B6 hosted runner state where required, authorized test resources, proven writer stop, and validated evidence schemas.

### Allowed mutations

Only generated test fixtures, isolated test DB rows, test R2 prefixes, ephemeral test runtime/Tunnel, isolated restore resources, and test alert state named by authorization.

### Forbidden mutations

Production, canonical content, full queue/worker resume, provider translation traffic, 10k/100k, Cloudflare purge/config, public R2, or unbounded retries.

### Tasks

1. Re-prove the frozen candidate, exact non-production target identities, authorization gates, fixture collision state, and independent writer/queue stop immediately before any write.
2. Register cancellation-safe cleanup, seed only the declared synthetic fixture, and bind every artifact to the candidate, campaign, run, topology, workload, and exact UTC interval.
3. Execute the exact reader request arithmetic, transport, cache-state, load-generator, and Quick Tunnel contracts below.
4. Execute the exact frontend navigation matrix and preserve lab-versus-field semantics.
5. Repeat the final candidate's fixture-only pipeline, database, and native R2 ingress/egress timing contracts.
6. Collect bounded Supabase, Cloudflare, and isolated Redis telemetry; record unsupported data as `unavailable` without inventing fields or billing evidence.
7. Create one same-point test-only database/R2 recovery set, restore it into isolated targets, verify consistency and public-boundary isolation, and evaluate recurring-control evidence.
8. Run cleanup after success, failure, timeout, or cancellation and independently prove zero generated database rows and R2 objects remain.
9. Validate every evidence artifact semantically and assign only the approved fail-closed dispositions.

### Transport path contract

Run the required route cells through exactly these transport classes:

| Transport class | Purpose | Acceptance role |
| --- | --- | --- |
| direct_service | direct application comparison path | diagnostic only |
| caddy_loopback | local reverse-proxy comparison path | diagnostic only; send the explicit Host header localhost |
| cloudflare_tunnel | isolated ephemeral Cloudflare path | sole reader SLO gate |

Direct and Caddy results explain local overhead but cannot replace the
Cloudflare SLO gate. A Caddy request without Host=localhost is not a valid
loopback comparison and must be recorded as not_run or failed according to
the harness contract.

### Exact reader request arithmetic

The phrase “1k profile” means exactly the SLO-gate request set below:

- 5 required routes: liveness, catalog, detail, chapter, search;
- 2 declared cache states;
- 100 counted attempts per route/state cell;
- `5 x 2 x 100 = 1,000` counted SLO-gate attempts through `cloudflare_tunnel`.

Warmup, readiness, ranking/home diagnostics, Tunnel readiness, cache reset, and comparison topologies are additional and excluded from the 1,000.

Comparison evidence is separate:

- `direct_service`: `5 x 2 x 50 = 500` counted attempts;
- `caddy_loopback`: `5 x 2 x 50 = 500` counted attempts;
- total required-route attempts across all topologies: 2,000;
- only the Cloudflare 1,000 is the named SLO stage.

No hidden retry replaces an attempt. `max_attempts_per_cell` equals the planned count. Every attempt is included in the denominator.

#### Reader transport contract

- retry policy for counted requests: none; readiness/setup retries are finite,
  separately reported, and never added to the SLO denominator;
- maximum attempts per cell: finite and equal to the declared denominator
  (100 for each required route/cache-state cell);
- every request outcome, including transport/error/timeout, consumes one
  counted attempt.

- warm concurrency: 8;
- controlled-origin-cold concurrency: 1 because reset/request pairs share cache state;
- request timeout: 20 seconds;
- redirect following: disabled;
- expected status: HTTP 200 for every required route;
- any 3xx, 4xx, 5xx, 429/WAF/rate-limit, timeout, DNS, TLS, transport, invalid body, or wrong fixture is counted and prevents a pass;
- p50/p95/p99 use nearest-rank over valid HTTP 200 durations only;
- a complete cell over p95 budget is `failed`;
- a cell with fewer planned attempts/valid responses due to a stop is `blocked`;
- cancellation records completed and unstarted counts and still runs cleanup.

Budgets:

| Route | p95 |
| --- | ---: |
| liveness | 100 ms |
| catalog | 500 ms |
| detail | 300 ms |
| chapter | 750 ms |
| search | 500 ms |

#### Cache-state contract

`warm` requires a declared warmup and readiness proof.

`controlled_origin_cold` requires, before every counted request, either an isolated cache namespace guaranteeing a miss or the guarded reset helper followed by exactly one request. One reset followed by many requests is not a cold sample.

Record each layer separately:

- browser: not applicable to HTTP profile;
- application cache;
- Redis projection/cache;
- Caddy cache;
- Cloudflare edge cache;
- R2 internal/cache state;
- database buffer/cache.

Only application/Redis/Caddy layers that the isolated helper safely resets may be `controlled`. Cloudflare, R2 internal, and database buffers are normally `not_controlled` because purge/restart is forbidden. Therefore the sample is never called globally cold.

#### Load-generator observation

For each run record runner CPU, memory, open-file/socket pressure where measurable, event-loop scheduling delay, internal request queue delay, DNS/transport/timeouts, and saturation classification. A saturated generator invalidates bottleneck attribution.

#### Quick Tunnel contract

Start one ephemeral Quick Tunnel only after isolated local liveness succeeds. Mask and never upload its URL. Require HTTP 200 before load. Quick Tunnel is test/development transport with external variability, no SLA, and a documented concurrent-request limit; concurrency 8 remains below it. It is the owner-selected non-production SLO path, not a persistent production topology, CDN guarantee, edge-latency proof, or HA proof.

### Frontend measurement contract

Measure these anonymous public routes using the fixture where applicable:

- `/`;
- `/browse-novels`;
- novel detail;
- chapter reader;
- `/ranking`.

Use the Playwright-pinned Chromium version and record it. Chrome DevTools protocol may capture performance traces; browser tools do not mutate provider state.

Profiles:

| Profile | Viewport | Context |
| --- | --- | --- |
| desktop | 1440 x 900 | declared CPU/network settings |
| mobile | 390 x 844 | declared CPU/network settings |

The public performance contexts are exactly anonymous_fresh and
anonymous_warm. Fresh means a new browser context with no prior navigation,
storage, or service-worker state. Warm means one excluded readiness
navigation followed by the measured navigations in the same context. These
contexts are browser-cache semantics only; they do not claim that Cloudflare,
R2, or database caches are cold.

For each of 5 routes x 2 device profiles x 2 context states x 7 measured navigations, collect exactly 140 navigations. Fresh context creates a new browser context for every navigation. Warm context performs one excluded warmup then seven measured navigations. Redirects, navigation failures, console errors, and failed required API/image requests are counted and prevent functional pass.

Record TTFB, FCP, LCP, CLS, TBT, JS transfer/evaluation, hydration marker when implemented, API wait, image transfer, cache status, and nearest-rank median/p75/p95. Synthetic INP is recorded only when the fixed interaction script produces a valid PerformanceEventTiming value; otherwise use `unavailable` and TBT as a lab diagnostic. Never label these results field Core Web Vitals. Performance targets are diagnostic unless a separately approved release budget exists; `frontend_status` primarily records measurement completeness and functional correctness.

### Protected frontend authorization lane

The public 140-navigation arithmetic excludes protected UI. Run a separate
test-only lane when authorized, with no production identities:

| Route class | Principal | Required boundary |
| --- | --- | --- |
| login | anonymous | public shell may load; credential submission uses a test identity only |
| representative account/library | authenticated user | user sees only user-owned data and never owner controls |
| representative owner/admin | owner | owner-only controls remain inaccessible to guest and ordinary user |

For each route class, device profile, and browser context, use seven measured
navigations after the same fresh/warm setup, for 3 x 2 x 2 x 7 = 84 protected
navigations when the authorized test identities and routes exist. If a
test-only identity, route, or authorization is unavailable, record the lane
as blocked or unavailable with a fixed reason; do not substitute a real
identity or silently remove the denominator. This lane is functional and
authorization evidence, not part of the reader SLO denominator.

Capture principal class, auth state, route class, device, context, request
failure counts, navigation timing, TTFB, FCP/LCP where valid, API wait,
resource transfer, hydration/route-transition timing, console errors, and
authorization result. Sanitize traces, screenshots, HARs, cookies, headers,
tokens, account data, and raw URLs before retention or upload.

### Final pipeline and data-path timing

Repeat the B4 fixture-only pipeline contract on the frozen candidate. No real translation provider is called. Record all stage intervals and critical path.

Repeat database and native R2 ingress/egress microprofiles on the candidate. Record client upload/download, bytes, pool/SQL, gateway/Workers binding timing, and exact operation counts. Local/process counters are not provider billing.

### Hosted telemetry

#### Supabase hosted telemetry

Use advisors and read-only aggregate SQL for:

- security/performance finding counts;
- migration head;
- `pg_stat_activity` aggregate and pool occupancy;
- `pg_stat_statements` calls/time/rows when permitted;
- connection mode/class and exact UTC window.

Cumulative database counters use provenance `database_cumulative`, never billing actual.

#### Cloudflare

Use OpenAPI `search` before read-only `execute` to query supported resources/datasets for:

- test Tunnel/connection status;
- approved route relationship;
- HTTP/cache/Tunnel analytics for the exact window when available;
- `r2OperationsAdaptiveGroups` and `r2StorageAdaptiveGroups` for exact test bucket/window where supported.

Do not invent dataset names or infer billing. Unsupported interval/field/permission becomes bounded unavailable evidence.

#### Redis

Use only isolated test Redis. Use bounded `SCAN` and `LLEN`, never `KEYS`. Record queue/writer state separately from reader HTTP.

### Recovery consistency contract

Before backup:

1. record `owner_role=project_owner` without contact details;
2. prove all writers quiesced;
3. create one opaque recovery-point ID;
4. capture migration head and the complete referenced-object digest set in a repeatable-read test transaction;
5. create the R2 backup manifest/checksums under the run prefix;
6. create the database snapshot/dump while the writer stop remains proven;
7. bind DB snapshot identity, R2 manifest identity, schema head, reference-set digest, algorithm, timestamps, and candidate into one recovery manifest.

Unrelated DB and R2 backup times do not prove recovery.

The recovery manifest must bind, at minimum, one opaque recovery-point ID,
candidate SHA, source test project class, application and backup bucket
classes, backup timestamps, migration/schema head, expected database entity
counts, expected R2 key digests/counts/byte lengths/checksums, restore target
fingerprint, observed backup and restore durations, verification status, and
cleanup status. It must identify whether each field is measured,
unavailable, blocked, or not_run. Record observed age and duration without
calling them RPO/RTO compliance unless an approved objective exists.

Restore only into an ephemeral database whose name contains `restore` and a unique R2 restore prefix. Verify:

- schema/migration head;
- tables, constraints, counts, fixture rows, and representative relationships;
- exact referenced R2 objects, sizes, checksums, broken-reference count, and unexpected extras;
- application-level representative public/private reads;
- public-boundary isolation;
- cleanup.

Verify backup schedule-derived freshness, manifest-last commit, retention, stale/failure transition, and non-production alert delivery. One manual success does not prove recurring control: require at least two consecutive scheduled candidate-compatible observations. If time or delivery path is unavailable, recovery remains partial/blocked as applicable.

Never force-delete Object-Locked material. Never send a production alert.

### Cleanup contract

Every creating step registers cleanup before creation. Workflow cleanup uses `always()`; local code uses `finally`. Cleanup is target-guarded, prefix-scoped, idempotent, production-refusing, and independently reported.

After every failure, timeout, cancellation, or success:

- delete only generated DB fixture rows;
- delete only exact generated application/recovery R2 keys;
- tear down ephemeral restore DB, runtime, Tunnel, and Redis state;
- use Supabase read-only SQL to prove zero fixture rows;
- use the native test gateway's paginated prefix inventory to prove zero fixture objects;
- confirm recovery prefixes are absent or document Object Lock retention;
- report cleanup failure independently.

A passed test with failed cleanup does not yield clean overall completion.

### Required evidence

- `baseline.json`
- `route-profile.json`
- `latency-attribution.json`
- `load-generator.json`
- `frontend-profile.json`
- `pipeline-timing.json`
- `database-microprofile.json`
- `r2-microprofile.json`
- `hosted-telemetry.json`
- `security-boundary.json`
- `writer-state-before.json`
- `writer-state-after.json`
- `recovery-manifest.json`
- `backup-controls.json`
- `restore-verification.md`
- `cleanup.json`
- `stage-1000/*.json`
- `validation.md`

### Validation

Run semantic evidence validators over every artifact, focused/full affected checks, sanitized artifact scan, writer-state proof, exact candidate join, and zero-residue checks.

### Hard stops

Writer state unknown, fixture collision, Tunnel not ready, load generator saturated, target mismatch, secret leak, production exposure, recovery-point mismatch, or cleanup guard failure.

### Quantified blockers

Provider analytics unavailable, edge/R2/DB cold layers not controlled, protected gateway absent, alert delivery unavailable, or two scheduled recovery observations not yet available.

### Exit criteria

All attempted evidence has truthful dispositions, required cleanup passes, and no result is generalized to production.

### Canonical-document updates

Actual implemented/evidenced changes map through the canonical update table below.

### Next phase

B8, or return to B4/B5 for an evidence-backed fix. Any candidate change invalidates affected B6/B7 evidence.

## Phase B8 - Documentation, final status, Git closeout, and handoff

### Objective

Validate all outputs, synchronize canonical truth, complete authorized Git operations, and issue a final non-production handoff.

### Inputs and dependencies

B7 evidence/cleanup, exact candidate, Plan A documentation contract, and Git operation authorizations.

### Allowed mutations

Canonical documentation reflecting actual changes/evidence, final validators, exact authorized Git operations, and sanitized artifacts.

### Forbidden mutations

Invented success, destructive documentation cleanup, unrelated formatting, unapproved remote/setting/provider operations, and production claims.

### Canonical update map

| Change | Canonical owner |
| --- | --- |
| architecture/trust/roles | `ARCHITECTURE.md` |
| environment/configuration | `CONFIGURATION.md` |
| workflow/release/deploy | `DEPLOYMENT.md` |
| runbook/recovery/cleanup | `OPERATIONS.md` |
| storage/R2 contract | `STORAGE.md` |
| translation/pipeline contract | `TRANSLATION.md` |
| current blocker/decision | `STATUS.md` |
| verified completed result | `EVIDENCE.md` |
| UI/design contract | `DESIGN.md` |

Use Plan A's checker and formatting rules. Do not recreate them here.

### Tasks

1. Validate every evidence artifact against schema and semantic postconditions.
2. Hash final artifacts and record bounded retention.
3. Reconcile final candidate against all evidence; invalidate stale bundles.
4. Update only owning canonical docs with current truth and verified outcomes.
5. Run all required local and hosted checks.
6. Review diff for unrelated changes and stale migration terminology.
7. Stage exact paths/hunks, keep hooks enabled, and commit/push/PR/merge only as separately authorized.
8. Verify remote PR/merge state rather than trusting command prose.
9. Rerun final default-branch hosted checks after merge when authorized.
10. Produce `handoff.md` and `handoff.json` with workflow/run URLs, artifact names, sanitized outcomes, cleanup proof, recovery status, commands/exit codes, changed Markdown, preserved owner changes, blockers, uncertainty, and one next action.
11. Never include secrets, raw IDs/hosts, or private URLs in public handoff.

12. Run a deterministic contradiction review across the plans, canonical
docs, active specifications, workflows, and evidence schemas. Search at
minimum for conflicting claims about private/public visibility, test versus
production targets, native R2 versus compatibility storage, hosted versus
self-hosted runners, queue/writer state, reader denominator and cache
semantics, frontend filename/arithmetic, user/owner authority, status
vocabulary, and old canonical paths. Resolve or block every contradiction;
do not accept a green workflow as proof that the contract is satisfied.

### Required final check command matrix

Resolve exact repository paths and versions from the candidate before running,
then record command, timeout, exit code, result count, paths, and candidate
SHA:

~~~powershell
pwsh -NoProfile -File tools/docs-check.ps1
tools/ruff.ps1 check .
tools/pyright.ps1
tools/pytest.ps1 <focused-backend-tests>
pre-commit run --all-files
git diff --check
~~~

When frontend behavior or its validator changed, also run:

~~~powershell
Push-Location frontend
npm run lint
npm run typecheck
npm run test
npm run build
Pop-Location
~~~

When Worker code changed, run the repository's canonical Wrangler check,
generated-type check, and Worker tests without deploying. Run the workflow
security/guard tests, evidence validators, router guard, stale-path and
forbidden-fallback searches, and a final graph refresh. A command that is not
applicable is recorded as not_run or not_applicable, never as passed.

### Required status fields

Each field uses the evidence namespace unless noted:

- `reader_slo_status`;
- `path_profile_status`;
- `frontend_status`;
- `pipeline_timing_status`;
- `telemetry_status`;
- `security_status`;
- `recovery_status`;
- `cleanup_status`;
- `documentation_status`;
- `public_repository_status`;
- `overall_follow_up_disposition`: `complete`, `complete_with_quantified_blocker`, or `blocked`;
- `production_capacity_claim`: always `not_established`.

No `passed_with_notes` exists.

### Required evidence

- `final-validation.json`
- `artifact-manifest.json`
- `handoff.md`
- `handoff.json`

### Validation

At minimum:

```powershell
pwsh -NoProfile -File tools/docs-check.ps1
tools/ruff.ps1 check .
tools/pyright.ps1
git diff --check
graphify update . --no-cluster
```

Also run focused/broad backend, frontend, Worker, workflow, migration, security, evidence, and capacity validators based on changed surfaces. Record command, timeout, exit code, result count, paths, and candidate SHA. Never claim an unrun command passed.

### Hard stops

Stale evidence, failed required validator, cleanup residue, missing canonical update, unrelated staged change, or requested remote state not verifiable.

### Quantified blockers

Legitimate provider/recurring evidence unavailable after all safe attempts.

### Exit criteria

The final candidate/evidence/docs are internally consistent, authorized Git state is verified, and all remaining limits are explicit.

### Canonical-document updates

Per the update map.

### Next phase

None. Plan B work can be complete while external evidence remains unavailable only when `overall_follow_up_disposition=complete_with_quantified_blocker` and no hard safety or cleanup gate remains.

## Security stop conditions, rollback points, and failure matrix

### Hard stops

Stop the affected phase and every dependent phase immediately when an active
credential is found in source/history/logs/artifacts; a target cannot be
proven non-production; the Supabase project match is zero or ambiguous; an
R2 bucket is not exactly allowlisted; a fixture collides; writer or queue
state is unknown before destructive work; fork code reaches secrets or
privileged tokens; a public PR can execute on a persistent runner; a
visibility/settings snapshot is stale or cannot be restored; an artifact
contains raw provider data; cleanup scope is broader than the run; a
provider operation would mutate forbidden Cloudflare or production state; or
an isolated restore target cannot be proven.

### Quantified blockers

Continue unaffected work only when the limitation is genuinely bounded:
provider analytics granularity, pg_stat_statements permission, exact
Cloudflare/R2/Tunnel timing, Chrome DevTools availability, an authorized
test gateway, a non-production alert destination, Quick Tunnel service
availability, hosted queue capacity, or recurring scheduled observations.
Each blocker names the affected evidence, target class, UTC interval, fixed
reason, owner role, next action, retry condition, and safety disposition.

### Failure classification

| Situation | Disposition | Permitted continuation |
| --- | --- | --- |
| complete sample exceeds a budget | failed | attribution/remediation only; no pass claim |
| required sample is incomplete | blocked | unaffected cells only |
| provider metric is not exposed or permitted | unavailable | continue with bounded omission |
| secret or privileged fork path is found | blocked | no publication until repaired and revalidated |
| fixture collision or production target | blocked | stop without overwrite or deletion |
| timing overlap/negative residual | failed | fix instrumentation and rerun evidence |
| Quick Tunnel readiness failure | blocked | no reader load; comparison diagnostics may run only if safe |
| cleanup leaves residue | failed/blocked | retry exact scoped cleanup; no closeout |
| DB and R2 backups are different points | failed/blocked | no recovery pass |
| alert delivery is unauthorized/unavailable | unavailable | recovery remains partial/blocked as applicable |

### Rollback and exposure response

Before visibility change, rollback is a reviewed revert of Plan B-owned
changes only; preserve owner-pre-existing work and never rewrite history
without explicit authority. After visibility change, publication is an
irreversible disclosure event, not a reliable rollback target: revoke/rotate
affected secrets, disable the path, remove accessible logs/artifacts where
useful, assess forks/clones/caches, repair the candidate, and record the
incident. Reducing visibility later does not erase copies.

For test data, rollback means exact run-ID database cleanup, exact R2 prefix
cleanup, isolated restore-target teardown, test Redis namespace cleanup, and
ephemeral Tunnel/container shutdown. Never use a broad restore or wildcard
deletion. If an Object-Locked object cannot be removed, record the retained
prefix and its retention reason.

Even a completely successful non-production campaign does not establish
production capacity: the runner, Tunnel, provider telemetry, writers, and
traffic pattern are intentionally different. production_capacity_claim
remains not_established.

## Universal evidence envelope

Every JSON evidence record contains:

- `schema_version`;
- `plan_id` and `plan_version`;
- `candidate_sha`;
- `workflow_run_id` when hosted;
- `campaign_id` and `run_id`;
- `environment=non-production`;
- sanitized target classes/digests;
- UTC start/end;
- monotonic clock source where applicable;
- topology/workload/config fingerprint;
- fixed metric/status names;
- value and unit or fixed `unavailable_reason`;
- sample/attempt/error counts;
- aggregation;
- collection status;
- provenance;
- validator command/exit;
- artifact SHA-256.

Artifacts use seven-day retention by default unless recovery/Object Lock policy requires a longer reviewed period. Evidence intended for public Actions artifacts is scanned before upload.

### Canonical evidence bundle

The final bundle uses one name per purpose. It includes baseline.json,
workflow-inventory.json, publication-audit.json, route-profile.json,
frontend-profile.json, pipeline-timing.json, latency-attribution.json,
load-generator.json, database-microprofile.json, r2-microprofile.json,
hosted-telemetry.json, security-boundary.json, writer-state-before.json,
writer-state-after.json, recovery-manifest.json, backup-controls.json,
restore-verification.md, cleanup.json, stage-1000/*.json, validation.md,
final-validation.json, artifact-manifest.json, handoff.md, and handoff.json
as applicable to the phase that produced them. Do not emit a second legacy
name for the same artifact; if a validator expects an old name, migrate the
validator and references atomically.

### Timing span schema

Each span records name, parent, clock, start offset, duration, sample count,
aggregation, availability, and a fixed unavailable reason when needed.
Durations are non-negative. An exclusive_children list or equivalent states
which non-overlapping children are subtracted from a parent. Sibling overlap
is allowed only when the spans are genuinely concurrent and is never summed
as serial time. Cross-process subtraction requires a clock/alignment proof;
otherwise the derived layer is unavailable. The validator rejects a child
sum greater than its parent beyond a documented rounding tolerance and
rejects a negative residual.

### Reader route-cell schema

Each route cell records route class rather than a raw URL, transport class,
cache mode, layers_reset, layers_not_controlled, attempted/completed counts,
warm/controlled-cold counts, failures, timeouts, p50/p75/p90/p95/p99,
bytes in/out where safe, concurrency, timeout, budget, exact UTC window,
candidate/run identity, and attribution status. The validator requires
denominator reconciliation and rejects a budget result when the required
sample count or readiness proof is incomplete.

### Frontend profile schema

Each browser cell records lane, route class, principal class, authentication
state, device profile, viewport, browser/Playwright revision, fresh or warm
context, navigation count, functional failures, request failure classes,
timing metrics, resource groups, cache classification, and sanitization
status. Public performance and protected authorization lanes remain
separate. Browser lab metrics are not field Web Vitals and do not change the
reader SLO denominator.

### Provider telemetry schema

Each provider metric records provider, supported dataset or API-operation
category, exact UTC window, target class/digest, fixed metric name,
aggregation, value and unit, collection status, provenance, and an
unavailable reason when unsupported. Use database_cumulative for cumulative
PostgreSQL statistics. Never infer billing, provider-internal timing, or
cost from local counters or end-to-end duration.

### Backup and restore manifest schema

The recovery manifest binds one opaque run/recovery-point ID, candidate SHA,
source test project class, application and backup bucket classes, backup
timestamps, migration/schema head, expected database entity counts, expected
R2 key hashes/counts/byte lengths/checksums, restore target fingerprint,
observed backup/restore durations, verification status, and cleanup status.
The manifest explicitly distinguishes measured, unavailable, blocked, and
not_run fields. RPO/RTO compliance is not claimed without approved
objectives and recurring evidence.

### Security-boundary evidence

Record test case IDs and sanitized outcomes, never personal identities:

- guest_user_route_401;
- guest_owner_route_401;
- user_owner_route_403;
- user_a_user_b_read_denied;
- user_a_user_b_write_denied;
- revoked_session_denied;
- csrf_required_cookie_mutation;
- unpublished_public_read_denied;
- service_role_not_browser_equivalent;
- rls_server_check_consistent.

The tests must prove session-derived identity, explicit role boundaries,
RLS/grant/server-check agreement, CSRF for cookie mutations, and that service
credentials are not a browser authorization mechanism.

### Sanitization validator

Reject an artifact that contains private-key headers, token/PAT/JWT-like
values, credentialed or signed URLs, DSNs, cookies, authorization headers,
raw SQL, email addresses where disallowed, internal/ephemeral hostnames,
request/response bodies, source or translated content, raw provider payloads,
or unapproved object keys. Report only artifact path and fixed category/count,
never the matched value.

### Evidence disposition rules

- complete valid required samples within budget: `passed`;
- complete valid required samples over budget or wrong response: `failed`;
- incomplete required samples, invalid target/readiness, or safety stop: `blocked`;
- some independent evidence complete and some unavailable: `partial`;
- provider does not expose/permit the metric: `unavailable`;
- authorized attempt never started: `not_run`.

A successful workflow proves orchestration completion only. It does not prove its capacity, security, recovery, cleanup, or publication assertions unless semantic validators pass.

## Path registry

Every execution refreshes this registry and gives every concrete path one category. The category records the planned disposition; B0 separately records whether the path is currently present.

| Path | Category |
| --- | --- |
| both `docs/plans/` files | `exists_now` |
| nine canonical files from the validated Plan A handoff | `exists_now` |
| `tools/docs_check.py` and `tools/docs-check.ps1` from the validated Plan A handoff | `exists_now` |
| each current workflow path listed in B1 | `exists_now` at Plan B start |
| each renamed workflow destination listed in B1 | `renamed_by_plan_b` |
| each newly created workflow path listed in B1 | `created_by_plan_b` |
| each obsolete compatibility workflow/client/test path | `removed_by_plan_b` after B3 |
| native Worker gateway source/config/test paths | `created_by_plan_b` |
| `artifacts/public-hosted-execution/**` | `created_by_plan_b` |
| provider test Worker/Access/binding paths not selected by authorization | `optional` |
| production resources and paths | `forbidden` |
| historical archives containing migration terms | `historical_only` |

B0 expands this table to every concrete path named in code, workflows, specs, docs, and artifacts. A path may not have two categories; when a target is renamed, the source and destination are separate concrete rows.

## Official guidance baseline

Execution must refresh these primary sources because platform behavior changes:

- [GitHub repository visibility effects](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/managing-repository-settings/setting-repository-visibility)
- [GitHub Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions)
- [GitHub-hosted runners](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)
- [GitHub Actions secure use](https://docs.github.com/en/actions/reference/security/secure-use)
- [GitHub pull_request_target security](https://docs.github.com/en/actions/reference/security/securely-using-pull_request_target)
- [GitHub Actions secure-use reference](https://docs.github.com/en/actions/reference/security/secure-use)
- [GitHub workflow permissions and fork behavior](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax)
- [Cloudflare R2 API surfaces](https://developers.cloudflare.com/r2/api/)
- [Cloudflare R2 Workers API](https://developers.cloudflare.com/r2/api/workers/workers-api-reference/)
- [Cloudflare Quick Tunnel limits](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/trycloudflare/)
- [Cloudflare R2 metrics](https://developers.cloudflare.com/r2/platform/metrics-analytics/)
- [Supabase RLS](https://supabase.com/docs/guides/database/postgres/row-level-security)
- [Supabase connection modes](https://supabase.com/docs/guides/database/connecting-to-postgres)
- [Supabase database advisors](https://supabase.com/docs/guides/database/database-advisors)
- [Web Vitals lab versus field semantics](https://web.dev/articles/vitals)

External guidance informs the plan; repository contracts and explicit owner decisions control project behavior.

## Phase command and check matrix

Resolve the exact repository command and candidate version in B0. Every
executed command is recorded with timeout, exit code, result count when
applicable, affected paths, and candidate SHA. An inapplicable command is
not_run or not_applicable, never passed.

| Phase | Minimum checks |
| --- | --- |
| B0 | Git baseline; Plan A handoff/hash validator; docs checker; workflow/runner inventory; Supabase projects first; Cloudflare search-only discovery; target deny-list and fixture collision checks |
| B1 | secret/history/public-surface review; workflow trigger/secret/cache review; GitHub protection snapshot; governance/license review; Cloudflare/Supabase read-only posture; sanitized audit |
| B2 | YAML parse; action/container pin check; Zizmor/security checks; pre-commit all-files; timeout/permission/concurrency/resource-control tests; hosted Ubuntu compatibility smoke |
| B3 | Worker type/check/test; backend R2 client tests; exact-key/range/checksum/conditional/prefix/identity deny tests; active compatibility-term zero scan; no-deploy provider guard |
| B4 | timing-schema self-tests; overlap and negative-residual tests; authorization/CSRF/session/RLS tests; database and R2 microprofiles; pipeline timing validator; redaction and zero-residue checks |
| B5 | all open/closed Dependabot disposition; lock consistency; vulnerability/dependency review; affected backend/frontend/Worker/workflow tests; exact candidate/publication audit |
| B6 | private default-branch hosted runs; workflow timing; ruleset/protection before/after verification; secretless fork proof; visibility transition only when authorized; public-main reruns |
| B7 | target identity/writer proof; fixture collision gate; direct/Caddy/Tunnel route cells; browser public/protected lanes; telemetry; same-point DB/R2 recovery; cleanup after all outcomes |
| B8 | semantic artifact validators; docs checker; Ruff/Pyright; focused and affected tests; frontend lint/typecheck/test/build when applicable; router/security/stale-term guards; diff and Graphify checks; authorized Git/remote verification |

Required frontend commands, when the frontend surface changed, are:

~~~powershell
Push-Location frontend
npm run lint
npm run typecheck
npm run test
npm run build
Pop-Location
~~~

Required repository wrappers, when their affected surfaces apply, are:

~~~powershell
tools/pyright.ps1
tools/ruff.ps1 check .
tools/pytest.ps1 <focused-or-affected-tests>
pre-commit run --all-files
~~~

The matrix is a checklist of evidence to collect, not a declaration that any
command has already run.

## Scenario simulation and deterministic disposition

| Scenario | Required result |
| --- | --- |
| Plan A handoff mismatch | hard stop before any Plan B mutation |
| production/ambiguous project or bucket | hard stop |
| dirty owner changes | preserve and isolate; stop only on unsafe overlap |
| unsafe public workflow or secret | block publication |
| no test R2 gateway authorization | repository cutover may complete; live R2/reader evidence blocked; no fallback |
| provider metric unavailable | explicit unavailable snapshot; no invented value |
| Quick Tunnel readiness failure | no reader load; blocked |
| partially controlled cold path | label controlled layers; never call globally cold |
| complete slow route | failed |
| incomplete route | blocked |
| load generator saturated | attribution blocked |
| cleanup failure | cleanup failed and overall blocked |
| DB/R2 backups from different points | recovery failed/blocked |
| alert path unavailable | alert delivery unavailable; recovery partial/blocked |
| dependency changes after evidence | invalidate affected evidence and return to B5 |
| docs-only post-freeze change | preserve runtime evidence only with byte-identical runtime/workflow proof |
| visibility authority absent | repository stays private; public status blocked |
| post-public secret discovery | revoke/rotate, remove accessible artifacts where useful, assess copies; privacy reversal is not rollback |
| successful non-production campaign | production capacity remains not established |

## Definition of complete

Plan B is complete only when:

- Plan A handoff remains valid;
- publication and workflow trust audits are complete;
- target workflow set is hosted, bounded, pinned, and fork-safe;
- active storage has one native R2 Worker path and no compatibility/filesystem fallback;
- authorization and timing contracts are implemented/tested;
- all Dependabot open/closed proposals have a verified disposition;
- one immutable candidate joins every final artifact;
- authorized publication/protection work is verified, or its absence is a quantified blocker with no unsafe partial mutation;
- reader/frontend/pipeline/database/R2/telemetry/recovery evidence has truthful dispositions;
- cleanup proves zero residue or the overall result is blocked;
- canonical docs and final handoff pass Plan A's checker;
- all authorized Git/remote outcomes are independently verified;
- `production_capacity_claim=not_established`.

This definition does not require every provider metric to exist. It does require every absence to be bounded, every safety gate to remain closed, and no successful non-production result to be promoted into a production claim.
