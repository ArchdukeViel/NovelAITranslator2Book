# Glossary Candidate Import and Provider Suggestion Plan

## 1. Purpose

Glossary candidate import exists because saved novels already contain evidence
that can help the owner build a better per-novel glossary before more chapters
are translated.

Saved raw chapters can contain source-side names, places, ranks, skills, and
setting terms. Saved translated chapters can contain the English renderings that
have already appeared, including drift such as different spellings for the same
character or place. A no-provider importer can mine that evidence without cost
or model risk.

Provider-assisted suggestion may later help identify terms that simple
heuristics miss, especially names, titles, and concepts whose raw and translated
forms are hard to align. Provider output is only suggestion data. It must never
be trusted as owner-approved. Provider-created terms enter the glossary as
Reviewing candidates, which map to backend `candidate` status. Owner approval is
required before a term becomes an Approved glossary rule.

This document is a plan only. It does not implement import, provider calls,
prompt injection, QA scanning, seed data, chapter rewrite, storage mutation, DB
mutation, frontend UI, backend routes, or migrations.

## 2. Definitions

- Reviewing candidate: an unapproved glossary entry shown to the owner as
  `Reviewing`. Backend status should be `candidate` for v1. It may have
  confidence, aliases, and provenance, but it is not enforced.
- Approved glossary term: an owner-approved entry for one novel. Backend status
  is `approved`. The approved translation becomes the default glossary
  translation for that term in that novel.
- Raw term: the source-side term or surface form from saved raw chapter text.
  For Japanese novels this may be kanji, kana, romaji, or an internal concept
  label when source text is mojibaked or unavailable.
- Translation: the English rendering that should be used for an approved term,
  or a suggested rendering on a Reviewing candidate.
- Alias: an observed, allowed, rejected, banned, deprecated, or source-side
  variant attached to a glossary entry.
- Provenance/evidence: compact source metadata and local references explaining
  where a candidate or decision came from. Provenance can include source site,
  adapter, source novel ID, chapter references, raw term, observed translated
  term, confidence, and short evidence references.
- Provider-assisted suggestion: a glossary candidate proposed by an LLM or
  translation provider after comparing raw and translated chapter context.
- Saved-chapter import: a no-provider scan over existing saved raw and
  translated chapter data that proposes Reviewing entries and evidence.
- Prompt injection: a later translation phase that inserts owner-approved
  glossary constraints into future translation prompts.
- Repair/apply approved terms: a later explicit process that previews and
  applies approved glossary decisions to already saved translated chapters with
  backup/versioning and rollback.

## 3. Source-Agnostic Ownership Rule

Glossary entries are owned by platform `novel_id`.

Source site, source adapter, source URL, source novel ID, source chapter ID, and
local chapter references are provenance only. They explain evidence. They do not
own canonical glossary decisions.

The same term may exist differently in different novels. `Pocott` in one novel
and another `Pocott` in a different novel are separate glossary decisions. The
system must work for Syosetu, Kakuyomu, Novel18, generic imports, local imports,
mirrors, and future source adapters without creating source-specific glossary
tables, routes, or UI ownership rules.

## 4. No-Provider Saved Chapter Import

### Inputs

The importer should read existing saved data only:

- DB novel and chapter metadata for the target `novel_id`.
- Saved raw chapter payloads through storage services, not raw filesystem paths
  exposed to callers.
- Saved translated chapter payloads through storage services.
- Chapter IDs, chapter numbers, source site, source adapter, source novel ID,
  source URL, and stable local references.
- Existing glossary entries, aliases, provenance, and QA findings for
  deduplication and conflict handling.

It should not scrape, call providers, translate, repair chapters, or mutate
stored chapter text.

### Raw/Translated Pairing

Pair raw and translated chapters by DB `chapters.id` where available. If DB
chapter rows are incomplete, fall back to stable chapter identifiers already
stored in the chapter payloads, chapter numbers, or source chapter IDs. Pairing
must be conservative: if a raw and translated chapter cannot be confidently
matched, skip cross-text alignment and record only single-side candidates.

The importer should split both raw and translated text into paragraph-like
units when stable paragraph IDs exist. If paragraph IDs are unavailable, it may
use chapter-level evidence references. It should store references such as
chapter ID, chapter number, paragraph ID, or local key, not long copyrighted
source excerpts.

### Term Candidate Heuristics

The no-provider importer should produce candidates from repeated and distinctive
signals, not from common words.

English translated-text heuristics:

- Repeated capitalized phrases, for example `Pocott Village`, `World Tree`,
  `Order of Knights`, `Slime King`.
- Repeated proper-name-like tokens that are not sentence-start-only artifacts.
- Multi-word title-case phrases with fantasy domain terms such as `House`,
  `Order`, `Realm`, `Kingdom`, `Saint`, `Blessing`, `Sword`, `World Tree`.
- Parenthesized skill/rank notation such as `Woodcutter (N)` or `UR`.
- Repeated inconsistent variants with small edit distance, for example
  `Pokot` versus `Pocott`, or `Guld` versus `Gurd`.
- Repeated organization/place phrases that appear across chapters.

Japanese/source-side heuristics when raw text is reliable:

- Repeated katakana sequences likely to be names or loanwords.
- Repeated kanji compounds followed by titles, ranks, honorifics, or place
  suffixes.
- Known proper-noun markers, honorifics, and entity suffixes when detectable.
- Ruby/furigana/readings if the source adapter already preserved them.
- Source terms that align near repeated English proper nouns when paragraph or
  sentence alignment is available.

Mojibake or unreliable source text should lower confidence and avoid invented
Japanese terms. In that case, an internal concept label and translated evidence
may be acceptable as a Reviewing candidate.

### Skipped Candidates

Skip candidates when they are likely unsafe:

- Common English words, days, months, generic pronouns, and sentence-start-only
  capitalized words.
- Short one-letter or two-letter tokens unless whitelisted by domain context,
  such as rank notation.
- Terms seen only once, unless they are unusually structured and the owner has
  asked for low-confidence candidates.
- Long sentences or copyrighted excerpts.
- Provider/model names, UI labels, logs, or metadata that are not story terms.
- Candidates that already exist as approved glossary entries.

### Deduplication and Confidence

Deduplicate within the same `novel_id` by normalized term text and normalized
translation. Do not deduplicate globally across novels.

Suggested confidence factors:

- Frequency across chapters.
- Frequency within a chapter.
- Whether the term appears in both raw and translated evidence.
- Whether variants are consistently aligned.
- Whether the candidate is a multi-word phrase or source-side proper noun.
- Whether source text is clean or mojibaked.
- Whether an existing alias or approved entry already explains it.

Confidence should be numeric when stored in current tables. Suggested bands:

- `0.80-1.00`: repeated across chapters with clear evidence.
- `0.50-0.79`: repeated but source/translation alignment is partial.
- `0.20-0.49`: low-confidence single-side evidence or mojibake-heavy evidence.

Confidence is a review signal only. It does not approve a term.

### Alias Observation and Provenance

When likely variants appear, the importer should attach aliases as observed
variants on a Reviewing entry, or create a review note/QA finding if the owner
has already approved a conflicting canonical term.

Provenance rows should include:

- `novel_id`
- `source_site`
- `source_adapter`
- `source_novel_id`
- `source_chapter_id` and/or `source_chapter_number`
- optional DB `chapter_id`
- `raw_source_term` when reliable
- `observed_translated_term`
- compact `evidence_ref` or `local_reference`
- `evidence_quality`
- `confidence`

The importer should create Reviewing candidates only. It must not mark terms
Approved automatically, even when confidence is high.

## 5. Provider-Assisted Candidate Suggestion

Provider-assisted suggestion is optional and configurable. It compares raw
source text and translated text to propose glossary candidates that heuristics
may miss.

Rules:

- Provider output creates Reviewing entries only.
- Provider output never creates Approved entries.
- No direct chapter rewrite is allowed.
- No prompt injection is performed by this step.
- Provider output is not trusted without validation.
- Provider calls must follow existing provider credential and routing patterns.
- Provider calls must have owner-only access, cost limits, rate limits, maximum
  chapters per run, maximum characters per prompt, and dry-run preview.
- Provider outputs must be validated against a strict JSON schema before merge.
- Invalid, malformed, duplicate, overly broad, or excerpt-heavy output is
  rejected or returned as a preview error.

The provider step should run after local dedupe. The importer should avoid
sending candidates that are already approved or obvious duplicates. Provider
calls should focus on uncertain chapters, high-drift chapters, or owner-selected
ranges.

## 6. Provider Prompt Contract

The prompt should send bounded chapter or batch context:

- novel identity and chapter references
- raw source text or short bounded chunks when available
- translated text or short bounded chunks
- existing approved glossary terms for exclusion and conflict awareness
- existing Reviewing candidates for dedupe awareness

The task should ask for glossary candidates only. It should not ask for chapter
translation, rewrite, repair, or QA enforcement.

Prompt requirements:

- Return strict JSON only.
- Include `raw_term`, `suggested_translation`, `term_type`, `confidence`,
  `aliases`, `evidence`, and `rationale`.
- Mark uncertainty explicitly.
- Avoid duplicate/common words.
- Avoid long copyrighted excerpts in output.
- Prefer references, short terms, and compact evidence summaries.
- Do not invent source terms when source text is mojibaked or uncertain.
- Do not approve anything.

Example JSON response shape:

```json
{
  "candidates": [
    {
      "raw_term": "ポコット",
      "suggested_translation": "Pocott",
      "term_type": "place",
      "confidence": 0.86,
      "uncertain": false,
      "aliases": [
        {
          "alias_text": "Pokot",
          "alias_type": "observed",
          "applies_to": "translated_text",
          "reason": "Observed alternate rendering in translated chapter context."
        }
      ],
      "evidence": [
        {
          "source_chapter_id": "4",
          "source_chapter_number": 4,
          "raw_source_term": "ポコット",
          "observed_translated_term": "Pocott",
          "context_ref": "chapter:4"
        }
      ],
      "rationale": "Repeated place name with one observed spelling variant."
    }
  ],
  "warnings": [
    {
      "message": "Some source text was mojibake; source terms marked uncertain."
    }
  ]
}
```

## 7. Candidate Merge and Upsert Behavior

Merge behavior must protect owner decisions.

- If an existing Approved term exists, do not overwrite it.
- If an existing Approved term conflicts with a suggestion, create a QA/review
  note or observed alias candidate, not an automatic replacement.
- If an existing Reviewing candidate exists, update confidence, provenance, and
  observed aliases only.
- If a conflicting translation appears for an existing Reviewing candidate,
  preserve the original candidate and add evidence/alias/review notes.
- If a banned or rejected alias appears, create a QA finding or review note.
- Preserve owner notes, owner locks, public visibility, and decision history.
- Do not change Approved to Reviewing.
- Do not change an owner-approved translation without explicit owner action.
- Do not set `owner_locked` from importer or provider output.

Upsert should be scoped to `novel_id`. The same candidate in another novel is a
separate entry.

## 8. Owner Review Flow

Imported candidates appear in the admin UI as Reviewing.

The owner can:

- edit Term
- edit Translation
- edit Type
- review confidence and source/evidence
- approve the row

Approved means the translation becomes the default glossary translation for that
word or phrase in that novel. The owner-facing UI should continue showing only
Reviewing and Approved. Backend internals may keep `candidate` and `approved`
statuses, and may retain `recommended`, `rejected`, and `deprecated` for older
or advanced workflows.

Approving a glossary term does not rewrite saved chapters. It only changes the
glossary decision.

## 9. Prompt Injection Later

Prompt injection belongs to a later phase.

Later behavior:

- Approved terms are injected into future translation prompts.
- Reviewing terms are not enforced.
- Rejected or banned aliases may be included as "avoid these variants" only
  after owner review, and only when helpful.
- Prompt injection should respect prompt budget limits.
- Long glossaries should be prioritized by relevance to the current chapter,
  owner lock, term type, first/last seen chapter, frequency, and known drift.
- Selected glossary inputs should be snapshotted or hashed with translation job
  metadata for reproducibility.
- Provider fallback must preserve the same glossary snapshot instead of silently
  changing constraints.

## 10. Saved Chapter Apply/Repair Later

Saved chapter apply/repair belongs to a later explicit phase.

Rules:

- Applying approved terms to saved chapters must be explicit.
- There must be a preview before rewrite.
- Chapter backup or version history is required before mutation.
- Rollback must be available.
- Matching policy must be explicit, for example exact phrase, word boundary, or
  manual only.
- Approve must not trigger hidden rewrite.
- Simple exact replacement should not require a provider call.
- Risky replacement requires manual review.
- Paragraph IDs, chapter structure, reader layout, active translation versions,
  and public chapter contracts must be preserved.

Repair should produce a reviewable diff and audit trail. It should not be
implemented as blind global find/replace.

## 11. Pipeline Placement

Candidate import can fit in several places:

- After parse/import, using raw source text only.
- After single-chapter translation, using raw and translated chapter pairs.
- After batch translation, using broader repeated-term evidence.
- Manually triggered from the admin UI for an existing novel.
- Scheduled or queued as a background task after enough chapters exist.

Recommended v1:

1. Manual admin-triggered no-provider import from saved chapters.
2. Preview candidates before saving.
3. Save selected candidates as Reviewing.
4. Add provider-assisted suggestion as an optional second phase.
5. Only later consider automatic pipeline sidecar import.

Manual first is safer because it avoids hidden provider spend, avoids surprise
DB writes, and lets the owner inspect import quality before automation.

## 12. Admin UI Implications

Future UI should add an owner-only import flow:

- `Import candidates` button on the admin glossary page.
- Source selector: `Saved chapters` or `Provider-assisted`.
- Chapter range and max chapter controls.
- Dry-run preview before save.
- Candidate list with term, translation, type, confidence, source, and evidence.
- Dedupe/conflict labels.
- Create selected rows as Reviewing only.
- Owner manually approves after import.
- No direct repair in the import flow.
- No prompt injection toggle in the import flow.
- No provider run unless owner explicitly chooses provider-assisted mode.

The simplified owner list should remain simple. Advanced evidence/history views
can be a separate details action later.

## 13. Safety and Cost Controls

Safety controls:

- Owner-only access.
- Dry-run preview by default.
- Max chapters per run.
- Max characters per prompt.
- Max candidates per run.
- Dedupe before provider calls where possible.
- No secrets logged.
- No `.env` printing.
- No raw provider credentials exposed to frontend.
- No large source excerpts stored.
- Store compact evidence references rather than copyrighted passages.
- Validate provider JSON before merge.
- Keep provider calls optional and disabled unless configured.

Cost controls:

- Per-run budget.
- Per-day budget.
- Provider/model selection through existing credential patterns.
- Rate-limit and cooldown awareness.
- Clear estimate before running provider-assisted suggestion when possible.
- Cancel/retry behavior through existing job/activity conventions in later
  implementation.

## 14. Implementation Roadmap

Recommended implementation order:

1. `GLOSSARY-CANDIDATE-IMPORT-REPOSITORY-1`
   - Add service/repository helpers for candidate preview, dedupe, upsert, alias
     observation, provenance creation, and conflict reporting.
   - No provider calls.
2. `GLOSSARY-CANDIDATE-IMPORT-API-1`
   - Add owner-only dry-run and save endpoints for saved-chapter import.
   - Keep routers thin and delegate to services.
3. `GLOSSARY-CANDIDATE-IMPORT-UI-1`
   - Add Import candidates UI with preview and selected save as Reviewing.
4. `GLOSSARY-PROVIDER-CANDIDATE-SUGGESTION-1`
   - Add optional provider-assisted suggestion with strict JSON validation,
     budget/rate controls, and no approval.
5. `GLOSSARY-PROMPT-INJECTION-1`
   - Inject Approved terms into future translation prompts only.
6. `GLOSSARY-APPROVED-TERM-APPLY-PLAN-1`
   - Plan explicit preview, versioning, rollback, and matching safety for saved
     chapter repair.
7. `GLOSSARY-APPROVED-TERM-APPLY-1`
   - Implement explicit, reversible apply/repair after the plan is accepted.

## 15. Non-Goals

- No automatic approval.
- No hidden chapter rewrite.
- No direct translation provider call during this docs phase.
- No prompt injection yet.
- No QA scanner yet.
- No public reader glossary popovers yet.
- No user override UI yet.
- No scraping.
- No translation.
- No seed data insertion.
- No storage or DB mutation in this phase.

## 16. Recommended Next Phase

Recommended next phase:

`GLOSSARY-CANDIDATE-IMPORT-REPOSITORY-1`

Start with no-provider saved-chapter candidate import because it is cheaper,
safer, reviewable, and uses evidence already present in the project. Provider
suggestion should come only after preview, dedupe, merge, provenance, and owner
Reviewing/Approved flows are stable.
