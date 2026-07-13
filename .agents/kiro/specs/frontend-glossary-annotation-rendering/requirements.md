# requirements.md

# Requirements: Frontend Glossary Annotation Rendering

## Introduction

The public reader frontend needs to render glossary annotations returned by the public chapter API. It must highlight matched terms, show safe glossary definitions, support text and block rendering modes, remain accessible, and avoid unsafe HTML injection.

## Requirement 1: Annotation response compatibility

### User story

As a reader, I want chapters to render normally whether or not glossary annotations are present.

### Acceptance criteria

1. WHEN `glossary_annotations` is missing THEN the reader SHALL render the chapter normally.
2. WHEN `glossary_annotations` is an empty list THEN the reader SHALL render the chapter normally.
3. WHEN `glossary_annotations` contains valid annotations THEN the reader SHALL render highlights for supported annotations.
4. WHEN an annotation has unsupported or missing optional fields THEN the reader SHALL skip or degrade gracefully.
5. WHEN old public chapter responses do not include annotation fields THEN the frontend SHALL not crash.
6. WHEN annotation rendering fails for one annotation THEN the rest of the reader content SHALL remain visible.
7. WHEN the public chapter API response shape changes only additively THEN existing reader behavior SHALL remain compatible.

## Requirement 2: Text-mode highlight rendering

### User story

As a reader, I want matched glossary terms highlighted in plain text chapters.

### Acceptance criteria

1. WHEN the reader renders plain `text` and valid text-offset annotations exist THEN the matching spans SHALL be highlighted.
2. WHEN text-mode annotations are rendered THEN offsets SHALL be interpreted relative to the returned text.
3. WHEN text before an annotation exists THEN it SHALL render normally.
4. WHEN text after an annotation exists THEN it SHALL render normally.
5. WHEN annotation offsets are outside the text bounds THEN the annotation SHALL be skipped.
6. WHEN annotation start offset is greater than or equal to end offset THEN the annotation SHALL be skipped.
7. WHEN `match_text` does not match the offset span and strict validation is enabled THEN the annotation SHOULD be skipped.
8. WHEN no valid annotations remain THEN the reader SHALL render normal text.

## Requirement 3: Reader-block highlight rendering

### User story

As a reader, I want glossary terms highlighted correctly in block-based chapter rendering.

### Acceptance criteria

1. WHEN the reader renders `reader_blocks` and valid block annotations exist THEN matching spans SHALL be highlighted inside the correct block.
2. WHEN annotations include `block_id` THEN the frontend SHALL use it to match annotations to blocks where possible.
3. WHEN annotations do not include `block_id` but include `block_index` THEN the frontend SHALL use block index.
4. WHEN annotation block reference does not match any rendered block THEN the annotation SHALL be skipped.
5. WHEN annotation offsets are outside the block text bounds THEN the annotation SHALL be skipped.
6. WHEN a block has no text field or unsupported block type THEN annotations for that block SHALL be skipped.
7. WHEN block rendering has existing layout behavior THEN annotation rendering SHALL preserve it.
8. WHEN no valid annotations exist for a block THEN the block SHALL render normally.

## Requirement 4: Annotation ordering and overlap handling

### User story

As a maintainer, I want deterministic annotation rendering so highlights do not shift unpredictably.

### Acceptance criteria

1. WHEN annotations are rendered THEN they SHALL be sorted deterministically.
2. WHEN annotations have offsets THEN they SHALL be sorted by start offset ascending.
3. WHEN multiple annotations start at the same offset THEN the longer match SHOULD be preferred.
4. WHEN annotations overlap and nested rendering is not supported THEN the frontend SHALL skip later overlapping annotations.
5. WHEN invalid annotations are skipped THEN valid annotations SHALL still render.
6. WHEN the same annotation appears multiple times with the same span THEN duplicates SHOULD be deduplicated.
7. WHEN annotation order from backend differs between requests THEN frontend output SHOULD remain deterministic for equivalent data.

## Requirement 5: Tooltip or popover display

### User story

As a reader, I want to see the meaning of highlighted glossary terms.

### Acceptance criteria

1. WHEN a reader hovers, focuses, or taps a highlighted term THEN the UI SHALL show a tooltip, popover, or equivalent detail surface.
2. WHEN tooltip content is shown THEN it SHALL include the display term.
3. WHEN a public definition is available THEN tooltip content SHALL include the definition.
4. WHEN a public source term is available and intended for display THEN tooltip content MAY include it.
5. WHEN definition is missing THEN tooltip content SHALL still show the display term.
6. WHEN tooltip closes THEN reader content SHALL remain unchanged.
7. WHEN multiple highlights exist THEN opening one tooltip SHALL not corrupt another highlight.
8. WHEN tooltip rendering fails THEN reader text SHALL remain visible.

## Requirement 6: User preference toggle

### User story

As a reader, I want to turn glossary highlights on or off so I can control reading distraction.

### Acceptance criteria

1. WHEN a reader opens reader settings THEN a glossary highlights toggle SHOULD be available.
2. WHEN glossary highlights are enabled THEN valid annotations SHALL be rendered.
3. WHEN glossary highlights are disabled THEN reader text SHALL render without annotation highlights.
4. WHEN the preference is changed THEN the change SHALL apply without requiring a page reload where practical.
5. WHEN the preference is saved THEN it SHALL persist locally or through the existing reader preference store.
6. WHEN no saved preference exists THEN annotations SHALL default to enabled unless product policy says otherwise.
7. WHEN annotations are disabled THEN tooltip/popover behavior SHALL also be disabled.
8. WHEN preference storage fails THEN the current session SHOULD still respect the toggle where practical.

## Requirement 7: Accessibility

### User story

As a reader using keyboard or assistive technology, I want glossary annotations to be accessible.

### Acceptance criteria

1. WHEN a glossary highlight is interactive THEN it SHALL be keyboard focusable.
2. WHEN a highlight receives keyboard focus THEN the tooltip/popover SHALL be available.
3. WHEN a tooltip/popover is open THEN it SHALL have an accessible label or description.
4. WHEN a tooltip/popover is open THEN Escape SHOULD close it where supported.
5. WHEN focus indicators are shown THEN they SHALL be visible.
6. WHEN a screen reader encounters a highlighted term THEN it SHOULD be able to access the term and definition.
7. WHEN annotations are disabled THEN the reader SHALL remain accessible.
8. WHEN mobile/touch interaction is used THEN tap targets SHALL be reasonably usable.

## Requirement 8: Security and HTML safety

### User story

As an operator, I want annotation rendering to be safe so glossary content cannot inject scripts or unsafe HTML.

### Acceptance criteria

1. WHEN annotation text is rendered THEN it SHALL be escaped by the framework or renderer.
2. WHEN annotation definitions are rendered THEN they SHALL be escaped or sanitized.
3. WHEN annotation fields contain HTML tags THEN those tags SHALL not execute as HTML.
4. WHEN annotation fields contain scripts or event handlers THEN they SHALL not execute.
5. WHEN annotation fields contain URLs THEN URLs SHALL not be rendered as clickable links unless explicitly sanitized and supported.
6. WHEN rendering annotation content THEN the frontend SHALL NOT use unsafe raw HTML injection.
7. WHEN tests include malicious annotation content THEN the UI SHALL display safe text or omit unsafe content.
8. WHEN analytics/logging exists THEN annotation text/definition SHALL not be sent as analytics payload unless separately approved.

## Requirement 9: Theme and layout compatibility

### User story

As a reader, I want glossary highlights to work with existing reader themes and layout.

### Acceptance criteria

1. WHEN the reader is in light theme THEN highlights SHALL remain readable.
2. WHEN the reader is in dark theme THEN highlights SHALL remain readable.
3. WHEN the reader has custom font size or line height THEN highlights SHALL not break layout.
4. WHEN the reader uses paragraph/block spacing THEN highlights SHALL preserve spacing.
5. WHEN the reader uses mobile layout THEN highlights SHALL remain tappable and not overflow.
6. WHEN the reader uses selectable text behavior THEN highlights SHOULD preserve text selection where practical.
7. WHEN annotations are disabled THEN layout SHALL match the existing non-annotation reader as closely as possible.

## Requirement 10: Performance

### User story

As a reader, I want annotated chapters to remain fast and smooth.

### Acceptance criteria

1. WHEN a chapter has annotations THEN rendering SHALL avoid obviously quadratic processing for normal chapter sizes.
2. WHEN reader blocks exist THEN annotations SHALL be grouped by block before rendering.
3. WHEN annotation input has many entries THEN invalid entries SHALL be filtered efficiently.
4. WHEN the same chapter and annotations are rendered repeatedly THEN processed segments SHOULD be memoized where practical.
5. WHEN annotation count exceeds frontend-safe limits THEN the frontend SHALL degrade gracefully.
6. WHEN tooltip components are used THEN they SHOULD not create excessive DOM or event listeners where avoidable.
7. WHEN annotations are disabled THEN annotation segmentation work SHOULD be skipped where practical.

## Requirement 11: Error handling

### User story

As a reader, I want the chapter to remain readable even if annotation data is malformed.

### Acceptance criteria

1. WHEN annotation data is malformed THEN the reader SHALL skip invalid annotations.
2. WHEN annotation offsets are invalid THEN the reader SHALL skip those annotations.
3. WHEN annotation block references are invalid THEN the reader SHALL skip those annotations.
4. WHEN annotation tooltip content is missing THEN the reader SHALL show fallback content or no tooltip.
5. WHEN annotation processing throws unexpectedly THEN the reader SHALL fall back to unannotated content where practical.
6. WHEN annotation rendering errors occur THEN user-facing errors SHALL be safe and minimal.
7. WHEN development logging is enabled THEN annotation errors MAY be logged without private content.

## Requirement 12: Test coverage

### User story

As a maintainer, I want frontend tests so annotation rendering does not regress.

### Acceptance criteria

1. WHEN tests run THEN they SHALL cover rendering without annotations.
2. WHEN tests run THEN they SHALL cover text-mode highlight rendering.
3. WHEN tests run THEN they SHALL cover reader-block highlight rendering.
4. WHEN tests run THEN they SHALL cover tooltip/popover display.
5. WHEN tests run THEN they SHALL cover missing definition fallback.
6. WHEN tests run THEN they SHALL cover user preference disabled state.
7. WHEN tests run THEN they SHALL cover invalid offset skipping.
8. WHEN tests run THEN they SHALL cover overlap handling.
9. WHEN tests run THEN they SHALL cover duplicate handling where implemented.
10. WHEN tests run THEN they SHALL cover HTML/script escaping.
11. WHEN tests run THEN they SHALL cover keyboard focus behavior.
12. WHEN tests run THEN they SHOULD cover theme/layout compatibility where practical.
13. WHEN tests run THEN they SHALL cover malformed annotation resilience.

## Requirement 13: Completion verification

### User story

As a maintainer, I want a clear verification path so annotation rendering is complete only when highlights and tooltips work safely.

### Acceptance criteria

1. WHEN a public chapter includes valid annotations THEN highlighted terms SHALL appear in the reader.
2. WHEN a highlighted term is opened THEN the tooltip/popover SHALL show the display term and definition.
3. WHEN a chapter has no annotations THEN reader rendering SHALL be unchanged.
4. WHEN annotations are disabled in reader settings THEN highlights SHALL disappear.
5. WHEN malformed annotations are returned THEN the chapter SHALL remain readable.
6. WHEN malicious annotation content is returned in a test fixture THEN it SHALL not execute as HTML or script.
7. WHEN reader blocks are used THEN block-relative highlights SHALL appear in the correct block.
8. WHEN keyboard navigation is used THEN highlights SHALL be reachable and usable.
