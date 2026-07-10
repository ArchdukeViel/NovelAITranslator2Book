# design.md

# Design: Frontend Glossary Annotation Rendering

## Overview

`frontend-glossary-annotation-rendering` adds public reader UI rendering for glossary annotations returned by the public chapter API.

The backend wiring spec exposes `glossary_annotations` on public chapter responses. This spec uses that field to highlight matched terms in the reader and show safe glossary definitions in tooltips, popovers, or inline panels.

This is feature polish. It should not change backend matching rules, glossary visibility logic, or translation behavior.

## Goals

* Render glossary highlights in the public reader.
* Support annotations for plain `text` responses.
* Support annotations for `reader_blocks` responses.
* Show tooltip/popover content for glossary terms.
* Preserve reader readability and layout.
* Add local user preference to enable/disable annotations.
* Avoid breaking chapters that have no annotations.
* Avoid unsafe HTML injection.
* Add frontend tests for highlight rendering, offsets, tooltips, disabled state, and malformed annotations.

## Non-goals

* No backend annotation matching. That belongs to `public-reader-glossary-annotations-wiring`.
* No glossary editor changes.
* No public glossary API changes.
* No backend visibility changes.
* No glossary diagnostics pipeline changes.
* No annotation caching redesign.
* No mobile push/notification behavior.
* No admin glossary analytics.

## Input contract

The public chapter API should return:

```json id="6n7qv2"
{
  "text": "The Royal Capital was quiet.",
  "reader_blocks": [],
  "glossary_annotations": [
    {
      "term_id": "term_123",
      "display_term": "Royal Capital",
      "definition": "The capital city of the kingdom.",
      "match_text": "Royal Capital",
      "start_offset": 4,
      "end_offset": 17,
      "match_type": "exact"
    }
  ]
}
```

For block rendering:

```json id="2gyl3z"
{
  "reader_blocks": [
    {
      "id": "block_1",
      "type": "paragraph",
      "text": "The Royal Capital was quiet."
    }
  ],
  "glossary_annotations": [
    {
      "term_id": "term_123",
      "display_term": "Royal Capital",
      "definition": "The capital city of the kingdom.",
      "block_id": "block_1",
      "block_index": 0,
      "start_offset": 4,
      "end_offset": 17,
      "match_text": "Royal Capital",
      "match_type": "exact"
    }
  ]
}
```

The frontend should treat `glossary_annotations` as optional and default to `[]`.

## Rendering strategy

The frontend should split reader text into safe text spans and annotation spans.

For each annotation:

```text id="227x9y"
text before annotation
highlighted annotation text
text after annotation
```

Do not use raw HTML string interpolation.

Recommended component structure:

```text id="x88gmu"
ReaderPage
ReaderContent
ReaderBlock
AnnotatedText
GlossaryAnnotationHighlight
GlossaryTooltip
GlossaryAnnotationPreferenceToggle
```

## Text mode

When the chapter response uses a plain `text` field:

```text id="0yvymn"
1. Sort annotations by start_offset.
2. Validate offsets.
3. Remove or resolve invalid/overlapping annotations.
4. Split text into segments.
5. Render normal text segments as escaped text.
6. Render annotation segments as highlight components.
```

Offsets are relative to the returned text.

## Reader block mode

When the chapter response uses `reader_blocks`:

```text id="6e5pg5"
1. Group annotations by block_id where available.
2. Fall back to block_index if block_id is unavailable.
3. Validate annotation offsets against each block’s text.
4. Render each block using AnnotatedText.
5. Preserve existing block types and layout.
```

Annotations should not affect non-text blocks unless the block has a clear text field.

## Overlap handling

Backend should ideally resolve overlaps. The frontend still needs defensive handling.

Recommended policy:

```text id="efbyzf"
drop invalid annotations
sort by start offset
prefer longest annotation for same start
skip annotations that overlap an already accepted annotation
preserve deterministic output
```

Do not attempt complex nested highlights in V1.

## Tooltip/popover content

Tooltip should show safe public glossary content.

Recommended fields:

```text id="aoi0xm"
display term
definition
source term if provided and safe
match type if useful
```

Example:

```text id="0p65uh"
Royal Capital
The capital city of the kingdom.
```

Optional metadata:

```text id="59s4pc"
Matched from: 王都
```

Do not show:

```text id="w52n83"
internal notes
approval status
private glossary metadata
raw model diagnostics
raw prompt text
admin-only fields
```

## Interaction model

Recommended desktop behavior:

```text id="41trma"
hover highlight -> show tooltip
focus highlight -> show tooltip
click highlight -> pin/open popover if tooltip library supports it
Escape -> close tooltip/popover
```

Recommended mobile behavior:

```text id="7hgq4c"
tap highlight -> open popover/sheet
tap outside or close button -> close
```

Keyboard accessibility:

```text id="9vaogl"
highlights are focusable
tooltip content is reachable or announced
Escape closes open popover
tab order follows reading order
```

## User preference

Add a local reader preference:

```text id="i4rfhn"
showGlossaryAnnotations: true | false
```

Default:

```text id="2yul0p"
true
```

Storage:

```text id="e26mdh"
localStorage or existing reader preferences store
```

UI:

```text id="sgzclk"
Reader settings -> Glossary highlights -> On/Off
```

Preference should be client-side for this spec. Backend settings belong to a separate spec.

## Styling

Highlights should be visible but not disruptive.

Recommended states:

```text id="t0dmyo"
default highlight
hover/focus highlight
active/open highlight
disabled/no highlight
```

The implementation should respect existing reader themes:

```text id="ug2h7v"
light mode
dark mode
sepia or reader themes if available
high contrast preference if available
```

Avoid hardcoded colors if the project has design tokens.

## Performance

Rendering should be efficient for long chapters.

Recommended limits:

```text id="k6s1qg"
avoid O(n²) splitting
group annotations by block
memoize processed segments by text + annotations + preference
virtualized reader compatibility if existing
do not render tooltip components for every annotation if a shared tooltip system exists
```

If annotations are very large:

```text id="8bjujp"
cap rendered annotations at backend limit
drop invalid annotations
log safe client warning only in development
```

## Error handling

Expected behavior:

```text id="e7imlo"
missing glossary_annotations -> render normal reader
empty glossary_annotations -> render normal reader
invalid offsets -> skip invalid annotation
overlapping annotations -> deterministic skip/resolve
missing definition -> show display term only
tooltip error -> keep reader text visible
preference disabled -> render normal reader
```

Reader content must never disappear because annotation rendering fails.

## Security

All annotation content must be rendered safely.

Rules:

```text id="fnqtth"
do not use dangerouslySetInnerHTML for annotation text or definitions
escape all text
do not execute HTML from definition fields
sanitize URLs if any are ever added
do not expose private metadata
do not store annotation content in analytics
```

## Accessibility

Requirements:

```text id="4m5eij"
annotation highlights keyboard focusable
tooltip/popover has accessible label
focus indicator visible
screen readers can access term and definition
tap targets usable on mobile
reader remains usable with annotations disabled
```

Recommended ARIA:

```text id="io169t"
button or span with role/button only if interactive
aria-describedby for tooltip
aria-expanded when popover is open
```

Use project accessibility conventions.

## Testing strategy

Frontend tests should cover:

```text id="zsmb19"
renders chapter without annotations
renders text-mode annotation highlight
renders reader-block annotation highlight
tooltip shows display term and definition
preference disables highlights
invalid offsets are skipped
overlapping annotations resolved deterministically
missing definition handled
annotation content escaped
keyboard focus opens tooltip/popover
mobile/click interaction if supported
dark/theme compatibility if testable
```

## Rollout plan

1. Inspect public reader rendering path.
2. Inspect response types for `text`, `reader_blocks`, and `glossary_annotations`.
3. Add annotation normalization/validation helper.
4. Add text segmentation helper.
5. Add `AnnotatedText` component.
6. Wire into text reader.
7. Wire into block reader.
8. Add tooltip/popover component.
9. Add reader preference toggle.
10. Add tests.
11. Verify:

    * chapters without annotations render unchanged.
    * glossary matches are highlighted.
    * tooltips show safe definitions.
    * invalid annotations do not break reader.
    * annotations can be disabled.
