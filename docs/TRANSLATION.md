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

Deferred semantic-cache and broader advisory-QA work lives in [`WORK.md`](WORK.md).
