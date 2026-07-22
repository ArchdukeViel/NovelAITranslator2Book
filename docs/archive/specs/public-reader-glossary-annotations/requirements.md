# Requirements: Public Reader Glossary Annotations

## Introduction

The glossary system improves translation quality, prompt consistency, and editor workflows, but public readers currently receive only translated chapter content. Some names, places, skills, titles, honorifics, cultural concepts, and recurring terminology may benefit from optional reader-facing annotations.

This spec adds public-safe glossary annotations to the public reader. The backend selects approved glossary entries that are explicitly safe for public display, matches their translated/display forms against public chapter text, and returns compact annotation metadata. The frontend may render highlights, tooltips, or popovers without changing stored translated text.

The feature is additive and privacy-conscious. It must not expose admin diagnostics, prompt metadata, editor QA metadata, glossary review state, pending terms, rejected terms, internal notes, or unpublished glossary data.

## Scope

In scope:

- Public-safe glossary term selection.
- Optional public reader glossary annotation payloads.
- Deterministic matching against translated reader text.
- Block-level match offsets for frontend rendering.
- Public reader frontend highlights, tooltips/popovers, and toggle.
- Global and per-novel enable/disable configuration.
- Bounded annotation payloads and matching cost.
- Backend and frontend tests for public safety, matching, rendering, and compatibility.

Out of scope:

- Changing translated chapter text.
- Re-running translation.
- Changing prompt-time glossary injection.
- Changing glossary admin review workflows.
- Changing glossary-aware editor QA.
- Exposing glossary diagnostics publicly.
- Exposing editor QA metadata publicly.
- Exposing prompt details publicly.
- Implementing full public glossary browsing.
- Changing public reader availability policy.
- Changing active-version selection.
- Adding LLM-based annotation detection.

## Requirements

### REQ-1: Select Only Public-Safe Glossary Terms

Only glossary entries explicitly safe for public display may be exposed in public reader responses.

- REQ-1.1: Public annotations must use approved glossary entries only.
- REQ-1.2: Candidate entries must not be exposed.
- REQ-1.3: Pending entries must not be exposed.
- REQ-1.4: Rejected entries must not be exposed.
- REQ-1.5: Disabled, archived, or inactive entries must not be exposed.
- REQ-1.6: Internal or admin-only entries must not be exposed.
- REQ-1.7: Entries must support a public visibility flag or an equivalent explicit public-safe policy.
- REQ-1.8: If no public visibility flag exists, default behavior must be conservative.
- REQ-1.9: Conservative fallback must not expose all approved terms by default.
- REQ-1.10: Conservative fallback may expose terms only when a global setting, novel setting, and explicit public-safe marker all allow exposure.
- REQ-1.11: Public selection may include inherited/global glossary entries only if existing glossary repository behavior already supports inherited/global entries.
- REQ-1.12: Public selection must respect the same novel and chapter publication checks as the public reader endpoint.

### REQ-2: Avoid Public Leakage of Internal Glossary Data

Public annotation payloads must not reveal internal workflow or admin-only data.

- REQ-2.1: Public annotations must not expose glossary diagnostics.
- REQ-2.2: Public annotations must not expose prompt diagnostics.
- REQ-2.3: Public annotations must not expose prompt blocks.
- REQ-2.4: Public annotations must not expose editor QA metadata.
- REQ-2.5: Public annotations must not expose glossary conflict warnings.
- REQ-2.6: Public annotations must not expose glossary review notes.
- REQ-2.7: Public annotations must not expose glossary decision history.
- REQ-2.8: Public annotations must not expose internal aliases.
- REQ-2.9: Public annotations must not expose internal definitions.
- REQ-2.10: Public annotations must not expose provider/model metadata.
- REQ-2.11: Public annotations must not expose confidence scores unless explicitly marked public-safe.
- REQ-2.12: Public annotations should avoid exposing raw internal database IDs when an opaque public-safe ID can be used.

### REQ-3: Support Optional Public Visibility Fields

The glossary model may add explicit public-facing fields if existing metadata is insufficient.

- REQ-3.1: The implementation may add `public_visible`.
- REQ-3.2: The implementation may add `public_definition`.
- REQ-3.3: The implementation may add `public_display_term`.
- REQ-3.4: If `public_visible` is added, the default migration value must be `false`.
- REQ-3.5: `public_definition` must be separate from internal reviewer notes.
- REQ-3.6: `public_display_term` must be separate from internal-only glossary text when needed.
- REQ-3.7: If no migration is added, existing metadata/tags may be reused only when they clearly mark public-safe exposure.
- REQ-3.8: Existing glossary admin/editor workflows must remain compatible.

### REQ-4: Expose a Compact Public Annotation Shape

The public chapter API must expose annotations using a compact additive shape.

- REQ-4.1: Public chapter responses may include `glossary_annotations`.
- REQ-4.2: When annotations are unavailable or disabled, the field may be omitted or returned as an empty list according to existing API style.
- REQ-4.3: Each annotation must include stable `term_id`.
- REQ-4.4: `term_id` must be non-sensitive and public-safe.
- REQ-4.5: Each annotation must include `display_term` or `translation`.
- REQ-4.6: Each annotation may include `source_term` only when public-safe.
- REQ-4.7: Each annotation may include `reading` only when public-safe.
- REQ-4.8: Each annotation may include `term_type` only when public-safe.
- REQ-4.9: Each annotation may include `short_definition` only when public-safe.
- REQ-4.10: Each annotation may include `aliases` only when public-safe.
- REQ-4.11: Each annotation must include `matches` for inline annotation mode.
- REQ-4.12: Initial inline implementation should return only terms with at least one match.
- REQ-4.13: Future glossary sidebar mode may allow terms with empty `matches`, but that is not required here.
- REQ-4.14: Response changes must be additive.

### REQ-5: Include Match Metadata for Rendering

Annotation matches must provide enough data for frontend rendering without changing text.

- REQ-5.1: Each match must include the matched `surface` text.
- REQ-5.2: Each match must include `block_index` when reader blocks are available.
- REQ-5.3: Each match must include `start` offset in the block text.
- REQ-5.4: Each match must include `end` offset in the block text.
- REQ-5.5: Offsets must refer to the public rendered block text, not raw source text.
- REQ-5.6: Match offsets must not require the frontend to modify stored translated text.
- REQ-5.7: When reader blocks are unavailable, the backend may fall back to translated text matching only if the frontend can still render safely.
- REQ-5.8: Matching against raw source text must not be used for public reader annotation placement.

### REQ-6: Match Terms in Public Translated Chapter Text

The annotation service must detect public glossary terms in translated reader text.

- REQ-6.1: Matching must search translated chapter text or reader blocks.
- REQ-6.2: Matching must support approved English translations.
- REQ-6.3: Matching must support `display_term`.
- REQ-6.4: Matching may support public-safe aliases.
- REQ-6.5: Matching must be deterministic.
- REQ-6.6: Matching must not call an LLM.
- REQ-6.7: Matching must preserve translated text unchanged.
- REQ-6.8: Matching should prefer reader block text when available.
- REQ-6.9: Matching must return only matched public-safe terms for inline annotation mode.

### REQ-7: Avoid False Positives and Overlaps

Matching must avoid obvious bad highlights.

- REQ-7.1: Matching must be case-insensitive for Latin-script terms by default.
- REQ-7.2: Matching must use word boundaries for Latin-script terms where practical.
- REQ-7.3: Matching must avoid substring false positives inside unrelated words.
- REQ-7.4: Matching may use exact substring matching for non-Latin scripts where word boundaries are unreliable.
- REQ-7.5: Matching should sort longer terms before shorter terms.
- REQ-7.6: Matching must resolve overlapping matches deterministically.
- REQ-7.7: For overlapping matches, the longest match should win.
- REQ-7.8: If overlapping matches have equal length, the earliest match should win.
- REQ-7.9: If overlap order is still tied, stable glossary term order should decide.
- REQ-7.10: The final match list must not contain nested or overlapping highlights for the same text span.

### REQ-8: Bound Annotation Payloads and Matching Cost

Annotation generation must remain safe for public reader response size and latency.

- REQ-8.1: Annotation generation must enforce a maximum number of glossary terms per chapter.
- REQ-8.2: Annotation generation must enforce a maximum number of aliases per term.
- REQ-8.3: Annotation generation must enforce a maximum number of matches per term.
- REQ-8.4: Annotation generation must enforce a maximum total number of matches per chapter.
- REQ-8.5: Annotation generation must enforce a maximum public definition length.
- REQ-8.6: Annotation generation must avoid repeated database scans per paragraph.
- REQ-8.7: Annotation generation must use bounded deterministic matching when caching is not implemented.
- REQ-8.8: When limits are reached, the service must truncate safely rather than returning oversized payloads.
- REQ-8.9: Limit behavior must be covered by tests.

### REQ-9: Add Annotation Configuration

Annotations must be optional and configurable.

- REQ-9.1: Backend must support disabling public reader glossary annotations globally.
- REQ-9.2: Backend may support enabling/disabling annotations per novel.
- REQ-9.3: Backend may support request-level opt-in, such as `include_glossary_annotations=true`.
- REQ-9.4: If request-level opt-in is used, default public chapter behavior may remain unchanged unless the parameter is present.
- REQ-9.5: If always returning the additive field, disabled annotations must return an empty list.
- REQ-9.6: Deployment default should be conservative until public-safe glossary curation is ready.
- REQ-9.7: Recommended first rollout default is disabled unless product policy explicitly enables it.
- REQ-9.8: Per-novel setting must not bypass public-safe glossary filtering.

### REQ-10: Preserve Public Reader Availability Behavior

Annotations must integrate with the public reader without changing availability semantics.

- REQ-10.1: Existing public reader availability behavior must remain unchanged.
- REQ-10.2: Existing active translated version selection must remain unchanged.
- REQ-10.3: Existing reader block generation must remain unchanged.
- REQ-10.4: Existing public chapter response fields must remain compatible.
- REQ-10.5: Untranslated chapter shell responses must return empty annotations or omit the annotation field according to existing API style.
- REQ-10.6: Annotations must not expose data for unpublished novels.
- REQ-10.7: Annotations must not expose data for unpublished or inaccessible chapters.
- REQ-10.8: Annotation generation failure must not break public chapter loading unless existing API policy requires hard failure.

### REQ-11: Support Optional Annotation Caching

Annotation caching may be added, but correctness and privacy must be preserved.

- REQ-11.1: Cache may key by novel ID.
- REQ-11.2: Cache may key by chapter ID.
- REQ-11.3: Cache must key by active translated version ID.
- REQ-11.4: Cache must key by glossary revision or public glossary hash.
- REQ-11.5: Cache should key by annotation setting state.
- REQ-11.6: Cache should key by reader block rendering version when applicable.
- REQ-11.7: Cache must vary or invalidate when active translated version changes.
- REQ-11.8: Cache must vary or invalidate when public glossary visibility changes.
- REQ-11.9: Cache must vary or invalidate when public glossary revision/hash changes.
- REQ-11.10: Cache must store only public-safe annotation payloads.
- REQ-11.11: If caching is not implemented initially, matching must still be bounded and tested.

### REQ-12: Render Annotations in the Public Reader UI

The public reader frontend must render annotations without harming readability.

- REQ-12.1: Annotated terms must be visually distinguishable.
- REQ-12.2: Annotation styling must not be disruptive.
- REQ-12.3: Rendering must preserve original visible text.
- REQ-12.4: Rendering must preserve paragraph and block structure.
- REQ-12.5: Rendering must avoid nested highlights.
- REQ-12.6: Rendering must avoid overlapping highlights.
- REQ-12.7: Rendering must work on desktop.
- REQ-12.8: Rendering must work on mobile.
- REQ-12.9: Rendering must handle empty annotation payloads gracefully.
- REQ-12.10: Rendering must not mutate stored text or cached reader text.

### REQ-13: Provide Accessible Annotation Interactions

Annotation UI must be accessible by mouse, touch, and keyboard.

- REQ-13.1: Hover should show tooltip or popover on desktop where appropriate.
- REQ-13.2: Focus must show tooltip or popover.
- REQ-13.3: Tap must open popover or sheet on mobile.
- REQ-13.4: Escape should close tooltip/popover where applicable.
- REQ-13.5: Outside click or equivalent interaction should close tooltip/popover.
- REQ-13.6: Keyboard navigation must be able to reach annotated terms.
- REQ-13.7: Screen reader labels should identify annotations as glossary notes.
- REQ-13.8: Missing definitions must render gracefully.
- REQ-13.9: Annotation UI must not block normal reading when disabled.

### REQ-14: Add Reader Toggle

Readers must be able to show or hide glossary annotations.

- REQ-14.1: Add a reader control labeled clearly, such as `Glossary notes`.
- REQ-14.2: The toggle must hide annotations without changing chapter text.
- REQ-14.3: The toggle should restore annotations without reloading when possible.
- REQ-14.4: The reader should remember the user preference locally if existing reader settings already support local storage.
- REQ-14.5: If annotations are unavailable, the toggle should be hidden, disabled, or shown with a clear unavailable state.
- REQ-14.6: Reader remains usable when annotations are disabled.

### REQ-15: Preserve Backward Compatibility

Existing public reader clients and glossary workflows must continue to work.

- REQ-15.1: Public chapter response changes must be additive.
- REQ-15.2: Clients that ignore `glossary_annotations` must render as before.
- REQ-15.3: Existing public reader availability behavior must remain intact.
- REQ-15.4: Existing public chapter text must not change.
- REQ-15.5: Existing translated text storage must not be modified for annotation rendering.
- REQ-15.6: Existing glossary admin features must remain unchanged.
- REQ-15.7: Existing glossary editor QA features must remain unchanged.
- REQ-15.8: Existing glossary diagnostics admin surfacing must remain admin-only.
- REQ-15.9: Existing prompt-time glossary injection must remain unchanged.

### REQ-16: Security and Privacy

Public annotations must not leak private, unpublished, or admin-only data.

- REQ-16.1: Public annotations must follow the same publication checks as the public chapter API.
- REQ-16.2: Public annotations must not expose unpublished novels.
- REQ-16.3: Public annotations must not expose unpublished chapters.
- REQ-16.4: Public annotations must not expose rejected terms.
- REQ-16.5: Public annotations must not expose pending terms.
- REQ-16.6: Public annotations must not expose internal/admin-only terms.
- REQ-16.7: Public annotations must not expose glossary review notes.
- REQ-16.8: Public annotations must not expose glossary status history.
- REQ-16.9: Public annotations must not expose prompt injection diagnostics.
- REQ-16.10: Public annotations must not expose editor QA diagnostics.
- REQ-16.11: Public annotations must not expose internal confidence scores unless explicitly marked public-safe.
- REQ-16.12: Public annotations must not expose provider, scheduler, storage, or export metadata.

### REQ-17: Backend Tests

Focused backend tests must cover public-safe selection, matching, configuration, privacy, and compatibility.

- REQ-17.1: Test approved public-visible glossary term is exposed.
- REQ-17.2: Test approved non-public term is not exposed.
- REQ-17.3: Test pending term is not exposed.
- REQ-17.4: Test rejected term is not exposed.
- REQ-17.5: Test candidate term is not exposed.
- REQ-17.6: Test internal/admin-only term is not exposed.
- REQ-17.7: Test public display term is matched in reader block.
- REQ-17.8: Test approved translation is matched in reader block.
- REQ-17.9: Test public-safe alias is matched.
- REQ-17.10: Test Latin substring false positive is avoided.
- REQ-17.11: Test overlapping matches resolve deterministically.
- REQ-17.12: Test longer overlapping match wins.
- REQ-17.13: Test match limits are enforced.
- REQ-17.14: Test global disabled setting returns empty annotations.
- REQ-17.15: Test per-novel disabled setting returns empty annotations where implemented.
- REQ-17.16: Test chapter shell response returns empty annotations.
- REQ-17.17: Test unpublished novel or chapter does not expose annotations.
- REQ-17.18: Test public reader response excludes glossary diagnostics.
- REQ-17.19: Test public reader response excludes editor QA metadata.
- REQ-17.20: Test public reader response excludes prompt metadata.
- REQ-17.21: Test existing clients can ignore annotation fields.
- REQ-17.22: Test caching dimensions if annotation cache is implemented.

### REQ-18: Frontend Tests

Frontend tests must cover rendering, toggle behavior, accessibility, and layout.

- REQ-18.1: Test annotations render without changing visible text.
- REQ-18.2: Test paragraph and block structure is preserved.
- REQ-18.3: Test tooltip or popover shows public definition.
- REQ-18.4: Test missing definition renders gracefully.
- REQ-18.5: Test toggle hides annotations.
- REQ-18.6: Test toggle restores annotations.
- REQ-18.7: Test annotations are not rendered when payload is empty.
- REQ-18.8: Test keyboard focus opens annotation UI.
- REQ-18.9: Test Escape closes annotation UI where supported.
- REQ-18.10: Test mobile popover or sheet behavior where frontend test setup supports it.
- REQ-18.11: Test overlapping highlight ranges are not rendered.
- REQ-18.12: Test public reader UI does not show admin diagnostics.

## Non-Goals

- This spec does not change translated chapter text.
- This spec does not modify translated text storage.
- This spec does not re-run translation.
- This spec does not change machine translation prompt injection.
- This spec does not add glossary-aware editor QA.
- This spec does not expose admin diagnostics publicly.
- This spec does not expose editor QA metadata publicly.
- This spec does not expose prompt diagnostics publicly.
- This spec does not implement full public glossary browsing.
- This spec does not change public reader availability policy.
- This spec does not change active-version selection.
- This spec does not expose unpublished glossary data.
- This spec does not use LLM-based annotation detection.