# Requirements: Translation QA Hardening

## Introduction

The translation pipeline has a real `TranslationQAStage` with a score-based pass/fail gate (score ≥ 0.75, no errors). The existing checks cover: empty output, output same as source, extreme length ratios, provider refusal/error text detection, structural placeholder preservation, and paragraph marker fidelity. That is a solid defensive net for gross failures.

Three gaps undermine the system's value for literary quality control. First, **`qa_status` is permanently `"pending"`**: `_save_chunk_output` writes `"qa_status": "pending"` on every output record and nothing ever updates it to `"passed"` or `"failed"`. The actual QA outcome lives in `context.metadata` but is never written back to the persisted output record, making per-chunk QA auditing impossible after the fact. Second, **activation is unconditional**: `save_translated_chapter` always activates the new version immediately. The gate is implicit — `TranslationQAStage` raises `TranslationQAError` to abort the pipeline before save — but there is no explicit soft gate that saves a low-confidence translation for audit without activating it as the reader version. Third, **Japanese residue is not detected**: a translation that silently contains large amounts of untranslated CJK characters passes QA as long as it is not empty and not too short/long.

This spec closes those three gaps and adds the literary QA checks the audit identifies as missing for premium Japanese web-novel translation.

## Requirements

### REQ-1: Update `qa_status` in Persisted Chunk Output Records

After `TranslationQAStage` evaluates each chunk, the persisted output record must reflect the actual QA outcome.

- REQ-1.1: After `TranslationQAStage` updates `context.chunk_states[chunk_id]["status"]`, it must also call a storage update to set the chunk output record's `qa_status` to `"passed"` or `"qa_failed"` to match the `result.passed` value.
- REQ-1.2: `qa_score`, `qa_warnings`, and `qa_errors` must also be written to the persisted chunk output record at the same time as `qa_status`.
- REQ-1.3: The storage method for this update must be `upsert_chunk_state` or an equivalent that does not create a new output record — it must update the existing one written by `TranslateStage`.
- REQ-1.4: If the storage update fails, the pipeline must continue — the update is best-effort audit metadata, not a blocking step.

### REQ-2: Explicit Soft Activation Gate for Low-Confidence Translations

A translated version that passes QA but has a low confidence score must be saved but not automatically activated as the reader version.

- REQ-2.1: A configurable `low_confidence_activation_threshold` setting must be added to `backend/src/novelai/config/settings.py` (default: `0.55`). When `confidence_score < low_confidence_activation_threshold`, the new version must be saved but not set as the active version.
- REQ-2.2: `save_translated_chapter` must accept an optional `auto_activate: bool = True` parameter. When `auto_activate=False`, the function must append the version to `translation_versions` but must not call `_set_active_translation_version`.
- REQ-2.3: The orchestration layer that calls `save_translated_chapter` after a translation run must pass `auto_activate=False` when `confidence_score < low_confidence_activation_threshold`.
- REQ-2.4: The admin chapter version list response must expose `active: bool` per version so operators can see which version is active and which are saved-but-not-activated.
- REQ-2.5: The admin must be able to manually activate a saved version via the existing `activate_translated_chapter_version` endpoint (from `glossary-apply-safety` spec). This spec does not add a new endpoint for this.
- REQ-2.6: A `WARNING` log must be emitted when a chapter is saved with `auto_activate=False` due to low confidence: `"Chapter {chapter_id} saved with low confidence ({score:.2f}), not activated. Use activate endpoint to promote."`.

### REQ-3: Japanese / CJK Residue Detection

Translated output that contains a large fraction of CJK characters must be flagged as a QA warning or error.

- REQ-3.1: A new check `_check_source_language_residue` must be added to `backend/src/novelai/translation/qa.py`.
- REQ-3.2: The check must compute `cjk_char_ratio = cjk_char_count / max(1, total_output_chars)` on the translated output text.
- REQ-3.3: If `cjk_char_ratio > 0.10` and `len(output_text) > 50`, the check must append `"cjk_residue_high"` to `errors` (translation likely not done or heavily copy-pasted from source). Threshold: >10% CJK is an error.
- REQ-3.4: If `cjk_char_ratio > 0.03` and `cjk_char_ratio <= 0.10`, the check must append `"cjk_residue_moderate"` to `warnings`. Threshold: 3–10% is a warning (some proper nouns in Japanese script may be intentional).
- REQ-3.5: CJK characters are defined as the Unicode ranges: CJK Unified Ideographs (U+4E00–U+9FFF), Hiragana (U+3040–U+309F), Katakana (U+30A0–U+30FF), and CJK Compatibility (U+F900–U+FAFF).
- REQ-3.6: `_check_source_language_residue` must be called from `evaluate_translation_quality` after `_check_basic_text`.
- REQ-3.7: The thresholds (0.03 and 0.10) must be configurable constants at the top of `qa.py`, not hardcoded inline.

### REQ-4: Repeated-Line / Duplicated-Fragment Detection

Translated output that contains a large proportion of repeated lines must be flagged.

- REQ-4.1: A new check `_check_repetition` must be added to `qa.py`.
- REQ-4.2: The check must split the output into non-empty lines and compute `duplicate_line_fraction = duplicate_lines / total_lines`.
- REQ-4.3: If `duplicate_line_fraction > 0.30` and `total_lines >= 5`, append `"repetition_high"` to `errors`.
- REQ-4.4: If `duplicate_line_fraction > 0.15` and `duplicate_line_fraction <= 0.30` and `total_lines >= 5`, append `"repetition_moderate"` to `warnings`.
- REQ-4.5: Marker-only lines (`[P pNNNN]`, `[CHAPTER ...]`) must be excluded from the line deduplication count to avoid false positives from structural markers.
- REQ-4.6: `_check_repetition` must be called from `evaluate_translation_quality`.

### REQ-5: Glossary-Term Consistency Check in QA

When approved glossary terms are available in context, the QA stage must check that they appear in the translation.

- REQ-5.1: `evaluate_translation_quality` must accept an optional `approved_glossary: list[dict]` parameter containing `{"source": ..., "target": ...}` entries.
- REQ-5.2: For each entry where `source` appears in `source_text`: if `target` does not appear (case-insensitive substring match) in `output_text`, append `"glossary_term_missing:{term}"` to `warnings`.
- REQ-5.3: The check must be skipped (not an error) when `approved_glossary` is `None` or empty.
- REQ-5.4: The maximum number of terms checked must be capped at 20 to limit warning noise on large glossaries.
- REQ-5.5: `TranslationQAStage` must pass the rendered glossary terms from `context.metadata.get("glossary_prompt_blocks")` (already populated by `TranslateStage`) to `evaluate_translation_quality` when available.

### REQ-6: QA Diagnostics in Admin Chapter Response

Per-chapter QA results must be visible in the admin chapter detail response.

- REQ-6.1: The admin chapter version list endpoint (in `library.py`) must include `qa_status`, `qa_score`, `qa_warnings` (list), and `qa_errors` (list) per version.
- REQ-6.2: These fields must come from the persisted chunk output records (after REQ-1 is implemented). For legacy versions written before this spec, these fields must default to `null`/empty list.
- REQ-6.3: The fields must be sourced from the translated chapter bundle's version record, not re-computed on read.

### REQ-7: Tests

- REQ-7.1: A new test file `backend/tests/test_translation_qa_hardening.py` must be created.
- REQ-7.2: `test_qa_status_updated_in_chunk_output` — after `TranslationQAStage.run()`, the persisted output record has `qa_status="passed"` or `qa_status="qa_failed"` matching the result.
- REQ-7.3: `test_cjk_residue_error` — output with >10% CJK → `"cjk_residue_high"` in errors, `passed=False`.
- REQ-7.4: `test_cjk_residue_warning` — output with 5% CJK → `"cjk_residue_moderate"` in warnings.
- REQ-7.5: `test_cjk_residue_clean` — output with <3% CJK (normal proper nouns) → no residue flags.
- REQ-7.6: `test_repetition_error` — output with 40% duplicate lines (≥5 lines) → `"repetition_high"` in errors.
- REQ-7.7: `test_repetition_warning` — output with 20% duplicate lines → `"repetition_moderate"` in warnings.
- REQ-7.8: `test_repetition_excludes_markers` — structural markers not counted as duplicate lines.
- REQ-7.9: `test_low_confidence_not_activated` — `confidence_score=0.40`, threshold=`0.55` → version saved but `active_translation_version_id` not updated.
- REQ-7.10: `test_high_confidence_activated` — `confidence_score=0.85` → version saved and activated.
- REQ-7.11: `test_glossary_term_missing_warning` — source contains term "Akira", glossary says target="Akira", output does not contain "Akira" → `"glossary_term_missing:Akira"` in warnings.
- REQ-7.12: `test_glossary_check_skipped_when_no_glossary` — `approved_glossary=None` → no glossary warnings.
- REQ-7.13: `test_qa_score_decreases_on_new_errors` — adding a `cjk_residue_high` error reduces score below the passing threshold when combined with other errors.

## Non-Goals

- This spec does not add cross-chapter continuity memory or context injection.
- This spec does not change the existing passing threshold (0.75). New checks add to the existing system.
- This spec does not add a UI activation workflow beyond what `glossary-apply-safety` already specifies for the version activate endpoint.
- This spec does not add provider-specific quality checks (hallucination detection, named-entity drift) — those require an external QA model call.
- This spec does not change the public reader API.
