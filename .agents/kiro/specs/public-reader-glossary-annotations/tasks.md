# Tasks: Public Reader Glossary Annotations

## Overview

Implement optional public-safe glossary annotations in the public reader.

This feature adds compact annotation metadata to public chapter responses and renders reader-facing highlights/tooltips without changing stored translated text. It must be conservative by default and must not expose admin-only glossary data, glossary diagnostics, editor QA metadata, prompt details, pending terms, rejected terms, internal notes, unpublished glossary entries, or provider/scheduler/storage metadata.

Scope boundaries:

- Do not change translated chapter text.
- Do not modify translated text storage.
- Do not re-run translation.
- Do not change prompt-time glossary injection.
- Do not change glossary admin/editor workflows.
- Do not change glossary-aware editor QA.
- Do not expose admin diagnostics publicly.
- Do not change public reader availability behavior.
- Do not change active-version selection.
- Do not use LLM-based annotation detection.
- Keep the feature optional, bounded, and backward compatible.

## Task List

- [ ] 1. Preflight Reader, Glossary, and Privacy Review
  - [ ] 1.1 Inspect public reader chapter API response shape.
  - [ ] 1.2 Inspect public reader chapter shell/unavailable response shape.
  - [ ] 1.3 Inspect public reader frontend rendering of `text`.
  - [ ] 1.4 Inspect public reader frontend rendering of `reader_blocks`.
  - [ ] 1.5 Inspect active translated version selection in public reader.
  - [ ] 1.6 Inspect public novel/chapter publication checks.
  - [ ] 1.7 Inspect glossary DB models for status, approval, aliases, definitions, internal flags, and visibility-related fields.
  - [ ] 1.8 Inspect glossary repository support for inherited/global glossary entries.
  - [ ] 1.9 Inspect glossary diagnostics and editor QA response fields to ensure they stay admin-only.
  - [ ] 1.10 Inspect settings/feature-flag patterns.
  - [ ] 1.11 Inspect per-novel metadata patterns.
  - [ ] 1.12 Inspect frontend reader preference/toggle patterns.
  - [ ] 1.13 Inspect existing public reader backend tests.
  - [ ] 1.14 Inspect existing public reader frontend tests.

- [ ] 2. Define Rollout and Enablement Strategy
  - [ ] 2.1 Decide whether annotations are request-level opt-in, always additive, or deployment-enabled.
  - [ ] 2.2 Prefer conservative first rollout.
  - [ ] 2.3 Add global backend setting for public glossary annotations.
  - [ ] 2.4 Add per-novel enable/disable metadata only if consistent with existing reader settings.
  - [ ] 2.5 Add request-level opt-in such as `include_glossary_annotations=true` if preserving current default response is preferred.
  - [ ] 2.6 Ensure disabled annotations return an empty list or omit the field according to existing API style.
  - [ ] 2.7 Ensure per-novel enablement cannot bypass public-safe glossary filtering.

- [ ] 3. Define Public Annotation API Contract
  - [ ] 3.1 Define additive `glossary_annotations` response field.
  - [ ] 3.2 Define behavior when annotations are disabled.
  - [ ] 3.3 Define behavior when annotations are unavailable.
  - [ ] 3.4 Define behavior for untranslated chapter shell responses.
  - [ ] 3.5 Define annotation object schema.
  - [ ] 3.6 Include stable public-safe `term_id`.
  - [ ] 3.7 Include `display_term` or `translation`.
  - [ ] 3.8 Include `source_term` only when public-safe.
  - [ ] 3.9 Include optional public-safe `reading`.
  - [ ] 3.10 Include optional public-safe `term_type`.
  - [ ] 3.11 Include optional public-safe `short_definition`.
  - [ ] 3.12 Include optional bounded public-safe `aliases`.
  - [ ] 3.13 Include required `matches` for inline annotation mode.
  - [ ] 3.14 Document that initial inline mode returns only matched terms.
  - [ ] 3.15 Keep response changes additive.

- [ ] 4. Define Match Metadata Contract
  - [ ] 4.1 Define match object schema.
  - [ ] 4.2 Include matched `surface` text.
  - [ ] 4.3 Include `block_index` when reader blocks are available.
  - [ ] 4.4 Include `start` offset in block text.
  - [ ] 4.5 Include `end` offset in block text.
  - [ ] 4.6 Specify that offsets refer to public rendered block text.
  - [ ] 4.7 Specify that offsets must not refer to raw source text.
  - [ ] 4.8 Specify fallback behavior when reader blocks are unavailable.
  - [ ] 4.9 Ensure match metadata lets frontend render without modifying stored text.

- [ ] 5. Add Public Glossary Term Selection Helper
  - [ ] 5.1 Add `list_public_glossary_terms(novel_id)` or equivalent helper.
  - [ ] 5.2 Load terms through existing glossary repository/service patterns.
  - [ ] 5.3 Include approved entries only.
  - [ ] 5.4 Exclude candidate entries.
  - [ ] 5.5 Exclude pending entries.
  - [ ] 5.6 Exclude rejected entries.
  - [ ] 5.7 Exclude disabled, archived, or inactive entries.
  - [ ] 5.8 Exclude internal/admin-only entries.
  - [ ] 5.9 Include inherited/global entries only if existing repository behavior supports them.
  - [ ] 5.10 Respect public novel/chapter publication checks.
  - [ ] 5.11 Return public-safe fields only.
  - [ ] 5.12 Do not expose glossary review notes, decision history, diagnostics, prompt metadata, or editor QA metadata.

- [ ] 6. Add Public Visibility Fields Only If Needed
  - [ ] 6.1 Check whether existing glossary schema already has a clear public-safe marker.
  - [ ] 6.2 If needed, add `public_visible`.
  - [ ] 6.3 If needed, add `public_definition`.
  - [ ] 6.4 If needed, add `public_display_term`.
  - [ ] 6.5 Default `public_visible` to `false` in migration.
  - [ ] 6.6 Keep `public_definition` separate from reviewer/internal notes.
  - [ ] 6.7 Keep `public_display_term` separate from internal-only glossary text.
  - [ ] 6.8 If avoiding migration, use existing tags/metadata only when they clearly mark public-safe exposure.
  - [ ] 6.9 Do not default all approved terms to public-visible.
  - [ ] 6.10 Keep existing glossary admin/editor workflows compatible.

- [ ] 7. Define Public Glossary Term Internal Shape
  - [ ] 7.1 Define `PublicGlossaryTerm` or equivalent internal object.
  - [ ] 7.2 Include opaque public-safe `term_id`.
  - [ ] 7.3 Include `display_term`.
  - [ ] 7.4 Include optional `translation`.
  - [ ] 7.5 Include optional public-safe `source_term`.
  - [ ] 7.6 Include optional public-safe `reading`.
  - [ ] 7.7 Include optional public-safe `term_type`.
  - [ ] 7.8 Include optional public-safe `short_definition`.
  - [ ] 7.9 Include bounded public-safe `aliases`.
  - [ ] 7.10 Include `match_terms` derived from display term, approved translation, and public-safe aliases.
  - [ ] 7.11 Ensure internal notes are never copied into public fields.

- [ ] 8. Add Annotation Limits and Settings
  - [ ] 8.1 Add max glossary terms per chapter setting.
  - [ ] 8.2 Add max aliases per term setting.
  - [ ] 8.3 Add max matches per term setting.
  - [ ] 8.4 Add max total matches per chapter setting.
  - [ ] 8.5 Add max public definition length setting.
  - [ ] 8.6 Add optional cache enable setting if cache is implemented.
  - [ ] 8.7 Use conservative default limits.
  - [ ] 8.8 Ensure limit behavior truncates safely.

- [ ] 9. Implement `PublicGlossaryAnnotationService`
  - [ ] 9.1 Add `PublicGlossaryAnnotationService` or equivalent helper.
  - [ ] 9.2 Keep service independent of HTTP/router concerns.
  - [ ] 9.3 Load public-safe glossary terms.
  - [ ] 9.4 Prefer matching against `reader_blocks`.
  - [ ] 9.5 Fall back to translated text only when reader blocks are unavailable and frontend can render safely.
  - [ ] 9.6 Match translated/display terms.
  - [ ] 9.7 Match approved translations.
  - [ ] 9.8 Match public-safe aliases.
  - [ ] 9.9 Return annotations grouped by glossary term.
  - [ ] 9.10 Return only matched terms for inline annotation mode.
  - [ ] 9.11 Do not mutate translated text.
  - [ ] 9.12 Do not call an LLM.

- [ ] 10. Implement Deterministic Matching
  - [ ] 10.1 Use case-insensitive matching for Latin-script terms.
  - [ ] 10.2 Use word-boundary-aware matching for Latin-script terms where practical.
  - [ ] 10.3 Avoid substring false positives inside unrelated words.
  - [ ] 10.4 Use exact substring matching for non-Latin scripts where word boundaries are unreliable.
  - [ ] 10.5 Sort longer match terms before shorter terms.
  - [ ] 10.6 Resolve overlapping matches deterministically.
  - [ ] 10.7 Keep longest overlapping match.
  - [ ] 10.8 If lengths tie, keep earliest match.
  - [ ] 10.9 If still tied, use stable glossary term order.
  - [ ] 10.10 Ensure final match list contains no nested or overlapping highlight spans.
  - [ ] 10.11 Enforce max term count.
  - [ ] 10.12 Enforce max alias count.
  - [ ] 10.13 Enforce max matches per term.
  - [ ] 10.14 Enforce max total matches.
  - [ ] 10.15 Truncate public definitions safely.

- [ ] 11. Integrate Backend Public Chapter Response
  - [ ] 11.1 Integrate annotations after translated text and reader blocks are loaded.
  - [ ] 11.2 Preserve existing public reader availability behavior.
  - [ ] 11.3 Preserve existing active translated version selection.
  - [ ] 11.4 Preserve existing reader block generation.
  - [ ] 11.5 Check global annotation setting.
  - [ ] 11.6 Check per-novel annotation setting where implemented.
  - [ ] 11.7 Check request-level opt-in where implemented.
  - [ ] 11.8 Call annotation service only when enabled and chapter is publicly readable.
  - [ ] 11.9 Return `glossary_annotations` when enabled according to selected API style.
  - [ ] 11.10 Return empty annotations for chapter shell/unavailable responses.
  - [ ] 11.11 Return empty annotations when no public-safe terms match.
  - [ ] 11.12 Do not expose annotations for unpublished novels.
  - [ ] 11.13 Do not expose annotations for unpublished or inaccessible chapters.
  - [ ] 11.14 Ensure annotation generation failure does not break public chapter loading unless existing API policy requires hard failure.

- [ ] 12. Add Optional Annotation Cache
  - [ ] 12.1 Decide whether bounded matching is enough for initial implementation.
  - [ ] 12.2 If caching is skipped, document that matching is bounded and deterministic.
  - [ ] 12.3 If caching is implemented, key by novel ID.
  - [ ] 12.4 If caching is implemented, key by chapter ID.
  - [ ] 12.5 If caching is implemented, key by active translated version ID.
  - [ ] 12.6 If caching is implemented, key by glossary revision or public glossary hash.
  - [ ] 12.7 If caching is implemented, key by annotation setting state.
  - [ ] 12.8 If caching is implemented, key by reader block rendering version where applicable.
  - [ ] 12.9 Invalidate or vary cache when active translated version changes.
  - [ ] 12.10 Invalidate or vary cache when public glossary visibility changes.
  - [ ] 12.11 Invalidate or vary cache when public glossary revision/hash changes.
  - [ ] 12.12 Ensure cache stores only public-safe annotation payloads.

- [ ] 13. Implement Frontend Annotation Rendering
  - [ ] 13.1 Render annotations from block-level matches.
  - [ ] 13.2 Preserve original visible text.
  - [ ] 13.3 Preserve paragraph and block structure.
  - [ ] 13.4 Wrap matched text with semantic element such as `button`, `span`, or `mark`.
  - [ ] 13.5 Avoid nested highlights.
  - [ ] 13.6 Avoid overlapping highlights.
  - [ ] 13.7 Render empty annotation payloads gracefully.
  - [ ] 13.8 Do not mutate stored text.
  - [ ] 13.9 Do not mutate cached reader text.
  - [ ] 13.10 Keep styling visually clear but non-disruptive.

- [ ] 14. Add Accessible Annotation Interactions
  - [ ] 14.1 Show tooltip/popover on hover where appropriate.
  - [ ] 14.2 Show tooltip/popover on keyboard focus.
  - [ ] 14.3 Open popover or sheet on mobile tap.
  - [ ] 14.4 Close tooltip/popover with Escape where supported.
  - [ ] 14.5 Close tooltip/popover on outside click or equivalent interaction.
  - [ ] 14.6 Ensure keyboard navigation can reach annotated terms.
  - [ ] 14.7 Add screen reader label identifying glossary notes.
  - [ ] 14.8 Render missing definitions gracefully.
  - [ ] 14.9 Ensure annotation UI does not block normal reading when disabled.

- [ ] 15. Add Reader Toggle
  - [ ] 15.1 Add reader control labeled `Glossary notes` or equivalent.
  - [ ] 15.2 Toggle annotations off without changing chapter text.
  - [ ] 15.3 Toggle annotations back on without reloading when possible.
  - [ ] 15.4 Store preference locally if existing reader settings already support local storage.
  - [ ] 15.5 Hide, disable, or explain the toggle when annotations are unavailable.
  - [ ] 15.6 Ensure reader remains usable when annotations are disabled.

- [ ] 16. Security and Privacy Review
  - [ ] 16.1 Confirm public annotations follow the same publication checks as public chapter API.
  - [ ] 16.2 Confirm unpublished novels cannot expose annotations.
  - [ ] 16.3 Confirm unpublished chapters cannot expose annotations.
  - [ ] 16.4 Confirm rejected terms are not exposed.
  - [ ] 16.5 Confirm pending terms are not exposed.
  - [ ] 16.6 Confirm internal/admin-only terms are not exposed.
  - [ ] 16.7 Confirm glossary review notes are not exposed.
  - [ ] 16.8 Confirm glossary status history is not exposed.
  - [ ] 16.9 Confirm prompt injection diagnostics are not exposed.
  - [ ] 16.10 Confirm glossary diagnostics admin metadata is not exposed.
  - [ ] 16.11 Confirm editor QA diagnostics are not exposed.
  - [ ] 16.12 Confirm internal confidence scores are not exposed unless explicitly public-safe.
  - [ ] 16.13 Confirm provider, scheduler, storage, and export metadata are not exposed.
  - [ ] 16.14 Confirm public annotation payloads are bounded.

- [ ] 17. Add Backend Tests
  - [ ] 17.1 Test approved public-visible glossary term is exposed.
  - [ ] 17.2 Test approved non-public term is not exposed.
  - [ ] 17.3 Test pending term is not exposed.
  - [ ] 17.4 Test rejected term is not exposed.
  - [ ] 17.5 Test candidate term is not exposed.
  - [ ] 17.6 Test internal/admin-only term is not exposed.
  - [ ] 17.7 Test public display term is matched in reader block.
  - [ ] 17.8 Test approved translation is matched in reader block.
  - [ ] 17.9 Test public-safe alias is matched.
  - [ ] 17.10 Test Latin substring false positive is avoided.
  - [ ] 17.11 Test overlapping matches resolve deterministically.
  - [ ] 17.12 Test longer overlapping match wins.
  - [ ] 17.13 Test max term limit is enforced.
  - [ ] 17.14 Test max alias limit is enforced.
  - [ ] 17.15 Test max matches per term is enforced.
  - [ ] 17.16 Test max total matches is enforced.
  - [ ] 17.17 Test global disabled setting returns empty annotations.
  - [ ] 17.18 Test per-novel disabled setting returns empty annotations where implemented.
  - [ ] 17.19 Test request-level opt-in behavior where implemented.
  - [ ] 17.20 Test chapter shell response returns empty annotations.
  - [ ] 17.21 Test unpublished novel or chapter does not expose annotations.
  - [ ] 17.22 Test public reader response excludes glossary diagnostics.
  - [ ] 17.23 Test public reader response excludes editor QA metadata.
  - [ ] 17.24 Test public reader response excludes prompt metadata.
  - [ ] 17.25 Test public reader response excludes provider/scheduler/storage/export metadata.
  - [ ] 17.26 Test existing clients can ignore annotation fields.
  - [ ] 17.27 Test cache dimensions if annotation cache is implemented.

- [ ] 18. Add Frontend Tests
  - [ ] 18.1 Test annotations render without changing visible text.
  - [ ] 18.2 Test paragraph and block structure is preserved.
  - [ ] 18.3 Test tooltip/popover shows public definition.
  - [ ] 18.4 Test missing definition renders gracefully.
  - [ ] 18.5 Test toggle hides annotations.
  - [ ] 18.6 Test toggle restores annotations.
  - [ ] 18.7 Test annotations are not rendered when payload is empty.
  - [ ] 18.8 Test keyboard focus opens annotation UI.
  - [ ] 18.9 Test Escape closes annotation UI where supported.
  - [ ] 18.10 Test outside click closes annotation UI where supported.
  - [ ] 18.11 Test mobile popover or sheet behavior where frontend test setup supports it.
  - [ ] 18.12 Test overlapping highlight ranges are not rendered.
  - [ ] 18.13 Test public reader UI does not show admin diagnostics.
  - [ ] 18.14 Test reader remains usable when annotations are disabled.

- [ ] 19. Backward Compatibility Checks
  - [ ] 19.1 Confirm public chapter response changes are additive.
  - [ ] 19.2 Confirm clients ignoring `glossary_annotations` render as before.
  - [ ] 19.3 Confirm public reader availability behavior remains intact.
  - [ ] 19.4 Confirm active-version selection is unchanged.
  - [ ] 19.5 Confirm existing public chapter text is unchanged.
  - [ ] 19.6 Confirm translated text storage is not modified.
  - [ ] 19.7 Confirm glossary admin features are unchanged.
  - [ ] 19.8 Confirm glossary editor QA features are unchanged.
  - [ ] 19.9 Confirm glossary diagnostics admin surfacing remains admin-only.
  - [ ] 19.10 Confirm prompt-time glossary injection remains unchanged.

- [ ] 20. Documentation
  - [ ] 20.1 Document public annotation response contract.
  - [ ] 20.2 Document public-safe glossary selection rules.
  - [ ] 20.3 Document visibility/default exposure policy.
  - [ ] 20.4 Document matching behavior and limits.
  - [ ] 20.5 Document configuration settings.
  - [ ] 20.6 Document optional cache dimensions if implemented.
  - [ ] 20.7 Document frontend toggle behavior.
  - [ ] 20.8 Document privacy guarantees and excluded metadata.

- [ ] 21. Run Verification
  - [ ] 21.1 Run focused backend annotation tests.
  - [ ] 21.2 Run existing public reader backend tests.
  - [ ] 21.3 Run existing glossary repository/service tests.
  - [ ] 21.4 Run existing glossary diagnostics tests if present.
  - [ ] 21.5 Run existing editor QA tests if present.
  - [ ] 21.6 Run focused frontend annotation tests.
  - [ ] 21.7 Run existing public reader frontend tests.
  - [ ] 21.8 Run frontend lint/type/test commands if UI changed.
  - [ ] 21.9 Run `ruff check` on changed backend source and test files.
  - [ ] 21.10 Run configured backend type checker, such as `pyright` or `mypy`, if present.
  - [ ] 21.11 Fix test, lint, and type failures caused by this work.

- [ ] 22. Final Acceptance Review
  - [ ] 22.1 Verify public chapter response can include annotations when enabled.
  - [ ] 22.2 Verify only approved public-safe glossary entries are exposed.
  - [ ] 22.3 Verify pending, rejected, candidate, internal, admin-only, and unpublished glossary data are excluded.
  - [ ] 22.4 Verify matching finds translated/display terms.
  - [ ] 22.5 Verify matching avoids obvious substring false positives.
  - [ ] 22.6 Verify overlapping matches resolve deterministically.
  - [ ] 22.7 Verify annotation payloads are bounded.
  - [ ] 22.8 Verify reader rendering preserves original text and paragraph structure.
  - [ ] 22.9 Verify reader has show/hide glossary notes control.
  - [ ] 22.10 Verify public APIs do not expose glossary diagnostics, editor QA metadata, prompt details, or unpublished glossary data.
  - [ ] 22.11 Verify existing public reader behavior remains compatible when annotations are disabled or ignored.
  - [ ] 22.12 Verify focused backend and frontend tests pass.

## Requirement Coverage Matrix

| Requirement | Covered By Tasks |
|---|---|
| REQ-1 Select Only Public-Safe Glossary Terms | 1, 5, 6, 7, 16, 17, 22 |
| REQ-2 Avoid Public Leakage of Internal Glossary Data | 5, 7, 11, 16, 17, 22 |
| REQ-3 Support Optional Public Visibility Fields | 6, 17, 19, 20 |
| REQ-4 Compact Public Annotation Shape | 3, 7, 11, 17, 22 |
| REQ-5 Match Metadata for Rendering | 4, 9, 10, 13, 17, 18 |
| REQ-6 Match Terms in Public Translated Text | 9, 10, 17, 22 |
| REQ-7 Avoid False Positives and Overlaps | 10, 13, 17, 18, 22 |
| REQ-8 Bound Annotation Payloads and Matching Cost | 8, 10, 12, 16, 17, 22 |
| REQ-9 Annotation Configuration | 2, 8, 11, 12, 15, 17, 20 |
| REQ-10 Preserve Public Reader Availability Behavior | 1, 11, 17, 19, 22 |
| REQ-11 Optional Annotation Caching | 12, 17, 20 |
| REQ-12 Public Reader UI Rendering | 13, 18, 22 |
| REQ-13 Accessible Annotation Interactions | 14, 18, 22 |
| REQ-14 Reader Toggle | 15, 18, 22 |
| REQ-15 Backward Compatibility | 11, 19, 21, 22 |
| REQ-16 Security and Privacy | 5, 7, 11, 16, 17, 22 |
| REQ-17 Backend Tests | 17, 21 |
| REQ-18 Frontend Tests | 18, 21 |

## Definition of Done

- [ ] Public-safe glossary selection helper exists.
- [ ] Public visibility policy is conservative by default.
- [ ] Optional visibility fields or equivalent public-safe markers are supported.
- [ ] Public chapter response can include additive `glossary_annotations`.
- [ ] Annotation payload includes stable public-safe term data and block-level match offsets.
- [ ] Annotation matching searches translated reader text, not raw source text.
- [ ] Matching is deterministic, bounded, and avoids obvious substring false positives.
- [ ] Overlapping matches are resolved deterministically.
- [ ] Public reader availability and active-version selection remain unchanged.
- [ ] Frontend renders accessible highlights/tooltips/popovers without changing text.
- [ ] Reader has a show/hide glossary notes control.
- [ ] Public APIs do not expose admin-only glossary data, glossary diagnostics, editor QA metadata, prompt metadata, provider metadata, or unpublished glossary data.
- [ ] Existing public reader clients remain compatible.
- [ ] Backend and frontend tests pass.