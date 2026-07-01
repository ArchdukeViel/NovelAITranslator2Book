# Glossary Prompt Injection Plan

## 1. Purpose

Approved glossary prompt injection exists to make future translations more
stable. Once the owner approves a per-novel glossary entry, future provider
requests should carry that decision so recurring names, places, titles, ranks,
magic terms, and setting concepts keep the same English rendering.

Glossary rules are scoped to one platform novel. Owner approval is the trust
boundary: no-provider imports and provider-assisted suggestions can create
Reviewing candidates, but they must not become translation rules until the
owner approves them.

This document is a plan only. It does not implement prompt injection, provider
calls, translation jobs, QA scanning, saved chapter repair, seed data, database
mutation, frontend UI, backend routes, or migrations.

## 2. Definitions

- Approved glossary term: a `novel_glossary_entries` row for one `novel_id`
  with `status = "approved"`. It may influence future translation prompts.
- Reviewing candidate: a candidate or recommended entry that still needs owner
  review. In the current backend this is usually `status = "candidate"` or
  `status = "recommended"`. It must not be injected as a rule.
- Term/raw term: the source-side surface form or neutral concept label stored
  as `canonical_term`. When reliable raw text exists, this should be the source
  term used for matching.
- Translation: the owner-approved English rendering stored in
  `approved_translation`.
- Allowed alias: an alias row whose `alias_type` is `allowed` and whose
  `applies_to` makes it relevant to matching, prompt context, QA, or display.
- Banned/rejected alias: an alias row whose `alias_type` is `banned` or
  `rejected`. It is not a translation target; it can only appear as an avoid
  variant tied to an approved entry.
- Prompt glossary block: a compact, deterministic prompt section listing
  approved owner glossary rules for the current novel and request.
- Injection budget: the configured maximum number of terms and maximum
  characters or tokens allowed for the prompt glossary block.
- Active chapter context: the chapter, chunk, paragraph refs, source text, and
  available candidate/provenance evidence known before the provider call.
- Repair/apply saved chapters: a future explicit workflow for previewing and
  applying approved glossary decisions to already saved translated chapters. It
  is separate from prompt injection.

## 3. Source-Agnostic Rule

Glossary entries are owned by platform `novel_id`. Source site, source adapter,
source URL, Syosetu ncode, Kakuyomu work ID, Novel18 ID, generic import ID, and
source chapter ID are provenance only.

The same raw term may have different translations in different novels. Prompt
injection must therefore query and select terms by platform `novel_id`, not by
source site or source novel ID. The same service should work for Syosetu,
Kakuyomu, Novel18, generic sources, local imports, mirrors, and future adapters.

## 4. Eligibility Rules

Only entries that satisfy all core eligibility rules can become prompt rules:

- `status` must be `approved`.
- `canonical_term` must be non-blank.
- `approved_translation` should be non-blank.
- Deprecated entries must be excluded.
- Rejected entries must be excluded.
- Reviewing/backend candidate entries must be excluded.
- Provider-suggested entries must be ignored until the owner approves them.
- Owner-locked approved terms should receive high priority.

Entries without a usable `approved_translation` should normally be skipped and
reported as skipped. If a later implementation needs to represent them for
awareness, it must do so as non-enforcing context, not as a canonical
translation rule.

`enforcement_level` and `owner_locked` should influence priority and QA
strictness, but they must not make an unapproved entry eligible.

## 5. Term and Translation Mapping

Current field mapping:

- Prompt source/term field: `NovelGlossaryEntry.canonical_term`.
- Prompt translation field: `NovelGlossaryEntry.approved_translation`.
- Status gate: `NovelGlossaryEntry.status == "approved"`.
- Strong priority signal: `NovelGlossaryEntry.owner_locked == True`.
- Matching policy: `NovelGlossaryEntry.matching_policy`, with exact phrase
  matching as the safe default.
- Confidence, first/last seen chapter numbers, and provenance can support
  ranking but do not change approval.

Fallback behavior:

- If `approved_translation` is empty, skip the entry and emit a structured
  translation warning such as `glossary_entry_missing_translation`.
- Do not fall back to a Reviewing candidate translation.
- Do not fall back to provider output from the current request.

Alias representation:

- `allowed` aliases may be used for matching the active chapter context and may
  optionally be shown as compact context under the approved canonical rule.
- `source_variant` aliases may help match raw source text.
- `observed` aliases are evidence and should not be presented as approved
  alternatives unless the owner explicitly marks them allowed.
- `banned` and `rejected` aliases should be represented only as avoid variants
  tied to an approved entry.
- `deprecated` aliases should usually be excluded from prompt rules unless they
  are needed as avoid variants for QA or drift prevention.

## 6. Prompt Format

The prompt glossary block should be concise, deterministic, clearly separated
from chapter text, and explicit that it contains owner-approved rules.

Example:

```text
GLOSSARY FOR THIS NOVEL
These are approved owner glossary rules. Use them consistently when the source
term appears. Do not treat Reviewing candidates as rules.

Use these approved translations:
- seireikai => Spirit Realm
- maso => magicules

Avoid these rejected variants:
- seireikai: avoid "Spirit World" unless context clearly requires it.
```

Requirements:

- Include only owner-approved terms.
- Do not include Reviewing candidates.
- Do not include large source or translated excerpts.
- Keep one deterministic line per rule where possible.
- Keep avoid variants separate from canonical translations.
- Keep glossary content separate from active chapter text.
- Avoid raw JSON blobs in the provider-facing prompt unless a provider-specific
  structured prompt mode is intentionally designed and tested.

## 7. Injection Placement

Preferred placement:

1. System message, if the provider abstraction supports durable system
   instructions for the active provider.
2. Otherwise, before the chapter content in the user prompt.

The current prompt builder already supports `glossary_entries` in
`build_translation_request`, which places an additional instruction block inside
the user prompt. The first implementation should extend or replace that block
through the prompt layer, not from routers or React components.

The glossary block must be visibly separated from the chapter source text. It
must not be concatenated into raw chapter text, must not change
`TranslationChunk.source_text`, and must work across providers through the
existing `TranslationRequest` abstraction.

## 8. Budget and Prioritization

Suggested v1 defaults:

- Maximum terms per prompt: 20.
- Maximum glossary block characters: 2,000.
- Maximum avoid variants per term: 3.
- Maximum note/context characters per term: 120.

These values should be configurable through translation metadata or settings,
but hard fail-safe limits should exist even when configuration is missing.

Priority order:

1. Approved terms observed in the current chapter or chunk.
2. `owner_locked` approved terms.
3. Approved terms with banned or rejected aliases.
4. Frequently observed approved terms.
5. Recently approved terms.

Truncation behavior:

- Never exceed the configured term or character budget.
- Prefer dropping lower-priority terms over shortening canonical term or
  translation text into ambiguous forms.
- Emit a structured warning when truncation occurs, including counts only:
  selected terms, skipped terms, and budget reason.
- Do not log full chapter text or secrets with the warning.

## 9. Chapter-Aware Filtering

Prompt injection should avoid sending the entire novel glossary on every
provider call.

Filtering rules:

- Match `canonical_term` against the active raw chapter or chunk text where
  source text is available.
- Match `allowed` and `source_variant` aliases for relevance, but keep
  `canonical_term` as the displayed source term in the prompt.
- Exact phrase matching should be used first.
- Case-insensitive matching can be used for Latin translated evidence only when
  the entry or alias matching policy permits it.
- Do not use regex matching unless a later review explicitly approves the
  pattern and tests it.
- If raw matching is unavailable, fall back to owner-locked approved terms and
  high-priority approved terms with strong provenance.
- Candidate import evidence and provenance can improve ranking, but cannot make
  unapproved terms eligible.

The existing `rank_glossary_terms_for_text` and `TranslateStage` chunk glossary
selection are useful starting points, but the implementation must feed them
from database-approved entries and must not allow the older runtime glossary
statuses to weaken the new approval rule.

## 10. Conflict Behavior

Conflicts must be reported, not silently hidden.

Examples:

- Two approved entries in the same novel have the same `canonical_term` with
  different `approved_translation` values.
- One approved entry's rejected alias equals another approved entry's canonical
  translation.
- A Reviewing candidate proposes a translation that contradicts an approved
  term.

Rules:

- Do not silently choose between conflicting approved terms.
- Report a translation warning, QA finding, or prompt-build warning.
- `owner_locked` can win only when the conflict policy explicitly defines that
  behavior and logs the discarded competing rule.
- A Reviewing candidate must never override an Approved term.
- Provider output must never override an Approved term.

## 11. Translation Pipeline Integration

Likely integration point:

1. Segmentation and chapter/chunk context are known.
2. A glossary prompt injection service loads approved entries for
   `context.novel_id`.
3. The service filters and ranks terms for each `TranslationChunk.source_text`.
4. `TranslateStage._build_prompt_request` receives the selected approved
   `GlossaryTerm` objects.
5. `build_translation_request` includes the glossary block exactly once.
6. Provider translation runs through the existing scheduler and provider
   abstraction.

The implementation must be available to all providers, batch translation, and
delta/retry translation. It should be testable with mock providers and without
real provider calls.

Existing prompt metadata already records `prompt_version` and `glossary_hash`.
Implementation should update `glossary_hash` to reflect the selected approved
glossary snapshot, not raw database object reprs or unapproved runtime state.

## 12. Result and Audit Behavior

The translation run should record safe metadata:

- Selected glossary entry IDs.
- Selected source terms and approved translations, if safe and bounded.
- Count of injected terms.
- Count of terms skipped due to budget.
- Conflicts detected.
- Whether the glossary block was empty.
- Glossary hash for cache and reproducibility.

It must not log:

- Provider secrets.
- Auth headers, cookies, or credentials.
- Full chapter text.
- Large excerpts.
- Raw provider payloads containing sensitive material.

Warnings should be structured and compact, for example:

- `glossary_prompt_empty`
- `glossary_prompt_truncated`
- `glossary_conflict_detected`
- `glossary_entry_missing_translation`

## 13. QA Interaction Later

Future glossary QA should run after provider output and before publication or
manual acceptance decisions.

Later behavior:

- Check whether approved terms were followed when their source terms appeared.
- Create QA findings for banned or rejected aliases used in translated output.
- Respect allowed aliases where the entry permits them.
- Surface findings to owner/admin review.
- Do not rewrite automatically.
- Keep repair/apply as an explicit preview and rollback workflow.

## 14. Saved Chapter Repair Separation

Prompt injection affects future translations only. It must not rewrite already
saved translated chapters.

Approving a glossary entry must not trigger hidden repair. Applying approved
terms to saved chapters requires a separate workflow with:

- preview
- owner confirmation
- scoped chapter selection
- backup or versioning
- rollback plan
- audit trail

No prompt injection phase should mutate saved chapter text.

## 15. Admin UI Implications

Possible future owner UI work:

- Show "Used in future translations" for Approved entries that are eligible for
  injection.
- Show why a Reviewing entry is not yet enforced.
- Add a prompt injection preview for a selected chapter or chunk.
- Show glossary truncation warnings from translation runs.
- Show conflicts that blocked or weakened injection.

No public reader changes are part of prompt injection. Public glossary popovers
and user override UI remain separate future phases.

## 16. Tests Required for Implementation

Implementation should include tests for:

- Only Approved entries are injected.
- Reviewing candidates are excluded.
- Rejected and deprecated entries are excluded.
- Provider-suggested candidates are excluded until owner-approved.
- Entries without usable translations are skipped safely.
- Banned/rejected aliases are represented only as avoid variants.
- Allowed/source aliases support matching without becoming canonical
  translations.
- Glossary block respects term and character budgets.
- Chapter-aware filtering selects terms observed in active source text.
- Fallback priority includes owner-locked terms when raw matching is
  unavailable.
- Conflicts are reported and do not silently choose unsafe rules.
- Provider prompt includes the glossary block exactly once.
- `glossary_hash` changes when selected approved glossary rules change.
- Cache keys account for the selected glossary snapshot.
- Saved chapter text is not mutated.
- No real provider calls occur in tests.

Likely test files:

- `backend/tests/test_glossary_prompt_injection.py`
- `backend/tests/test_prompts.py`
- `backend/tests/test_pipeline_stages.py`
- `backend/tests/test_translation_scheduler.py`

## 17. Implementation Roadmap

Recommended phases:

1. `GLOSSARY-PROMPT-INJECTION-SERVICE-1`
   - Add a backend service that loads approved entries by `novel_id`, maps them
     to prompt-safe glossary terms, filters/ranks by active chapter text, and
     returns warnings.
2. `GLOSSARY-PROMPT-INJECTION-PIPELINE-1`
   - Wire the service into `TranslateStage` after segmentation/context is known
     and before provider calls.
3. `GLOSSARY-PROMPT-INJECTION-TESTS-1`
   - Add focused prompt, service, pipeline, cache/hash, and no-mutation tests if
     the first two phases need a separate hardening pass.
4. `GLOSSARY-PROMPT-INJECTION-LIVE-SMOKE-1`
   - Run a safe mock or controlled local translation smoke proving approved
     terms enter prompts and Reviewing terms do not.
5. `GLOSSARY-APPROVED-TERM-APPLY-PLAN-1`
   - Plan the separate saved-chapter repair/apply preview and rollback
     workflow.
6. `GLOSSARY-APPROVED-TERM-APPLY-1`
   - Implement explicit owner-confirmed saved chapter repair only after the
     plan is accepted.

## 18. Non-Goals

This docs phase does not include:

- provider calls
- implementation
- backend code changes
- frontend code changes
- migrations
- saved chapter rewrite
- automatic repair
- QA scanner or QA engine
- public reader glossary popovers
- user override UI
- automatic approval
- scraping
- translation
- seed data
- DB or storage mutation
