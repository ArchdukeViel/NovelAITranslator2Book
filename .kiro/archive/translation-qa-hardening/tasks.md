# Tasks: Translation QA Hardening

## Task List

- [x] 1. Add CJK residue check to `qa.py`
  - [x] 1.1 Add `CJK_RESIDUE_ERROR_THRESHOLD = 0.10` and `CJK_RESIDUE_WARNING_THRESHOLD = 0.03` constants to `backend/src/novelai/translation/qa.py` (REQ-3.7)
  - [x] 1.2 Add `_CJK_RANGES` list covering Hiragana, Katakana, CJK Unified Ideographs, CJK Compatibility ranges (REQ-3.5)
  - [x] 1.3 Implement `_is_cjk(ch: str) -> bool` helper (REQ-3.5)
  - [x] 1.4 Implement `_check_source_language_residue(output_text, *, warnings, errors)`: compute CJK ratio, append `"cjk_residue_high"` or `"cjk_residue_moderate"` as appropriate; skip when `len(output_text) <= 50` (REQ-3.1–REQ-3.4)
  - [x] 1.5 Call `_check_source_language_residue` from `evaluate_translation_quality` after `_check_basic_text` (REQ-3.6)

- [x] 2. Add repetition check to `qa.py`
  - [x] 2.1 Add `REPETITION_ERROR_THRESHOLD = 0.30`, `REPETITION_WARNING_THRESHOLD = 0.15`, `REPETITION_MIN_LINES = 5` constants (REQ-4.3, REQ-4.4, REQ-4.5)
  - [x] 2.2 Implement `_check_repetition(output_text, *, warnings, errors)`: filter non-empty content lines excluding marker lines, compute duplicate fraction, append `"repetition_high"` or `"repetition_moderate"` (REQ-4.1–REQ-4.5)
  - [x] 2.3 Call `_check_repetition` from `evaluate_translation_quality` (REQ-4.6)

- [x] 3. Add optional glossary term check to `evaluate_translation_quality`
  - [x] 3.1 Add `approved_glossary: list[dict] | None = None` parameter to `evaluate_translation_quality` (REQ-5.1)
  - [x] 3.2 Implement `_check_glossary_terms(source_text, output_text, approved_glossary, *, warnings)`: cap at 20 terms, skip terms not in source, append `"glossary_term_missing:{source_term}"` when target absent from output (REQ-5.2, REQ-5.4)
  - [x] 3.3 Call `_check_glossary_terms` when `approved_glossary` is non-empty (REQ-5.3)

- [x] 4. Update `TranslationQAStage` to persist `qa_status` in chunk output records
  - [x] 4.1 After updating `context.chunk_states[chunk_id]` in `translation_qa.py`, add best-effort call to update the persisted output record with `qa_status`, `qa_score`, `qa_warnings`, `qa_errors` (REQ-1.1, REQ-1.2)
  - [x] 4.2 Wrap the update call in try/except to ensure it is non-blocking (REQ-1.4)
  - [x] 4.3 Set `qa_status = "passed"` when `result.passed`, else `"qa_failed"` (REQ-1.1)

- [x] 5. Pass approved glossary terms to `evaluate_translation_quality` from `TranslationQAStage`
  - [x] 5.1 In `TranslationQAStage.run()`, extract approved glossary terms from `context.metadata` (from `glossary_approved_terms` or by parsing `glossary_prompt_blocks`) (REQ-5.5)
  - [x] 5.2 Pass the extracted terms as `approved_glossary` to `evaluate_translation_quality` (REQ-5.5)

- [x] 6. Add `glossary_approved_terms` to context in `TranslateStage`
  - [x] 6.1 In `TranslateStage`, after building the prompt glossary block, store the included term list as `context.metadata["glossary_approved_terms"]` in the format `[{"source": term, "target": translation}, ...]` so `TranslationQAStage` can access it (REQ-5.5)

- [x] 7. Add `auto_activate` parameter to `save_translated_chapter`
  - [x] 7.1 Add `auto_activate: bool = True` parameter to `save_translated_chapter` in `backend/src/novelai/storage/translations.py` (REQ-2.2)
  - [x] 7.2 When `auto_activate=False`, skip calling `_set_active_translation_version` and log `WARNING` (REQ-2.2, REQ-2.6)

- [x] 8. Add `TRANSLATION_LOW_CONFIDENCE_ACTIVATION_THRESHOLD` setting
  - [x] 8.1 Add `TRANSLATION_LOW_CONFIDENCE_ACTIVATION_THRESHOLD: float` to `backend/src/novelai/config/settings.py`, reading from env var with default `0.55` (REQ-2.1)

- [x] 9. Pass `auto_activate` from orchestration layer
  - [x] 9.1 In the orchestration translation layer, compute `auto_activate = confidence_score is None or confidence_score >= settings.TRANSLATION_LOW_CONFIDENCE_ACTIVATION_THRESHOLD` (REQ-2.3)
  - [x] 9.2 Pass `auto_activate` to `save_translated_chapter` (REQ-2.3)
  - [x] 9.3 Log `WARNING` when `auto_activate=False` (REQ-2.6)

- [x] 10. Expose QA fields in admin chapter version list
  - [x] 10.1 QA fields already flow through via `_translated_payload_to_version` → `list_translated_chapter_versions` → `translation_provider_response` → API response; no router changes needed (REQ-6.1)
  - [x] 10.2 Fields default to `None`/`[]` when absent from stored data (REQ-6.2, REQ-6.3)

- [x] 11. Write tests
  - [x] 11.1 Create `backend/tests/test_translation_qa_hardening.py` (REQ-7.1)
  - [x] 11.2 Write `test_cjk_residue_error` (REQ-7.3)
  - [x] 11.3 Write `test_cjk_residue_warning` (REQ-7.4)
  - [x] 11.4 Write `test_cjk_residue_clean` (REQ-7.5)
  - [x] 11.5 Write `test_repetition_error` (REQ-7.6)
  - [x] 11.6 Write `test_repetition_warning` (REQ-7.7)
  - [x] 11.7 Write `test_repetition_excludes_markers` (REQ-7.8)
  - [x] 11.8 Write `test_qa_status_updated_in_chunk_output` (REQ-7.2)
  - [x] 11.9 Write `test_low_confidence_not_activated` (REQ-7.9)
  - [x] 11.10 Write `test_high_confidence_activated` (REQ-7.10)
  - [x] 11.11 Write `test_glossary_term_missing_warning` (REQ-7.11)
  - [x] 11.12 Write `test_glossary_check_skipped_when_no_glossary` (REQ-7.12)
  - [x] 11.13 Write `test_qa_score_decreases_on_new_errors` (REQ-7.13)
  - [x] 11.14 Run `pytest backend/tests/test_translation_qa_hardening.py --tb=short -q` and confirm all pass
  - [x] 11.15 Run `ruff check backend/src/novelai/translation/qa.py backend/src/novelai/translation/pipeline/stages/translation_qa.py backend/src/novelai/storage/translations.py` and fix issues
  - [x] 11.16 Run `pyright backend/src/novelai/translation/qa.py backend/src/novelai/translation/pipeline/stages/translation_qa.py` and fix type errors
