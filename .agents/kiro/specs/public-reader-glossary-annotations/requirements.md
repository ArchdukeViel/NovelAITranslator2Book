# Requirements: Public Reader Glossary Annotations

## Introduction

The glossary system is already useful for translation quality and editor workflows, but public readers currently receive only translated chapter content. Some glossary terms, names, skills, places, honorifics, and culturally specific concepts may benefit from optional reader-facing annotations. This spec adds safe public glossary annotations to the reader experience without changing translated text, exposing admin diagnostics, or making unpublished glossary data public.

The feature is additive: public chapter responses may include annotation metadata, and the frontend may render term highlights/tooltips when enabled.

## Requirements

### REQ-1: Public-Safe Glossary Term Selection

Only glossary entries explicitly safe for public display may be exposed.

- REQ-1.1: Public annotations must use approved glossary entries only.
- REQ-1.2: Candidate, rejected, internal, pending, or admin-only entries must not be exposed.
- REQ-1.3: Entries must support a public visibility flag or equivalent policy.
- REQ-1.4: If no public visibility flag exists, default behavior must be conservative: do not expose terms unless they are approved and explicitly allowed by configuration.
- REQ-1.5: Public annotations must not expose glossary diagnostics, conflict warnings, editor QA notes, or prompt metadata.

### REQ-2: Public Annotation Data Shape

The public reader API must expose a compact annotation shape.

- REQ-2.1: Chapter response may include `glossary_annotations: []`.
- REQ-2.2: Each annotation must include a stable `term_id`.
- REQ-2.3: Each annotation must include `source_term` when safe.
- REQ-2.4: Each annotation must include `translation` or `display_term`.
- REQ-2.5: Each annotation may include `reading`, `term_type`, `short_definition`, and `aliases` when public-safe.
- REQ-2.6: Each annotation must include matched surface forms found in the rendered chapter text.
- REQ-2.7: Annotation payloads must be bounded to avoid oversized reader responses.
- REQ-2.8: Response changes must be additive.

### REQ-3: Matching Terms in Public Chapter Text

The backend or frontend must identify glossary terms present in public chapter text.

- REQ-3.1: Matching must search translated chapter text, not raw source text, for public reader annotation rendering.
- REQ-3.2: Matching must support approved English translations.
- REQ-3.3: Matching may support aliases if aliases are public-safe.
- REQ-3.4: Matching must avoid substring false positives inside unrelated words.
- REQ-3.5: Matching must be case-insensitive for Latin-script terms by default.
- REQ-3.6: Matching must preserve translated text unchanged.
- REQ-3.7: If reader content is split into `reader_blocks`, matching must work at block level or provide enough data for frontend rendering.

### REQ-4: Reader Rendering

The public reader frontend must render annotations without breaking readability.

- REQ-4.1: Annotated terms must be visually distinguishable but not disruptive.
- REQ-4.2: Annotation UI must show short public-safe details on hover, focus, tap, or equivalent accessible interaction.
- REQ-4.3: Rendering must preserve original text content and paragraph structure.
- REQ-4.4: Rendering must avoid nested or overlapping highlights.
- REQ-4.5: Rendering must work on mobile and desktop.
- REQ-4.6: Annotation controls must be keyboard accessible.
- REQ-4.7: Reader must remain usable when annotations are disabled or unavailable.

### REQ-5: Reader Controls and Configuration

Annotations must be optional.

- REQ-5.1: Add a public reader setting or frontend toggle to show/hide glossary annotations.
- REQ-5.2: The default may be enabled or disabled by deployment setting.
- REQ-5.3: The reader must remember user preference locally if existing frontend patterns support it.
- REQ-5.4: Backend must support disabling annotations globally.
- REQ-5.5: Per-novel metadata may override whether public glossary annotations are enabled.

### REQ-6: Security and Privacy

Public annotations must not leak internal workflow data.

- REQ-6.1: Do not expose glossary entry status history.
- REQ-6.2: Do not expose reviewer notes.
- REQ-6.3: Do not expose prompt injection diagnostics.
- REQ-6.4: Do not expose editor QA diagnostics.
- REQ-6.5: Do not expose internal confidence scores unless explicitly marked public-safe.
- REQ-6.6: Do not expose unpublished novels or unpublished chapters through annotation endpoints.
- REQ-6.7: Public annotation API must follow the same publication checks as public chapter API.

### REQ-7: Performance and Caching

Annotations must not significantly slow public reader responses.

- REQ-7.1: Annotation generation must be bounded by max terms per chapter.
- REQ-7.2: Annotation matching should use efficient lookup/matching, not repeated DB scans per paragraph.
- REQ-7.3: Public chapter responses may cache annotation results by novel ID, chapter ID, active version ID, and glossary revision.
- REQ-7.4: Cache must invalidate or vary when active translation version changes.
- REQ-7.5: Cache must invalidate or vary when public glossary revision changes.
- REQ-7.6: If caching is not implemented initially, matching must still be bounded and tested.

### REQ-8: Backward Compatibility

Existing reader clients must continue to work.

- REQ-8.1: Public chapter response fields must remain unchanged except additive annotation fields.
- REQ-8.2: Clients that ignore `glossary_annotations` must render as before.
- REQ-8.3: Existing public reader availability behavior must remain intact.
- REQ-8.4: Existing glossary admin/editor features must remain unchanged.
- REQ-8.5: Existing translated text storage must not be modified for annotation rendering.

### REQ-9: Tests

Focused tests must cover backend annotation selection, public safety, matching, and rendering.

- REQ-9.1: Test approved public glossary terms are exposed.
- REQ-9.2: Test pending/rejected/internal terms are not exposed.
- REQ-9.3: Test matching finds approved translation in chapter text.
- REQ-9.4: Test matching avoids substring false positives.
- REQ-9.5: Test public chapter response includes `glossary_annotations` when enabled.
- REQ-9.6: Test public chapter response omits or returns empty annotations when disabled.
- REQ-9.7: Test public reader does not expose admin diagnostics.
- REQ-9.8: Test annotation rendering preserves text and paragraph structure.
- REQ-9.9: Test mobile/keyboard accessible annotation interaction if frontend test setup supports it.

## Non-Goals

- This spec does not change translation text.
- This spec does not add glossary-aware editor QA.
- This spec does not expose admin diagnostics publicly.
- This spec does not implement full public glossary browsing.
- This spec does not change public reader availability policy.
- This spec does not change machine translation prompt injection.

