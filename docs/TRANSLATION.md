# Translation and Glossary

Canonical translation quality, prompt, glossary, and cache identity contract.

## Pipeline

Source chapters become deterministic paragraphs and temporary chunks. Prompt
assembly injects approved glossary terms and bounded context. Provider output is
parsed, checked by deterministic QA, post-processed, and saved as a versioned
translated chapter. Failed chapters do not erase successful siblings.

## JP-EN Quality Rules

JP-EN policy applies when source is `ja|japanese` and target is `en|english`.
Policy identity is `jp_en_quality_v1`; changing output-shaping instructions
requires a version bump and cache invalidation.

Prompts must:

1. Preserve facts; never omit, summarize, censor, soften, or add information.
2. Use approved glossary translations exactly.
3. Preserve tone, register, narrator voice, paragraph order, and scene order.
4. Prefer natural publication-quality English over awkward literalness.
5. Never invent gender, identity, relationships, motives, or speaker attribution.
6. Preserve ambiguity with neutral wording when context cannot resolve it.
7. Preserve notes and structural boundaries; do not introduce markup needlessly.

Honorific mode is one of `retain`, `translate`, or `omit`; do not mix modes
without clear source need. Dialogue and narration remain distinct.

## Glossary Lifecycle

File glossary and PostgreSQL glossary are distinct stores bridged through explicit
sync. Approved DB entries are translation truth. Suggested/candidate terms never
become public or prompt-active without approval.

Required states:

- file entries: source-derived candidate state;
- DB entries: candidate, approved, rejected, disabled as implemented;
- novel glossary: lifecycle status used by onboarding/translation gates.

Rules:

- Glossary injection happens once per prompt; do not duplicate full blocks.
- Conflicts keep approved term and may report bounded review metadata.
- Revision/hash changes participate in translation/cache invalidation.
- Public annotations include only explicitly public-visible approved entries.
- Diagnostics and sync never expose private notes or credentials.

## Optional Review Metadata

Structured responses may include `uncertainties`, `glossary_conflicts`, and
`style_notes`. Fields remain optional, parser-compatible, bounded, and excluded
from public chapter text.

## Cache Identity

Cache identity includes source/target language, provider/model, style and
consistency settings, glossary revision/hash, prompt template version, and JP-EN
policy version. Never reuse cache across changed output-shaping inputs.

## Cache Acceptance by Attempt

Cache eligibility is locked to the exact QA-accepted attempt. A `CacheEntry`
carries `attempt_number`, `translation_run_id`, `output_hash`, and
`cache_key`. `make_cache_key` includes provider key, model id, prompt template
version, and the canonical glossary hash so provider / model / prompt /
glossary changes produce different keys.

`CacheFlushStage` rejects any chunk whose status is in the rejection set
`needs_retry | needs_review | qa_failed`; pending entries for such chunks are
dropped (or permanently invalidated) before any cache write. For accepted
chunks the pending entry survives the same dedupe-by-key step. `status` is
immutable per attempt; a model switch produces a new key and a model-A
attempt never collides with model-B. Rejected attempts persist an evidence
trail; only accepted outputs land in the cache.

## Translation Overlay and Raw Generation Immutability

Translation writes land in the per-chapter overlay
(`translations/<encoded-chapter-stem>.json` plus an `active/` pointer), never
in the raw chapter bundle (`chapters/<encoded-chapter-stem>.json`). Once a
committed raw generation is activated under `generations/<gen-id>/`, the raw
bundle and its image assets are byte-immutable; every retranslation,
manual edit, or QA retry rewrites only the overlay. Readers compose the
active raw generation with the active translation overlay on read.

## Run Manifest and Translation Lineage

Each translation run produces a `TranslationRunManifest` linking:

- `translation_run_id` (stable across stages of one run);
- `raw_generation_id` (the activated generation the run fed on; **provenance only** — a new generation with identical raw content/structure/image hashes can reuse the prior translation without invalidation);
- canonical glossary hash (a SHA-256 of normalized glossary entries);
- `prompt_template_version` resolved from `novelai.prompts.PROMPT_TEMPLATE_VERSION`;
- `qa_policy_fingerprint` (mode, deterministic-QA version, LLM grader model,
  minimum score, retry budget, structured-output policy version);
- `provider_key`, `provider_model`, `source_language`, `target_language`;
- finalized counts (`expected_count`, `completed_count`, `skipped_count`,
  `review_count`, `failed_count`) and source-order `chapter_ids`.

Manifest persistence is logged but never silently swallowed so CI and
operators see when the committed manifest goes missing. Initial manifest
persistence (`status="running"`) occurs before chapter translation work;
final manifest update runs after chapter execution and records finalized counts.

### Production Reuse Gate & Delta Retranslation Contract

Before returning `already_complete` or `already_translated`, the production
resume path builds the **current effective translation contract** and calls
`is_translation_valid()` with it. The contract includes:

- `source_text_hash` (current raw text hash)
- `active_glossary_hash` (current glossary hash)
- `prompt_version` (current prompt template version)
- `provider_key`, `provider_model` (current provider/model)
- `active_raw_generation_id` (current active generation)
- `source_structure_hash` (current raw structure hash)
- `source_image_manifest_hash` (current image manifest hash)
- `qa_policy_fingerprint` (current QA policy)
- `source_language`, `target_language` (current languages; missing stored
  language fails closed)
- `style_preset`, `consistency_mode`, `json_output`, `honorific_policy`
  (current output-shaping settings — any change alters generated text and
  forces retranslation; honorific policy compares normalized identity, so
  case/whitespace spelling variation never causes spurious retranslation)

When delta retranslation is enabled (`TRANSLATION_DELTA_RETRANSLATION_ENABLED=True`,
the default), the delta execution path (`_try_delta_translate_chapter`) enforces the
identical output-shaping and generation-provenance contract before declaring a chapter
`whole_chapter_unchanged`. If the stored translation version differs in style preset,
consistency mode, JSON output, honorific policy, or lacks raw generation provenance,
the delta path bails with `fallback_reason="output_contract_changed"` and forces full
retranslation.

`is_translation_valid` **fails closed** when a required input has no stored
value on the existing translation version. A DB `COMPLETE` state is evidence
of previous completion, **not** of current validity — a stale source text,
glossary, prompt, QA policy, provider/model, target language, structure,
image manifest, or output-shaping setting forces retranslation. The previous
version is retained in the per-chapter overlay history. `raw_generation_id`
is **provenance**: a stored id must exist when a generation is active
(missing lineage is stale / needs-backfill), but the stored id is never
compared for equality with the current active generation id — an otherwise
identical translation stays reusable across generation activations (hashes
and the effective contract are the validity gate).

## Chapter Selection

A selection string (`"all"`, `"1-3;8"`, `"2"`, `"kakuyomu:1681809307..."`)
resolves through `resolve_chapter_selection` against the complete current
chapter index. Numeric selections resolve to the chapter sitting at the
given sequence position, then run all downstream operations against the
stable `chapter_id`. Kakuyomu percent-encoded ids (`kakuyomu:<episode>`) and
Syosetu numeric ids share one pipeline — there is no `int(chapter["id"])`
or `chapter_id.isdigit()` branch in the request flow.

## Source-Order Convergence

Source state persists `ordered_episode_ids` matching the complete current
index plus per-episode `source_availability`, `first_seen_at`,
`last_seen_at`, `missing_since`, `content_hash`, `structure_hash` where
known. Episodes absent from the index become
`source_availability == "missing_from_current_index"` (raw + translated
history is retained); on reappearance `missing_since` is cleared. Repeated
crawls after reconciliation produce no reorder / removal delta. Reorder
signals propagate to reader / export ordering without retranslation.

## QA

Deterministic checks cover empty or source-identical text, suspicious length,
unresolved placeholders, provider refusals/error text, paragraph mapping, and
glossary consistency. LLM QA is advisory, disabled by default where configured,
and cannot silently replace deterministic gates or auto-publish findings.

## Change Checklist

- Update prompt/policy version when output can change.
- Update cache identity and invalidation tests.
- Preserve approved glossary terms and structural mapping.
- Keep review metadata optional and private.
- Update focused prompt snapshots intentionally.
- Run prompt, translation, glossary, and integration regression tests.
- Re-hash the canonical glossary; new hash invalidates dependents.
- Bump `qa_policy_fingerprint` and `prompt_template_version` together with
  any output-shaping change.

Deferred semantic-cache and broader advisory-QA work lives in [`WORK.md`](WORK.md).
