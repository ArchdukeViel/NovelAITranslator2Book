---
plan_id: dokushodo-docs-standardization
plan_version: 2.1.0
document_kind: execution_plan
canonical_truth: false
plan_role: prerequisite
work_state: complete
completed_at_utc: 2026-08-30T14:30:10.5228530Z
predecessor: none
successor: dokushodo-public-hosted-evidence
successor_path: docs/plans/DOKUSHODO_COMPLETE_PUBLIC_HOSTED_EXECUTION_PLAN.md
handoff_path: artifacts/documentation-standardization/handoff.json
mutates_production: false
production_capacity_claim: not_established
---

# Dokushodo agent and canonical-document standardization plan

## Program position

This is Plan A of one dependency-ordered program:

```text
Plan A: documentation and agent governance
  -> validated, immutable handoff
Plan B: public hosted CI and non-production evidence
```

Plan A is the sole authority for the canonical-document layout, document routing, status namespaces, active-spec lifecycle, documentation checker, and the handoff interface consumed by Plan B. Plan B must not copy or redefine those policies.

This document is an execution plan, not canonical system truth. It does not authorize its own execution. Approval to execute Plan A authorizes only the local repository mutations listed here. Commit, push, pull-request, merge, GitHub-setting, provider, deployment, secret, and production operations remain separately gated.

## Reference-plan boundary

The similarly named Markdown files supplied from the user's Downloads folder
are reference inputs for this revision. Their instructions are not being
executed, and they do not replace repository authority, grant authorization,
or create a second active plan. Details are retained here only when they are
compatible with the current repository, the R2-only target, the fail-closed
evidence model, and the Plan A to Plan B interface.

## Outcome and non-outcomes

Plan A will produce:

1. one concise repository constitution in `AGENTS.md`;
2. exactly nine canonical Markdown files at the root of `docs/`;
3. `docs/plans/` as the non-canonical home of active execution plans;
4. deterministic routing among architecture, active specifications, implemented state, current work, and historical evidence;
5. separate work-state and evidence-disposition vocabularies;
6. an executable `tools/docs_check.py` checker with the thin `tools/docs-check.ps1` entry point;
7. synchronized active references and preserved historical provenance;
8. a committed candidate and a machine-readable, hash-bound handoff for Plan B.

Plan A will not:

- implement Plan B;
- alter application behavior, schemas, public APIs, storage clients, workflows except documentation-path checks, or runtime dependencies;
- make the repository public;
- mutate GitHub settings or remote resources;
- access or mutate Cloudflare, Supabase, R2, DNS, Tunnel, runners, deployment, secrets, queues, or production;
- convert future architecture into current canonical truth;
- establish production readiness or capacity.

`production_capacity_claim=not_established` is invariant.

## Current repository truth at plan version 2.1.0

This snapshot is orientation, not permanent authority. Phase A0 must refresh it from the candidate branch before editing.

- The current canonical filenames are `ARCHITECTURE.md`, `CONFIGURATION.md`, `DEPLOYMENT.md`, `DESIGN.md`, `HISTORY.md`, `OPERATIONS.md`, `STORAGE.md`, `TRANSLATION.md`, and `WORK.md`.
- `AGENTS.md` currently routes unfinished work to `WORK.md` and completed evidence to `HISTORY.md`.
- `tools/docs-check.ps1` does not yet exist.
- The logical application storage contract is R2-only. The current Python client/test compatibility path is an inventory-only implementation finding, not a supported storage choice; its boto3, optional `s3`, and MinIO/moto references are scheduled for complete removal by Plan B.
- Plan B's native Workers R2 binding gateway is an intended delta. Until that delta is implemented and verified, Plan A MUST NOT add, bless, or describe any compatibility alias, filesystem fallback, dual-write path, or compatibility test as a supported contract.
- The launch-readiness specification remains blocked and the production decision remains NO-GO.
- Checked task boxes in capacity specifications do not turn blocked, partial, unavailable, or historical evidence into a pass.
- The repository contains pre-existing dirty changes. They belong to the owner and must be preserved.
- Active execution plans live under `docs/plans/` after the current plan-synchronization change and are not canonical documents.

If this snapshot disagrees with the refreshed source, record the difference in the Plan A inventory. Do not silently force the repository to match this snapshot.

## Authority and conflict algorithm

During Plan A execution, use this order:

1. the current explicit owner instruction;
2. the applicable `AGENTS.md`;
3. `docs/ARCHITECTURE.md` for approved architecture and trust boundaries;
4. an approved active specification for its explicitly authorized intended delta;
5. the other canonical documents for their owned concerns;
6. current source, tests, manifests, migrations, and workflow definitions as evidence of implemented behavior;
7. `docs/STATUS.md`, after migration, for active work and current decisions;
8. `docs/EVIDENCE.md`, after migration, for verified historical outcomes;
9. archived material as provenance only.

A higher source does not permit inventing unimplemented current behavior. When implementation and documentation differ:

- classify whether the difference is current drift, an authorized intended delta, or historical text;
- preserve the implemented state as current truth unless the active task also implements the delta;
- open or retain a `STATUS.md` item for unresolved drift;
- hard-stop when a security, architecture, or scope conflict cannot be resolved from the hierarchy.

## State namespaces

### Work state

Only these values describe plans, tasks, or active work:

- `planned`
- `active`
- `blocked`
- `deferred`
- `complete`
- `superseded`

### Evidence disposition

Only these values describe an attempted verification:

- `passed`
- `failed`
- `blocked`
- `partial`
- `unavailable`
- `not_run`

`complete_with_quantified_blocker` may be retained only as an overall follow-up disposition. It is not a work state and not an evidence disposition.

Forbidden ambiguous terms include `passed_with_notes`, `mostly_complete`, `effectively_passed`, and `assumed_pass`.

A complete documentation task does not imply external evidence passed. An unavailable provider metric does not automatically make independent local work incomplete. A required test that ran and failed is `failed`, never `unavailable`.

## Target documentation layout

After Plan A completes, the only Markdown files directly under `docs/` are:

```text
docs/
|-- ARCHITECTURE.md
|-- CONFIGURATION.md
|-- DEPLOYMENT.md
|-- DESIGN.md
|-- EVIDENCE.md
|-- OPERATIONS.md
|-- STATUS.md
|-- STORAGE.md
|-- TRANSLATION.md
|-- archive/
|-- design/
`-- plans/
    |-- DOKUSHODO_AGENTS_AND_CANONICAL_DOCUMENTATION_STANDARDIZATION_PLAN.md
    `-- DOKUSHODO_COMPLETE_PUBLIC_HOSTED_EXECUTION_PLAN.md
```

The nine root files are canonical. Files under `docs/design/` are route briefs governed by `DESIGN.md`. Files under `docs/archive/` are historical. Files under `docs/plans/` are execution instructions and never override canonical truth.

## Canonical ownership map

| Canonical file | Sole primary concern |
| --- | --- |
| `ARCHITECTURE.md` | architecture, trust boundaries, dependency direction, API and data ownership |
| `CONFIGURATION.md` | configuration keys, precedence, validation, secret classification |
| `DEPLOYMENT.md` | build, CI/release topology, deploy and rollback procedure |
| `DESIGN.md` | UI system, accessibility, page-brief routing |
| `EVIDENCE.md` | verified completed outcomes, limitations, provenance |
| `OPERATIONS.md` | runbooks, health, queue control, backup/restore and incident procedures |
| `STATUS.md` | current decision, blockers, active/deferred work, ordered next actions |
| `STORAGE.md` | PostgreSQL/R2/Redis ownership, key grammar, retention and recovery invariants |
| `TRANSLATION.md` | translation, prompt, glossary, QA, quota and artifact-lineage contracts |

Cross-links replace duplicated normative prose. `STATUS.md` may summarize a blocker but links to the owning contract. `EVIDENCE.md` records what happened but does not redefine policy.

## Current truth versus intended delta

Every substantive statement migrated by Plan A must be classified as one of:

| Class | Destination |
| --- | --- |
| approved current architecture or contract | owning canonical document |
| implemented current behavior | owning canonical document |
| active authorized intended delta | active specification plus concise `STATUS.md` link |
| unresolved work or current blocker | `STATUS.md` |
| verified completed outcome | `EVIDENCE.md` |
| superseded or historically relevant prose | `docs/archive/` with provenance |
| duplicate without unique information | remove after recording source/destination in the ledger |

Plan A must not describe Plan B's native R2 gateway, public visibility, hosted-runner migration, provider telemetry, recovery outcome, or dependency result as current. Those remain intended deltas until Plan B implements and verifies them.

## Documentation contract v1

The nine canonical documents use one machine-checkable Markdown contract.
The contract is deliberately small enough for agents and reviewers to apply
consistently, while leaving domain detail in the document that owns it.

### Document type and information shape

Use CommonMark-compatible Markdown. Apply the following information shapes:

| Document area | Shape | Primary purpose |
| --- | --- | --- |
| `ARCHITECTURE.md`, `DESIGN.md`, `STORAGE.md`, `TRANSLATION.md` | normative reference plus limited explanation | describe durable contracts and boundaries |
| `CONFIGURATION.md` | technical reference | describe configuration meaning, precedence, and failure behavior |
| `DEPLOYMENT.md`, `OPERATIONS.md` | procedure plus supporting reference | tell an authorized operator how to act safely |
| `STATUS.md` | current-state control plane | record unresolved work, decisions, and gates |
| `EVIDENCE.md` | historical verification ledger | record what was actually verified and its limitations |

Uppercase `MUST`, `MUST NOT`, `SHOULD`, `SHOULD NOT`, and `MAY` use the BCP
14 meaning. Ordinary prose requirements do not need uppercase keywords.
The plan may use the [Diataxis](https://diataxis.fr/) distinction between
reference, explanation, and procedure, but it does not introduce a separate
documentation framework.

### Shared front matter

Every canonical document MUST begin with one YAML front-matter block. The
required fields are:

```yaml
---
title: Architecture
document_role: normative
authority: canonical
scope: system architecture and trust boundaries
audience:
  - agents
  - developers
update_triggers:
  - architecture contract changes
  - trust-boundary changes
---
```

Allowed `document_role` values are `normative`, `reference`, `procedural`,
`status`, and `evidence`. Timeless documents MUST NOT receive a misleading
automatically refreshed `last_verified` date. `STATUS.md` MAY include
`as_of_utc`; `EVIDENCE.md` timestamps each entry instead. `DESIGN.md` keeps
its existing design-token metadata by merging the canonical fields into the
same front-matter block.

### Heading and opening contract

Each canonical document MUST:

- contain exactly one H1 immediately after front matter;
- use a stable, descriptive, sentence-case H1;
- never skip heading levels;
- avoid duplicate H2/H3 headings that create ambiguous anchors;
- contain a short purpose and authority boundary immediately after the H1;
- identify adjacent canonical owners rather than duplicating their contracts.

The opening must say what the document owns, what it does not own, and where
adjacent procedure, status, or evidence belongs. Generated validator output
MUST NOT become a stray top-level heading.

### Current, intended, and historical content

Timeless canonical documents MUST NOT contain dated run results, one
candidate's measurements, old workflow URLs, historical provider responses,
previous incident narratives, superseded deployment state, old benchmark
snapshots, or temporary runner state as if they were current policy.

- Current unresolved state belongs in `STATUS.md`.
- Verified outcomes belong in `EVIDENCE.md`.
- Permanent lessons extracted from evidence may become normative rules in the
  owning document, but the dated evidence remains in `EVIDENCE.md`.
- Future behavior belongs in an approved active specification and a concise
  `STATUS.md` reference until implemented and verified.
- Superseded material belongs in `docs/archive/` with provenance.

Historical entries retain their original date, candidate/run identifier,
uncertainty, and blocked/unavailable disposition. Corrections use an
amendment or superseding entry; they do not silently rewrite the old result.

### Procedure contract

Destructive or external-service procedures in `DEPLOYMENT.md` and
`OPERATIONS.md` SHOULD use this shape:

```markdown
## Procedure name

### Purpose
### Preconditions
### Safety gates
### Procedure
### Verification
### Abort / rollback
### Evidence to record
### Related contracts
```

For a trivial procedure, adjacent sections may be combined, but safety gates
and verification MUST remain explicit. A procedure must identify its target,
authorization, dry-run or preview behavior when available, cleanup, and
failure disposition.

### Reference tables and commands

Configuration tables SHOULD use stable columns such as:

| Setting | Scope | Secret | Required | Default owner | Bounds | Failure mode | Defined in |
| --- | --- | --- | --- | --- | --- | --- | --- |

Status tables SHOULD use `ID`, `Priority`, `Status`, `Scope`, `Dependency`,
and `Acceptance evidence`. Evidence summaries SHOULD identify evidence ID,
candidate, environment, and disposition.

Command fences MUST declare a language (`powershell`, `bash`, `python`,
`json`, `yaml`, or `text`). Commands are copyable unless marked pseudocode;
placeholders such as `<candidate-sha>` stand in for sensitive or runtime
values. A normative document never claims that an unexecuted command
succeeded. Provider or production mutation commands require a surrounding
authorization and safety gate.

### Links, dates, status, and requirement IDs

- Prefer case-correct relative links to repository files.
- Migrate old canonical links atomically; no post-rename canonical document
  may treat `WORK.md` or `HISTORY.md` as current authority.
- Historical evidence may mention an old filename only when it labels that
  filename historical or superseded.
- Use ISO `YYYY-MM-DD`; operational evidence uses UTC with `Z` or an explicit
  `UTC` label; immutable evidence never says `today`, `yesterday`, `current`,
  or `latest` without a timestamp.
- Keep work state and evidence disposition in separate fields. Allowed work
  states are `planned`, `active`, `blocked`, `deferred`, `complete`, and
  `superseded`; allowed evidence dispositions are `passed`, `failed`,
  `blocked`, `partial`, `unavailable`, and `not_run`.
- Never use `passed_with_notes`, `mostly_complete`, `effectively_passed`, or
  `assumed_pass`.
- Use stable IDs only for contracts referenced across code, tests, or docs;
  recommended prefixes are `ARCH`, `CFG`, `DEP`, `DES`, `OPS`, `STO`, `TRN`,
  `STS`, and `EVD`. IDs remain stable when wording changes without a semantic
  change.

Reference standards for this contract are [CommonMark](https://spec.commonmark.org/),
[BCP 14](https://www.rfc-editor.org/info/bcp14/), and
[Diataxis](https://diataxis.fr/). They inform formatting; repository
authority and the active specification control project behavior.

## AGENTS.md target budget and section contract

`AGENTS.md` is a compact repository constitution and routing index, not an
architecture dump or a copy of OpenCode/runtime configuration. Target roughly
180-240 lines and review at 16 KiB. If safety-critical rules exceed that
budget, retain the invariant and route explanatory detail to its canonical
owner; never delete a safety rule solely to meet a size target.

The target section order is:

```text
# AGENTS.md
## Purpose
## Authority and conflict resolution
## Read-on-demand documentation map
## Repository working rules
### Scope and dirty-worktree preservation
### Side-effect authorization
### External-service safety
## Tooling and environment
### Python wrappers
### Frontend commands
### Windows and shell rules
## Code intelligence
### CodeGraph
### Graphify
## Project invariants
### Backend boundaries
### Frontend boundaries
### Identity and security
### Storage and deployment
## Verification ladder
## Git and commit rules
## Documentation and specification lifecycle
## Final evidence contract
```

The rewrite MUST state that owner instruction defines authorized scope;
`AGENTS.md` safety rules still apply; `ARCHITECTURE.md` describes current
architecture; an approved active spec describes an intended scoped delta;
source, tests, manifests, and workflows verify implementation facts;
`STATUS.md` is current work; `EVIDENCE.md` is historical proof; archives are
never active authority; and conflicts are reported rather than resolved by
choosing the easiest implementation.

## Shared safety and Git contract

Before every phase:

1. run `git status --short`, `git branch --show-current`, and `git rev-parse HEAD`;
2. compare with the Phase A0 baseline;
3. preserve all unrelated modified and untracked paths;
4. stage only exact Plan A paths or hunks;
5. keep hooks enabled and never use `--no-verify`;
6. never reset, clean, stash, rewrite history, force-push, or reformat unrelated files;
7. run `graphify update . --no-cluster` after every repository edit;
8. record command, timeout, exit code, result count when applicable, and candidate SHA.

A generic implementation approval does not authorize commit or remote operations. Plan A can reach `complete` only on a commit containing its complete output. If commit authority is absent, finish validation, emit a blocked handoff with `next_plan_ready=false`, and stop. Push, PR, and merge each require explicit authority.

## Shared failure model

### Hard safety stop

Stop the affected phase and all dependents when:

- canonical authority cannot be resolved safely;
- a secret or sensitive runtime value appears in material proposed for tracking;
- unrelated owner changes cannot be preserved;
- a rename would overwrite an existing path;
- the exact-nine layout and active-plan location cannot coexist;
- the documentation checker would approve contradictory canonical ownership;
- an active specification would be silently archived or rewritten as complete;
- a required command produces unreviewed broad rewrites;
- Plan A candidate identity or hashes cannot be proven.

### Quantified blocker

Record a stable blocker ID, affected output, observed fact, owner role, next action, and admission condition when work can safely continue elsewhere. Examples include missing commit authority, a historical reference that requires owner interpretation, or unavailable optional tooling.

### Test failure

A check that ran and violated its contract is `failed`. Fix it within Plan A scope or stop. Do not relabel it unavailable.

## Phase execution record

Every phase record must contain:

- objective;
- inputs and dependencies;
- allowed mutations;
- forbidden mutations;
- tasks;
- required evidence;
- validation;
- hard stops;
- quantified blockers;
- exit criteria;
- artifacts;
- canonical-document updates;
- next phase.

The phase may advance only when every exit criterion is true or an explicitly independent branch is documented as safe to continue.

## Phase A0 - Freeze, inventory, and reconciliation ledger

### Objective

Capture an immutable baseline and classify every relevant document, rule, specification, workflow reference, and path before rewriting.

### Inputs and dependencies

- current owner instruction;
- both plans in `docs/plans/`;
- root and nested agent instructions;
- all canonical documents;
- `.agents/rules/**`, `.agents/workflows/**`, and `.agents/specs/**`;
- `.github/workflows/**`, `.github/dependabot.yml`, templates, and governance files;
- textual files under `tools/**`;
- `pyproject.toml`, lockfiles, `frontend/package.json`, frontend lockfile, and `.pre-commit-config.yaml`;
- Git baseline.

### Allowed mutations

Only temporary, ignored inventory output under `artifacts/documentation-standardization/work/` after confirming the directory is ignored and contains no secret values.

### Forbidden mutations

Tracked files, Git index, remotes, providers, runtime data, and generated production artifacts.

### Tasks

1. Record branch, HEAD, status, tracked/untracked ownership, and UTC start.
2. Read every scoped file completely or record a bounded parse with a content hash and why full rendering was unnecessary.
3. Determine each specification's actual work state from its metadata and evidence, not checkbox count.
4. Inventory every workflow's triggers, permissions, runner, timeout, concurrency, secret use, artifact flow, and referenced path.
5. Build the authoritative reconciliation ledger:

| Concern | Plan A finding | Plan B finding | Conflict or duplication | Final authority | Required transition |
| --- | --- | --- | --- | --- | --- |
| execution order | producer | consumer | must be explicit | Plan A handoff contract | Plan B blocks on validated handoff |
| canonical names | migration owner | consumer | stale aliases | Plan A | B uses `STATUS`/`EVIDENCE` only |
| plan location | governs exact-nine | root drafts | structural conflict | Plan A | both plans under `docs/plans/` |
| AGENTS authority | owner | consumer | duplicate rules drift | Plan A | B references resulting `AGENTS.md` |
| state vocabularies | owner | mixed statuses | semantic collision | Plan A | separate namespaces |
| R2 architecture | current truth only | future delta | present/future conflation | current canonical docs, then Plan B | no Plan A future claim |
| resources | interface | executor | must match | shared interface | immutable-ID verification |
| artifacts | docs handoff | runtime evidence | different bundles | each producing plan | common envelope fields |
| Git and side effects | local governance | remote/publication work | generic approval risk | each plan plus owner gate | operation-specific authorization |
| final claim | invariant | invariant | none | shared interface | always not established |

6. Extend the ledger to every concern named in the synchronization request, including cleanup, rollback, dependencies, public/fork safety, validation, and provider boundaries.
7. Produce a path inventory with exactly one category per path: `exists_now`, `created_by_plan_a`, `created_by_plan_b`, `renamed_by_plan_a`, `archived_by_plan_a`, `removed_by_plan_a`, `optional`, `forbidden`, or `historical_only`. Content actions such as merge or rewrite belong in the ledger, not in a second path category.
8. Record all active references to the two filenames being renamed and the superseded documentation-plan path.
9. Run Graphify for cross-document relationships and verify every material result against source.

### Required evidence

- `artifacts/documentation-standardization/work/baseline.json`
- `artifacts/documentation-standardization/work/reconciliation-ledger.json`
- `artifacts/documentation-standardization/work/path-inventory.json`
- `artifacts/documentation-standardization/work/reference-inventory.json`

Artifacts contain paths, counts, hashes, and fixed labels only.

### Validation

Validate JSON parseability, unique path classification, complete scoped-file coverage, and unchanged Git status relative to baseline.

### Hard stops

Unowned dirty overlap, unreadable authoritative input, ambiguous spec state affecting archival, or a path assigned multiple categories.

### Quantified blockers

Optional Graphify query unavailable; historical prose requiring owner interpretation.

### Exit criteria

The ledger covers every synchronization concern, every named path has one category, and no tracked file changed.

### Canonical-document updates

None.

### Next phase

A1.

## Phase A1 - Establish agent and documentation governance

### Objective

Rewrite `AGENTS.md` and directly affected agent rules so one compact constitution owns authority, routing, safety, validation, and documentation lifecycle.

### Inputs and dependencies

Validated A0 ledger and current root/nested instructions.

### Allowed mutations

`AGENTS.md` and only the `.agents/rules/**` or `.agents/workflows/**` files identified by the ledger as conflicting with the target governance.

### Forbidden mutations

Application code, specs' requirement semantics, workflows, providers, secrets, and canonical-document content beyond path references required by this phase.

### Tasks

1. Replace duplicated procedural detail in `AGENTS.md` with a read-on-demand map.
2. Preserve project invariants: architecture precedence, layer boundaries, session-derived identity, R2-only logical ownership, safe health contracts, wrapper use, dirty-tree protection, exact validation evidence, and Graphify refresh after edits.
3. Add `docs/plans/` routing and explicitly mark plans noncanonical.
4. Add the state namespaces and conflict algorithm from this plan.
5. Define current/future/historical classification and active-spec lifecycle.
6. Remove active compatibility and filesystem-overlay guidance wherever it claims a supported contract. A factual inventory note may remain only as a classified migration finding; Plan B must remove the implementation, dependency, tests, and terminology without adding a replacement fallback.
7. Update affected rules atomically so no lower rule contradicts root `AGENTS.md`.
8. Keep provider and remote mutation authority operation-specific.

### Required evidence

`artifacts/documentation-standardization/work/agents-reconciliation.json` with changed sections, removed duplications, preserved invariants, and hashes.

### Validation

- duplicate `##` heading guard returns no matches;
- all routing targets exist or are classified future paths;
- source-of-truth and status terms match this plan;
- targeted stale-rule searches produce only classified migration/history hits;
- `git diff --check`;
- Graphify refresh.

### Hard stops

A lower-scoped rule requires a materially different architecture or security decision, or the rewrite would weaken an invariant.

### Quantified blockers

A non-security wording conflict may be recorded for owner resolution while independent sections continue.

### Exit criteria

One unambiguous agent constitution exists and all modified subordinate rules agree with it.

### Artifacts

The A1 evidence file and command log.

### Canonical-document updates

None beyond links explicitly needed to keep current paths usable before A3.

### Next phase

A2.

## Phase A2 - Implement the documentation contract checker

### Objective

Create the executable checker that makes the target layout and documentation rules deterministic.

### Inputs and dependencies

A1 governance and A0 path inventory.

### Allowed mutations

`tools/docs_check.py`, `tools/docs-check.ps1`, and focused tests or fixtures under an existing tooling-test location selected from repository convention. If no such location exists, implement a `-SelfTest` mode rather than inventing a new test framework.

### Forbidden mutations

Canonical prose, runtime dependencies, provider access, and broad formatter changes.

### Tasks

The checker must:

1. assert exactly the nine approved Markdown filenames at `docs/` root;
2. permit only approved documentation subdirectories, including `archive`, `design`, and `plans`;
3. validate required front matter, one H1, unique required headings, valid status fields, and stable anchors;
4. validate local Markdown links and case-correct relative paths;
5. enforce canonical ownership and detect active duplicate normative sections;
6. reject active references to renamed canonical paths, with explicit bounded exemptions for Plan A's migration ledger and clearly marked historical text;
7. reject the superseded documentation-plan path as an active dependency;
8. validate that every `docs/plans/` file says `canonical_truth: false`;
9. validate Plan A/Plan B interface fields and exact handoff path;
10. scan for forbidden secret-bearing evidence patterns without printing matched values;
11. report machine-readable counts plus a nonzero exit code on violations;
12. provide `-SelfTest` cases for pass, broken link, duplicate heading, stale active path, invalid status, extra root document, malformed front matter, and forbidden secret-pattern classification;
13. expose one stable machine-readable result shape for local and hosted callers, including violation category/count, checked paths, exit code, and candidate SHA;
14. do not print matched secret values, raw front matter payloads, or provider/runtime data while reporting a violation.

docs_check.py owns the checking logic. docs-check.ps1 is a thin repository
entry point that resolves the repository root, invokes the canonical project
interpreter when Python is needed, forwards arguments, and returns the
checker exit code. The checker must not require a new third-party dependency
when the standard library and existing project tooling are sufficient.

The checker also rejects heading-level skips, malformed fenced blocks,
trailing whitespace, duplicate requirement IDs, duplicate active evidence
IDs, invalid YAML/front matter types, and a canonical root set that differs
from the migration contract. Allowlist entries must identify the exact path,
line/range or structural reason, and whether the text is migration-only or
historical; broad wildcard exemptions are not valid.

### Required evidence

- checker source hash;
- self-test report;
- fixture list;
- command log with exit codes and counts.

### Validation

Run the checker self-test, focused tooling tests, `git diff --check`, and Graphify refresh. Run Ruff/Pyright only if Python source or Python fixtures are added.

### Hard stops

The checker needs an unapproved dependency, emits matched secret content, or cannot distinguish migration/history exemptions from active instructions.

### Quantified blockers

None for a required checker capability; a missing capability is a test failure.

### Exit criteria

All self-tests pass and deliberate negative fixtures fail for the expected fixed reason.

### Artifacts

`artifacts/documentation-standardization/work/docs-check-self-test.json`.

### Canonical-document updates

None.

### Next phase

A3.

## Phase A3 - Atomic layout and filename migration

### Objective

Create the target documentation tree and replace every active canonical-path reference without losing provenance.

### Inputs and dependencies

Passing A2 checker in migration mode and the A0 reference inventory.

### Allowed mutations

Documentation paths, active references in agent rules/specs/templates/workflows/tooling, and archive moves explicitly listed in the ledger.

### Forbidden mutations

Historical rewriting, runtime behavior, workflow behavior unrelated to path validation, and deletion of unique evidence.

### Tasks

1. Preflight that destinations do not exist and source hashes match A0.
2. Rename atomically:
   - `docs/HISTORY.md` to `docs/EVIDENCE.md`;
   - `docs/WORK.md` to `docs/STATUS.md`.
3. Keep both master plans under `docs/plans/`.
4. Update all active links, commands, templates, active specs, agent rules, and workflow/documentation checks to the new names.
5. Classify old-name literals in archives and Plan A migration tables as historical or migration-only; never leave them executable.
6. Remove the superseded documentation-plan path from active dependency chains and archive it only if the ledger proves it exists and has unique provenance.
7. Run a case-sensitive path/link audit before continuing.

### Required evidence

`artifacts/documentation-standardization/work/rename-map.json` containing old/new hashes, every changed reference, exemptions, and zero unresolved active hits.

### Validation

Run the checker in migration mode and normal mode, stale-reference searches, relative-link validation, `git diff --check`, and Graphify refresh.

### Hard stops

Destination collision, source hash drift, unresolved active old-name reference, broken plan path, or unique historical content with no destination.

### Quantified blockers

A historical literal whose context cannot be classified; keep `next_plan_ready=false` until resolved.

### Exit criteria

The target filenames exist, old paths do not, active references resolve, and exemptions are bounded and documented.

### Artifacts

Rename map and validation log.

### Canonical-document updates

`EVIDENCE.md` and `STATUS.md` receive only naming/front-matter changes in this phase; substantive restructuring follows.

### Next phase

A4.

## Phase A4 - Standardize the nine canonical documents

### Objective

Make each canonical file authoritative only for its owned concern while preserving current truth and evidence provenance.

### Inputs and dependencies

A3 layout, A0 classification ledger, and current source verification.

### Allowed mutations

The nine canonical files and directly governed route briefs.

### Forbidden mutations

Unimplemented future claims, application behavior, provider state, and deletion of unique history.

### Tasks

For each file:

1. add consistent front matter with `title`, `document_role`, `authority`, `scope`, `audience`, `update_triggers`, and `owned_concerns`; do not add an automatically refreshed `last_verified_utc` to timeless documents;
2. add purpose, authority boundary, current-state statement, related contracts, and maintenance rule;
3. move duplicate normative content to its sole owner and replace copies with links;
4. classify every status/evidence field using the two namespaces;
5. use `STATUS.md` only for current work and `EVIDENCE.md` only for verified completed outcomes;
6. preserve NO-GO and `production_capacity_claim=not_established`;
7. record the currently implemented R2 S3-compatible Python path only as a bounded migration finding in the ledger; canonical documents must state R2-only as the sole active contract and must not preserve generic S3, MinIO, moto, filesystem, alias, or fallback guidance;
8. keep the Workers R2 binding migration as a Plan B intended delta;
9. preserve active route-brief hierarchy under `docs/design/`;
10. keep commands secret-safe and executable from the documented working directory.

### Per-document target structures

The following outlines restore detail from the reference plan without
duplicating ownership. A phase may reorder subsections to match existing
content, but it must preserve the owner and cleanup rules.

#### ARCHITECTURE.md

Role: document_role=normative. Target sections:

Purpose and authority; System context; Runtime topology; Domain boundaries;
Dependency direction; Ingestion and crawl architecture; Translation
architecture; Data ownership and persistence; Public reader architecture;
Identity and trust boundaries; API and service contracts; Reliability and
concurrency contracts; Forbidden dependencies and patterns; Architecture
change protocol.

Move dated capacity checkpoints to EVIDENCE.md, operational steps to
OPERATIONS.md, release procedure to DEPLOYMENT.md, and environment detail to
CONFIGURATION.md. Keep only current architecture and stable,
cross-referenced security/storage IDs.

#### CONFIGURATION.md

Role: document_role=reference. Target sections:

Purpose and ownership; Loading and precedence; Environment file policy; Secret
classification; Database configuration; R2 / storage configuration; Redis /
coordination configuration; Authentication and email; Translation/provider
configuration; Runtime and capacity controls; Frontend configuration;
Validation and fail-closed rules; Configuration change checklist.

Use grouped tables with setting, scope, secret classification, required
environments, default owner, bounds, failure behavior, and source. Do not
copy every source-defined default or expose environment values.

#### DEPLOYMENT.md

Role: document_role=procedural. Target sections:

Purpose and boundaries; Supported topologies; Service topology; Routing;
Build and immutable release artifacts; GitHub release controls; Deployment
prerequisites; Release procedure; Migration procedure; Deployment
verification; Rollback procedure; External monitoring boundary; Acceptance
contract; Related runbooks.

Move dated staging/deployment/runner checkpoints to EVIDENCE.md and current
unresolved release state to STATUS.md. Preserve repeatable release,
migration, verification, and rollback procedures with safety gates.

#### DESIGN.md

Role: document_role=normative. Preserve existing design-token metadata inside
the shared front matter, exactly one H1, public/admin brief indexing, and the
route hierarchy under docs/design/public/ and docs/design/admin/. Target
sections:

Purpose and authority; Design principles; Brand identity; Color system;
Typography; Layout and spacing; Shape and elevation; Components; Interaction
and state; Accessibility; Responsive behavior; Motion and graphics; Content
and copy; SEO and metadata; Page-brief contract; Route brief index;
Verification and maintenance.

Remove stray validator headings and keep page-specific implementation out of
the global design contract.

#### EVIDENCE.md

Role: document_role=evidence. It is append-oriented, reverse chronological,
sanitized, candidate/environment specific, and immutable in meaning. Target
H1: Verification and Delivery Evidence.

Each dated entry must identify an evidence ID, scope, candidate, sanitized
environment, disposition, objective, verified actions, evidence/metrics,
artifacts, limitations/blockers, supersession, and follow-up. Missing
historical fields are unavailable, never invented. This document receives
dated results moved from other canonical files without pretending that the
migration reran them.

Each entry follows this minimum shape:

~~~markdown
## YYYY-MM-DD - Milestone title {#EVD-YYYY-MM-DD-001}

| Field | Value |
| --- | --- |
| Evidence ID | EVD-YYYY-MM-DD-001 |
| Scope | sanitized scope |
| Candidate | commit SHA or unavailable |
| Environment | sanitized environment |
| Disposition | passed / failed / blocked / partial / unavailable / superseded |

### Objective
### Verified actions
### Evidence and metrics
### Artifacts
### Limitations / blockers
### Supersedes / superseded by
### Follow-up
~~~

#### OPERATIONS.md

Role: document_role=procedural. Target sections:

Purpose and safety boundary; Routine operational checks; Health and readiness;
Worker and queue control; Scheduler and maintenance; Reader-capacity evidence
procedure; Managed test database verification; Backup procedure; Restore
verification; R2 garbage collection; Incident response; Rollback
coordination; Secret rotation; Email / alert activation; Provider credential
operations; Recovery of local tooling; Evidence requirements.

Every destructive runbook requires preconditions, exact target isolation,
dry-run/preview when available, abort conditions, cleanup, verification, and
evidence capture. Dated run results belong in EVIDENCE.md.

#### STORAGE.md

Role: document_role=normative. Target sections:

Purpose and ownership; Source-of-truth matrix; PostgreSQL ownership; R2
ownership; Redis / coordination ownership; Object-key grammar; Immutability
and content addressing; Generation activation; Translation and media
artifacts; Backup object model; Garbage collection semantics; Deletion and
retention invariants; Restore contract; Storage change protocol.

STORAGE.md states what must be true. OPERATIONS.md states how an authorized
operator performs backup, restore, cleanup, or recovery. The R2-only
architecture must not be broadened with S3, MinIO, or filesystem support.

#### TRANSLATION.md

Role: document_role=normative. Target sections:

Purpose and authority; Pipeline contract; Provider/model resolution; Prompt
lifecycle and versioning; JP-EN quality policy; Glossary lifecycle; Chunking
and context; QA contract; Retry and failure semantics; Cache identity and
acceptance; Translation artifact lineage; Credential isolation and
accounting; Quota and bounded-concurrency contract; Source-order
convergence; Change checklist.

Move dated async/capacity checkpoints to EVIDENCE.md, while retaining
permanent pipeline, quality, quota, and lineage rules.

#### STATUS.md

Role: document_role=status; target H1: Project Status and Active Work.
Target sections:

Current decision; Current candidate / baseline; Launch blockers; Active work;
Active specifications; Operator acceptance gates; Deferred work; Explicitly
out of scope; Next ordered actions.

STATUS.md contains zero completed-work narratives. Every current item has a
stable ID, priority, state, scope, dependency, missing evidence, and
acceptance condition. Completed work moves to EVIDENCE.md; superseded
snapshots are removed or preserved there with provenance.

### Required evidence

One content-move ledger per canonical file with source anchor, destination anchor, classification, and hash.

### Validation

`tools/docs-check.ps1`, targeted implementation-to-doc checks, status vocabulary scan, link/path checks, `git diff --check`, and Graphify refresh after each edit.

### Hard stops

A statement cannot be classified as current, intended, historical, or unresolved; a canonical conflict remains; or security posture would be overstated.

### Quantified blockers

Optional external evidence unavailable. Record it in `STATUS.md`, not as invented current truth.

### Exit criteria

Every canonical concern has one owner, all nine files pass the checker, and current versus future behavior is explicit.

### Artifacts

`artifacts/documentation-standardization/work/canonical-content-ledger.json`.

### Canonical-document updates

All nine, limited to their owned concerns.

### Next phase

A5.

## Phase A5 - Reconcile plans, specifications, and non-canonical documentation

### Objective

Remove active-document ambiguity without erasing provenance or changing an active specification's meaning.

### Inputs and dependencies

A4 canonical set and A0 lifecycle inventory.

### Allowed mutations

`docs/archive/`, `docs/plans/` interface metadata, active spec path references/status labels, and non-canonical docs classified by A0.

### Forbidden mutations

Archiving an active or blocked spec, marking evidence passed from task checkboxes, deleting unique history, and implementing Plan B.

### Tasks

1. For each non-canonical root document, choose exactly one: merge unique current contract, move unresolved work to `STATUS.md`, move verified outcome to `EVIDENCE.md`, archive with provenance, or delete only a proven exact duplicate.
2. Keep active and blocked specs under `.agents/specs/`.
3. Archive a spec only when its work state is `complete` or `superseded` and all unresolved work is represented in `STATUS.md`.
4. Update active specs to new canonical paths without rewriting their historical evidence.
5. Ensure archived copies are not simultaneously treated as active.
6. Ensure both master plans carry matching interface metadata and no stale active dependency.
7. Record all archive moves and source hashes.

The ledger must explicitly classify these known non-canonical root candidates
when they exist at A0:

| Source path | Content decisions | Final path disposition |
| --- | --- | --- |
| docs/R2-ONLY-CONFORMANCE.md | invariants to STORAGE/ARCHITECTURE, procedures to OPERATIONS, unresolved acceptance to STATUS, verified results to EVIDENCE | archive with provenance after content ledger |
| docs/R2-Only Content Storage Rearchitecture-plan.md | implemented decisions to canonical owners, future work to STATUS/spec, historical plan text to archive | archive with provenance after content ledger |
| docs/PERFORMANCE_AUDIT.md | measurements to EVIDENCE, permanent rules to ARCHITECTURE, procedures to OPERATIONS, open issues to STATUS | archive with provenance after content ledger |
| docs/PERFORMANCE_ACTION_PLAN.md | open work to STATUS/spec, completed work to EVIDENCE, permanent rules to ARCHITECTURE | archive or remove only after duplicate proof |
| docs/DOCUMENTATION_PLAN.md | valid requirements into this plan or completed canonical evidence; obsolete instructions marked superseded | archive as superseded, never execute its delete/archive directions |

If a listed path is absent, record absent in the inventory instead of
manufacturing an archive move. A source path has one final path category;
merge/rewrite/remove-duplicate is a content action recorded separately.

### .agents lifecycle reconciliation

Audit every file under .agents/rules/, .agents/workflows/, and
.agents/specs/. Remove stale canonical-name instructions, retain only
tool/workflow-specific overlays in rules, and keep permanent repository facts
in AGENTS.md or the owning canonical document. Classify each spec as active,
complete, superseded, or blocked from metadata and evidence rather than
checkbox count. Do not archive a spec solely because implementation appears
complete; archive only after its acceptance/evidence is represented in
EVIDENCE.md, and ensure archived specs are absent from STATUS.md active indexes.

### Required evidence

`artifacts/documentation-standardization/work/lifecycle-and-archive-ledger.json`.

### Validation

Docs checker, active/archive duplicate-ID check, stale-reference audit, spec-state audit, link check, `git diff --check`, and Graphify refresh.

### Hard stops

Spec state cannot be proven, archive destination collides, or unique evidence would be lost.

### Quantified blockers

Owner interpretation required for ambiguous historical prose.

### Exit criteria

No non-canonical root Markdown remains, active specs are correctly located, and archive provenance is intact.

### Artifacts

Lifecycle/archive ledger and validation log.

### Canonical-document updates

`STATUS.md` and `EVIDENCE.md` only for classified moved content.

### Next phase

A6.

## Phase A6 - Candidate validation and exact commit

### Objective

Validate one complete Plan A candidate and bind it to a commit without absorbing unrelated work.

### Inputs and dependencies

All prior phase outputs.

### Allowed mutations

Fixes within Plan A scope and, with explicit commit authority, exact-path staging and one or more clearly bounded Plan A commits.

### Forbidden mutations

Remote operations without explicit authorization, unrelated staging, hook bypass, history rewrite, and Plan B work.

### Tasks

1. Re-read both plans top to bottom and simulate the Plan A-to-Plan B transition.
2. Run `tools/docs-check.ps1`.
3. Run checker self-tests and any focused tests for tooling changes.
4. Run repository stale-reference, invalid-heading, duplicate-heading, link, and path-category checks.
5. Run `git diff --check` and the AGENTS heading guard.
6. Run Ruff/Pyright only if affected source requires them.
7. Run `graphify update . --no-cluster` and record the result.
8. Review the complete diff against A0 owner-change ownership.
9. If commit authority exists, format only applicable source files, stage exact paths, run `git diff --cached --check`, commit with hooks enabled, and verify the resulting commit tree.
10. If hooks modify files, review, restage exact expected paths, rerun affected checks, and retry once.
11. Record the Plan A candidate SHA and verify the working tree contains only the preserved pre-existing changes plus ignored evidence artifacts.

### Validation command matrix

The documentation-only default is:

~~~powershell
pwsh -NoProfile -File tools/docs-check.ps1
pwsh -NoProfile -File tools/docs-check.ps1 -SelfTest
pre-commit run --all-files
git diff --check
~~~

If the checker or Python fixtures change, also run the repository wrappers:

~~~powershell
tools/ruff.ps1 check .
tools/pyright.ps1
tools/pytest.ps1 <focused-documentation-check-tests>
~~~

If a frontend generator, route-brief validator, or frontend source changes,
run these from the frontend directory as applicable:

~~~powershell
Push-Location frontend
npm run lint
npm run typecheck
npm run test
npm run build
Pop-Location
~~~

Pure Markdown changes do not require frontend or broad application tests, but
every skipped command must be recorded as not applicable rather than passed.

### Suggested commit boundaries

Keep Plan A reviewable and do not absorb owner changes. When commit authority
exists, suitable boundaries are:

1. docs(agents): tighten repository guidance and source routing
2. chore(docs): add canonical documentation contract checks
3. docs: rename work and history canonical records
4. docs: standardize architecture configuration and deployment
5. docs: standardize design operations storage and translation
6. docs: normalize status and evidence records
7. docs: consolidate and archive superseded documentation
8. docs: rebase downstream execution plan references

The exact grouping may be reduced when the dirty worktree requires safer
isolation. Each commit records its paths, checks, and resulting tree; none
contains Plan B implementation or unrelated pre-existing changes.

### Required evidence

`artifacts/documentation-standardization/validation.json` and a candidate file manifest with SHA-256 digests.

### Validation

Every recorded command must have a timeout, exit code, result count when applicable, and candidate SHA. A missing `tools/docs-check.ps1` is `not_run` before A2, but is a hard failure here.

### Hard stops

Any required check fails, commit tree differs from validated content, unrelated changes are staged, or commit authority is absent.

### Quantified blockers

Missing commit authority yields `work_state=blocked` and `next_plan_ready=false` after local validation.

### Exit criteria

All required checks pass against one committed candidate and preserved dirty changes are accounted for.

### Artifacts

Validation record and candidate manifest.

### Canonical-document updates

`STATUS.md` records the actual Plan A state. `EVIDENCE.md` records completion only after the commit is verified.

### Next phase

A7.

## Phase A7 - Emit and verify the successor handoff

### Objective

Produce the sole machine-readable admission record for Plan B.

### Inputs and dependencies

A6 committed candidate.

### Allowed mutations

Ignored, sanitized artifacts under `artifacts/documentation-standardization/` and factual Plan A completion entries already included in the validated candidate.

### Forbidden mutations

Candidate source changes, remote/provider mutations, and setting readiness by inference.

### Tasks

1. Generate `artifacts/documentation-standardization/handoff.json` from the committed tree.
2. Hash canonical files and `AGENTS.md` with SHA-256 lowercase hexadecimal.
3. Validate every canonical path from the commit, not the mutable working tree.
4. Compare Plan B's predecessor interface to this plan's successor contract.
5. Set `next_plan_ready=true` only when every required condition below passes.
6. Re-run handoff validation after generation; do not edit the candidate afterward.

The handoff validator MUST require that canonical_doc_hashes has exactly the
same nine keys as canonical_docs, that each value is a lowercase SHA-256
digest, and that every digest is computed from the predecessor commit tree.
An example or partial hash map is invalid admission evidence.

### Handoff schema

```json
{
  "schema_version": 1,
  "plan_id": "dokushodo-docs-standardization",
  "plan_version": "2.1.0",
  "work_state": "complete",
  "completed_at_utc": "RFC3339 UTC",
  "candidate_commit": "40-hex commit",
  "canonical_docs": [
    "docs/ARCHITECTURE.md",
    "docs/CONFIGURATION.md",
    "docs/DEPLOYMENT.md",
    "docs/DESIGN.md",
    "docs/EVIDENCE.md",
    "docs/OPERATIONS.md",
    "docs/STATUS.md",
    "docs/STORAGE.md",
    "docs/TRANSLATION.md"
  ],
  "canonical_doc_hashes": {
    "docs/ARCHITECTURE.md": "sha256-lowercase-hex",
    "docs/CONFIGURATION.md": "sha256-lowercase-hex",
    "docs/DEPLOYMENT.md": "sha256-lowercase-hex",
    "docs/DESIGN.md": "sha256-lowercase-hex",
    "docs/EVIDENCE.md": "sha256-lowercase-hex",
    "docs/OPERATIONS.md": "sha256-lowercase-hex",
    "docs/STATUS.md": "sha256-lowercase-hex",
    "docs/STORAGE.md": "sha256-lowercase-hex",
    "docs/TRANSLATION.md": "sha256-lowercase-hex"
  },
  "agents_md_hash": "sha256-lowercase-hex",
  "docs_checker_command": "pwsh -NoProfile -File tools/docs-check.ps1",
  "docs_checker_exit_code": 0,
  "graphify_result": {
    "command": "graphify update . --no-cluster",
    "exit_code": 0
  },
  "stale_reference_result": {
    "unresolved_active_count": 0,
    "classified_historical_count": 0
  },
  "dirty_worktree_disposition": {
    "preexisting_paths_preserved": [],
    "plan_a_uncommitted_paths": []
  },
  "renames": [
    {"from": "historical-status-source", "to": "docs/STATUS.md"},
    {"from": "historical-evidence-source", "to": "docs/EVIDENCE.md"}
  ],
  "archived_documents": [],
  "active_specs": [],
  "known_documentation_blockers": [],
  "next_plan": "dokushodo-public-hosted-evidence",
  "next_plan_path": "docs/plans/DOKUSHODO_COMPLETE_PUBLIC_HOSTED_EXECUTION_PLAN.md",
  "next_plan_ready": true,
  "production_capacity_claim": "not_established"
}
```

The real `renames` field records actual old paths. The illustrative schema intentionally avoids making those old paths active instructions.

### Required admission conditions

- Plan A work state is `complete`.
- Candidate commit exists and contains every required output.
- Canonical docs are exactly the nine target paths.
- Every recorded hash matches `git show <candidate>:<path>` content.
- Docs checker and self-tests passed.
- No unresolved active stale canonical reference exists.
- Plan B exists at the declared path and its predecessor interface matches.
- No Plan A output remains uncommitted.
- Pre-existing dirty paths are preserved and identified.
- Known documentation blockers are empty.
- Production capacity remains not established.

### Required evidence

The handoff and `artifacts/documentation-standardization/handoff-validation.json`.

### Validation

Run a parser/validator that rejects missing fields, unknown state values, bad hashes, a mutable candidate, or a mismatched successor contract.

### Hard stops

Any admission condition fails. Emit `next_plan_ready=false` with fixed blocker records and stop.

### Quantified blockers

None can be waived inside Plan A. The owner may authorize a later corrective Plan A candidate.

### Exit criteria

Handoff validation passes and the candidate has not changed.

### Artifacts

Final handoff and validator report.

### Canonical-document updates

None after candidate freeze.

### Next phase

Plan B Phase B0, only when `next_plan_ready=true`.

## Plan B successor interface

Plan B must consume this exact interface:

| Field | Contract |
| --- | --- |
| required predecessor | `dokushodo-docs-standardization` version `2.1.0` |
| handoff | `artifacts/documentation-standardization/handoff.json` |
| canonical names | the nine target files, including `STATUS.md` and `EVIDENCE.md` |
| docs checker | `pwsh -NoProfile -File tools/docs-check.ps1` |
| agent authority | committed root `AGENTS.md` hash from handoff |
| source hierarchy | owner instruction, AGENTS, architecture, approved active spec, canonical concerns, implementation evidence, status, evidence |
| resource allowlist | `testingdatabase-dokushodo`, `test-dokushodo`, and `test-dokushodo-backup`, resolved by immutable IDs |
| provider mutation | forbidden unless a later operation-specific authorization permits a non-production action |
| production mutation | forbidden |
| production capacity | `not_established` |

If Plan B cannot validate any field, it must stop before mutation.

## Authoritative reconciliation ledger

This table is Plan A's cross-plan authority record. Plan B references it and repeats only the interface above.

| Concern | Final authority | Resolution |
| --- | --- | --- |
| execution order | Plan A handoff | Plan B is blocked until a hash-valid handoff says ready |
| canonical layout/names | Plan A | exactly nine root canonical files; plans live below `docs/plans/` |
| AGENTS and doc routing | Plan A | Plan B consumes committed output |
| current architecture | canonical docs plus verified implementation | Plan A records current state; Plan B updates after implementation |
| active intended delta | approved active spec | never rewritten as current before implementation |
| historical evidence | `EVIDENCE.md` and archives | preserves provenance; never establishes current capacity |
| current work | `STATUS.md` | one unfinished-work register |
| status vocabulary | Plan A | work and evidence namespaces remain separate |
| runtime evidence schemas | Plan B | must import Plan A state terms |
| Git/worktree | each plan plus operation-specific owner authority | exact staging and preserved dirty paths |
| GitHub/publication | Plan B | separate snapshot, mutation, and publication gates |
| Cloudflare/Supabase/R2 | Plan B | read-only discovery by default; target-guarded non-production writes only when separately authorized |
| R2 direction | current docs, then Plan B delta | current compatibility implementation is an inventory-only finding; target has one native R2 path and no compatibility fallback |
| runners/workflows | Plan B | inventory before rename/consolidation; hosted public-fork-safe target |
| dependencies | Plan B | candidate-changing updates invalidate affected evidence |
| cleanup/recovery | Plan B | cancellation-safe, same recovery point, zero-residue proof |
| Graphify/docs validation | Plan A | Plan B calls the established checker and refresh |
| remote operations | explicit owner gate | no generic implementation authorization |
| final readiness | invariant | non-production evidence never establishes production capacity |

## Path transition registry

| Path or class | Category | Responsible phase |
| --- | --- | --- |
| `AGENTS.md` | `exists_now` | A1 |
| nine current canonical source files | `exists_now` | A3/A4 |
| `docs/plans/` and both master plans | `exists_now` | current synchronization task |
| `tools/docs_check.py` | `created_by_plan_a` | A2 |
| `tools/docs-check.ps1` | `created_by_plan_a` | A2 |
| `artifacts/documentation-standardization/handoff.json` | `created_by_plan_a` | A7 |
| `docs/HISTORY.md` | `renamed_by_plan_a` | A3 |
| `docs/WORK.md` | `renamed_by_plan_a` | A3 |
| `docs/EVIDENCE.md` | `renamed_by_plan_a` | A3 |
| `docs/STATUS.md` | `renamed_by_plan_a` | A3 |
| non-canonical root documents | `archived_by_plan_a` | A5; content actions are recorded separately in the ledger |
| active `.agents/specs/**` | `exists_now` | A5 reference synchronization |
| Plan B runtime/evidence artifacts | `created_by_plan_b` | Plan B |
| provider-specific test gateway source paths | `optional` | Plan B only if separately authorized |
| old documentation-plan material | `historical_only` after A5 | A5 |

A0 must expand this registry to every concrete path named by either plan.

## Required command families

Plan A uses current repository tooling, not copied version numbers:

```powershell
git status --short
git branch --show-current
git rev-parse HEAD
pwsh -NoProfile -File tools/docs-check.ps1
pwsh -NoProfile -File tools/docs-check.ps1 -SelfTest
git diff --check
graphify update . --no-cluster
```

Run `tools/ruff.ps1 check .`, `tools/pyright.ps1`, and focused tests only when affected source requires them. Frontend checks are not required for pure documentation changes unless a frontend contract or tool is modified. Never report an unexecuted command as passed.

## Definition of complete

Plan A is complete only when:

- the target layout exists with exactly nine root canonical Markdown files;
- both plans are under `docs/plans/` and marked noncanonical;
- `AGENTS.md` and subordinate rules agree;
- `STATUS.md` and `EVIDENCE.md` are authoritative and all active references migrated;
- every current/future/historical statement is classified;
- the docs checker and self-tests pass;
- active specs remain accurately classified;
- unique history is preserved;
- all required checks pass on one committed candidate;
- the handoff validates with `next_plan_ready=true`;
- unrelated owner changes remain intact;
- no provider, GitHub, deployment, secret, or production mutation occurred;
- `production_capacity_claim=not_established`.

Passing this definition means the governance prerequisite is ready. It does not mean Plan B ran, the repository is public, reader capacity passed, recovery is complete, or production is ready.
